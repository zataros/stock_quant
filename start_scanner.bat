@echo off
chcp 65001
echo 🚀 Global Quant Scanner를 시작합니다...
echo.

:: 가상환경이 있다면 활성화 (venv 폴더가 있을 경우)
if exist venv\Scripts\activate (
    call venv\Scripts\activate
)

:: 필요한 패키지 확인 및 설치
echo 📦 라이브러리 확인 중...
pip install -r requirements.txt > nul 2>&1

:: Streamlit 실행
echo 🖥️ 브라우저를 엽니다...
streamlit run app.py

pause