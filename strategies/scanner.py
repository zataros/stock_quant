import pandas as pd
import numpy as np
from .common import fetch_data, format_price
from .library import ACTIVE_STRATEGIES

# [수정] exclude_penny 파라미터 삭제
def analyze_single_stock(code, name_raw, market_raw):
    try:
        df = fetch_data(code)
        if df is None: return None
        curr = df.iloc[-1]
        
        # [삭제] 동전주 체크 로직 삭제됨
        
        scored_strategies = []
        
        for strat in ACTIVE_STRATEGIES:
            score = strat.check_signal(df)
            if score > 0:
                scored_strategies.append((strat.name, score))
        
        if not scored_strategies: return None
        
        scored_strategies.sort(key=lambda x: x[1], reverse=True)
        strategies_list = [s[0] for s in scored_strategies]
        top_strategy_name = strategies_list[0]
        
        top_strat_obj = next((s for s in ACTIVE_STRATEGIES if s.name == top_strategy_name), None)
        past_win_rate = "N/A"
        if top_strat_obj:
            win_rate_str = calc_win_rate(df, top_strat_obj)
            past_win_rate = f"{top_strategy_name}: {win_rate_str}"
            
        item = {
            "종목명": name_raw, "코드": code, "시장": market_raw,
            "현재가_RAW": curr['Close'], "현재가": format_price(curr['Close'], market_raw, code),
            "발견된_전략": " > ".join(strategies_list), "전략_리스트": strategies_list,
            "과거승률": past_win_rate,
            "RSI": round(curr['RSI'], 0), "Bandwidth": round(curr['Bandwidth'], 3),
            "Disparity25": round(curr['Disparity25'], 1), "MA20": curr['MA20'], "MA5": curr['MA5'],
            "ATR": curr.get('ATR', curr['Close']*0.01), "High20": curr['High20'],
            "HMA": curr.get('HMA', 0),
            "chart_dates": df.tail(100).index.strftime('%Y-%m-%d').tolist(),
            "chart_close": df.tail(100)['Close'].tolist(),
            "chart_open": df.tail(100)['Open'].tolist(), "chart_high": df.tail(100)['High'].tolist(),
            "chart_low": df.tail(100)['Low'].tolist(), "chart_vol": df.tail(100)['Volume'].tolist(),
            "chart_ma": df.tail(100)['MA20'].fillna(0).tolist(),
            "chart_up": df.tail(100)['BB_Up2'].fillna(0).tolist(), "chart_down": df.tail(100)['BB_Dn2'].fillna(0).tolist(),
            "vwap_val": [x if x > 0 else None for x in df.tail(100)['VWAP'].fillna(0).tolist()] if 'VWAP' in df else [],
            "macd": df.tail(100)['MACD'].fillna(0).tolist(), "macd_sig": df.tail(100)['Signal'].fillna(0).tolist(),
            "macd_hist": df.tail(100)['MACD_Hist'].fillna(0).tolist(),
            "stoch_k": df.tail(100)['Stoch_D'].fillna(0).tolist(), "stoch_d": df.tail(100)['Stoch_SlowD'].fillna(0).tolist(),
            "rsi_line": df.tail(100)['RSI'].fillna(0).tolist(), "mfi_line": df.tail(100)['MFI'].fillna(50).tolist()
        }
        
        if top_strat_obj:
            item["ai_report_html"] = top_strat_obj.get_report(item)
            
        return item
    except Exception as e: return None

def calc_win_rate(df, strategy_obj):
    try:
        cond = strategy_obj.backtest(df)
        signal_indices = np.where(cond.iloc[:-5])[0]
        total = len(signal_indices)
        if total == 0: return "0% (0/0)"
        
        entry_prices = df['Close'].iloc[signal_indices].values
        future_prices = df['Close'].iloc[signal_indices + 5].values
        wins = np.sum(future_prices > entry_prices)
        return f"{(wins/total)*100:.0f}% ({wins}/{total})"
    except: return "Err"

# (나머지 deep_dive 함수 등은 수정 없음, 그대로 둠)
def analyze_strategy_deep_dive(df, capital_krw, usd_rate, strategy_full_name, ticker_code):
    try:
        short_name = strategy_full_name.split(' ')[0] + strategy_full_name.split(' ')[1]
        target_strat = next((s for s in ACTIVE_STRATEGIES if s.name.replace(" ", "") == short_name.replace(" ", "")), None)
        
        if not target_strat:
             target_strat = next((s for s in ACTIVE_STRATEGIES if strategy_full_name.split('(')[0].strip() in s.name), None)

        if not target_strat: return None
        
        res = target_strat.deep_dive(df)
        
        is_us = ticker_code.isalpha()
        applied_capital = capital_krw / usd_rate if is_us else capital_krw
        curr_price = res['entry_price']
        risk_per_share = curr_price - res['stop_price']
        allowable_risk = applied_capital * 0.02
        
        shares = 0
        if risk_per_share > 0: shares = int(allowable_risk / risk_per_share)
        if shares * curr_price > applied_capital: shares = int(applied_capital / curr_price)
        
        final_df = res.get('df', df)
        
        res.update({
            "shares": shares, "total_loss": shares * risk_per_share, "allowable_risk": allowable_risk,
            "df": final_df.tail(150),
            "atr": df.iloc[-1].get('ATR', 0), 
            "bandwidth": df.iloc[-1].get('Bandwidth', 0), "disparity": df.iloc[-1].get('Disparity25', 0),
            "is_us": is_us, "price": df.iloc[-1]['Close']
        })
        return res
    except: return None

def get_all_strategies_status(df):
    status = {}
    for s in ACTIVE_STRATEGIES:
        res = s.deep_dive(df)
        status[s.name] = res['signal']
    return status