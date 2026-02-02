import pandas as pd
import numpy as np
from .common import format_price

# ==========================================
# 기본 전략 클래스 (틀)
# ==========================================
class StrategyBase:
    name = "Base"
    def check_signal(self, df): return 0 
    def get_report(self, item): return "" 
    def deep_dive(self, df): return {} 
    def backtest(self, df): 
        return pd.Series(False, index=df.index)
    def _make_html(self, title, analysis, action):
        return f"""<div style="background-color:#1a1c24; padding:15px; border-radius:10px;"><div style="font-size:1.4em; font-weight:bold; color:#fff;">{title}</div><ul style="color:#ddd; margin:10px 0;">{analysis}</ul><div style="background-color:#25262b; border-left:5px solid #00d2d3; padding:10px; color:#fff;">{action}</div></div>"""

# ==========================================
# 1. TH 알고리즘 (Smart Momentum)
# ==========================================
class StrategyTH(StrategyBase):
    name = "🧬TH알고리즘"
    
    def check_signal(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        if pd.notnull(curr.get('HMA')) and pd.notnull(prev.get('HMA')):
            trend_reversal = (curr['HMA'] > prev['HMA']) and (prev['HMA'] <= df.iloc[-3]['HMA'])
            trend_following = (curr['HMA'] > prev['HMA']) and (curr['Close'] > curr['HMA'])
            
            if (trend_reversal or trend_following) and curr['RSI'] < 75:
                slope = (curr['HMA'] - prev['HMA']) / prev['HMA'] * 10000
                return slope + (curr['RSI'] / 2)
        return 0

    def get_report(self, item):
        title = "🧬 TH알고리즘: 스마트 모멘텀"
        analysis = "<li><b>상황:</b> Zero-Lag HMA 상승 추세 포착.</li><li><b>AI판단:</b> 추세 강도 양호, 진입 적기.</li>"
        action = f"시스템 매수. 🛑 SafeZone: {format_price(item['현재가_RAW'] - 2.5*item.get('ATR',0), item['시장'], item['코드'])}"
        return self._make_html(title, analysis, action)

    def backtest(self, df):
        if 'HMA' not in df.columns: return pd.Series(False, index=df.index)
        return (df['HMA'] > df['HMA'].shift(1)) & (df['Close'] > df['HMA'])

    def deep_dive(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        
        # [Fix] Chart_Signal 컬럼 생성 필수
        buy_cond = self.backtest(df)
        df = df.copy()
        df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1
        
        hma_up = curr.get('HMA', 0) > prev.get('HMA', 0)
        price_ok = curr['Close'] > curr.get('HMA', 0)
        
        if hma_up and price_ok:
            if (prev.get('HMA', 0) <= df.iloc[-3].get('HMA', 0)) or (prev['Close'] <= prev.get('HMA', 0)):
                sig = "BUY (진입)"
            else:
                sig = "BUY (추세지속)"
        else:
            sig = "Wait"
            
        entry = curr['Close']
        stop = curr['Close'] - (3.0 * curr['ATR'])
        target = curr['Close'] + (6.0 * curr['ATR'])
        
        return {"signal": sig, "df": df, "entry_price": entry, "stop_price": stop, "target_price": target}

# ==========================================
# 2. 터틀 트레이딩 (Breakout)
# ==========================================
class StrategyTurtle(StrategyBase):
    name = "🐢터틀"
    def check_signal(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        if curr['Close'] > curr['High20'] and prev['Close'] <= prev['High20'] and curr['Close'] > curr['MA200']:
            return ((curr['Close'] / curr['High20']) - 1) * 1000
        return 0
    
    def get_report(self, item):
        return self._make_html("🐢 터틀: 신고가 돌파", "<li><b>상황:</b> 20일 저항선 강력 돌파.</li>", f"추세 추종 매수.")
    
    def backtest(self, df):
        return (df['Close'] > df['High20']) & (df['Close'].shift(1) <= df['High20'].shift(1)) & (df['Close'] > df['MA200'])

    def deep_dive(self, df):
        curr = df.iloc[-1]
        
        # [Fix] Chart_Signal 컬럼 생성 필수
        buy_cond = self.backtest(df)
        df = df.copy()
        df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1
        
        if buy_cond.iloc[-1]: sig = "BUY (돌파)"
        elif curr['Close'] < curr['Low10']: sig = "EXIT"
        elif curr['Close'] > curr['MA200']: sig = "HOLD (보유)"
        else: sig = "Wait"
        
        return {"signal": sig, "df": df, "entry_price": curr['High20'], "stop_price": curr['High20'] - 2*curr['ATR'], "target_price": curr['High20'] + 4*curr['ATR']}

# ==========================================
# 3. BNF (Rebound)
# ==========================================
class StrategyBNF(StrategyBase):
    name = "💧BNF"
    def check_signal(self, df):
        if df.iloc[-1]['Disparity25'] <= 90: return (100 - df.iloc[-1]['Disparity25']) * 2
        return 0

    def get_report(self, item):
        return self._make_html("💧 BNF: 과매도 반등", "<li><b>상황:</b> 이격도 90 이하 투매 발생.</li>", "역추세 매수.")

    def backtest(self, df):
        return (df['Disparity25'] <= 90)

    def deep_dive(self, df):
        curr = df.iloc[-1]
        
        # [Fix] Chart_Signal 컬럼 생성 필수
        buy_cond = self.backtest(df)
        df = df.copy()
        df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1
        
        sig = "BUY (과매도)" if curr['Disparity25'] <= 90 else "Wait"
        return {"signal": sig, "df": df, "entry_price": curr['Close'], "stop_price": curr['Close']*0.95, "target_price": curr['MA25']}

# ==========================================
# 4. 하이퍼 스나이퍼 (Hyper Sniper)
# ==========================================
class StrategyHyperSniper(StrategyBase):
    name = "🔫하이퍼스나이퍼"
    
    def check_signal(self, df):
        if len(df) < 60: return 0
        curr = df.iloc[-1]; prev = df.iloc[-2]
        
        vwap_ok = True
        if 'VWAP' in df.columns and pd.notnull(curr.get('VWAP')):
            vwap_ok = curr['Close'] >= curr['VWAP']
            
        avg_bw = df['Bandwidth'].rolling(20).mean().iloc[-1]
        squeeze_ok = (curr['Bandwidth'] < 0.20) or (curr['Bandwidth'] < avg_bw)
        elite_ok = curr['EMA10'] > curr['EMA20']
        
        breakout = (prev['Close'] < prev['MA20']) and (curr['Close'] > curr['MA20'])
        support = (curr['Close'] > curr['MA20']) and (curr['Low'] <= curr['MA20']*1.03) and (curr['Close'] > curr['Open'])
        trigger_ok = breakout or support
        momentum_ok = curr['MACD_Hist'] > prev['MACD_Hist']
        
        if vwap_ok and squeeze_ok and elite_ok and trigger_ok and momentum_ok:
            score = 80
            if breakout: score += 10 
            if curr['Volume'] > df['Volume'].rolling(20).mean().iloc[-1]: score += 10
            return score
        return 0

    def get_report(self, item):
        return self._make_html(
            "🔫 하이퍼 스나이퍼", 
            "<li><b>상태:</b> 에너지 응축(Squeeze) + 세력 지지(VWAP).</li><li><b>신호:</b> 20일선 맥점 돌파/지지 성공.</li>", 
            f"강력 매수. 🛑 손절: {format_price(item['MA20']*0.97, item['시장'], item['코드'])}"
        )

    def backtest(self, df):
        cond_cross = (df['Close'] > df['MA20']) & (df['Close'].shift(1) <= df['MA20'].shift(1))
        cond_elite = df['EMA10'] > df['EMA20']
        return cond_cross & cond_elite

    def deep_dive(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        is_above_ma20 = curr['Close'] > curr['MA20']
        elite_ok = curr['EMA10'] > curr['EMA20']
        
        breakout = (prev['Close'] < prev['MA20']) and is_above_ma20
        support = is_above_ma20 and (curr['Low'] <= curr['MA20'] * 1.03) and (curr['Close'] > curr['Open'])
        
        score_msg = []
        if 'VWAP' in df.columns and pd.notnull(curr.get('VWAP')):
            if curr['Close'] >= curr['VWAP']: score_msg.append("VWAP지지✅")
            else: score_msg.append("VWAP이탈❌")
        if curr['Bandwidth'] < 0.25: score_msg.append("응축됨✅")
        if elite_ok: score_msg.append("정배열✅")
        
        # [Fix] Chart_Signal 컬럼 생성 필수 (이미 되어 있음)
        buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1
        
        if breakout: sig = "BUY (돌파)"
        elif support and elite_ok: sig = "BUY (눌림목)"
        elif is_above_ma20 and elite_ok: sig = "HOLD (추세중)"
        elif not is_above_ma20: sig = "Wait (20일선 이탈)"
        else: sig = "Wait"
        
        entry = curr['Close']
        stop = curr['MA20'] * 0.97
        target = entry * 1.15
        
        return {"signal": sig, "df": df, "entry_price": entry, "stop_price": stop, "target_price": target, "msg": " ".join(score_msg)}

# ==========================================
# 활성화된 전략 목록
# ==========================================
ACTIVE_STRATEGIES = [
    StrategyHyperSniper(), 
    StrategyTH(),          
    StrategyTurtle(),      
    StrategyBNF()          
]