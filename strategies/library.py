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
# 1. TH 알고리즘 (Smart Momentum) - 정밀도 UP
# ==========================================
class StrategyTH(StrategyBase):
    name = "🧬TH알고리즘"
    
    def check_signal(self, df):
        if len(df) < 5: return 0
        curr = df.iloc[-1]; prev = df.iloc[-2]; prev2 = df.iloc[-3]
        
        if pd.isna(curr.get('HMA')): return 0

        # [수정] 단순 추세 추종 제거, '변곡점(Turn)'만 포착
        # 1. HMA가 하락하다가 상승 반전 (V자 반등)
        hma_turn_up = (curr['HMA'] > prev['HMA']) and (prev['HMA'] <= prev2['HMA'])
        
        # 2. 눌림목: HMA가 상승 중인데, 주가가 HMA 근처까지 왔다가 양봉 발생
        is_uptrend = curr['HMA'] > prev['HMA'] > prev2['HMA']
        pullback = is_uptrend and (prev['Close'] < prev['HMA']) and (curr['Close'] > curr['HMA'])
        
        # 필터: RSI가 과열(70)이 아니어야 함
        rsi_ok = 40 <= curr['RSI'] <= 70
        
        if (hma_turn_up or pullback) and rsi_ok:
            return 80 + (curr['RSI'] / 5) # 점수 계산
            
        return 0

    def get_report(self, item):
        title = "🧬 TH알고리즘: 스마트 변곡점"
        analysis = "<li><b>상황:</b> 하락하던 추세가 AI HMA 라인을 타고 <b>상승 반전</b>했습니다.</li><li><b>특징:</b> 단순 상승이 아닌, 추세의 <b>시작점</b>을 포착했습니다.</li>"
        action = f"추세 초입 매수. 🛑 손절선: {format_price(item['HMA'], item['시장'], item['코드'])} 이탈 시"
        return self._make_html(title, analysis, action)

    def backtest(self, df):
        if 'HMA' not in df.columns: return pd.Series(False, index=df.index)
        # HMA 상승 반전 조건
        return (df['HMA'] > df['HMA'].shift(1)) & (df['HMA'].shift(1) <= df['HMA'].shift(2)) & (df['Close'] > df['HMA'])

    def deep_dive(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1
        
        hma_turn = (curr['HMA'] > prev['HMA']) and (prev['HMA'] <= df.iloc[-3]['HMA'])
        
        if hma_turn: sig = "BUY (변곡점)"
        elif (curr['HMA'] > prev['HMA']) and (curr['Close'] > curr['HMA']): sig = "HOLD (추세중)"
        else: sig = "Wait"
            
        return {"signal": sig, "df": df, "entry_price": curr['Close'], "stop_price": curr['HMA'], "target_price": curr['Close']*1.1}

# ==========================================
# 2. 터틀 트레이딩 (Breakout) - 거래량 필터 추가
# ==========================================
class StrategyTurtle(StrategyBase):
    name = "🐢터틀"
    def check_signal(self, df):
        curr = df.iloc[-1]; prev = df.iloc[-2]
        
        # 1. 20일 신고가 돌파
        breakout = curr['Close'] > curr['High20'] and prev['Close'] <= prev['High20']
        
        # [수정] 거래량 필터 추가 (평균 거래량보다 커야 함) - 가짜 돌파 방지
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        vol_ok = curr['Volume'] > avg_vol
        
        # [수정] 장기 추세 필터 (200일선 위에 있어야 안전)
        trend_ok = curr['Close'] > curr['MA200']
        
        if breakout and vol_ok and trend_ok:
            return 90
        return 0
    
    def get_report(self, item):
        return self._make_html("🐢 터틀: 거래량 실린 신고가", "<li><b>상황:</b> 20일 고점을 <b>강한 거래량</b>과 함께 돌파.</li><li><b>의미:</b> 새로운 시세의 출발 신호.</li>", f"돌파 매수.")
    
    def backtest(self, df):
        vol_ma = df['Volume'].rolling(20).mean()
        return (df['Close'] > df['High20']) & (df['Close'].shift(1) <= df['High20'].shift(1)) & (df['Volume'] > vol_ma)

    def deep_dive(self, df):
        curr = df.iloc[-1]
        buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1
        
        if buy_cond.iloc[-1]: sig = "BUY (강한돌파)"
        elif curr['Close'] < curr['Low10']: sig = "EXIT"
        elif curr['Close'] > curr['MA200']: sig = "HOLD"
        else: sig = "Wait"
        
        return {"signal": sig, "df": df, "entry_price": curr['High20'], "stop_price": curr['High20'] - 2*curr['ATR'], "target_price": curr['High20'] + 4*curr['ATR']}

# ==========================================
# 3. BNF (Rebound) - RSI 필터 추가
# ==========================================
class StrategyBNF(StrategyBase):
    name = "💧BNF"
    def check_signal(self, df):
        curr = df.iloc[-1]
        # 1. 이격도 90 이하 (10% 이상 괴리)
        disp_ok = curr['Disparity25'] <= 90
        
        # [수정] RSI 침체권 확인 (떨어지는 칼날 잡기 방지)
        rsi_ok = curr['RSI'] < 35 
        
        if disp_ok and rsi_ok:
            return (100 - curr['Disparity25']) * 3
        return 0

    def get_report(self, item):
        return self._make_html("💧 BNF: 과매도 바닥 잡기", "<li><b>상황:</b> 이격도 90 이하 + RSI 침체.</li><li><b>판단:</b> 기술적 반등 확률 매우 높음.</li>", "분할 매수 진입.")

    def backtest(self, df):
        return (df['Disparity25'] <= 90) & (df['RSI'] < 35)

    def deep_dive(self, df):
        curr = df.iloc[-1]
        buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1
        
        sig = "BUY (투매발생)" if (curr['Disparity25'] <= 90 and curr['RSI'] < 35) else "Wait"
        return {"signal": sig, "df": df, "entry_price": curr['Close'], "stop_price": curr['Close']*0.93, "target_price": curr['MA25']}

# ==========================================
# 4. 하이퍼 스나이퍼 (Hyper Sniper) - 조건 대폭 강화
# ==========================================
class StrategyHyperSniper(StrategyBase):
    name = "🔫하이퍼스나이퍼"
    
    def check_signal(self, df):
        if len(df) < 60: return 0
        curr = df.iloc[-1]; prev = df.iloc[-2]
        
        # 1. [필수] 거래량 폭발 조건 추가 (평균 대비 150% 이상)
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        if avg_vol == 0: return 0
        vol_spike = curr['Volume'] >= (avg_vol * 1.5)
        
        # 2. [필수] 캔들 조건 (양봉이어야 함)
        is_bullish = curr['Close'] > curr['Open']
        
        # 3. VWAP 지지 (세력선 위)
        vwap_ok = True
        if 'VWAP' in df.columns and pd.notnull(curr.get('VWAP')):
            vwap_ok = curr['Close'] >= curr['VWAP']
            
        # 4. 스퀴즈 (응축) 조건
        # 밴드폭이 매우 좁거나(0.15 이하), 좁았다가 막 벌어지는(Expansion) 순간
        bw = curr['Bandwidth']
        prev_bw = prev['Bandwidth']
        is_tight = bw < 0.15 # 매우 좁음
        is_expanding = (bw < 0.30) and (bw > prev_bw) and (prev_bw < 0.20) # 좁았다가 팍!
        squeeze_ok = is_tight or is_expanding
        
        # 5. 정배열 초입 (10일선 > 20일선)
        elite_ok = curr['EMA10'] > curr['EMA20']
        
        # 6. 트리거 (20일선 돌파 or 지지반등)
        breakout = (prev['Close'] < prev['MA20']) and (curr['Close'] > curr['MA20'])
        support = (curr['Close'] > curr['MA20']) and (curr['Low'] <= curr['MA20']*1.02)
        trigger_ok = breakout or support
        
        # 7. RSI (힘이 있어야 함)
        rsi_ok = 50 <= curr['RSI'] <= 80

        # [종합 판정] 모든 조건 만족 시에만 신호 발생 (AND 조건)
        if vol_spike and is_bullish and vwap_ok and squeeze_ok and elite_ok and trigger_ok and rsi_ok:
            score = 90
            if is_expanding: score += 10 # 이제 막 터지는 놈 가산점
            return score
            
        return 0

    def get_report(self, item):
        return self._make_html(
            "🔫 하이퍼 스나이퍼 (급등 포착)", 
            "<li><b>응축 폭발:</b> 밴드폭 축소 후 <b>거래량 150%↑</b> 폭발 발생.</li><li><b>세력 개입:</b> VWAP 위에서 양봉 발생. 급등 직전 패턴.</li>", 
            f"강력 매수 (Sniper Shot). 🛑 손절: {format_price(item['MA20']*0.97, item['시장'], item['코드'])}"
        )

    def backtest(self, df):
        # 백테스트 조건도 동일하게 강화
        vol_ma = df['Volume'].rolling(20).mean()
        vol_cond = df['Volume'] > (vol_ma * 1.5)
        bullish = df['Close'] > df['Open']
        ma_cross = df['Close'] > df['MA20']
        squeeze = df['Bandwidth'] < 0.30
        return vol_cond & bullish & ma_cross & squeeze

    def deep_dive(self, df):
        curr = df.iloc[-1]
        
        # 분석 메시지 생성
        score_msg = []
        vol_ma = df['Volume'].rolling(20).mean().iloc[-1]
        if curr['Volume'] > vol_ma * 1.5: score_msg.append("거래량폭발🔥")
        if curr['Bandwidth'] < 0.20: score_msg.append("초강력응축⚡")
        elif curr['Bandwidth'] < 0.30: score_msg.append("응축양호✅")
        
        if 'VWAP' in df.columns and curr['Close'] >= curr['VWAP']: score_msg.append("세력선지지🛡️")
        
        # 차트 신호 표시
        buy_cond = self.backtest(df)
        df = df.copy(); df['Chart_Signal'] = 0
        df.loc[buy_cond, 'Chart_Signal'] = 1
        
        # 신호 판단 (엄격하게)
        is_signal = self.check_signal(df) > 0
        
        if is_signal: sig = "BUY (Sniper!)"
        elif curr['Close'] > curr['MA20']: sig = "HOLD"
        else: sig = "Wait"
        
        entry = curr['Close']
        stop = curr['MA20'] * 0.97
        target = entry * 1.20 # 목표가 상향
        
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