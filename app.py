import streamlit as st
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

import database as db
import data_loader as dl
import strategies as st_algo
import ui_components as ui

import tabs_scanner
import tabs_favorites
import tabs_lab
import guide as gd

# -----------------------------------------------------------------------------
# 기본 설정 & CSS
# -----------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Global Quant Scanner V29.3")
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    div[data-testid="stDataFrame"] td { text-align: right; }
    div[data-testid="stDataFrame"] td:nth-child(2) { text-align: left !important; }
    .badge { display: inline-block; padding: 3px 10px; margin-right: 5px; border-radius: 12px; font-size: 0.8em; font-weight: bold; color: white; }
    div.stButton > button { min-height: 50px; }
    
    /* V29.3 Fix: 화면 흐려짐 방지 */
    .stApp { transition: none !important; animation: none !important; }
    div[data-testid="stStatusWidget"] { display: none; }
    [data-testid="stAppViewContainer"] {
        opacity: 1 !important; filter: none !important;
        transition: none !important; transform: none !important;
        background-color: transparent !important;
    }
    [data-testid="stForm"] { border: 1px solid #333; padding: 20px; border-radius: 10px; }
    .stSpinner { z-index: 100; }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "username" not in st.session_state: st.session_state["username"] = None
if "role" not in st.session_state: st.session_state["role"] = "user"
if "scan_data" not in st.session_state: st.session_state["scan_data"] = None
if "fav_data" not in st.session_state: st.session_state["fav_data"] = None
if "last_update_time" not in st.session_state: st.session_state["last_update_time"] = time.time()
if "usd_rate" not in st.session_state: st.session_state["usd_rate"] = 1400.0

def login_page():
    st.title("🔐 Quant Scanner 접속")
    
    # 탭 3개: 로그인 / 회원가입 / 비밀번호 찾기(초기화)
    tab1, tab2, tab3 = st.tabs(["로그인", "회원가입", "비밀번호 초기화"])

    # [탭 1] 로그인
    with tab1:
        st.subheader("로그인")
        login_id = st.text_input("아이디", key="login_id")
        login_pw = st.text_input("비밀번호", type="password", key="login_pw")
        
        if st.button("로그인", type="primary", key="btn_login"):
            if db.check_login(login_id, login_pw):
                st.session_state["logged_in"] = True
                st.session_state["username"] = login_id
                st.session_state["role"] = db.get_user_role(login_id)  # 권한 가져오기
                st.session_state["usd_rate"] = st_algo.get_exchange_rate()
                
                welcome_msg = f"{login_id}님 환영합니다!"
                if st.session_state["role"] == 'admin':
                    welcome_msg += " (관리자 모드)"
                st.success(welcome_msg)
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")

    # [탭 2] 회원가입
    with tab2:
        st.subheader("새 계정 만들기")
        with st.form("signup_form"):
            new_id = st.text_input("아이디")
            new_email = st.text_input("이메일 (비밀번호 찾기용)")
            new_pw = st.text_input("비밀번호", type="password")
            new_pw_chk = st.text_input("비밀번호 확인", type="password")
            submit = st.form_submit_button("계정 생성")
            
            if submit:
                if not new_id or not new_pw or not new_email:
                    st.warning("모든 항목을 입력해주세요.")
                elif new_pw != new_pw_chk:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    if db.sign_up(new_id, new_pw, new_email):
                        st.success(f"가입 완료! '{new_id}' 계정이 생성되었습니다.")
                    else:
                        st.error("이미 존재하는 아이디입니다.")

    # [탭 3] 비밀번호 초기화
    with tab3:
        st.subheader("비밀번호 재설정")
        st.caption("가입 시 입력한 아이디와 이메일이 일치하면 비밀번호를 변경할 수 있습니다.")
        
        # 1단계: 본인 확인
        find_id = st.text_input("아이디", key="find_id")
        find_email = st.text_input("이메일", key="find_email")
        
        if db.verify_user_email(find_id, find_email):
            st.success("정보가 확인되었습니다. 새로운 비밀번호를 설정하세요.")
            # 2단계: 새 비번 입력
            with st.form("reset_pw_form"):
                reset_pw = st.text_input("새로운 비밀번호", type="password")
                reset_pw_chk = st.text_input("새로운 비밀번호 확인", type="password")
                btn_reset = st.form_submit_button("비밀번호 변경")
                
                if btn_reset:
                    if reset_pw == reset_pw_chk:
                        db.update_password(find_id, reset_pw)
                        st.success("비밀번호가 변경되었습니다. 로그인 탭에서 로그인해주세요.")
                    else:
                        st.error("비밀번호가 서로 다릅니다.")
        else:
            if find_id and find_email:
                st.warning("일치하는 계정 정보가 없습니다.")

def main_app():
    user = st.session_state["username"]
    role = st.session_state.get("role", "user")
    
    with st.sidebar:
        st.write(f"👋 **{user}**님")
        if role == 'admin':
            st.badge("👑 관리자")
        else:
            st.caption("일반 사용자")
            
        st.caption(f"💵 USD/KRW: {st.session_state['usd_rate']:.1f}원")
        
        if st.button("로그아웃"):
            st.session_state["logged_in"] = False
            st.session_state["username"] = None
            st.session_state["role"] = None
            st.rerun()
            
        # [삭제됨] 기존 관심종목 리스트 및 추가 기능 제거
        # 이제 tabs_favorites.py 내부에서 처리합니다.
        
        st.divider()
        st.info("📌 팁: 관심종목 관리는 '관심종목' 탭에서 할 수 있습니다.")

    st.title("📈 Global Quant Scanner V29.4") # 버전업
    st.caption("System: Favorites Portfolio Management Added")

    # 탭 구성: 관리자일 경우 '관리자' 탭 추가
    tabs_list = ["📊 전략 스캐너", "💖 관심종목", "🔬 전략 연구소", "📘 가이드"]
    if role == 'admin':
        tabs_list.append("👑 관리자")
        
    tabs = st.tabs(tabs_list)

    with tabs[0]:
        tabs_scanner.run()

    with tabs[1]:
        tabs_favorites.run()

    with tabs[2]:
        tabs_lab.run()

    with tabs[3]:
        gd.show()
        
    # 관리자 탭 (role == 'admin'일 때만 생성됨)
    if role == 'admin':
        with tabs[4]:
            st.header("👑 회원 관리")
            st.warning("주의: 회원을 삭제하면 해당 회원의 데이터가 영구적으로 삭제됩니다.")
            
            # 모든 유저 가져오기
            all_users = db.get_all_users()
            df_users = pd.DataFrame(all_users, columns=["아이디", "이메일", "권한"])
            st.dataframe(df_users, use_container_width=True)
            
            st.divider()
            
            # 회원 삭제 기능
            c1, c2 = st.columns([3, 1])
            with c1:
                target_user = st.selectbox("관리할 회원 선택", [u[0] for u in all_users])
            with c2:
                # 본인 삭제 방지
                if target_user == user:
                    st.button("본인 삭제 불가", disabled=True)
                else:
                    if st.button(f"'{target_user}' 계정 삭제", type="primary"):
                        db.delete_user(target_user)
                        st.success(f"{target_user} 계정이 삭제되었습니다.")
                        time.sleep(1)
                        st.rerun()

if __name__ == "__main__":
    if st.session_state["logged_in"]:
        main_app()
    else:
        login_page()