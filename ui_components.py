import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from plotly.subplots import make_subplots

def render_consensus_html(consensus):
    """HTML 카드 UI"""
    style = """<style>.cons-container {display:flex;flex-wrap:wrap;gap:8px;justify-content:center;background-color:#1e1e1e;padding:15px;border-radius:10px;border:1px solid #333;margin-bottom:20px;}.cons-card {background-color:#2b2b2b;border-radius:8px;width:13%;min-width:90px;text-align:center;padding:10px 5px;box-shadow:0 2px 4px rgba(0,0,0,0.3);transition:transform 0.2s;}.cons-card:hover {transform:translateY(-3px);border:1px solid #555;}.cons-emoji {font-size:24px;margin-bottom:5px;}.cons-title {font-size:11px;color:#aaa;margin-bottom:5px;font-weight:bold;white-space:nowrap;}.cons-val {font-size:13px;font-weight:bold;color:#fff;}.val-buy {color:#39ff14;text-shadow:0 0 8px rgba(57,255,20,0.5);}.val-hold {color:#ffeb3b;}.val-sell {color:#ff4b4b;}.val-wait {color:#777;}@media (max-width: 768px) {.cons-card {width:30%;margin-bottom:5px;}}</style>"""
    emoji_map = { "🐢 터틀": "🐢", "⚡ 엘리트": "⚡", "🔥 DBB": "🔥", "💧 BNF": "🍱", "🤖 AI스퀴즈": "🤖", "🛡️ 버핏": "👴", "⚓ VWAP": "⚓" }
    order = ["🐢 터틀", "⚡ 엘리트", "🔥 DBB", "💧 BNF", "🤖 AI스퀴즈", "🛡️ 버핏", "⚓ VWAP"]
    cards = []
    for key in order:
        val = consensus.get(key, "WAIT")
        cls = "val-wait"
        if "BUY" in val: cls = "val-buy"
        elif "HOLD" in val: cls = "val-hold"
        elif "SELL" in val: cls = "val-sell"
        name_clean = key.split(' ')[1] if ' ' in key else key
        icon = emoji_map.get(key, '📊')
        cards.append(f"""<div class="cons-card"><div class="cons-emoji">{icon}</div><div class="cons-title">{name_clean}</div><div class="cons-val {cls}">{val}</div></div>""")
    return f"{style}<div class='cons-container'>{''.join(cards)}</div>"

def draw_detailed_chart(item):
    """스캐너 탭용 차트"""
    dates = item['chart_dates']; last_price = item['chart_close'][-1]; last_vol = item['chart_vol'][-1]; last_macd = item['macd'][-1]; last_stoch = item['stoch_k'][-1]; last_rsi = item['rsi_line'][-1]
    style_g = "font-size:20px; font-weight:bold; color:#00ff00;"
    titles = (f"{item['종목명']} <span style='{style_g}'>Price: {int(last_price):,}</span>", f"Volume <span style='{style_g}'>{int(last_vol):,}</span>", f"MACD <span style='{style_g}'>{last_macd:.2f}</span>", f"Stoch <span style='{style_g}'>{last_stoch:.1f}</span>", f"RSI <span style='{style_g}'>{last_rsi:.1f}</span>")
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.4, 0.1, 0.15, 0.15, 0.15], subplot_titles=titles)
    fig.add_trace(go.Candlestick(x=dates, open=item['chart_open'], high=item['chart_high'], low=item['chart_low'], close=item['chart_close'], name='Price', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=item['chart_ma'], line=dict(color='orange', width=1.5), name='MA 20'), row=1, col=1)
    strats = item['전략_리스트']
    if any(x in strats for x in ["🔥DBB", "🤖AI스퀴즈"]):
        fig.add_trace(go.Scatter(x=dates, y=item['chart_up'], line=dict(color='gray', width=1, dash='dot'), name='Upper'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=item['chart_down'], line=dict(color='gray', width=1, dash='dot'), name='Lower'), row=1, col=1)
    if any(x is not None for x in item.get('vwap_val', [])) and "⚓VWAP" in strats:
        fig.add_trace(go.Scatter(x=dates, y=item['vwap_val'], line=dict(color='cyan', width=2), name='VWAP'), row=1, col=1)
    colors = ['#ef5350' if c >= o else '#26a69a' for o, c in zip(item['chart_open'], item['chart_close'])]
    fig.add_trace(go.Bar(x=dates, y=item['chart_vol'], marker_color=colors, name='Volume'), row=2, col=1)
    fig.add_trace(go.Bar(x=dates, y=item['macd_hist'], marker_color='gray', name='MACD Hist'), row=3, col=1)
    fig.add_trace(go.Scatter(x=dates, y=item['macd'], line=dict(color='white', width=1), name='MACD'), row=3, col=1)
    fig.add_trace(go.Scatter(x=dates, y=item['macd_sig'], line=dict(color='yellow', width=1), name='Signal'), row=3, col=1)
    fig.add_trace(go.Scatter(x=dates, y=item['stoch_k'], line=dict(color='skyblue', width=1), name='Slow %K'), row=4, col=1)
    fig.add_trace(go.Scatter(x=dates, y=item['stoch_d'], line=dict(color='orange', width=1), name='Slow %D'), row=4, col=1)
    fig.add_trace(go.Scatter(x=dates, y=item['rsi_line'], line=dict(color='#a29bfe', width=1.5), name='RSI'), row=5, col=1)
    fig.update_layout(height=1000, template="plotly_dark", showlegend=False, xaxis_rangeslider_visible=False, legend=dict(x=0.01, y=0.99, bgcolor='#000000', bordercolor='#444', borderwidth=1))
    for i in range(1, 6): fig.update_yaxes(side="right", showticklabels=True, row=i, col=1)
    return fig

def draw_strategy_chart(df, code, strategy_name):
    dates = pd.to_datetime(df.index); last_price = df['Close'].iloc[-1]; end_date = dates[-1]; start_date = end_date - pd.DateOffset(months=4)
    style_g = "font-size:20px; font-weight:bold; color:#00ff00;"; style_p = "font-size:20px; font-weight:bold; color:#ff00ff;"
    
    if "터틀" in strategy_name:
        last_atr = df['ATR'].iloc[-1]
        titles = (f"{strategy_name} ({code}) <span style='{style_g}'>Price: {int(last_price):,}</span>", f"Volatility (ATR 20) <span style='{style_g}'>{int(last_atr):,}</span>")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25], subplot_titles=titles)
        fig.add_trace(go.Candlestick(x=dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['High20'], line=dict(color='#ff4b4b', width=2), name='High 20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['Low10'], line=dict(color='#00b894', width=2), name='Low 10'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['MA200'], line=dict(color='white', width=1.5), name='SMA 200'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['ATR'], line=dict(color='#fab1a0', width=2), name='ATR (N)'), row=2, col=1)
        fig.update_xaxes(range=[start_date, end_date + pd.DateOffset(days=5)], row=2, col=1)
    elif "엘리트" in strategy_name:
        last_vol = df['Volume'].iloc[-1]; last_macd = df['MACD'].iloc[-1]
        titles = (f"{strategy_name} ({code}) <span style='{style_g}'>Price: {int(last_price):,}</span>", f"Volume <span style='{style_g}'>{int(last_vol):,}</span>", f"MACD <span style='{style_p}'>{last_macd:.2f}</span>")
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.6, 0.15, 0.25], subplot_titles=titles)
        fig.add_trace(go.Candlestick(x=dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['EMA10'], line=dict(color='yellow', width=1.5), name='EMA 10'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['EMA20'], line=dict(color='orange', width=1.5), name='EMA 20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['EMA60'], line=dict(color='green', width=2), name='EMA 60'), row=1, col=1)
        colors = ['#ef5350' if c >= o else '#26a69a' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=dates, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
        fig.add_trace(go.Bar(x=dates, y=df['MACD_Hist'], marker_color='gray', name='MACD Hist'), row=3, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['MACD'], line=dict(color='white', width=1), name='MACD'), row=3, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['Signal'], line=dict(color='yellow', width=1), name='Signal'), row=3, col=1)
        fig.update_xaxes(range=[start_date, end_date + pd.DateOffset(days=5)], row=3, col=1)
    elif "DBB" in strategy_name:
        last_vol = df['Volume'].iloc[-1]; last_rsi = df['RSI'].iloc[-1]
        titles = (f"{strategy_name} ({code}) <span style='{style_g}'>Price: {int(last_price):,}</span>", f"Volume <span style='{style_g}'>{int(last_vol):,}</span>", f"RSI <span style='{style_g}'>{last_rsi:.1f}</span>")
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.6, 0.15, 0.25], subplot_titles=titles)
        fig.add_trace(go.Candlestick(x=dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['MA20'], line=dict(color='orange', width=1.5, dash='dash'), name='SMA 20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['BB_Up2'], line=dict(color='gray', width=1), name='Upper 2SD'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['BB_Dn2'], line=dict(color='gray', width=1), name='Lower 2SD'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['BB_Up2'], line=dict(color='rgba(0,0,0,0)'), fill='tonexty', fillcolor='rgba(255, 0, 0, 0.15)', name='Buy Zone'), row=1, col=1)
        colors = ['#ef5350' if c >= o else '#26a69a' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=dates, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['RSI'], line=dict(color='#a29bfe', width=1.5), name='RSI'), row=3, col=1)
        fig.update_xaxes(range=[start_date, end_date + pd.DateOffset(days=5)], row=3, col=1)
    elif "BNF" in strategy_name:
        last_vol = df['Volume'].iloc[-1]; last_disp = df['Disparity25'].iloc[-1]
        titles = (f"{strategy_name} ({code}) <span style='{style_g}'>Price: {int(last_price):,}</span>", f"Volume <span style='{style_g}'>{int(last_vol):,}</span>", f"Disparity(25) <span style='{style_p}'>{last_disp:.1f}%</span>")
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.6, 0.15, 0.25], subplot_titles=titles)
        fig.add_trace(go.Candlestick(x=dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['MA25'], line=dict(color='cyan', width=1.5), name='SMA 25'), row=1, col=1)
        colors = ['#ef5350' if c >= o else '#26a69a' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=dates, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['Disparity25'], line=dict(color='#a29bfe', width=1.5), name='이격도'), row=3, col=1)
        fig.add_hline(y=90, line_dash="dot", row=3, col=1, line_color="red")
        fig.update_xaxes(range=[start_date, end_date + pd.DateOffset(days=5)], row=3, col=1)
    elif "스퀴즈" in strategy_name:
        last_vol = df['Volume'].iloc[-1]; last_bw = df['Bandwidth'].iloc[-1]
        titles = (f"{strategy_name} ({code}) <span style='{style_g}'>Price: {int(last_price):,}</span>", f"Volume <span style='{style_g}'>{int(last_vol):,}</span>", f"Bandwidth <span style='{style_p}'>{last_bw:.3f}</span>")
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.6, 0.15, 0.25], subplot_titles=titles)
        fig.add_trace(go.Candlestick(x=dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['BB_Up2'], line=dict(color='gray', width=1, dash='dot'), name='Upper'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['BB_Dn2'], line=dict(color='gray', width=1, dash='dot'), name='Lower'), row=1, col=1)
        colors = ['#ef5350' if c >= o else '#26a69a' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=dates, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['Bandwidth'], line=dict(color='white', width=1.5), name='Bandwidth'), row=3, col=1)
        fig.update_xaxes(range=[start_date, end_date + pd.DateOffset(days=5)], row=3, col=1)
    elif "버핏" in strategy_name:
        last_rsi = df['RSI'].iloc[-1]
        titles = (f"{strategy_name} ({code}) <span style='{style_g}'>Price: {int(last_price):,}</span>", f"RSI <span style='{style_g}'>{last_rsi:.1f}</span>")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.75, 0.25], subplot_titles=titles)
        fig.add_trace(go.Candlestick(x=dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['MA200'], line=dict(color='gold', width=2.5), name='SMA 200'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['RSI'], line=dict(color='#a29bfe', width=1.5), name='RSI'), row=2, col=1)
        fig.update_xaxes(range=[start_date, end_date + pd.DateOffset(days=5)], row=2, col=1)
    elif "VWAP" in strategy_name:
        last_vol = df['Volume'].iloc[-1]; last_mfi = df['MFI'].iloc[-1]
        titles = (f"{strategy_name} ({code}) <span style='{style_g}'>Price: {int(last_price):,}</span>", f"Volume <span style='{style_g}'>{int(last_vol):,}</span>", f"MFI <span style='{style_p}'>{last_mfi:.1f}</span>")
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.6, 0.15, 0.25], subplot_titles=titles)
        fig.add_trace(go.Candlestick(x=dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
        if 'VWAP' in df.columns and pd.notnull(df['VWAP'].iloc[-1]):
            fig.add_trace(go.Scatter(x=dates, y=df['VWAP'], line=dict(color='cyan', width=2), name='Anchored VWAP'), row=1, col=1)
        colors = ['#ef5350' if c >= o else '#26a69a' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=dates, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
        fig.add_trace(go.Scatter(x=dates, y=df['MFI'], line=dict(color='#fab1a0', width=1.5), name='MFI'), row=3, col=1)
        fig.update_xaxes(range=[start_date, end_date + pd.DateOffset(days=5)], row=3, col=1)

    buys = df[df['Chart_Signal'] == 1]
    if not buys.empty:
        fig.add_trace(go.Scatter(x=buys.index.strftime('%Y-%m-%d'), y=buys['Low']*0.98, mode='markers', marker=dict(symbol='triangle-up', size=12, color='#39ff14'), name='BUY'), row=1, col=1)
    
    fig.update_layout(height=800 if strategy_name in ["터틀", "엘리트", "DBB", "BNF", "스퀴즈", "버핏", "VWAP"] else 1000, 
                      template="plotly_dark", showlegend=True, xaxis_rangeslider_visible=False,
                      legend=dict(x=0.01, y=0.99, bgcolor='#000000', bordercolor='#444', borderwidth=1, font=dict(size=10, color="white")))
    rows_cnt = 2 if strategy_name in ["터틀", "버핏"] else (3 if strategy_name in ["엘리트", "DBB", "BNF", "스퀴즈", "VWAP"] else 5)
    for i in range(1, rows_cnt + 1): fig.update_yaxes(side="right", showticklabels=True, row=i, col=1)
    return fig