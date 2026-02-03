import streamlit as st
import pandas as pd
import threading
import time
import yfinance as yf
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import database as db
import data_loader as dl
import strategies as st_algo
import ui_components as ui

# [공포/탐욕 지수 데이터 가져오기]
@st.cache_data(ttl=3600)
def fetch_fear_greed_data():
    def calc_rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    tickers = {'KR': '^KS11', 'US': 'SPY'} 
    results = {}
    
    for mkt, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="6mo")
            
            if df.empty: continue

            df.index = df.index.tz_localize(None)
            df = df.sort_index(ascending=True)

            close_col = 'Close'
            if 'Close' not in df.columns and 'close' in df.columns:
                close_col = 'close'
            
            series = df[close_col]
            rsi = calc_rsi(series)
            rsi = rsi.dropna()
            
            recent = rsi.tail(20)
            
            if not recent.empty:
                final_df = pd.DataFrame()
                final_df['Score'] = recent
                final_df['DateStr'] = [d.strftime('%m-%d') for d in recent.index]
                results[mkt] = final_df
                
        except Exception as e:
            print(f"Sentiment Error ({mkt}): {e}")
            
    return results

def scan_worker(full_target, filter_opts, status_container):
    workers = 8  
    total = len(full_target)
    s_opts = filter_opts['strategies']
    
    results = []
    processed_count = 0
    
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for _, r in full_target.iterrows():
                # 중단 요청 시 즉시 루프 탈출
                if status_container.get('stop_requested', False): break

                raw_code = str(r['Code']).strip()
                if raw_code.isdigit() and len(raw_code) < 6: safe_code = raw_code.zfill(6)
                else: safe_code = raw_code
                
                ft = executor.submit(st_algo.analyze_single_stock, safe_code, r['Name'], r.get('Market', 'Unknown'))
                futures[ft] = r

            for future in as_completed(futures):
                # 중단 요청 시 결과 수집 중단
                if status_container.get('stop_requested', False): break
                
                try:
                    res = future.result(timeout=15)
                    if res:
                        d = res['전략_리스트']
                        match = False
                        
                        if s_opts['hyper'] and any("하이퍼스나이퍼" in s for s in d): match = True
                        if s_opts['th_algo'] and any("TH알고리즘" in s for s in d): match = True
                        if s_opts['turtle'] and any("터틀" in s for s in d): match = True
                        if s_opts['bnf'] and any("BNF" in s for s in d): match = True
                        
                        any_chk = any(s_opts.values())
                        if not any_chk: results.append(res)
                        elif match: results.append(res)
                        
                except TimeoutError: pass
                except Exception: pass
                
                processed_count += 1
                status_container['progress'] = processed_count
                status_container['total'] = total
                
    except Exception as e: print(f"Scan Worker Error: {e}")
        
    status_container['results'] = results
    status_container['running'] = False # 작업 끝남 표시

def run():
    if 'scan_status' not in st.session_state:
        st.session_state['scan_status'] = {'running': False, 'progress': 0, 'total': 0, 'results': [], 'stop_requested': False}

    global_stats = db.get_strategy_stats()
    def get_label(name, key): return f"{name} ({global_stats.get(key, 0.0):.0f}%)"

    # 1. 공포/탐욕 지수 (항상 상단 표시)
    c_title, c_refresh = st.columns([8, 1])
    c_title.subheader("🌡️ 시장 공포/탐욕 지수")
    if c_refresh.button("↻", help="현재 시간으로 갱신"):
        st.rerun()
    
    with st.spinner("Analyzing..."):
        sentiment_data = fetch_fear_greed_data()
        
        from datetime import datetime
        import pytz
        
        try:
            tz_kr = pytz.timezone('Asia/Seoul')
            tz_us = pytz.timezone('America/New_York')
            curr_kr = datetime.now(tz_kr).strftime("%m-%d %H:%M")
            curr_us = datetime.now(tz_us).strftime("%m-%d %H:%M")
            time_info = {'KR': f"{curr_kr} (KST)", 'US': f"{curr_us} (ET)"}
        except:
            now_str = datetime.now().strftime("%m-%d %H:%M")
            time_info = {'KR': now_str, 'US': now_str}

        fig_sentiment = ui.draw_fear_greed_chart(sentiment_data, time_info)
        
        if fig_sentiment:
            st.plotly_chart(fig_sentiment, use_container_width=True, config={'displayModeBar': False})
    
    st.divider() 

    # 상태 변수
    status = st.session_state['scan_status']
    is_running = status['running']

    # 2. 스캔 설정 (실행 중에도 보임 - 버튼만 변경됨)
    with st.container(border=True):
        st.subheader("🛠️ 스캔 설정")
        
        with st.form("scanner_form"):
            cols = st.columns(4)
            # 실행 중일 때는 조작 방지
            chk_kospi = cols[0].checkbox("🇰🇷 코스피", value=True, disabled=is_running)
            chk_kosdaq = cols[1].checkbox("🇰🇷 코스닥", value=False, disabled=is_running)
            chk_sp500 = cols[2].checkbox("🇺🇸 S&P 500", disabled=is_running)
            chk_nasdaq = cols[3].checkbox("🇺🇸 NASDAQ", disabled=is_running)
            
            st.divider()
            st.write("🎯 **전략 필터** (정예 4대 전략)")
            sc = st.columns(4)
            
            s_opts = {
                'hyper': sc[0].checkbox(get_label("🔫 하이퍼스나이퍼", "🔫하이퍼스나이퍼"), value=True, disabled=is_running),
                'th_algo': sc[1].checkbox(get_label("🧬 TH알고리즘", "🧬TH알고리즘"), value=True, disabled=is_running),
                'turtle': sc[2].checkbox(get_label("🐢 터틀", "🐢터틀"), value=False, disabled=is_running),
                'bnf': sc[3].checkbox(get_label("💧 BNF", "💧BNF"), value=False, disabled=is_running),
            }
            st.write("")
            
            # [버튼 로직] 실행 중이면 '분석 중...' 비활성 버튼 표시
            if is_running:
                st.form_submit_button("⏳ 현재 분석 진행 중입니다... (아래에서 중단 가능)", disabled=True, use_container_width=True)
                submitted = False
            else:
                submitted = st.form_submit_button("🚀 스캔 시작", type="primary", use_container_width=True)

        # 스캔 시작 로직
        if submitted and not is_running:
            markets = []
            if chk_kospi: markets.append("KOSPI")
            if chk_kosdaq: markets.append("KOSDAQ")
            if chk_sp500: markets.append("S&P500")
            if chk_nasdaq: markets.append("NASDAQ")
            
            if not markets: st.error("시장을 선택해주세요.")
            else:
                with st.spinner("종목 리스트를 불러오는 중..."):
                    full_target = pd.DataFrame()
                    for m in markets: full_target = pd.concat([full_target, dl.get_master_data(m)])
                    full_target = full_target.drop_duplicates(subset=['Code']).reset_index(drop=True)
                
                # 상태 초기화
                st.session_state['scan_status'] = {
                    'running': True, 'progress': 0, 'total': len(full_target), 
                    'results': [], 'stop_requested': False
                }
                st.session_state["scan_data"] = None
                
                t = threading.Thread(target=scan_worker, args=(full_target, {'strategies': s_opts}, st.session_state['scan_status']))
                t.daemon = True; t.start()
                st.rerun()

    # 3. 진행률 및 중단 버튼 (실행 중에만 하단에 표시)
    if is_running:
        with st.container(border=True):
            st.info("🔍 실시간 스캔 진행 중...")
            
            curr = status['progress']
            total = status['total']
            prog_val = min(1.0, curr / total) if total > 0 else 0
            
            st.progress(prog_val)
            c_stat1, c_stat2 = st.columns([3, 1])
            c_stat1.write(f"**진행률:** {curr} / {total} 종목 완료")
            
            # [수정된 중단 버튼 로직]
            if c_stat2.button("🛑 스캔 중단", type="primary", use_container_width=True):
                # 1. 백그라운드 스레드에 중단 신호
                st.session_state['scan_status']['stop_requested'] = True
                
                # 2. [핵심] UI 상태를 강제로 '정지'로 변경하여 즉시 화면 복귀
                st.session_state['scan_status']['running'] = False
                
                st.toast("⛔ 스캔을 중단하고 설정 화면으로 돌아갑니다.")
                
                # 3. 즉시 리런
                time.sleep(0.1)
                st.rerun()
                
            # 자동 새로고침 (중단 요청이 없을 때만)
            if not status.get('stop_requested', False):
                time.sleep(0.5)
                st.rerun()

    # 4. 결과 처리 (스캔 완료 또는 중단 후)
    if not is_running and status['total'] > 0:
        if st.session_state["scan_data"] is None:
            results = status['results']
            stop_req = status.get('stop_requested', False)
            if results:
                st.session_state["scan_data"] = pd.DataFrame(results)
                if not stop_req:
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    save_cnt = 0
                    for res in results:
                        s_list = res.get('전략_리스트', [])
                        for s_name in s_list:
                            db.save_scan_result(today_str, s_name, str(res['코드']), res['종목명'], float(res['현재가_RAW']), res.get('시장', 'KR'))
                            save_cnt += 1
                    if save_cnt > 0: st.toast(f"💾 {len(results)}개 종목 기록됨.", icon="📈")
                
                if stop_req: 
                    st.warning(f"🛑 스캔이 중단되었습니다. (발굴: {len(results)}개)")
                else: 
                    st.success(f"✅ 완료! {len(results)}개 종목 포착.")
                    st.balloons()
            else:
                # 결과가 없을 때 처리
                if stop_req: st.warning("🛑 스캔이 중단되었습니다.")
                else: st.warning("조건에 맞는 종목이 없습니다.")
                
                st.session_state["scan_data"] = pd.DataFrame()

    # 5. 결과 테이블 표시
    if st.session_state["scan_data"] is not None and not st.session_state["scan_data"].empty:
        df = st.session_state["scan_data"].copy()
        visible_cols = ["종목명", "시장", "발견된_전략", "과거승률", "RSI"]
        col_conf = {
            "종목명": st.column_config.TextColumn("종목명", width="medium"),
            "시장": st.column_config.TextColumn("시장", width="small"),
            "발견된_전략": st.column_config.TextColumn("포착된 신호", width="large"),
            "과거승률": st.column_config.TextColumn("과거 백테스트", width="medium"),
            "RSI": st.column_config.NumberColumn("RSI", format="%.1f"),
        }

# [tabs_scanner.py 파일 하단 부분 수정]

        # ... (상단 코드 동일) ...
        
        evt = st.dataframe(
            df, 
            column_config=col_conf, 
            column_order=visible_cols, 
            hide_index=True, 
            use_container_width=True, 
            height=400, 
            selection_mode="single-row", 
            on_select="rerun"
        )
        
# [tabs_scanner.py 하단 부분 - if len(evt.selection['rows']) > 0: 블록 내부]

        if len(evt.selection['rows']) > 0:
            sel_row = df.iloc[evt.selection['rows'][0]]
            st.divider()
            
            c_h, c_b = st.columns([5, 1])
            c_h.subheader(f"{sel_row['종목명']} ({sel_row['코드']})")
            
            # ... (관심종목 버튼 코드는 기존 유지) ...
            favs_raw = db.get_favorites(st.session_state["username"])
            fav_codes = [f[0] for f in favs_raw]
            is_fav = str(sel_row['코드']) in fav_codes
            
            if c_b.button(f"{'💔 해제' if is_fav else '❤ 관심등록'}", key=f"btn_{sel_row['코드']}"):
                if is_fav: db.remove_favorite(st.session_state["username"], str(sel_row['코드']))
                else:
                    s_str = ", ".join(sel_row.get('전략_리스트', []))
                    db.add_favorite(st.session_state["username"], str(sel_row['코드']), name=str(sel_row['종목명']), price=float(sel_row.get('현재가_RAW', 0)), strategies=s_str)
                st.rerun()
            
            # [레이아웃 분할]
            col_report, col_finance = st.columns([1.6, 1]) 
            
            with col_report:
                if 'ai_report_html' in sel_row and sel_row['ai_report_html']: 
                    st.markdown(sel_row['ai_report_html'], unsafe_allow_html=True)
                else:
                    st.info("전략 분석 리포트가 없습니다.")

            with col_finance:
                with st.spinner("재무 정보 가져오는 중..."):
                    from strategies.common import get_financial_summary
                    fin_data = get_financial_summary(sel_row['코드'])
                
                if fin_data:
                    debt_str = fin_data['부채비율'].replace('%','').replace('-','0')
                    debt_val = float(debt_str) if debt_str.replace('.','',1).isdigit() else 0
                    debt_color = '#ff4b4b' if debt_val > 200 else '#fff'
                    
                    # [들여쓰기 제거된 HTML 코드]
                    st.markdown(f"""
<div style="background-color:#1e1e1e; padding:15px; border-radius:10px; border:1px solid #444; font-size:0.9em;">
<div style="font-size:1.1em; font-weight:bold; color:#eee; margin-bottom:12px; border-bottom:1px solid #555; padding-bottom:5px;">
📊 기업 펀더멘털 (최근 1년)
</div>
<div style="margin-bottom:8px;">
<span style="color:#aaa; display:block;">시가총액</span>
<span style="color:#fff; font-weight:bold; font-size:1.1em;">{fin_data['시가총액']}</span>
</div>
<div style="margin-bottom:8px;">
<span style="color:#aaa; display:block;">분기별 영업이익</span>
<div style="color:#fff; font-size:0.95em; white-space:nowrap; overflow-x:auto; padding-bottom:2px;">
{fin_data['영업이익_추세']}
</div>
</div>
<div style="margin-bottom:8px;">
<span style="color:#aaa; display:block;">분기별 영업이익률</span>
<span style="color:#00ff00;">{fin_data['이익률_추세']}</span>
</div>
<div style="display:flex; justify-content:space-between; margin-top:12px; border-top:1px solid #333; padding-top:8px;">
<div>
<span style="color:#aaa; font-size:0.8em;">부채비율</span><br>
<span style="color:{debt_color}; font-weight:bold;">{fin_data['부채비율']}</span>
</div>
<div style="text-align:right;">
<span style="color:#aaa; font-size:0.8em;">PER / PBR</span><br>
<span style="color:#ccc;">{fin_data['PER']} / {fin_data['PBR']}</span>
</div>
</div>
</div>
""", unsafe_allow_html=True)
                else:
                    st.warning("재무 정보를 불러올 수 없습니다.")

            # [수정] 차트를 columns 블록 밖으로 꺼내서 하단에 넓게 표시
            st.divider()
            st.plotly_chart(ui.draw_detailed_chart(sel_row), use_container_width=True, key=f"chart_{sel_row['코드']}")