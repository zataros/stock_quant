import streamlit as st
import plotly.graph_objects as go
import numpy as np

def generate_concept_chart(strategy_type):
    x = np.linspace(0, 100, 100)
    fig = go.Figure()
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10), template="plotly_dark", showlegend=False)
    
    if strategy_type == "hyper":
        y = np.concatenate([np.full(50, 50) + np.random.normal(0, 1, 50), np.linspace(50, 100, 50) + np.random.normal(0, 2, 50)])
        ma20 = np.concatenate([np.full(50, 50), np.linspace(50, 90, 50)])
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='red', width=2), name='Price'))
        fig.add_trace(go.Scatter(x=x, y=ma20, line=dict(color='orange', width=2), name='MA20'))
        fig.add_annotation(x=50, y=55, text="Breakout!", showarrow=True, arrowhead=1, ax=0, ay=-30, font=dict(color="#00ff00"))
        
    elif strategy_type == "bnf":
        y = np.concatenate([np.linspace(100, 50, 50), np.linspace(50, 80, 50)])
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='cyan')))
        fig.add_trace(go.Scatter(x=x, y=np.linspace(100, 75, 100), line=dict(color='white')))
        
    elif strategy_type == "turtle":
        y = x + np.random.normal(0, 3, 100) + 30
        y_high = np.concatenate([np.full(30, 60), np.full(40, 80), np.full(30, 120)])
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='#00b894', width=2), name='Price'))
        fig.add_trace(go.Scatter(x=x, y=y_high, line=dict(color='#ff4b4b', width=2), name='신고가선'))
        
    elif strategy_type == "th_algo":
        y = x**1.1 + np.random.normal(0, 2, 100)
        hma = x**1.1 - 5 
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='white', width=2), name='Price'))
        fig.add_trace(go.Scatter(x=x, y=hma, line=dict(color='cyan', width=2), name='HMA Trend'))
        
    return fig

def show():
    st.title("📘 정예 4대 전략 가이드 (Ultimate V30)")
    st.markdown("---")
    
    st.markdown("""
    > **💡 Tip:** 여러 전략을 통합하여 가장 확률 높은 **4가지 핵심 전략**으로 압축했습니다.
    """)
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("1. 🔫 하이퍼 스나이퍼 (All-in-One)")
        st.plotly_chart(generate_concept_chart("hyper"), use_container_width=True)
        st.markdown("""
        - **철학:** "응축된 에너지가 폭발하는 첫 순간을 노린다"
        - **통합된 전략:** 스퀴즈 + VWAP + 엘리트 + 스나이퍼
        - **진입 조건:**
            1. **응축:** 볼린저 밴드가 좁아진 상태.
            2. **지지:** 주가가 VWAP(세력선) 위에 위치.
            3. **트리거:** 20일 이동평균선을 **강하게 돌파**하거나 지지.
        - **설명:** 기존의 여러 전략 장점을 하나로 합친 **끝판왕 전략**입니다. 급등 직전의 맥점을 포착합니다.
        """)
        st.divider()
        
        st.subheader("3. 🐢 터틀 트레이딩 (Breakout)")
        st.plotly_chart(generate_concept_chart("turtle"), use_container_width=True)
        st.markdown("""
        - **철학:** "가격이 모든 것을 말해준다" (전설의 추세 추종)
        - **진입 조건:**
            1. **20일 신고가(High 20)**를 주가가 뚫고 올라갈 때.
        - **설명:** 승률은 낮아도 한 번 터지면 끝까지 먹는 전략입니다. 강한 상승장에 유리합니다.
        """)

    with c2:
        st.subheader("2. 🧬 TH 알고리즘 (Smart Trend)")
        st.plotly_chart(generate_concept_chart("th_algo"), use_container_width=True)
        st.markdown("""
        - **철학:** "Zero-Lag 기술로 시장의 미세한 맥박을 읽는다"
        - **진입 조건:**
            1. **HMA 추세 상승:** 후행성이 제거된 이평선이 고개를 들 때.
            2. **스마트 필터:** 과열권(RSI > 75)이 아닐 때만 진입.
        - **설명:** 빠른 반응 속도가 장점인 AI 하이브리드 전략입니다. 단기 추세 추종에 적합합니다.
        """)
        st.divider()
        
        st.subheader("4. 💧 BNF 역추세 (Rebound)")
        st.plotly_chart(generate_concept_chart("bnf"), use_container_width=True)
        st.markdown("""
        - **철학:** "공포에 사서 환희에 팔아라"
        - **진입 조건:**
            1. **이격도 과매도:** 25일 이평선 대비 90% 이하로 급락.
        - **설명:** 단기 투매가 나왔을 때 기술적 반등을 노리는 역발상 매매입니다.
        """)