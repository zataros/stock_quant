import streamlit as st
import FinanceDataReader as fdr
import pandas as pd

@st.cache_data(ttl=3600)
def get_master_data(market_code):
    try:
        df = pd.DataFrame()
        # [수정] 한국 시장: 전 종목 수집 후 스팩/우선주 제거
        if market_code in ["KOSPI", "KOSDAQ"]:
            df_krx = fdr.StockListing('KRX') # 전체 데이터
            if 'Code' not in df_krx.columns and 'Symbol' in df_krx.columns:
                df_krx = df_krx.rename(columns={'Symbol': 'Code'})
            
            # 시장 구분
            if market_code == "KOSPI":
                df = df_krx[df_krx['Market'] == 'KOSPI']
            elif market_code == "KOSDAQ":
                df = df_krx[df_krx['Market'].isin(['KOSDAQ', 'KOSDAQ GLOBAL'])]
            
            # [필터링 핵심] 스팩(SPAC), 우선주, 리츠 제외
            # 1. 스팩 제거
            df = df[~df['Name'].str.contains('스팩', case=False)]
            df = df[~df['Name'].str.contains('제[0-9]+호', regex=True)] # 제N호 등
            # 2. 우선주 제거 (종목명이 '우'로 끝나거나 '우B' 등 포함)
            df = df[~df['Name'].str.endswith('우')]
            df = df[~df['Name'].str.endswith('우B')]
            df = df[~df['Name'].str.contains('리츠')] # 리츠도 제외 (보통 기술적 분석이 다름)
            
            df = df[['Code', 'Name']]
            df['Market'] = market_code
            
        # 미국 시장
        elif market_code in ["S&P500", "NASDAQ", "NYSE", "NASDAQ_100"]:
            sym = market_code
            if market_code == "NASDAQ_100": sym = "NASDAQ"
            df = fdr.StockListing(sym)
            if market_code == "NASDAQ_100": df = df.head(100)
            df = df[['Symbol', 'Name']].rename(columns={'Symbol': 'Code'})
            df['Market'] = market_code
            
        return df
    except:
        return pd.DataFrame(columns=['Code', 'Name', 'Market'])

def search_code_by_name(keyword):
    """한글/영어/티커 통합 검색 (전체 데이터 기반)"""
    keyword = str(keyword).strip().upper()
    
    if keyword.isdigit() and len(keyword) == 6: return keyword
    
    # 한국 시장 (통합 검색)
    df_kr_kospi = get_master_data("KOSPI")
    df_kr_kosdaq = get_master_data("KOSDAQ")
    df_kr = pd.concat([df_kr_kospi, df_kr_kosdaq])
    
    # 정확히 일치 우선
    exact = df_kr[df_kr['Name'] == keyword]
    if not exact.empty: return exact.iloc[0]['Code']
    
    # 포함 검색
    contains = df_kr[df_kr['Name'].str.contains(keyword, case=False)]
    if not contains.empty: return contains.iloc[0]['Code']
    
    # 미국 시장
    for mkt in ["NASDAQ", "S&P500"]:
        df_us = get_master_data(mkt)
        res = df_us[df_us['Code'] == keyword]
        if not res.empty: return res.iloc[0]['Code']
        res_name = df_us[df_us['Name'].str.contains(keyword, case=False)]
        if not res_name.empty: return res_name.iloc[0]['Code']
            
    return None

def get_stock_name(code):
    try:
        # 데이터가 많으므로 효율적으로 검색
        for mkt in ["KOSPI", "KOSDAQ", "NASDAQ", "S&P500"]:
            df = get_master_data(mkt)
            row = df[df['Code'] == str(code)]
            if not row.empty: return row.iloc[0]['Name']
        return code
    except: return code