import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        df = fdr.DataReader('USD/KRW', datetime.now() - timedelta(days=7))
        return df['Close'].iloc[-1]
    except: return 1400.0

def format_price(val, market="KR", code=None):
    try:
        if val is None: return "-"
        is_us = (code and str(code).isalpha()) or (market and "US" in str(market).upper()) or (market and "NASDAQ" in str(market).upper()) or (market and "NYSE" in str(market).upper())
        if is_us: return f"${val:,.2f}"
        else: return f"{int(val):,}원"
    except: return str(val)

@st.cache_data(ttl=3600)
def fetch_data(code):
    try:
        # 데이터 기간을 충분히 확보 (백테스팅용)
        df = fdr.DataReader(str(code), datetime.now() - timedelta(days=365)) 
        if len(df) < 200: return None 
        return calculate_indicators(df)
    except: return None

def calculate_indicators(df):
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    df['EMA10'] = df['Close'].ewm(span=10, adjust=False).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
    
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    
    std20 = df['Close'].rolling(window=20).std()
    df['BB_Up2'] = df['MA20'] + (std20 * 2)
    df['BB_Dn2'] = df['MA20'] - (std20 * 2)
    df['BB_Up1'] = df['MA20'] + (std20 * 1)
    df['BB_Dn1'] = df['MA20'] - (std20 * 1)
    df['Bandwidth'] = (df['BB_Up2'] - df['BB_Dn2']) / df['MA20']
    
    delta = df['Close'].diff()
    up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
    df['RSI'] = 100 - (100 / (1 + up.rolling(14).mean() / down.rolling(14).mean()))
    
    n = 14
    low_n = df['Low'].rolling(window=n).min()
    high_n = df['High'].rolling(window=n).max()
    df['Stoch_K'] = ((df['Close'] - low_n) / (high_n - low_n)) * 100
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
    df['Stoch_SlowD'] = df['Stoch_D'].rolling(window=3).mean()
    
    df['MA25'] = df['Close'].rolling(window=25).mean()
    df['Disparity25'] = (df['Close'] / df['MA25']) * 100
    
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TPV'] = df['TP'] * df['Volume']
    
    if len(df) >= 150:
        min_idx = df.iloc[-150:]['Low'].idxmin()
        subset = df.loc[min_idx:].copy()
        df.loc[min_idx:, 'VWAP'] = subset['TPV'].cumsum() / subset['Volume'].cumsum()
    elif len(df) > 0:
        min_idx = df['Low'].idxmin()
        subset = df.loc[min_idx:].copy()
        df.loc[min_idx:, 'VWAP'] = subset['TPV'].cumsum() / subset['Volume'].cumsum()
    else: 
        df['VWAP'] = np.nan

    positive_flow = pd.Series(0.0, index=df.index)
    negative_flow = pd.Series(0.0, index=df.index)
    pos_idx = df['TP'] > df['TP'].shift(1)
    neg_idx = df['TP'] < df['TP'].shift(1)
    positive_flow[pos_idx] = df.loc[pos_idx, 'TPV']
    negative_flow[neg_idx] = df.loc[neg_idx, 'TPV']
    mfi_period = 14
    pos_mf_sum = positive_flow.rolling(window=mfi_period).sum()
    neg_mf_sum = negative_flow.rolling(window=mfi_period).sum()
    money_ratio = pos_mf_sum / neg_mf_sum.replace(0, 1) 
    df['MFI'] = 100 - (100 / (1 + money_ratio))

    df['High20'] = df['High'].rolling(window=20).max().shift(1)
    df['Low20']  = df['Low'].rolling(window=20).min().shift(1)
    df['High10'] = df['High'].rolling(window=10).max().shift(1)
    df['Low10']  = df['Low'].rolling(window=10).min().shift(1)
    
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=20).mean()
        
    return df

# [최적화] 벡터 연산을 사용한 초고속 백테스팅
def backtest_past_performance(df, strategy_key):
    try:
        if len(df) < 60: return "N/A"
        
        # 전체 데이터에 대한 조건 벡터 생성
        conditions = pd.Series(False, index=df.index)
        
        if "엘리트" in strategy_key:
            conditions = (df['EMA10'] > df['EMA20']) & (df['EMA20'] > df['EMA60']) & \
                         (df['MACD'] > df['Signal']) & (df['MACD'].shift(1) <= df['Signal'].shift(1))
                         
        elif "DBB" in strategy_key:
            conditions = (df['Close'] > df['BB_Up2']) & (df['Close'].shift(1) <= df['BB_Up2'].shift(1))
            
        elif "BNF" in strategy_key:
            conditions = (df['Disparity25'] <= 90)
            
        elif "스퀴즈" in strategy_key:
            # 단순화된 조건 (속도 향상)
            conditions = (df['Bandwidth'] < 0.2) & \
                         (df['Volume'] > df['Volume'].shift(1) * 1.5) & \
                         (df['Close'] > df['Close'].shift(1))
                         
        elif "터틀" in strategy_key:
            # 터틀 조건 명확화
            conditions = (df['Close'] > df['High20']) & \
                         (df['Close'].shift(1) <= df['High20'].shift(1)) & \
                         (df['Close'] > df['MA200'])
                         
        elif "버핏" in strategy_key:
            conditions = (df['Close'] > df['MA200']) & (df['Close'].shift(1) <= df['MA200'].shift(1))
            
        elif "VWAP" in strategy_key:
             conditions = (abs(df['Close'] - df['VWAP']) / df['VWAP'] <= 0.03)

        # 신호가 발생한 날들의 인덱스 (마지막 5일은 결과 확인 불가하므로 제외)
        signal_indices = np.where(conditions.iloc[:-5])[0]
        
        total = len(signal_indices)
        if total == 0: return "0% (0/0)"
        
        # 5일 뒤 수익 여부 확인 (벡터 연산)
        # signal_indices에 해당하는 날짜의 Close와 5일 뒤 Close 비교
        entry_prices = df['Close'].iloc[signal_indices].values
        future_prices = df['Close'].iloc[signal_indices + 5].values
        
        wins = np.sum(future_prices > entry_prices)
        win_rate = (wins / total) * 100
        
        return f"{win_rate:.0f}% ({wins}/{total})"
    except Exception as e:
        return "Err"

def analyze_single_stock(code, name_raw, market_raw, exclude_penny=False):
    try:
        df = fetch_data(code)
        if df is None: return None
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        if curr['Volume'] == 0: return None
        
        mkt_upper = str(market_raw).upper()
        is_us = (code and str(code).isalpha()) or \
                ("US" in mkt_upper) or \
                ("NASDAQ" in mkt_upper) or \
                ("NYSE" in mkt_upper) or \
                ("S&P" in mkt_upper)

        if exclude_penny:
            if is_us and curr['Close'] < 1: return None 
            if not is_us and curr['Close'] < 1000: return None
        
        scored_strategies = []
        
        # 1. 엘리트
        is_aligned = (curr['EMA10'] > curr['EMA20'] > curr['EMA60'])
        is_macd_cross = (curr['MACD'] > curr['Signal']) and (prev['MACD'] <= prev['Signal'])
        if is_aligned and is_macd_cross: 
            score = 10 + (curr['RSI'] - 50) 
            scored_strategies.append(("⚡엘리트", score))

        # 2. DBB
        if (curr['Close'] > curr['BB_Up2']) and (prev['Close'] <= prev['BB_Up2']): 
            score = ((curr['Close'] / curr['BB_Up2']) - 1) * 1000
            scored_strategies.append(("🔥DBB", score))

        # 3. BNF
        if pd.notnull(curr['Disparity25']) and curr['Disparity25'] <= 90: 
            score = (100 - curr['Disparity25']) * 2
            scored_strategies.append(("💧BNF", score))
        
        # 4. AI 스퀴즈
        avg_bw = df['Bandwidth'].rolling(120).mean().iloc[-1]
        is_squeeze_prev = (prev['Bandwidth'] < 0.15) or (prev['Bandwidth'] < avg_bw * 0.7)
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        vol_explode = curr['Volume'] > vol_avg * 1.5
        is_up = curr['Close'] > prev['Close'] 
        if is_squeeze_prev and vol_explode and is_up:
            score = (curr['Volume'] / vol_avg) * 10
            scored_strategies.append(("🤖AI스퀴즈", score))

        # 5. 터틀
        if pd.notnull(curr['High20']) and pd.notnull(curr['MA200']):
            breakout_today = (curr['Close'] > curr['High20'])
            not_breakout_yesterday = (prev['Close'] <= prev['High20']) 
            trend_filter = (curr['Close'] > curr['MA200'])
            if breakout_today and not_breakout_yesterday and trend_filter: 
                score = ((curr['Close'] / curr['High20']) - 1) * 1000
                scored_strategies.append(("🐢터틀", score))

        # 6. 버핏
        if (curr['Close'] > curr['MA200']) and (prev['Close'] <= prev['MA200']): 
            score = ((curr['Close'] / curr['MA200']) - 1) * 100
            scored_strategies.append(("🛡️버핏", score))
        
        # 7. VWAP
        if pd.notnull(curr['VWAP']):
            diff_pct = abs(curr['Close'] - curr['VWAP']) / curr['VWAP']
            if diff_pct <= 0.03: 
                score = (1 - (diff_pct / 0.03)) * 50
                scored_strategies.append(("⚓VWAP", score))

        if not scored_strategies: return None

        scored_strategies.sort(key=lambda x: x[1], reverse=True)
        strategies = [s[0] for s in scored_strategies]
        
        # [백테스팅] 가장 높은 점수 전략에 대해 5일 보유 승률 계산
        top_strategy = strategies[0]
        past_win_rate = backtest_past_performance(df, top_strategy)
        
        strategies_str = " > ".join(strategies)

        df_chart = df.tail(100).copy()
        atr_val = curr['ATR'] if pd.notnull(curr['ATR']) else curr['Close']*0.01
        
        item = {
            "종목명": name_raw, "코드": code, "시장": market_raw,
            "현재가_RAW": curr['Close'], "현재가": format_price(curr['Close'], market_raw, code),
            "발견된_전략": strategies_str, "전략_리스트": strategies,
            "과거승률": f"{top_strategy}: {past_win_rate}", 
            "RSI": round(curr['RSI'], 0), "Bandwidth": round(curr['Bandwidth'], 3),
            "Disparity25": round(curr['Disparity25'], 1), "MA20": curr['MA20'], "MA5": curr['MA5'],
            "ATR": atr_val, "High20": curr['High20'],
            "chart_dates": df_chart.index.strftime('%Y-%m-%d').tolist(),
            "chart_open": df_chart['Open'].tolist(), "chart_high": df_chart['High'].tolist(),
            "chart_low": df_chart['Low'].tolist(), "chart_close": df_chart['Close'].tolist(),
            "chart_vol": df_chart['Volume'].tolist(),
            "chart_ma": df_chart['MA20'].fillna(0).tolist(),
            "chart_up": df_chart['BB_Up2'].fillna(0).tolist(), "chart_down": df_chart['BB_Dn2'].fillna(0).tolist(),
            "chart_up1": df_chart['BB_Up1'].fillna(0).tolist(), "chart_down1": df_chart['BB_Dn1'].fillna(0).tolist(),
            "macd": df_chart['MACD'].fillna(0).tolist(), "macd_sig": df_chart['Signal'].fillna(0).tolist(),
            "macd_hist": df_chart['MACD_Hist'].fillna(0).tolist(),
            "stoch_k": df_chart['Stoch_D'].fillna(0).tolist(), "stoch_d": df_chart['Stoch_SlowD'].fillna(0).tolist(),
            "rsi_line": df_chart['RSI'].fillna(0).tolist(),
            "vwap_val": [x if x > 0 else None for x in df_chart['VWAP'].fillna(0).tolist()],
            "mfi_line": df_chart['MFI'].fillna(50).tolist()
        }
        item["ai_report_html"] = generate_ai_report_html(item)
        return item
    except: return None

def generate_ai_report_html(item):
    try:
        strategies = item.get('전략_리스트', [])
        if not strategies: return "리포트 오류"
        
        main_strat = strategies[0]
        curr_price = item['현재가_RAW']
        ma20 = item['MA20']
        mkt, cd = item['시장'], item['코드']
        
        title, analysis, action = "🔍 복합 전략 포착", "<li>타이밍 포착</li>", "차트 확인"
        
        if "터틀" in main_strat:
            title = "🐢 터틀: 신고가 돌파"
            analysis = "<li><b>상황:</b> 20일 저항선을 <b>오늘</b> 강하게 돌파.</li>"
            atr = item.get('ATR', curr_price*0.02)
            action = f"추세 추종 매수. 🛑 손절: {format_price(curr_price - 2*atr, mkt, cd)}"
        elif "AI스퀴즈" in main_strat:
            title = "🚀 AI스퀴즈: 에너지 폭발"
            analysis = "<li><b>상황:</b> 응축 후 <b>첫</b> 발산 캔들.</li>"
            action = f"공격 매수. 🛑 손절: {format_price(ma20, mkt, cd)}"
        elif "엘리트" in main_strat:
            title = "⚡ 엘리트: 골든크로스"
            analysis = "<li><b>상황:</b> 정배열 + MACD 매수 신호.</li>"
            action = f"정석 매수. 🛑 손절: {format_price(ma20, mkt, cd)}"
        elif "DBB" in main_strat:
            title = "🔥 DBB: 밴드 상단 돌파"
            analysis = "<li><b>상황:</b> 볼린저밴드 상단 <b>방금</b> 돌파.</li>"
            action = f"돌파 매매. 🛑 손절: {format_price(curr_price*0.97, mkt, cd)}"
        elif "BNF" in main_strat:
            title = "💧 BNF: 과매도 반등"
            analysis = "<li><b>상황:</b> 25일 이평선 괴리율 극대화 (투매).</li>"
            action = f"역추세 매수. 🛑 손절: {format_price(curr_price*0.95, mkt, cd)}"
        elif "VWAP" in main_strat:
            title = "⚓ VWAP: 세력선 지지"
            analysis = "<li><b>상황:</b> VWAP 선 부근에서 지지 중.</li>"
            action = f"눌림목 매수. 🛑 손절: {format_price(curr_price*0.97, mkt, cd)}"
        elif "버핏" in main_strat:
            title = "🛡️ 버핏: 장기 추세 전환"
            analysis = "<li><b>상황:</b> 200일선을 <b>방금</b> 상향 돌파했습니다.</li>"
            action = f"장기 보유 진입. 🛑 손절: {format_price(curr_price*0.95, mkt, cd)}"
            
        return f"""<div style="background-color:#1a1c24; padding:15px; border-radius:10px;"><div style="font-size:1.4em; font-weight:bold; color:#fff;">{title}</div><ul style="color:#ddd; margin:10px 0;">{analysis}</ul><div style="background-color:#25262b; border-left:5px solid #00d2d3; padding:10px; color:#fff;">{action}</div></div>"""
    except: return "리포트 오류"

def analyze_strategy_deep_dive(df, capital_krw, usd_rate, strategy_type, ticker_code):
    try:
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        is_us = ticker_code.isalpha()
        applied_capital = capital_krw / usd_rate if is_us else capital_krw
        atr = curr['ATR']
        if pd.isna(atr) or atr == 0: atr = curr['Close'] * 0.01
        atr_pct = (atr / curr['Close']) * 100
        df = df.copy()
        df['Chart_Signal'] = 0
        signal = "관망"
        entry_price = curr['Close']
        stop_price = 0
        target_price = 0
        
        if "VWAP" in strategy_type:
            if pd.notnull(curr['VWAP']):
                entry_price = curr['VWAP']
                is_buy = abs(curr['Close'] - curr['VWAP']) / curr['VWAP'] <= 0.03
                
                if is_buy: signal = "BUY (지지권)"
                else: signal = "Wait"
                
                buy_cond = (df['Close'] >= df['VWAP']) & (df['Close'] <= df['VWAP'] * 1.03) & (df['Close'] >= df['Open'])
                df.loc[buy_cond, 'Chart_Signal'] = 1
                
                stop_price = curr['VWAP'] * 0.97
                target_price = entry_price * 1.15
            else: signal = "N/A"

        elif "터틀" in strategy_type:
            entry_price = curr['High20']
            buy_cond = (df['Close'] > df['High20']) & (df['Close'].shift(1) <= df['High20'].shift(1)) & (df['Close'] > df['MA200'])
            exit_cond = (df['Close'] < df['Low10']) & (df['Close'].shift(1) >= df['Low10'].shift(1))
            df.loc[buy_cond, 'Chart_Signal'] = 1
            df.loc[exit_cond, 'Chart_Signal'] = -1
            
            if buy_cond.iloc[-1]: signal = "BUY"
            elif (curr['Close'] < curr['Low10']): signal = "EXIT"
            elif (curr['Close'] > curr['MA200']): signal = "HOLD"
            else: signal = "Wait"
            stop_price = entry_price - (2 * atr)
            target_price = entry_price + (4 * atr)

        elif "엘리트" in strategy_type:
            entry_price = curr['Close']
            aligned = (df['EMA10'] > df['EMA20']) & (df['EMA20'] > df['EMA60'])
            macd_cross = (df['MACD'] > df['Signal']) & (df['MACD'].shift(1) <= df['Signal'].shift(1))
            df.loc[aligned & macd_cross, 'Chart_Signal'] = 1
            
            if aligned.iloc[-1] and macd_cross.iloc[-1]: signal = "BUY"
            elif aligned.iloc[-1]: signal = "HOLD"
            else: signal = "Wait"
            stop_price = curr['MA20']
            target_price = entry_price * 1.1

        elif "DBB" in strategy_type:
            entry_price = curr['BB_Up2']
            breakout = (df['Close'] > df['BB_Up2']) & (df['Close'].shift(1) <= df['BB_Up2'].shift(1))
            df.loc[breakout, 'Chart_Signal'] = 1
            
            if breakout.iloc[-1]: signal = "BUY"
            elif curr['Close'] > curr['BB_Up2']: signal = "HOLD"
            else: signal = "Wait"
            stop_price = curr['Close'] * 0.97
            target_price = entry_price * 1.15

        elif "BNF" in strategy_type:
            entry_price = curr['Close']
            oversold = (df['Disparity25'] <= 90) & (df['Disparity25'].shift(1) > 90)
            df.loc[oversold, 'Chart_Signal'] = 1
            
            if curr['Disparity25'] <= 90: signal = "BUY"
            else: signal = "Wait"
            stop_price = curr['Close'] * 0.95
            target_price = curr['MA25']

        elif "스퀴즈" in strategy_type:
            entry_price = curr['Close']
            avg_bw = df['Bandwidth'].rolling(120).mean()
            sqz = (df['Bandwidth'] < 0.15) | (df['Bandwidth'] < avg_bw * 0.7)
            vol = df['Volume'] > df['Volume'].rolling(20).mean() * 1.5
            trigger = sqz & (vol) & (df['Close'] > df['MA20']) 
            df.loc[trigger, 'Chart_Signal'] = 1
            
            if trigger.iloc[-1]: signal = "BUY"
            else: signal = "Wait"
            stop_price = curr['MA20']
            target_price = entry_price * 1.2

        elif "버핏" in strategy_type:
            entry_price = curr['Close']
            cross_up = (df['Close'] > df['MA200']) & (df['Close'].shift(1) <= df['MA200'].shift(1))
            df.loc[cross_up, 'Chart_Signal'] = 1
            
            if cross_up.iloc[-1]: signal = "BUY"
            elif curr['Close'] > curr['MA200']: signal = "HOLD"
            else: signal = "Wait"
            stop_price = curr['MA200']
            target_price = entry_price * 1.2

        allowable_risk = applied_capital * 0.02
        risk_per_share = entry_price - stop_price
        shares = 0
        if risk_per_share > 0: shares = int(allowable_risk / risk_per_share)
        if shares * entry_price > applied_capital: shares = int(applied_capital / entry_price)
        total_loss = shares * risk_per_share

        return {
            "price": curr['Close'], "signal": signal, 
            "atr": atr, "atr_pct": atr_pct,
            "high20": curr['High20'], "low10": curr['Low10'], "ma200": curr['MA200'],
            "entry_price": entry_price, "stop_price": stop_price, "target_price": target_price,
            "shares": shares, "allowable_risk": allowable_risk, "total_loss": total_loss,
            "df": df.tail(150), "strategy": strategy_type,
            "bandwidth": curr['Bandwidth'], "disparity": curr['Disparity25'],
            "vwap_val": curr['VWAP'] if pd.notnull(curr['VWAP']) else 0,
            "applied_capital": applied_capital, "is_us": is_us
        }
    except Exception as e: return None

def get_all_strategies_status(df):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    s_turtle = "Wait"
    if (curr['Close'] > curr['High20']) and (curr['Close'] > curr['MA200']):
        if prev['Close'] <= prev['High20']: s_turtle = "BUY"
        else: s_turtle = "HOLD"
    elif (curr['Close'] < curr['Low10']): s_turtle = "SELL"
    elif (curr['Close'] > curr['MA200']): s_turtle = "HOLD"
    
    s_elite = "Wait"
    is_aligned = (curr['EMA10'] > curr['EMA20']) & (curr['EMA20'] > curr['EMA60'])
    if is_aligned:
        is_cross = (curr['MACD'] > curr['Signal']) and (prev['MACD'] <= prev['Signal'])
        if is_cross: s_elite = "BUY"
        else: s_elite = "HOLD"
    
    s_dbb = "Wait"
    if curr['Close'] > curr['BB_Up2']:
        if prev['Close'] <= prev['BB_Up2']: s_dbb = "BUY"
        else: s_dbb = "HOLD"
        
    s_bnf = "Wait"
    if curr['Disparity25'] <= 90: s_bnf = "BUY"
    
    s_sqz = "Wait"
    avg_bw = df['Bandwidth'].rolling(120).mean().iloc[-1]
    is_sqz_prev = (prev['Bandwidth'] < 0.15) or (prev['Bandwidth'] < avg_bw * 0.7)
    vol_exp = curr['Volume'] > df['Volume'].rolling(20).mean().iloc[-1] * 1.5
    if is_sqz_prev and vol_exp and (curr['Close'] > prev['Close']): s_sqz = "BUY"
    
    s_buff = "Wait"
    if curr['Close'] > curr['MA200']:
        if prev['Close'] <= prev['MA200']: s_buff = "BUY"
        else: s_buff = "HOLD"
    
    s_vwap = "Wait"
    if pd.notnull(curr['VWAP']):
        if abs(curr['Close'] - curr['VWAP']) / curr['VWAP'] <= 0.03:
            s_vwap = "BUY"
        elif curr['Close'] > curr['VWAP']:
            s_vwap = "HOLD"
            
    return {
        "🐢 터틀": s_turtle, "⚡ 엘리트": s_elite, "🔥 DBB": s_dbb, "💧 BNF": s_bnf,
        "🤖 AI스퀴즈": s_sqz, "🛡️ 버핏": s_buff, "⚓ VWAP": s_vwap

    }
