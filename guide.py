import streamlit as st
import plotly.graph_objects as go
import numpy as np

def generate_concept_chart(strategy_type):
    x = np.linspace(0, 100, 100)
    fig = go.Figure()
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10), template="plotly_dark", showlegend=False)
    
    if strategy_type == "elite":
        y = x + np.random.normal(0, 2, 100)
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='green')))
        fig.add_trace(go.Scatter(x=x, y=x-5, line=dict(color='orange')))
    elif strategy_type == "dbb":
        y = x * 0.5 + 50 + np.random.normal(0, 1, 100)
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='red')))
        fig.add_trace(go.Scatter(x=x, y=y+2, line=dict(color='gray', dash='dot')))
    elif strategy_type == "bnf":
        y = np.concatenate([np.linspace(100, 50, 50), np.linspace(50, 80, 50)])
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='cyan')))
        fig.add_trace(go.Scatter(x=x, y=np.linspace(100, 75, 100), line=dict(color='white')))
    elif strategy_type == "turtle":
        y = x + np.random.normal(0, 3, 100) + 30
        y_high = np.concatenate([np.full(30, 60), np.full(40, 80), np.full(30, 120)])
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='#00b894', width=2), name='Price'))
        fig.add_trace(go.Scatter(x=x, y=y_high, line=dict(color='#ff4b4b', width=2), name='신고가선'))
        fig.add_annotation(x=35, y=85, text="돌파(매수)", showarrow=True, arrowhead=1, ax=0, ay=-20, font=dict(color="#ff4b4b"))
    elif strategy_type == "squeeze":
        y = np.concatenate([np.full(50, 50), np.linspace(50, 100, 50)])
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='white')))
    elif strategy_type == "th_algo":
        # TH알고리즘: 주가(White)가 HMA(Cyan) 위에서 상승하는 모습
        y = x**1.1 + np.random.normal(0, 2, 100)
        hma = x**1.1 - 5  # HMA가 주가 바로 아래서 따라감
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='white', width=2), name='Price'))
        fig.add_trace(go.Scatter(x=x, y=hma, line=dict(color='cyan', width=2), name='HMA Trend'))
        fig.add_trace(go.Scatter(x=x, y=y, fill='tonexty', fillcolor='rgba(0, 255, 255, 0.1)', line=dict(width=0), name='Bull Zone'))
    elif strategy_type == "vwap":
        y = x + 30 + np.random.normal(0, 2, 100)
        vwap_line = x + 25 
        fig.add_trace(go.Scatter(x=x, y=y, line=dict(color='#00b894', width=2), name='Price'))
        fig.add_trace(go.Scatter(x=x, y=vwap_line, line=dict(color='cyan', width=2), name='VWAP'))
    return fig

def show():
    st.title("📘 승리 공식: 7가지 실전 매매 가이드 (V29.4)")
    st.markdown("---")
    
    st.markdown("""
    > **💡 Tip:** 각 전략은 특정한 **시장 상황(추세/박스권/급락)**에 최적화되어 있습니다. 
    > 단순히 신호가 떴다고 진입하기보다, 차트를 통해 **맥락(Context)**을 확인하세요.
    """)
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("1. ⚡ 엘리트 매매법 (Trend Following)")
        st.plotly_chart(generate_concept_chart("elite"), use_container_width=True)
        st.markdown("""
        - **철학:** "추세는 내 친구다 (Trend is your friend)"
        - **진입 조건:**
            1. **이평선 정배열:** EMA 10 > 20 > 60
            2. **MACD 골든크로스:** MACD 선이 Signal 선을 상향 돌파
        - **설명:** 가장 정석적인 추세 매매법입니다. 정배열 상태에서의 눌림목 후 재상승을 노립니다.
        """)
        st.divider()
        
        st.subheader("3. 💧 BNF 역추세 매매 (Mean Reversion)")
        st.plotly_chart(generate_concept_chart("bnf"), use_container_width=True)
        st.markdown("""
        - **철학:** "공포에 사서 환희에 팔아라" (日 천재 트레이더 BNF의 기법)
        - **진입 조건:**
            1. **이격도 과매도:** 25일 이평선 대비 주가가 **90% 이하**로 급락 (괴리율 10% 이상)
        - **설명:** 단기간 과도한 하락(투매)이 발생했을 때, 기술적 반등(Dead Cat Bounce)을 노리는 역발상 매매입니다.
        """)
        st.divider()
        
        st.subheader("5. ⚓ VWAP (Institutional Support)")
        st.plotly_chart(generate_concept_chart("vwap"), use_container_width=True)
        st.markdown("""
        - **철학:** "세력(기관/외인)의 평단가와 함께하라"
        - **진입 조건:**
            1. 주가가 최근 의미 있는 저점에서 시작된 **VWAP 선을 지지**하고 반등.
            2. **MFI (자금 흐름) 지표**가 침체권에서 상승 반전하면 신뢰도 증가.
        - **설명:** 단순 이평선보다 거래량이 반영된 VWAP 선이 훨씬 강력한 지지/저항 역할을 합니다. (150일 기준 앵커링 적용)
        """)
        st.divider()
        
        st.subheader("7. 🐢 터틀 트레이딩 (Breakout)")
        st.plotly_chart(generate_concept_chart("turtle"), use_container_width=True)
        st.markdown("""
        - **철학:** "가격이 모든 것을 말해준다" (전설적인 터틀 그룹의 전략)
        - **진입 조건:**
            1. **20일 신고가(High 20) 돌파:** 붉은색 상단 라인을 주가가 뚫고 올라갈 때 무조건 매수.
        - **청산:** 10일 신저가(Low 10) 이탈 시 매도.
        - **설명:** 승률은 낮을 수 있으나, 한 번 터지는 대세 상승장에서 엄청난 수익을 거두는 전략입니다. 손절은 짧게, 익절은 길게 가져가는 것이 핵심입니다.
        """)

    with c2:
        st.subheader("2. 🔥 더블 볼린저 밴드 (DBB)")
        st.plotly_chart(generate_concept_chart("dbb"), use_container_width=True)
        st.markdown("""
        - **철학:** "추세는 밴드를 타고 달린다"
        - **진입 조건:**
            1. 캔들이 **Buy Zone (1표준편차 ~ 2표준편차 사이)**에 진입하거나 상단 돌파.
            2. **RSI 60~70 이상:** 일반적인 과매도 해석과 달리, DBB에서는 **강력한 상승 모멘텀의 확증**으로 봅니다.
        - **설명:** 밴드 상단을 타고 올라가는 강력한 급등주를 놓치지 않기 위한 전략입니다.
        """)
        st.divider()
        
        # [수정] TH알고리즘으로 변경
        st.subheader("4. 🧬 TH알고리즘 (Smart Momentum)")
        st.plotly_chart(generate_concept_chart("th_algo"), use_container_width=True)
        st.markdown("""
        - **철학:** "Zero-Lag 기술로 시장의 미세한 맥박을 읽는다"
        - **진입 조건:**
            1. **HMA 추세 상승:** 후행성이 제거된 Hull Moving Average가 상승 반전.
            2. **스마트 필터:** 주가가 HMA 위에 위치하며, 과열권(RSI > 75)이 아닐 때 진입.
        - **설명:** 기존 이평선의 단점(느린 반응)을 극복한 TH알고리즘 지표를 사용합니다. 추세의 초입을 정밀하게 타격하며, ATR 기반의 샹들리에 청산으로 수익을 지킵니다.
        """)
        st.divider()
        
        st.subheader("6. 🤖 AI 스마트 스퀴즈 (Volatility Squeeze)")
        st.plotly_chart(generate_concept_chart("squeeze"), use_container_width=True)
        st.markdown("""
        - **철학:** "에너지는 응축된 후에 폭발한다"
        - **진입 조건:**
            1. **Squeeze:** 볼린저밴드 폭(Bandwidth)이 0.15 이하로 극도로 좁아짐.
            2. **Explosion:** 거래량이 평소 대비 1.5배 이상 터지며 밴드를 상향 돌파.
        - **설명:** 긴 횡보 끝에 에너지가 폭발하는 시점을 포착합니다. 급등 직전의 고요함을 찾아냅니다.
        """)