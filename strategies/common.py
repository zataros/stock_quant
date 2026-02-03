import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import database as db

# -----------------------------------------------------------------------------
# 환율 정보
# -----------------------------------------------------------------------------
def get_exchange_rate():
    try:
        # 환율은 캐싱 없이 가볍게 호출하거나, 필요시 별도 처리
        ticker = yf.Ticker("USDKRW=X")
        hist = ticker.history(period="5d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except: pass
    return 1450.0

def format_price(val, market="KR", code=None):
    try:
        if val is None: return "-"
        val = float(val)
        
        is_us = False
        if code and str(code).isalpha(): is_us = True
        if market and any(x in str(market).upper() for x in ["US", "NASDAQ", "NYSE", "S&P500"]): is_us = True
            
        if is_us: return f"${val:,.2f}"
        else: return f"{int(val):,}원"
    except: return str(val)

# -----------------------------------------------------------------------------
# [핵심 수정] 데이터 수집 (스레드 안전성 강화: Ticker 객체 사용)
# -----------------------------------------------------------------------------
def fetch_data(code):
    """
    yf.download 대신 yf.Ticker().history() 사용 -> 멀티스레드 충돌 방지
    """
    try:
        # 티커 변환 (한국 주식)
        ticker_symbol = str(code)
        if ticker_symbol.isdigit(): 
            ticker_symbol = f"{code}.KS"

        # 1. DB에서 마지막 저장일 확인
        last_date_str = db.get_last_price_date(code)
        today = datetime.now().date()
        
        should_update = False
        
        # 날짜 계산 (기본 2년)
        start_date = datetime.now() - timedelta(days=730)
        
        if last_date_str:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            if last_date < today - timedelta(days=1): 
                should_update = True
                # 마지막 저장일 다음날부터
                start_date = last_date + timedelta(days=1)
        else:
            should_update = True

        # [업데이트 필요 시] 인터넷에서 다운로드
        if should_update:
            try:
                # [중요] yf.Ticker 객체 생성 (독립 인스턴스)
                stock = yf.Ticker(ticker_symbol)
                
                # start_date부터 오늘까지 데이터 요청
                df_new = stock.history(start=start_date, auto_adjust=False) # 수정주가 반영 X (필요시 True)
                
                # 코스피(.KS) 데이터 없으면 코스닥(.KQ) 시도
                if df_new.empty and ticker_symbol.endswith(".KS"):
                    ticker_symbol = ticker_symbol.replace(".KS", ".KQ")
                    stock = yf.Ticker(ticker_symbol)
                    df_new = stock.history(start=start_date, auto_adjust=False)
                
                if not df_new.empty:
                    # 타임존 제거
                    if df_new.index.tz is not None:
                        df_new.index = df_new.index.tz_localize(None)
                    
                    # DB 저장
                    db.save_daily_price(df_new, code)
                    
            except Exception as e:
                # print(f"Download error {code}: {e}")
                pass 

        # 2. DB에서 전체 데이터 로드 (분석은 항상 DB 데이터로)
        df_final = db.load_daily_price(code)
        
        # 데이터가 너무 적으면 분석 불가
        if df_final is None or len(df_final) < 60:
            return None
            
        # 3. 보조지표 계산
        return calculate_indicators(df_final)

    except Exception as e:
        return None

# -----------------------------------------------------------------------------
# 보조지표 계산 (기존 유지)
# -----------------------------------------------------------------------------
def calculate_hma(series, period=14):
    half_length = int(period / 2)
    sqrt_length = int(np.sqrt(period))
    wma_half = series.rolling(window=half_length).mean()
    wma_full = series.rolling(window=period).mean()
    raw_hma = (2 * wma_half) - wma_full
    hma = raw_hma.rolling(window=sqrt_length).mean()
    return hma

def calculate_indicators(df):
    # 필수 컬럼 존재 확인
    if 'Close' not in df.columns: return df

    # 이동평균
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # HMA
    df['HMA'] = calculate_hma(df['Close'], period=14)
    
    # EMA
    df['EMA10'] = df['Close'].ewm(span=10, adjust=False).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
    
    # MACD
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    
    # Bollinger Bands
    std20 = df['Close'].rolling(window=20).std()
    df['BB_Up2'] = df['MA20'] + (std20 * 2)
    df['BB_Dn2'] = df['MA20'] - (std20 * 2)
    
    # Zero division 방지
    ma20_safe = df['MA20'].replace(0, np.nan)
    df['Bandwidth'] = (df['BB_Up2'] - df['BB_Dn2']) / ma20_safe
    
    # RSI
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    roll_up = up.rolling(window=14).mean()
    roll_down = down.rolling(window=14).mean()
    rs = roll_up / roll_down
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Stochastic
    n = 14
    low_n = df['Low'].rolling(window=n).min()
    high_n = df['High'].rolling(window=n).max()
    denom = (high_n - low_n).replace(0, np.nan)
    df['Stoch_K'] = ((df['Close'] - low_n) / denom) * 100
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
    df['Stoch_SlowD'] = df['Stoch_D'].rolling(window=3).mean()
    
    # Disparity (이격도)
    ma25 = df['Close'].rolling(window=25).mean()
    df['MA25'] = ma25
    df['Disparity25'] = (df['Close'] / ma25) * 100
    
    # VWAP
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TPV'] = df['TP'] * df['Volume']
    cum_tpv = df['TPV'].cumsum()
    cum_vol = df['Volume'].cumsum()
    df['VWAP'] = cum_tpv / cum_vol.replace(0, np.nan)

    # MFI
    pos_flow = pd.Series(0.0, index=df.index)
    neg_flow = pd.Series(0.0, index=df.index)
    
    delta_tp = df['TP'].diff()
    pos_idx = delta_tp > 0
    neg_idx = delta_tp < 0
    
    pos_flow[pos_idx] = df.loc[pos_idx, 'TPV']
    neg_flow[neg_idx] = df.loc[neg_idx, 'TPV']
    
    mfi_len = 14
    pos_mf_sum = pos_flow.rolling(mfi_len).sum()
    neg_mf_sum = neg_flow.rolling(mfi_len).sum()
    mfi_ratio = pos_mf_sum / neg_mf_sum.replace(0, 1)
    df['MFI'] = 100 - (100 / (1 + mfi_ratio))

    # Turtle & ATR
    df['High20'] = df['High'].rolling(window=20).max().shift(1)
    df['Low10']  = df['Low'].rolling(window=10).min().shift(1)
    
    prev_close = df['Close'].shift(1)
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - prev_close).abs()
    tr3 = (df['Low'] - prev_close).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=20).mean()
        
    return df

# -----------------------------------------------------------------------------
# [업그레이드 Fix] 재무 정보 상세 (단위 수정 + 부채비율 직접 계산)
# -----------------------------------------------------------------------------
def get_financial_summary(code):
    try:
        ticker_symbol = str(code)
        if ticker_symbol.isdigit(): 
            ticker_symbol = f"{code}.KS"
            
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        # 데이터 없으면 코스닥 시도
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            if ticker_symbol.endswith(".KS"):
                ticker_symbol = ticker_symbol.replace(".KS", ".KQ")
                stock = yf.Ticker(ticker_symbol)
                info = stock.info

        if not info: return None

        # 1. 시가총액 직접 계산
        price = info.get('currentPrice') or info.get('regularMarketPrice') or 0
        shares = info.get('sharesOutstanding') or 0
        market_cap_raw = (price * shares) if (price > 0 and shares > 0) else info.get('marketCap', 0)
        
        is_us = not (ticker_symbol.endswith(".KS") or ticker_symbol.endswith(".KQ"))
        
        def fmt_cap(val):
            if not val: return "-"
            if is_us:
                usd_val = f"${val/1_000_000_000:.2f}B"
                try:
                    # 환율 적용 (get_exchange_rate 함수 활용)
                    # 이 함수가 상단에 정의되어 있어야 합니다.
                    rate = 1450.0 # 기본값 (혹은 get_exchange_rate() 호출)
                    krw_val = val * rate
                    krw_str = f"{krw_val/1_000_000_000_000:.1f}조" if krw_val >= 1e12 else f"{krw_val/1_000_000_000:.0f}억"
                    return f"{usd_val} ({krw_str})"
                except: return usd_val
            else:
                # 한국: 조/억 단위
                if val >= 1_000_000_000_000: return f"{val/1_000_000_000_000:.1f}조"
                else: return f"{val/1_000_000_000:.0f}억"

        # 2. 영업이익 & 이익률 (과거 확정 실적만 필터링)
        op_trend_str = "-"
        margin_trend_str = "-"
        
        try:
            q_fin = stock.quarterly_financials
            if not q_fin.empty:
                q_fin = q_fin.sort_index(axis=1) # 과거 -> 최신 정렬
                
                # 미래 데이터(컨센서스) 제외
                today = pd.Timestamp.now()
                past_cols = [c for c in q_fin.columns if pd.to_datetime(c) <= today]
                target_cols = past_cols[-4:] # 최근 4분기
                
                ops = []
                margins = []
                
                for date_col in target_cols:
                    try:
                        op = q_fin.loc['Operating Income', date_col] if 'Operating Income' in q_fin.index else 0
                        rev = q_fin.loc['Total Revenue', date_col] if 'Total Revenue' in q_fin.index else 0
                        
                        if op == 0 and rev == 0: continue

                        # [수정] 단위 포맷팅 버그 수정
                        if is_us: 
                            op_str = f"${op/1_000_000:.0f}M" # 백만 달러
                        else: 
                            # 한국: 1억 = 10^8 (기존 10^9 오류 수정)
                            op_str = f"{op/100_000_000:.0f}억"
                        
                        if rev and rev > 0:
                            margin = (op / rev) * 100
                            margins.append(f"{margin:.1f}%")
                        else:
                            margins.append("-")
                            
                        d_str = pd.to_datetime(date_col).strftime("%y.%m")
                        ops.append(f"<span style='font-size:0.8em; color:#aaa;'>{d_str}</span> {op_str}")
                    except: pass
                
                if ops:
                    op_trend_str = " / ".join(ops)
                    margin_trend_str = " / ".join(margins)
        except Exception: pass

        # 3. 부채비율 직접 계산 (info 데이터 부정확 해결)
        debt_ratio_val = 0
        try:
            bs = stock.balance_sheet
            # 최근 결산일 기준
            if not bs.empty:
                # Total Debt / Stockholders Equity
                total_debt_keys = ['Total Debt', 'Long Term Debt And Capital Lease Obligation'] # yfinance 키 확인
                equity_keys = ['Stockholders Equity', 'Total Equity Gross Minority Interest']
                
                debt = 0
                equity = 0
                
                # 부채 찾기
                for k in total_debt_keys:
                    if k in bs.index:
                        debt = bs.loc[k].iloc[0]
                        break
                # 자본 찾기
                for k in equity_keys:
                    if k in bs.index:
                        equity = bs.loc[k].iloc[0]
                        break
                        
                if equity > 0:
                    debt_ratio_val = (debt / equity) * 100
                else:
                    debt_ratio_val = info.get('debtToEquity', 0) # 실패 시 info 사용
            else:
                debt_ratio_val = info.get('debtToEquity', 0)
        except:
            debt_ratio_val = info.get('debtToEquity', 0)

        # PER/PBR
        per = info.get('trailingPE', 0)
        pbr = info.get('priceToBook', 0)

        return {
            "시가총액": fmt_cap(market_cap_raw),
            "영업이익_추세": op_trend_str,
            "이익률_추세": margin_trend_str,
            "부채비율": f"{debt_ratio_val:.1f}%" if debt_ratio_val else "-",
            "PER": f"{per:.2f}" if per else "-",
            "PBR": f"{pbr:.2f}" if pbr else "-"
        }
    except Exception:
        return None