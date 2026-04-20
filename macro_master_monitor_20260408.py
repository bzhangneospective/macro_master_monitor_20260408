import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import datetime
import akshare as ak
from fredapi import Fred

# ==========================================
# 1. Page Configuration & Professional CSS
# ==========================================
st.set_page_config(
    page_title="Macro Terminal V2.11", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; max-width: 100% !important; }
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] { height: 40px; font-size: 16px; font-weight: 600; }
        /* 强制 Radio 选项不换行并紧凑 */
        div[data-testid="stRadio"] label { white-space: nowrap; font-size: 12px !important; padding: 2px 0px; }
        div[data-testid="stColumn"] { display: flex; flex-direction: column; justify-content: center; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Institutional Data Engine
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)
def fetch_global_data():
    FRED_API_KEY = '2855fd24c8cbc761cd583d64f97e7004' 
    yf_tickers = [
        '^GSPC', '^NDX', '^SOX', '^N225', '^KS11', '^HSI', '000001.SS', '^TWII',
        'GC=F', 'SI=F', 'HG=F', 'CL=F', 'NG=F', 'BZ=F', 'ZC=F', 'ZS=F', 'ZW=F', 'CT=F', 'BTC-USD',
        'CNH=X', 'AUDUSD=X', 'JPY=X', 'IDR=X', 'INR=X', 'TRY=X', 'EURUSD=X', 'GBPUSD=X', 'CAD=X', 'MXN=X', 'BRL=X', 'ARS=X', 'ILS=X', 'HKD=X', 'TLT'
    ]
    yf_data = {}
    try:
        yf_raw = yf.download(yf_tickers, period="max", progress=False)
        for t in yf_tickers:
            try:
                df = pd.DataFrame({'Open': yf_raw['Open'][t], 'High': yf_raw['High'][t], 'Low': yf_raw['Low'][t], 'Close': yf_raw['Close'][t]}).dropna()
                yf_data[t] = df
            except: pass
    except: pass

    fred_tickers = ['SOFR', 'EFFR', 'DGS2', 'DGS10', 'DGS30', 'BAMLC0A1CAAA', 'BAMLC0A4CBBB', 'BAMLH0A0HYM2', 'BAMLEMHBHYCRPIUSOAS']
    fred_data = {}
    try:
        fred = Fred(api_key=FRED_API_KEY)
        for t in fred_tickers:
            try:
                series = fred.get_series(t)
                fred_data[t] = pd.DataFrame({'Close': series}).ffill().bfill()
            except: pass
    except: pass

    ak_symbols = {'SHFE_Silver': 'ag0', 'SHFE_Gold': 'au0', 'DCE_IronOre': 'i0'}
    cn_data = {}
    for name, symbol in ak_symbols.items():
        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            df['date'] = pd.to_datetime(df['date']); df.set_index('date', inplace=True)
            cn_data[name] = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}).apply(pd.to_numeric).dropna()
        except: pass
    return {"yf": yf_data, "fred": fred_data, "mock": cn_data}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_gics_heatmap_raw():
    hierarchy = [
        ('Technology', 'Software (IGV)', 'IGV', 12.0), ('Technology', 'Semiconductors (SOXX)', 'SOXX', 11.0), ('Technology', 'Hardware (IYW)', 'IYW', 6.0),
        ('Financials', 'Banks (KBE)', 'KBE', 4.0), ('Financials', 'Regional Banks (KRE)', 'KRE', 2.0), ('Financials', 'Insurance (KIE)', 'KIE', 7.0),
        ('Health Care', 'Biotech (IBB)', 'IBB', 4.0), ('Health Care', 'Devices (IHI)', 'IHI', 4.0), ('Health Care', 'Pharma (PPH)', 'PPH', 5.0),
        ('Cons Disc', 'Retail (XRT)', 'XRT', 6.0), ('Cons Disc', 'Home (ITB)', 'ITB', 2.0), ('Cons Disc', 'Broad (XLY)', 'XLY', 3.0),
        ('Comm Svcs', 'Internet (FDN)', 'FDN', 6.0), ('Comm Svcs', 'Telecom (IYZ)', 'IYZ', 3.0),
        ('Industrials', 'Aero (ITA)', 'ITA', 3.0), ('Industrials', 'Transport (IYT)', 'IYT', 3.0), ('Industrials', 'Broad (XLI)', 'XLI', 3.0),
        ('Cons Staples', 'Food (PBJ)', 'PBJ', 3.0), ('Cons Staples', 'Broad (XLP)', 'XLP', 3.0),
        ('Energy', 'E&P (XOP)', 'XOP', 2.0), ('Energy', 'Services (OIH)', 'OIH', 2.0),
        ('Materials', 'Mining (XME)', 'XME', 1.0), ('Materials', 'Broad (XLB)', 'XLB', 1.5),
        ('Real Estate', 'REITs (VNQ)', 'VNQ', 2.5), ('Utilities', 'Utilities (XLU)', 'XLU', 2.5)
    ]
    tickers = [item[2] for item in hierarchy]
    try:
        raw_df = yf.download(tickers, period="1y", progress=False)['Close']
        return raw_df, hierarchy
    except: return pd.DataFrame(), hierarchy

def calculate_heatmap_performance(raw_df, hierarchy, lookback):
    if raw_df.empty: return pd.DataFrame()
    rows = []; cur_yr = datetime.date.today().year
    for sec, sub, t, w in hierarchy:
        if t in raw_df.columns:
            s = raw_df[t].dropna()
            if len(s) < 2: continue
            p_now = s.iloc[-1]
            if lookback == "1D": p_old = s.iloc[-2]
            elif lookback == "5D": p_old = s.iloc[-min(len(s), 6)]
            elif lookback == "1M": p_old = s.iloc[-min(len(s), 22)]
            else:
                ytd = s[s.index.year == cur_yr]
                p_old = ytd.iloc[0] if not ytd.empty else s.iloc[0]
            perf = ((p_now - p_old) / p_old) * 100
            rows.append({'Sector': sec, 'Sub': sub, 'Perf': perf, 'Weight': w})
    return pd.DataFrame(rows)

# ==========================================
# 3. Charting Factory
# ==========================================
def draw_bloomberg_chart(df, title, color, res):
    if df is None or df.empty: return go.Figure()
    # Resampling Logic
    rule = {'Weekly': 'W', 'Monthly': 'ME'}.get(res, None)
    if rule:
        df = df.resample(rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    
    # EMA & Momentum
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
    mom = ((df['Close'].ewm(span=9).mean() - df['Close'].ewm(span=26).mean()) / df['Close'].ewm(span=26).mean() * 100).iloc[-1]
    
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#00CC96', decreasing_line_color='#FF4B4B'))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#FFD700', width=1.2), name='EMA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA60'], line=dict(color='#FF4B4B', width=1.2), name='EMA60'))
    
    # Viewport Lock
    if res != "MAX" and len(df) > 180:
        ldf = df.iloc[-180:]
        fig.update_layout(xaxis_range=[ldf.index[0], ldf.index[-1]], yaxis_range=[ldf['Low'].min()*0.98, ldf['High'].max()*1.02])
    
    fig.update_layout(height=490, margin=dict(l=10, r=10, t=50, b=10), template="plotly_dark", 
                      title=f"{title} <span style='color:{'#00CC96' if mom>=0 else '#FF4B4B'}'>PPO: {mom:.2f}%</span>",
                      yaxis=dict(side="right"), xaxis=dict(rangeslider=dict(visible=False)))
    return fig

# ==========================================
# 4. Main UI Execution
# ==========================================
with st.sidebar:
    st.title("Macro Terminal V2.11")
    cat = st.selectbox("📂 Category", ["📈 Equity Markets", "📊 Spreads", "⚒️ Commodity"])
    assets = {"📈 Equity Markets": ["S&P 500 (^GSPC)", "Nasdaq 100 (^NDX)", "Semiconductor (^SOX)"], "📊 Spreads": ["High-Yield OAS", "10Y-2Y Spread"], "⚒️ Commodity": ["Gold (GC=F)", "WTI Crude (CL=F)"]}
    sel_asset = st.radio("🎯 Asset", assets[cat])
    sel_res = st.radio("Res", ["Daily", "Weekly", "Monthly", "MAX"], horizontal=True)
    db = fetch_global_data()

if db:
    mapping = {"S&P 500 (^GSPC)": (db['yf'].get('^GSPC'), "#00CC96"), "Nasdaq 100 (^NDX)": (db['yf'].get('^NDX'), "#1E90FF"), "Semiconductor (^SOX)": (db['yf'].get('^SOX'), "#AB63FA")}
    target, color = mapping.get(sel_asset, (None, "#FFF"))
    
    if cat == "📈 Equity Markets":
        tab1, tab2 = st.tabs(["🎯 Asset Analysis", "📊 Sector X-Ray (GICS)"])
        with tab1:
            st.plotly_chart(draw_bloomberg_chart(target, sel_asset, color, sel_res), use_container_width=True)
        with tab2:
            # --- V2.11 终极侧边栏布局 ---
            c_tree, c_perf, c_period = st.columns([15, 0.8, 1.2])
            
            raw_h, hier = fetch_gics_heatmap_raw()
            
            with c_period:
                st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True) # 对齐顶端
                st.markdown("<p style='color:gray; font-size:12px; margin-bottom:5px;'>Period</p>", unsafe_allow_html=True)
                lookback = st.radio("L", ["1D", "5D", "1M", "YTD"], index=3, label_visibility="collapsed")

            df_t = calculate_heatmap_performance(raw_h, hier, lookback)
            
            with c_tree:
                if not df_t.empty:
                    fig_t = px.treemap(df_t, path=[px.Constant("S&P 500"), 'Sector', 'Sub'], values='Weight', color='Perf',
                                       color_continuous_scale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']], color_continuous_midpoint=0)
                    fig_t.update_layout(height=490, margin=dict(l=0, r=0, t=0, b=0), template="plotly_dark", coloraxis_showscale=False)
                    fig_t.update_traces(customdata=df_t[['Perf']], texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%", root_color="#000")
                    st.plotly_chart(fig_t, use_container_width=True, config={'displayModeBar': False})
            
            with c_perf:
                # 独立渲染纵向撑满的 Colorbar
                if not df_t.empty:
                    # 动态获取当前范围的极值
                    p_min, p_max = df_t['Perf'].min(), df_t['Perf'].max()
                    fig_p = go.Figure(go.Scatter(x=[None], y=[None], mode='markers',
                        marker=dict(colorscale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']],
                                    cmin=p_min, cmax=p_max, showscale=True,
                                    colorbar=dict(title=dict(text=f"{lookback}%", font=dict(size=12)),
                                                  thickness=15, len=1.0, x=0, y=0.5, yanchor="middle"))))
                    fig_p.update_layout(height=490, width=60, margin=dict(l=0, r=0, t=40, b=0), # t=40 给标题留空
                                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                        xaxis=dict(visible=False), yaxis=dict(visible=False))
                    st.plotly_chart(fig_p, use_container_width=False, config={'displayModeBar': False})
