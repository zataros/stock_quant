import streamlit as st
import pandas as pd
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import database as db
import data_loader as dl
import strategies as st_algo
import ui_components as ui

def scan_worker(full_target, filter_opts, status_container):
    workers = 8  
    total = len(full_target)
    
    exclude_penny = filter_opts['exclude_penny']
    s_opts = filter_opts['strategies']
    
    results = []
    processed_count = 0
    
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for _, r in full_target.iterrows():
                if status_container.get('stop_requested', False): break

                raw_code = str(r['Code']).strip()
                if raw_code.isdigit() and len(raw_code) < 6: safe_code = raw_code.zfill(6)
                else: safe_code = raw_code
                    
                ft = executor.submit(st_algo.analyze_single_stock, safe_code, r['Name'], r.get('Market', 'Unknown'), exclude_penny)
                futures[ft] = r

            for future in as_completed(futures):
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
    status_container['running'] = False

def run():
    if 'scan_status' not in st.session_state:
        st.session_state['scan_status'] = {'running': False, 'progress': 0, 'total': 0, 'results': [], 'stop_requested': False}

    global_stats = db.get_strategy_stats()
    def get_label(name, key): return f"{name} ({global_stats.get(key, 0.0):.0f}%)"

    with st.container(border=True):
        st.subheader("🛠️ 스캔 설정")
        status = st.session_state['scan_status']
        is_running = status['running']
        
        with st.form("scanner_form"):
            cols = st.columns(4)
            chk_kospi = cols[0].checkbox("🇰🇷 코스피", value=True)
            chk_kosdaq = cols[1].checkbox("🇰🇷 코스닥", value=False)
            chk_sp500 = cols[2].checkbox("🇺🇸 S&P 500")
            chk_nasdaq = cols[3].checkbox("🇺🇸 NASDAQ")
            st.write("")
            c_opt1, c_opt2 = st.columns(2)
            exclude_penny = c_opt1.checkbox("🚫 동전주 제외", value=True)
            
            st.divider()
            st.write("🎯 **전략 필터** (정예 4대 전략)")
            sc = st.columns(4)
            
            s_opts = {
                'hyper': sc[0].checkbox(get_label("🔫 하이퍼스나이퍼", "🔫하이퍼스나이퍼"), value=True),
                'th_algo': sc[1].checkbox(get_label("🧬 TH알고리즘", "🧬TH알고리즘"), value=True),
                'turtle': sc[2].checkbox(get_label("🐢 터틀", "🐢터틀"), value=False),
                'bnf': sc[3].checkbox(get_label("💧 BNF", "💧BNF"), value=False),
            }
            st.write("")
            submitted = st.form_submit_button("🚀 스캔 시작", type="primary", use_container_width=True, disabled=is_running)

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
                
                st.session_state['scan_status'] = {'running': True, 'progress': 0, 'total': len(full_target), 'results': [], 'stop_requested': False}
                st.session_state["scan_data"] = None
                t = threading.Thread(target=scan_worker, args=(full_target, {'exclude_penny': exclude_penny, 'strategies': s_opts}, st.session_state['scan_status']))
                t.daemon = True; t.start()
                st.toast("🚀 스캔을 시작합니다!"); st.rerun()

        if is_running:
            curr = status['progress']; total = status['total']
            prog_val = min(1.0, curr / total) if total > 0 else 0
            st.info(f"🔄 실시간 분석 중... ({curr}/{total})")
            st.progress(prog_val)
            if st.button("🛑 스캔 중단 (즉시 멈춤)", type="secondary", use_container_width=True):
                st.session_state['scan_status']['stop_requested'] = True
                st.warning("⛔ 중단 요청 확인! 잠시 후 멈춥니다..."); time.sleep(0.5); st.rerun()
            if not status.get('stop_requested', False): time.sleep(0.5); st.rerun()

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
                    
                    if stop_req: st.warning(f"🛑 중단됨 (발굴: {len(results)}개)")
                    else: st.success(f"✅ 완료! {len(results)}개 종목 포착."); st.balloons()
                else:
                    st.warning("조건에 맞는 종목이 없습니다." if not stop_req else "중단됨.")
                    st.session_state["scan_data"] = pd.DataFrame()

    if st.session_state["scan_data"] is not None and not st.session_state["scan_data"].empty:
        df = st.session_state["scan_data"].copy()
        
        # [수정] 보여줄 칼럼 순서 지정 (RSI 이후는 숨김)
        visible_cols = ["종목명", "시장", "발견된_전략", "과거승률", "RSI"]
        
        col_conf = {
            "종목명": st.column_config.TextColumn("종목명", width="medium"),
            "시장": st.column_config.TextColumn("시장", width="small"),
            "발견된_전략": st.column_config.TextColumn("포착된 신호", width="large"),
            "과거승률": st.column_config.TextColumn("과거 백테스트", width="medium"),
            "RSI": st.column_config.NumberColumn("RSI", format="%.1f"),
        }
        
        evt = st.dataframe(
            df, 
            column_config=col_conf, 
            column_order=visible_cols, # [핵심] 여기서 순서 및 노출 제어
            hide_index=True, 
            use_container_width=True, 
            height=400, 
            selection_mode="single-row", 
            on_select="rerun"
        )
        
        if len(evt.selection['rows']) > 0:
            sel_row = df.iloc[evt.selection['rows'][0]]
            st.divider()
            c_h, c_b = st.columns([5, 1])
            c_h.subheader(f"{sel_row['종목명']} ({sel_row['코드']})")
            
            favs_raw = db.get_favorites(st.session_state["username"])
            fav_codes = [f[0] for f in favs_raw]
            is_fav = str(sel_row['코드']) in fav_codes
            
            if c_b.button(f"{'💔 해제' if is_fav else '❤ 관심등록'}", key=f"btn_{sel_row['코드']}"):
                if is_fav: db.remove_favorite(st.session_state["username"], str(sel_row['코드']))
                else:
                    s_str = ", ".join(sel_row.get('전략_리스트', []))
                    db.add_favorite(st.session_state["username"], str(sel_row['코드']), name=str(sel_row['종목명']), price=float(sel_row.get('현재가_RAW', 0)), strategies=s_str)
                st.rerun()
            
            if 'ai_report_html' in sel_row and sel_row['ai_report_html']: st.markdown(sel_row['ai_report_html'], unsafe_allow_html=True)
            st.plotly_chart(ui.draw_detailed_chart(sel_row), use_container_width=True, key=f"chart_{sel_row['코드']}")