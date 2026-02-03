import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import database as db  # DB 모듈 연동 필수

# -----------------------------------------------------------------------------
# 1. 환율 정보 (yfinance 사용)
# -----------------------------------------------------------------------------
def get_exchange_rate():
    try:
        # Ticker 객체 사용으로 스레드 충돌 방지
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
# 2. 데이터 수집 (DB + yfinance Ticker + 스레드 안전)
# -----------------------------------------------------------------------------
def fetch_data(code):
    try:
        # 티커 변환
        ticker_symbol = str(code)
        if ticker_symbol.isdigit(): 
            ticker_symbol = f"{code}.KS"

        # A. DB에서 마지막 날짜 확인
        last_date_str = db.get_last_price_date(code)
        today = datetime.now().date()
        
        should_update = False
        start_date = datetime.now() - timedelta(days=730) # 기본 2년
        
        if last_date_str:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            # 어제보다 과거 데이터면 업데이트
            if last_date < today - timedelta(days=1): 
                should_update = True
                start_date = last_date + timedelta(days=1)
        else:
            should_update = True # DB에 없으면 전체 다운로드

        # B. 업데이트 필요 시 다운로드 & DB 저장
        if should_update:
            try:
                stock = yf.Ticker(ticker_symbol)
                df_new = stock.history(start=start_date, auto_adjust=False)
                
                # 코스피 없으면 코스닥 재시도
                if df_new.empty and ticker_symbol.endswith(".KS"):
                    ticker_symbol = ticker_symbol.replace(".KS", ".KQ")
                    stock = yf.Ticker(ticker_symbol)
                    df_new = stock.history(start=start_date, auto_adjust=False)
                
                if not df_new.empty:
                    if df_new.index.tz is not None:
                        df_new.index = df_new.index.tz_localize(None)
                    db.save_daily_price(df_new, code)
            except Exception: pass 

        # C. 분석은 무조건 DB 데이터로 수행 (속도/안정성)
        df_final = db.load_daily_price(code)
        
        if df_final is None or len(df_final) < 60:
            return None
            
        return calculate_indicators(df_final)

    except Exception:
        return None

# -----------------------------------------------------------------------------
# 3. 보조지표 계산
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
    if 'Close' not in df.columns: return df

    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    df['HMA'] = calculate_hma(df['Close'], period=14)
    
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
    
    ma20_safe = df['MA20'].replace(0, np.nan)
    df['Bandwidth'] = (df['BB_Up2'] - df['BB_Dn2']) / ma20_safe
    
    delta = df['Close'].diff()
    up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
    df['RSI'] = 100 - (100 / (1 + up.rolling(14).mean() / down.rolling(14).mean()))
    
    n = 14
    low_n = df['Low'].rolling(window=n).min()
    high_n = df['High'].rolling(window=n).max()
    denom = (high_n - low_n).replace(0, np.nan)
    df['Stoch_K'] = ((df['Close'] - low_n) / denom) * 100
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
    df['Stoch_SlowD'] = df['Stoch_D'].rolling(window=3).mean()
    
    ma25 = df['Close'].rolling(window=25).mean()
    df['MA25'] = ma25
    df['Disparity25'] = (df['Close'] / ma25) * 100
    
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TPV'] = df['TP'] * df['Volume']
    df['VWAP'] = df['TPV'].cumsum() / df['Volume'].cumsum().replace(0, np.nan)

    pos_flow = pd.Series(0.0, index=df.index)
    neg_flow = pd.Series(0.0, index=df.index)
    pos_idx = df['TP'] > df['TP'].shift(1)
    neg_idx = df['TP'] < df['TP'].shift(1)
    pos_flow[pos_idx] = df.loc[pos_idx, 'TPV']
    neg_flow[neg_idx] = df.loc[neg_idx, 'TPV']
    
    pos_mf_sum = pos_flow.rolling(14).sum()
    neg_mf_sum = neg_flow.rolling(14).sum()
    mfi_ratio = pos_mf_sum / neg_mf_sum.replace(0, 1)
    df['MFI'] = 100 - (100 / (1 + mfi_ratio))

    df['High20'] = df['High'].rolling(window=20).max().shift(1)
    df['Low10']  = df['Low'].rolling(window=10).min().shift(1)
    
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Close'].shift(1)).abs()
    tr3 = (df['Low'] - df['Close'].shift(1)).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=20).mean()
        
    return df

# -----------------------------------------------------------------------------
# 4. 재무 정보 상세 조회 (정확도 개선 버전)
# -----------------------------------------------------------------------------
def get_financial_summary(code):
    try:
        ticker_symbol = str(code)
        if ticker_symbol.isdigit(): 
            ticker_symbol = f"{code}.KS"
            
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
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
                    rate = 1450.0 
                    krw_val = val * rate
                    krw_str = f"{krw_val/1_000_000_000_000:.1f}조" if krw_val >= 1e12 else f"{krw_val/1_000_000_000:.0f}억"
                    return f"{usd_val} ({krw_str})"
                except: return usd_val
            else:
                if val >= 1_000_000_000_000: return f"{val/1_000_000_000_000:.1f}조"
                else: return f"{val/1_000_000_000:.0f}억"

        # 2. 영업이익 (단위 보정 및 필터링)
        op_trend_str = "-"
        margin_trend_str = "-"
        
        try:
            q_fin = stock.quarterly_financials
            if not q_fin.empty:
                q_fin = q_fin.sort_index(axis=1)
                today = pd.Timestamp.now()
                past_cols = [c for c in q_fin.columns if pd.to_datetime(c) <= today]
                target_cols = past_cols[-4:]
                
                ops = []
                margins = []
                
                for date_col in target_cols:
                    try:
                        op = q_fin.loc['Operating Income', date_col] if 'Operating Income' in q_fin.index else 0
                        rev = q_fin.loc['Total Revenue', date_col] if 'Total Revenue' in q_fin.index else 0
                        
                        if op == 0 and rev == 0: continue

                        if is_us: op_str = f"${op/1_000_000:.0f}M"
                        else: op_str = f"{op/100_000_000:.0f}억" # 1억 단위 수정됨
                        
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

        # 3. 부채비율 직접 계산
        debt_ratio_val = 0
        try:
            bs = stock.balance_sheet
            if not bs.empty:
                total_debt_keys = ['Total Debt', 'Long Term Debt And Capital Lease Obligation']
                equity_keys = ['Stockholders Equity', 'Total Equity Gross Minority Interest']
                
                debt = 0; equity = 0
                for k in total_debt_keys:
                    if k in bs.index:
                        debt = bs.loc[k].iloc[0]; break
                for k in equity_keys:
                    if k in bs.index:
                        equity = bs.loc[k].iloc[0]; break
                        
                if equity > 0: debt_ratio_val = (debt / equity) * 100
                else: debt_ratio_val = info.get('debtToEquity', 0)
            else:
                debt_ratio_val = info.get('debtToEquity', 0)
        except:
            debt_ratio_val = info.get('debtToEquity', 0)

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