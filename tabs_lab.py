import streamlit as st
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import database as db
import data_loader as dl
import strategies as st_algo
import ui_components as ui

def fetch_current_prices_batch(codes_markets):
    results = {}
    if not codes_markets: return results

    def fetch_one(code, market):
        try:
            ticker = code
            if str(code).isdigit(): 
                ticker = f"{code}.KS" if market == "KOSPI" else f"{code}.KQ"
            
            yf_ticker = yf.Ticker(ticker)
            price = yf_ticker.fast_info.get('last_price', 0.0)
            
            if price <= 0 and str(code).isdigit():
                alt_ticker = f"{code}.KQ" if ".KS" in ticker else f"{code}.KS"
                price = yf.Ticker(alt_ticker).fast_info.get('last_price', 0.0)
                
            return code, price
        except: return code, 0.0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_one, c, m) for c, m in codes_markets]
        for f in futures:
            c, p = f.result()
            results[c] = p
    return results

def run():
    st.header("🔬 전략 연구소 (Strategy Lab)")
    
    tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 분석", "📊 전략 성과(승률) 추적"])

    with tab1:
        with st.form("strategy_lab_form"):
            col_in1, col_in2 = st.columns(2)
            t_mode = col_in1.radio("종목 입력", ["직접 입력", "관심종목"], horizontal=True, label_visibility="collapsed")
            t_ticker_input = col_in1.text_input("직접 입력 (종목명/티커)", value="현대차")
            
            fav_data = db.get_favorites(st.session_state["username"])
            display_list = []
            ticker_map = {} 
            
            if fav_data:
                for item in fav_data:
                    if isinstance(item, (tuple, list)) and len(item) >= 5:
                        label = f"{item[4]} ({item[0]})"
                        ticker_map[label] = item[0]
                        display_list.append(label)
                    else:
                        label = str(item)
                        ticker_map[label] = label
                        display_list.append(label)
            else:
                display_list = ["관심종목이 없습니다"]
                ticker_map["관심종목이 없습니다"] = ""
                
            t_ticker_select_label = col_in1.selectbox("관심종목 선택", display_list)
            t_capital = col_in2.number_input("총 운용금 (원)", value=10000000, step=100000)
            
            lab_submitted = st.form_submit_button("🧬 정밀 분석 실행", type="primary", use_container_width=True)

        if lab_submitted:
            target = t_ticker_input if t_mode == "직접 입력" else ticker_map.get(t_ticker_select_label, "")
            if not target: st.warning("분석할 종목을 선택하거나 입력해주세요.")
            else:
                real_ticker = dl.search_code_by_name(target)
                if not real_ticker: real_ticker = target
                
                with st.spinner(f"'{real_ticker}' 데이터를 정밀 분석 중입니다..."):
                    raw_df = st_algo.fetch_data(real_ticker)
                    if raw_df is not None and not raw_df.empty:
                        strat_mapping = [
                            ("🐢 터틀", "🐢 터틀 트레이딩"), ("⚡ 엘리트", "⚡ 엘리트 매매법"),
                            ("🔥 DBB", "🔥 DBB (더블볼린저)"), ("💧 BNF", "💧 BNF (과매도)"),
                            ("🤖 AI스퀴즈", "🤖 AI 스퀴즈"), ("🛡️ 버핏", "🛡️ 버핏 (장기투자)"),
                            ("⚓ VWAP", "⚓ VWAP (지지선)")
                        ]
                        master_consensus = {}
                        master_details = {}
                        for short_name, full_name in strat_mapping:
                            res = st_algo.analyze_strategy_deep_dive(raw_df, t_capital, st.session_state["usd_rate"], full_name, real_ticker)
                            if res:
                                master_details[full_name] = res
                                master_consensus[short_name] = res['signal']
                            else:
                                master_consensus[short_name] = "Wait"
                                master_details[full_name] = None
                        
                        st.session_state['lab_master_result'] = {
                            'ticker': real_ticker, 'name': dl.get_stock_name(real_ticker),
                            'consensus': master_consensus, 'details': master_details, 'capital': t_capital
                        }
                        st.rerun()
                    else: st.error(f"'{target}'의 데이터를 불러오지 못했습니다.")

        if 'lab_master_result' in st.session_state:
            m_pack = st.session_state['lab_master_result']
            st.divider()
            st.subheader(f"📊 {m_pack['ticker']} ({m_pack['name']}) 종합 진단 결과")
            st.markdown(ui.render_consensus_html(m_pack['consensus']), unsafe_allow_html=True)
            
            s_tabs = st.tabs(["🐢 터틀", "⚡ 엘리트", "🔥 DBB", "💧 BNF", "🤖 AI스퀴즈", "🛡️ 버핏", "⚓ VWAP"])
            tab_names = ["🐢 터틀 트레이딩", "⚡ 엘리트 매매법", "🔥 DBB (더블볼린저)", "💧 BNF (과매도)", "🤖 AI 스퀴즈", "🛡️ 버핏 (장기투자)", "⚓ VWAP (지지선)"]
            mkt_hint = "US" if m_pack['ticker'].isalpha() else "KR"
            
            for i, tab in enumerate(s_tabs):
                with tab:
                    res = m_pack['details'].get(tab_names[i])
                    if res:
                        c1, c2 = st.columns([1, 1])
                        sig_color = "red" if "BUY" in res['signal'] else ("blue" if "HOLD" in res['signal'] else ("orange" if "EXIT" in res['signal'] else "gray"))
                        c1.markdown(f"**현재 신호**: :{sig_color}[**{res['signal']}**]")
                        c1.markdown(f"**현재가**: {st_algo.format_price(res['price'], mkt_hint, m_pack['ticker'])}")
                        
                        if "스퀴즈" in tab_names[i]: c2.metric("밴드폭", f"{res['bandwidth']:.3f}")
                        elif "BNF" in tab_names[i]: c2.metric("이격도", f"{res['disparity']:.1f}%")
                        else:
                            atr_val = st_algo.format_price(res['atr'], mkt_hint, m_pack['ticker'])
                            c2.markdown(f"**ATR (변동성)**: {atr_val}")

                        # [UI 복구] 매수 신호 시 상세 정보 카드 표시
                        if "BUY" in res['signal']:
                            st.success(f"✅ **[{tab_names[i]}] 진입 조건 만족!**")
                            currency_symbol = "$" if res['is_us'] else "₩"
                            try: profit_rate = ((res['target_price'] - res['entry_price']) / res['entry_price']) * 100
                            except: profit_rate = 0
                            
                            st.markdown(f"""
                            <div style="background-color:#222; padding:15px; border-radius:10px; border:1px solid #00b894; margin-bottom:15px;">
                                <div style="display:flex; justify-content:space-between; text-align:center; flex-wrap:wrap; gap:10px;">
                                    <div><div style="color:#aaa; font-size:0.8em;">추천 매수</div><div style="color:#00b894; font-size:1.3em; font-weight:bold;">{res['shares']:,} 주</div></div>
                                    <div><div style="color:#aaa; font-size:0.8em;">진입가</div><div style="color:#fff; font-size:1.1em;">{st_algo.format_price(res['entry_price'], mkt_hint, m_pack['ticker'])}</div></div>
                                    <div><div style="color:#aaa; font-size:0.8em;">손절가</div><div style="color:#ff4b4b; font-size:1.1em;">{st_algo.format_price(res['stop_price'], mkt_hint, m_pack['ticker'])}</div></div>
                                    <div><div style="color:#aaa; font-size:0.8em;">익절 예상가</div><div style="color:#fdcb6e; font-size:1.1em;">{st_algo.format_price(res['target_price'], mkt_hint, m_pack['ticker'])} ({profit_rate:.1f}%)</div></div>
                                    <div><div style="color:#aaa; font-size:0.8em;">예상 손실금</div><div style="color:#ff7675; font-size:1.1em;">{currency_symbol}{res['total_loss']:,.0f}</div></div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        elif "HOLD" in res['signal']: st.info(f"⏸ **[{tab_names[i]}] 추세 진행 중 (보유 관점)**")
                        elif "EXIT" in res['signal']: st.error(f"📉 **[{tab_names[i]}] 청산/매도 신호 발생!**")
                        elif "Wait" in res['signal']: st.warning(f"⏳ **[{tab_names[i]}] 진입 대기 (조건 불충족)**")
                        
                        st.plotly_chart(ui.draw_strategy_chart(res['df'], m_pack['ticker'], tab_names[i]), use_container_width=True)

    with tab2:
        st.subheader("📆 과거 추천 종목 검증 (Back-check)")
        st.info("과거에 포착된 종목들의 성과를 분석하고, 전략별 전역 승률을 갱신합니다.")
        
        available_dates = db.get_scan_history_dates()
        
        if not available_dates:
            st.warning("아직 기록된 스캔 내역이 없습니다.")
        else:
            c_sel1, c_sel2 = st.columns([1, 2])
            selected_date = c_sel1.selectbox("과거 날짜 선택", available_dates)
            
            if selected_date:
                history_rows = db.get_history_by_date(selected_date)
                if history_rows:
                    if c_sel1.button("🚀 성과 분석 시작", type="primary"):
                        with st.spinner(f"{selected_date} 데이터 분석 및 전역 통계 갱신 중..."):
                            target_list = [(r[1], r[4]) for r in history_rows]
                            current_prices = fetch_current_prices_batch(target_list)
                            
                            perf_data = []
                            stats = {} 
                            
                            for row in history_rows:
                                strat, code, name, entry, mkt = row
                                curr = current_prices.get(code, 0.0)
                                
                                if curr > 0:
                                    ret = ((curr - entry) / entry) * 100
                                    is_win = ret > 0 
                                    win_str = "🔴승" if is_win else "🔵패"
                                    
                                    if strat not in stats: stats[strat] = {'win':0, 'total':0}
                                    stats[strat]['total'] += 1
                                    if is_win: stats[strat]['win'] += 1
                                    
                                    perf_data.append({
                                        "전략": strat, "종목명": name, "코드": code,
                                        "포착당시가": entry, "현재가": curr,
                                        "수익률(%)": ret, "결과": win_str
                                    })
                            
                            if stats:
                                db.update_strategy_stats(stats)
                                st.toast("전략별 전역 승률이 업데이트 되었습니다!", icon="📡")

                            st.divider()
                            st.markdown(f"### 📊 {selected_date} 전략별 성적표")
                            cols = st.columns(len(stats)) if stats else []
                            for idx, (s_name, stat) in enumerate(stats.items()):
                                win_rate = (stat['win'] / stat['total']) * 100
                                with cols[idx]:
                                    st.metric(label=s_name, value=f"{win_rate:.0f}%", delta=f"{stat['total']}건")

                            st.dataframe(pd.DataFrame(perf_data), use_container_width=True)