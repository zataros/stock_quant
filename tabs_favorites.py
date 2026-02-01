import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor
import database as db
import data_loader as dl
import re

# -----------------------------------------------------------------------------
# [유틸리티] 포맷팅 및 파싱 함수
# -----------------------------------------------------------------------------
def format_price(val, is_kr):
    """숫자를 콤마가 포함된 문자열로 변환"""
    try:
        val = float(val)
        if is_kr:
            # 한국: 원화 표시, 3자리 콤마
            return f"₩{int(val):,}"
        else:
            # 미국: 달러 표시, 소수점 2자리, 3자리 콤마
            return f"${val:,.2f}"
    except:
        return str(val)

def parse_price(price_str):
    """문자열(₩1,000 등)에서 숫자만 추출"""
    if isinstance(price_str, (int, float)):
        return float(price_str)
    
    clean_str = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(clean_str)
    except:
        return 0.0

# -----------------------------------------------------------------------------
# 종목 검색 헬퍼 함수
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def search_stock_info(keyword):
    keyword = keyword.strip().upper()
    markets = ["KOSPI", "KOSDAQ", "S&P500", "NASDAQ"]
    
    for m in markets:
        df = dl.get_master_data(m)
        if df.empty: continue
        
        # 1. 코드 정확 일치
        code_match = df[df['Code'] == keyword]
        if not code_match.empty:
            return code_match.iloc[0]['Code'], code_match.iloc[0]['Name']
        
        # 2. 이름 포함 확인
        name_match = df[df['Name'].str.contains(keyword, case=False, na=False)]
        if not name_match.empty:
            name_match = name_match.sort_values(by="Name", key=lambda x: x.str.len())
            return name_match.iloc[0]['Code'], name_match.iloc[0]['Name']

    try:
        t = yf.Ticker(keyword)
        info = t.info
        if 'symbol' in info:
            return info['symbol'], info.get('shortName', keyword)
    except:
        pass
        
    return None, None

# -----------------------------------------------------------------------------
# 시세 조회 함수
# -----------------------------------------------------------------------------
def fetch_prices_threaded(codes):
    if not codes: return {}
    results = {}
    
    try:
        kospi_df = dl.get_master_data("KOSPI")
        kosdaq_df = dl.get_master_data("KOSDAQ")
        kospi_set = set(kospi_df['Code'].values)
        kosdaq_set = set(kosdaq_df['Code'].values)
    except:
        kospi_set = set()
        kosdaq_set = set()
    
    def fetch_one(code):
        try:
            target_ticker = code
            if str(code).isdigit() and len(str(code)) == 6:
                if code in kospi_set: target_ticker = f"{code}.KS"
                elif code in kosdaq_set: target_ticker = f"{code}.KQ"
                else: target_ticker = f"{code}.KS"
            
            ticker = yf.Ticker(target_ticker)
            price = ticker.fast_info.get('last_price', 0.0)
            
            if (price is None or price <= 0) and str(code).isdigit() and len(str(code)) == 6:
                alt_ticker = f"{code}.KQ" if ".KS" in target_ticker else f"{code}.KS"
                ticker_alt = yf.Ticker(alt_ticker)
                price = ticker_alt.fast_info.get('last_price', 0.0)
                if price > 0: ticker = ticker_alt

            if price is None or price <= 0:
                hist = ticker.history(period='5d')
                if not hist.empty: price = hist['Close'].iloc[-1]
                else: price = 0.0
            return code, price
        except: return code, 0.0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_one, c) for c in codes]
        for f in futures:
            c, p = f.result()
            results[c] = p
    return results

# -----------------------------------------------------------------------------
# 헬퍼: 한국 주식 여부 판별
# -----------------------------------------------------------------------------
def is_korean_stock(code):
    s_code = str(code)
    if s_code.isdigit() and len(s_code) == 6: return True
    if s_code.endswith(".KS") or s_code.endswith(".KQ"): return True
    return False

# -----------------------------------------------------------------------------
# DB 업데이트 공통 함수
# -----------------------------------------------------------------------------
def process_db_updates(user, edited_df, original_df):
    changes = False
    
    # 삭제 처리
    to_delete = edited_df[edited_df["선택"] == True]
    if not to_delete.empty:
        for c in to_delete["코드"]:
            db.remove_favorite(user, c)
            if "fav_prices" in st.session_state and c in st.session_state["fav_prices"]:
                del st.session_state["fav_prices"][c]
        st.success(f"{len(to_delete)}개 종목이 삭제되었습니다.")
        changes = True

    # 수정 처리
    for idx, row in edited_df.iterrows():
        orig_rows = original_df[original_df['코드'] == row['코드']]
        if orig_rows.empty: continue
        orig_row = orig_rows.iloc[0]

        # 매수가 변경 (파싱 필요)
        new_price_val = parse_price(row["매수가"])
        orig_price_val = parse_price(orig_row["매수가"])
        
        if abs(new_price_val - orig_price_val) > 0.001:
            db.update_favorite_price(user, row["코드"], new_price_val)
            changes = True
        
        # 등록일 변경
        if row["관심등록일"] != orig_row["관심등록일"]:
            new_date_str = row["관심등록일"].strftime("%Y-%m-%d")
            db.update_favorite_date(user, row["코드"], new_date_str)
            changes = True
            
    return changes

# -----------------------------------------------------------------------------
# 메인 실행 함수
# -----------------------------------------------------------------------------
def run():
    st.subheader("💖 관심종목 포트폴리오")
    user = st.session_state["username"]
    
    # 1. 종목 추가
    with st.expander("➕ 종목 수동 추가", expanded=False):
        c1, c2, c3 = st.columns([2, 2, 1])
        input_keyword = c1.text_input("종목명 또는 티커 검색", placeholder="예: 삼성전자, 005930, NVDA", key="fav_add_keyword")
        new_price = c2.number_input("매수가 (선택)", min_value=0.0, value=0.0, step=100.0, key="fav_add_price")
        
        if c3.button("검색 및 추가", use_container_width=True):
            if input_keyword:
                with st.spinner(f"'{input_keyword}' 검색 중..."):
                    found_code, found_name = search_stock_info(input_keyword)
                if found_code:
                    db.add_favorite(user, found_code, name=found_name, price=new_price, strategies="Manual")
                    st.success(f"✅ 등록 완료: {found_name} ({found_code})")
                    if "fav_prices" in st.session_state: del st.session_state["fav_prices"]
                    st.rerun()
                else:
                    st.error(f"❌ '{input_keyword}' 종목을 찾을 수 없습니다.")
            else:
                st.warning("검색어를 입력하세요.")

    # 2. 데이터 로드
    fav_list = db.get_favorites(user) 
    if not fav_list:
        st.info("등록된 관심종목이 없습니다.")
        return

    df = pd.DataFrame(fav_list, columns=["코드", "관심등록일", "매수가", "전략", "종목명"])
    
    def parse_date(d_str):
        try: return datetime.strptime(d_str, "%Y-%m-%d").date()
        except: return date.today()
    df["관심등록일"] = df["관심등록일"].apply(parse_date)

    # 3. 시세 조회
    if "fav_prices" not in st.session_state: st.session_state["fav_prices"] = {}
    codes = df["코드"].tolist()
    need_fetch = any(c not in st.session_state["fav_prices"] for c in codes)
    
    c_ref, _ = st.columns([1, 5])
    if c_ref.button("🔄 시세 새로고침"):
        with st.spinner("최신 시세 조회 중..."):
            new_prices = fetch_prices_threaded(codes)
            st.session_state["fav_prices"].update(new_prices)
    elif need_fetch:
        with st.spinner("데이터 로딩 중..."):
            new_prices = fetch_prices_threaded(codes)
            st.session_state["fav_prices"].update(new_prices)

    df["현재가_숫자"] = df["코드"].map(st.session_state["fav_prices"]).fillna(0.0)

    # 4. 계산 로직 (수익률, 기간, 일간수익률)
    today = date.today()
    
    # (1) 등록기간(일) 계산
    df['등록기간(일)'] = df['관심등록일'].apply(lambda d: (today - d).days)
    
    # (2) 수익률 계산
    def calc_return(row):
        try:
            cp = float(row["현재가_숫자"])
            bp = float(row["매수가"])
            if bp > 0 and cp > 0: return ((cp - bp) / bp) * 100
        except: pass
        return 0.0
    df["수익률(%)"] = df.apply(calc_return, axis=1)
    
    # (3) 일간수익률 (평균수익률) 계산
    # 등록기간이 0일(오늘)이면 1로 나누어 에러 방지
    df['일간수익률(%)'] = df.apply(lambda x: x['수익률(%)'] / max(1, x['등록기간(일)']), axis=1)

    # 5. 국가별 분리 및 포맷팅
    df['is_kr'] = df['코드'].apply(is_korean_stock)
    
    df_kr = df[df['is_kr'] == True].copy()
    df_us = df[df['is_kr'] == False].copy()

    # -------------------------------------------------------------
    # [국내 주식]
    # -------------------------------------------------------------
    if not df_kr.empty:
        df_kr["현재가"] = df_kr["현재가_숫자"].apply(lambda x: format_price(x, True))
        df_kr["매수가"] = df_kr["매수가"].apply(lambda x: format_price(x, True))
        
        # 순서 및 배치: 수익률 우측에 기간, 일간수익률 추가
        df_kr_display = df_kr[[
            "관심등록일", "코드", "종목명", "매수가", "전략", "현재가", 
            "수익률(%)", "등록기간(일)", "일간수익률(%)"
        ]].copy()
        df_kr_display.insert(0, "선택", False)
        
        st.markdown("#### 🇰🇷 국내 주식")
        edited_kr = st.data_editor(
            df_kr_display,
            column_config={
                "선택": st.column_config.CheckboxColumn("삭제", width="small"),
                "관심등록일": st.column_config.DateColumn("등록일", format="YYYY-MM-DD", step=1, width="small"),
                "코드": st.column_config.TextColumn("코드", disabled=True, width="small"),
                "종목명": st.column_config.TextColumn("종목명", disabled=True, width="medium"),
                
                # 매수가, 현재가: TextColumn이지만 width를 조절하여 정돈됨
                "매수가": st.column_config.TextColumn("매수가", width="medium"), 
                "전략": st.column_config.TextColumn("전략", disabled=True, width="medium"),
                "현재가": st.column_config.TextColumn("현재가", disabled=True, width="medium"),
                
                "수익률(%)": st.column_config.NumberColumn("수익률", format="%.2f%%", disabled=True, width="small"),
                
                # [신규] 등록기간 & 일간수익률
                "등록기간(일)": st.column_config.NumberColumn("기간(일)", format="%d일", disabled=True, width="small"),
                "일간수익률(%)": st.column_config.NumberColumn("일간수익률", format="%.2f%%", disabled=True, width="small"),
            },
            hide_index=True,
            use_container_width=True,
            key="fav_editor_kr"
        )
        
        if st.button("삭제", key="save_kr", type="primary"):  # type="primary"가 붉은색 효과를 줍니다
            if process_db_updates(user, edited_kr, df_kr):
                st.rerun()

    if not df_kr.empty and not df_us.empty:
        st.divider()

    # -------------------------------------------------------------
    # [해외 주식]
    # -------------------------------------------------------------
    if not df_us.empty:
        df_us["현재가"] = df_us["현재가_숫자"].apply(lambda x: format_price(x, False))
        df_us["매수가"] = df_us["매수가"].apply(lambda x: format_price(x, False))

        df_us_display = df_us[[
            "관심등록일", "코드", "종목명", "매수가", "전략", "현재가", 
            "수익률(%)", "등록기간(일)", "일간수익률(%)"
        ]].copy()
        df_us_display.insert(0, "선택", False)

        st.markdown("#### 🇺🇸 해외 주식")
        edited_us = st.data_editor(
            df_us_display,
            column_config={
                "선택": st.column_config.CheckboxColumn("삭제", width="small"),
                "관심등록일": st.column_config.DateColumn("등록일", format="YYYY-MM-DD", step=1, width="small"),
                "코드": st.column_config.TextColumn("코드", disabled=True, width="small"),
                "종목명": st.column_config.TextColumn("종목명", disabled=True, width="medium"),
                
                "매수가": st.column_config.TextColumn("매수가", width="medium"),
                "전략": st.column_config.TextColumn("전략", disabled=True, width="medium"),
                "현재가": st.column_config.TextColumn("현재가", disabled=True, width="medium"),
                
                "수익률(%)": st.column_config.NumberColumn("수익률", format="%.2f%%", disabled=True, width="small"),
                
                # [신규]
                "등록기간(일)": st.column_config.NumberColumn("기간(일)", format="%d일", disabled=True, width="small"),
                "일간수익률(%)": st.column_config.NumberColumn("일간수익률", format="%.2f%%", disabled=True, width="small"),
            },
            hide_index=True,
            use_container_width=True,
            key="fav_editor_us"
        )

        if st.button("삭제", key="save_us", type="primary"):
            if process_db_updates(user, edited_us, df_us):

                st.rerun()
