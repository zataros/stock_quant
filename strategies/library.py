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
# 1. TH 알고리즘 (핵심)
# ==========================================
class StrategyTH(StrategyBase):
    name = "🧬TH알고리즘"
    
    def check_signal(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        if pd.notnull(curr['HMA']) and pd.notnull(prev['HMA']):
            if curr['HMA'] > prev['HMA'] and curr['Close'] > curr['HMA'] and curr['RSI'] < 75:
                slope = (curr['HMA'] - prev['HMA']) / prev['HMA'] * 10000
                return slope + (curr['RSI'] / 2)
        return 0

    def get_report(self, item):
        title = "🧬 TH알고리즘: 스마트 모멘텀"
        analysis = "<li><b>상황:</b> Zero-Lag HMA 상승 추세 포착.</li><li><b>AI판단:</b> 추세 강도 양호, 진입 적기.</li>"
        action = f"시스템 매수. 🛑 SafeZone: {format_price(item['현재가_RAW'] - 2.5*item.get('ATR',0), item['시장'], item['코드'])}"
        return self._make_html(title, analysis, action)

    def backtest(self, df):
        return (df['HMA'] > df['HMA'].shift(1)) & \
               (df['HMA'].shift(1) <= df['HMA'].shift(2)) & \
               (df['Close'] > df['HMA'])

    def deep_dive(self, df):
        curr = df.iloc[-1]
        buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1
        
        signal = "BUY (AI Signal)" if buy_cond.iloc[-1] else ("EXIT" if curr['Close'] < curr['HMA'] else "HOLD")
        if signal == "BUY (AI Signal)":
            stop = curr['Close'] - (3.0 * curr['ATR'])
            target = curr['Close'] + (6.0 * curr['ATR'])
        else: stop = 0; target = 0
        
        # [Fix] df를 반드시 리턴에 포함해야 함
        return {"signal": signal, "df": df, "entry_price": curr['Close'], "stop_price": stop, "target_price": target}

# ==========================================
# 2. 터틀 트레이딩
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
        buy_cond = self.backtest(df)
        exit_cond = (df['Close'] < df['Low10'])
        df = df.copy(); df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1; df.loc[exit_cond, 'Chart_Signal'] = -1
        
        if buy_cond.iloc[-1]: sig = "BUY"
        elif curr['Close'] < curr['Low10']: sig = "EXIT"
        elif curr['Close'] > curr['MA200']: sig = "HOLD"
        else: sig = "Wait"
        return {"signal": sig, "df": df, "entry_price": curr['High20'], "stop_price": curr['High20'] - 2*curr['ATR'], "target_price": curr['High20'] + 4*curr['ATR']}

# ==========================================
# 3. 엘리트 매매법
# ==========================================
class StrategyElite(StrategyBase):
    name = "⚡엘리트"
    def check_signal(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        if (curr['EMA10'] > curr['EMA20'] > curr['EMA60']) and (curr['MACD'] > curr['Signal'] and prev['MACD'] <= prev['Signal']):
            return 10 + (curr['RSI'] - 50)
        return 0
    
    def get_report(self, item):
        return self._make_html("⚡ 엘리트: 골든크로스", "<li><b>상황:</b> 정배열 + MACD 신호.</li>", "정석 매수.")

    def backtest(self, df):
        return (df['EMA10'] > df['EMA20']) & (df['EMA20'] > df['EMA60']) & (df['MACD'] > df['Signal']) & (df['MACD'].shift(1) <= df['Signal'].shift(1))

    def deep_dive(self, df):
        curr = df.iloc[-1]
        buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0; df.loc[buy_cond, 'Chart_Signal'] = 1
        sig = "BUY" if buy_cond.iloc[-1] else ("HOLD" if (curr['EMA10'] > curr['EMA20']) else "Wait")
        return {"signal": sig, "df": df, "entry_price": curr['Close'], "stop_price": curr['MA20'], "target_price": curr['Close']*1.1}

# ==========================================
# 4. DBB (더블 볼린저)
# ==========================================
class StrategyDBB(StrategyBase):
    name = "🔥DBB"
    def check_signal(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        if curr['Close'] > curr['BB_Up2'] and prev['Close'] <= prev['BB_Up2']:
            return ((curr['Close']/curr['BB_Up2']) - 1) * 1000
        return 0

    def get_report(self, item):
        return self._make_html("🔥 DBB: 밴드 돌파", "<li><b>상황:</b> 볼린저 상단 강력 돌파.</li>", "돌파 매매 진입.")

    def backtest(self, df):
        return (df['Close'] > df['BB_Up2']) & (df['Close'].shift(1) <= df['BB_Up2'].shift(1))

    def deep_dive(self, df):
        curr = df.iloc[-1]; buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0; df.loc[buy_cond, 'Chart_Signal'] = 1
        sig = "BUY" if buy_cond.iloc[-1] else ("HOLD" if curr['Close'] > curr['BB_Up2'] else "Wait")
        return {"signal": sig, "df": df, "entry_price": curr['BB_Up2'], "stop_price": curr['Close']*0.97, "target_price": curr['BB_Up2']*1.15}

# ==========================================
# 5. BNF (과매도)
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
        curr = df.iloc[-1]; buy_cond = (df['Disparity25'] <= 90) & (df['Disparity25'].shift(1) > 90)
        df = df.copy(); df['Chart_Signal'] = 0; df.loc[buy_cond, 'Chart_Signal'] = 1
        sig = "BUY" if curr['Disparity25'] <= 90 else "Wait"
        return {"signal": sig, "df": df, "entry_price": curr['Close'], "stop_price": curr['Close']*0.95, "target_price": curr['MA25']}

# ==========================================
# 6. AI 스퀴즈
# ==========================================
class StrategySqueeze(StrategyBase):
    name = "🤖AI스퀴즈"
    def check_signal(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        avg_bw = df['Bandwidth'].rolling(120).mean().iloc[-1]
        if (prev['Bandwidth'] < 0.15 or prev['Bandwidth'] < avg_bw * 0.7) and \
           (curr['Volume'] > df['Volume'].rolling(20).mean().iloc[-1] * 1.5) and \
           (curr['Close'] > prev['Close']):
            return (curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1]) * 10
        return 0

    def get_report(self, item):
        return self._make_html("🚀 AI스퀴즈: 에너지 폭발", "<li><b>상황:</b> 응축 후 대량거래 폭발.</li>", "공격적 매수.")

    def backtest(self, df):
        avg_bw = df['Bandwidth'].rolling(120).mean()
        sqz = (df['Bandwidth'] < 0.15) | (df['Bandwidth'] < avg_bw * 0.7)
        vol = df['Volume'] > df['Volume'].rolling(20).mean() * 1.5
        return sqz & vol & (df['Close'] > df['MA20'])

    def deep_dive(self, df):
        curr = df.iloc[-1]; buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0; df.loc[buy_cond, 'Chart_Signal'] = 1
        sig = "BUY" if buy_cond.iloc[-1] else "Wait"
        return {"signal": sig, "df": df, "entry_price": curr['Close'], "stop_price": curr['MA20'], "target_price": curr['Close']*1.2}

# ==========================================
# 7. VWAP
# ==========================================
class StrategyVWAP(StrategyBase):
    name = "⚓VWAP"
    def check_signal(self, df):
        curr = df.iloc[-1]
        if pd.notnull(curr['VWAP']):
            diff = abs(curr['Close'] - curr['VWAP']) / curr['VWAP']
            if diff <= 0.03: return (1 - (diff / 0.03)) * 50
        return 0

    def get_report(self, item):
        return self._make_html("⚓ VWAP: 세력선 지지", "<li><b>상황:</b> VWAP 부근 지지 확인.</li>", "눌림목 매수.")

    def backtest(self, df):
        return (abs(df['Close'] - df['VWAP']) / df['VWAP'] <= 0.03)

    def deep_dive(self, df):
        curr = df.iloc[-1]
        if pd.isnull(curr['VWAP']): return {"signal": "N/A", "df": df, "entry_price": 0, "stop_price": 0, "target_price": 0}
        buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0; df.loc[buy_cond, 'Chart_Signal'] = 1
        is_buy = abs(curr['Close'] - curr['VWAP']) / curr['VWAP'] <= 0.03
        sig = "BUY (지지권)" if is_buy else ("HOLD" if curr['Close'] > curr['VWAP'] else "Wait")
        return {"signal": sig, "df": df, "entry_price": curr['VWAP'], "stop_price": curr['VWAP']*0.97, "target_price": curr['VWAP']*1.15}

# 활성화된 전략 목록
ACTIVE_STRATEGIES = [
    StrategyTH(), StrategyTurtle(), StrategyElite(), StrategyDBB(), 
    StrategyBNF(), StrategySqueeze(), StrategyVWAP()
]