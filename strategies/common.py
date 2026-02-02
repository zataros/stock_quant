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
        df = fdr.DataReader(str(code), datetime.now() - timedelta(days=365)) 
        if len(df) < 200: return None 
        return calculate_indicators(df)
    except: return None

def calculate_hma(series, period=14):
    half_length = int(period / 2)
    sqrt_length = int(np.sqrt(period))
    wma_half = series.rolling(window=half_length).mean()
    wma_full = series.rolling(window=period).mean()
    raw_hma = (2 * wma_half) - wma_full
    hma = raw_hma.rolling(window=sqrt_length).mean()
    return hma

def calculate_indicators(df):
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # TH알고리즘용 HMA
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