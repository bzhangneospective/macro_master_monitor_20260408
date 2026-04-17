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
    page_title="Macro Terminal V2.3 (Drill-down Mode)", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 0rem !important;
            max-width: 100% !important;
        }
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] {
            height: 40px;
            white-space: pre-wrap;
            font-size: 16px;
            font-weight: 600;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Institutional Data Engine
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)
def fetch_global_data():
    FRED_API_KEY = '2855fd24c8cbc761cd583d64f97e7004' 
    
    # 基础资产 + GICS 一级 + 科技/金融二级
    yf_tickers = [
        '^GSPC', '^NDX', '^SOX', '^N225', '^KS11', '^HSI', '000001.SS', '^TWII',
        'GC=F', 'SI=F', 'HG=F', 'CL=F', 'NG=F', 'BZ=F', 'ZC=F', 'ZS=F', 'ZW=F', 'CT=F', 'BTC-USD',
        'CNH=X', 'AUDUSD=X', 'JPY=X', 'IDR=X', 'INR=X', 'TRY=X', 'EURUSD=X', 'GBPUSD=X', 'CAD=X', 'MXN=X', 'BRL=X', 'ARS=X', 'ILS=X', 'HKD=X', 'TLT',
        # GICS Level 1
        'XLK', 'XLF', 'XLV', 'XLY', 'XLC', 'XLI', 'XLP', 'XLE', 'XLU', 'XLB', 'XLRE',
        # GICS Level 2 (Sub-Sectors)
        'IGV', 'SOXX', 'KRE', 'KBE', 'IAI', 'KIE'
    ]
    
    yf_data = {}
    try:
        yf_raw = yf.download(yf_tickers, period="max", progress=False)
        for t in yf_tickers:
            try:
                df = pd.DataFrame({
                    'Open': yf_raw['Open'][t], 'High': yf_raw['High'][t],
                    'Low': yf_raw['Low'][t], 'Close': yf_raw['Close'][t]
                }).dropna()
                yf_data[t] = df
            except: pass
    except: pass

    fred_tickers = ['SOFR', 'EFFR', 'DGS2', 'DGS10', 'DGS30', 'BAMLH0A0HYM2', 'BAMLEMHBHYCRPIUSOAS']
    fred_data = {}
    try:
        fred = Fred(api_key=FRED_API_KEY)
        for ticker in fred_tickers:
            try:
                series = fred.get_series(ticker)
                fred_data[ticker] = pd.DataFrame({'Close': series}).ffill().bfill()
            except: pass
    except: pass

    # Mock/CN Data Simplified for context
    cn_data = {}
    try:
        bond_df = ak.bond_zh_us_rate()
        bond_df['日期'] = pd.to_datetime(bond_df['日期'])
        bond_df.set_index('日期', inplace=True)
        cn_data['China_10Y_Yield'] = pd.DataFrame({'Close': pd.to_numeric(bond_df['中国国债收益率10年'], errors='coerce')}).dropna()
    except: pass

    return {"yf": yf_data, "fred": fred_data, "mock": cn_data, "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ==========================================
# 3. Analytics & Charting Factory
# ==========================================
def resample_data(df, timeframe):
    if df.empty or timeframe == "Daily": return df
    rule = 'W' if timeframe == "Weekly" else 'ME'
    if all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']):
        return df.resample(rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    return df.resample(rule).last().dropna()

def draw_bloomberg_chart(df_raw, title, base_color, timeframe, show_ma=True):
    if df_raw is None or df_raw.empty: return go.Figure()
    
    df = resample_data(df_raw.copy(), timeframe)
    has_ohlc = all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']) and timeframe != "MAX"
    close_col = 'Close' if 'Close' in df.columns else df.columns[0]
    
    # EMA Calculation
    df['EMA20'] = df[close_col].ewm(span=20, adjust=False).mean()
    df['EMA60'] = df[close_col].ewm(span=60, adjust=False).mean()
    
    # Momentum (PPO)
    ema9 = df[close_col].ewm(span=9, adjust=False).mean()
    ema26 = df[close_col].ewm(span=26, adjust=False).mean()
    mom_val = ((ema9 - ema26) / ema26 * 100).iloc[-1]
    mom_color = "#00CC96" if mom_val >= 0 else "#FF4B4B"

    fig = go.Figure()
    if has_ohlc:
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df[close_col], mode='lines', line=dict(color=base_color, width=2.5)))

    if show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], mode='lines', name='EMA20', line=dict(color='#FFD700', width=1.2)))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA60'], mode='lines', name='EMA60', line=dict(color='#FF4B4B', width=1.2)))

    # Viewport Lock (180 periods)
    x_range, y_range = None, None
    if len(df) > 10 and timeframe != "MAX":
        last_df = df.iloc[-min(len(df), 180):]
        x_range = [last_df.index[0], last_df.index[-1]]
        y_min = last_df['Low'].min() if has_ohlc else last_df[close_col].min()
        y_max = last_df['High'].max() if has_ohlc else last_df[close_col].max()
        y_range = [y_min * 0.98, y_max * 1.02]

    fig.update_layout(
        height=490, margin=dict(l=10, r=10, t=60, b=10), template="plotly_dark",
        xaxis=dict(range=x_range, rangeslider=dict(visible=False)),
        yaxis=dict(range=y_range, side="right", fixedrange=False),
        title=f"{title} <span style='color:{mom_color}'>PPO: {mom_val:.2f}%</span>"
    )
    return fig

# ==========================================
# 4. Bloomberg Dashboard UI
# ==========================================
with st.sidebar:
    st.title("Macro Terminal V2.3")
    page = st.selectbox("📂 Category", ["📊 Spreads & Ratios", "⚒️ Commodity", "💱 FX & FI", "📈 Equity Markets"])
    
    asset_list = []
    if page == "📊 Spreads & Ratios": asset_list = ["High-Yield Spread (OAS)", "Emerging Market (EMBI)"]
    elif page == "⚒️ Commodity": asset_list = ["Gold (GC=F)", "WTI Crude (CL=F)", "Bitcoin (BTC-USD)"]
    elif page == "💱 FX & FI": asset_list = ["USD/CNH", "USD/JPY", "US 10Y Yield", "China 10Y Yield"]
    elif page == "📈 Equity Markets": asset_list = ["S&P 500 (^GSPC)", "Nasdaq 100 (^NDX)", "Semiconductor (^SOX)"]
    
    selected_asset = st.radio("🎯 Select Asset", asset_list)
    selected_timeframe = st.radio("Res", ["Daily", "Weekly", "Monthly", "MAX"], horizontal=True)
    
    db = fetch_global_data()

# ==========================================
# 5. Main Execution
# ==========================================
if db:
    yf_df = db['yf']; fr_df = db['fred']
    
    def get_data(asset_name):
        mapping = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B", False),
            "Gold (GC=F)": (yf_df.get('GC=F'), "#FFD700", True),
            "WTI Crude (CL=F)": (yf_df.get('CL=F'), "#8B4513", True),
            "Bitcoin (BTC-USD)": (yf_df.get('BTC-USD'), "#FF8C00", True),
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B", True),
            "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000", True),
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96", True),
            "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF", True),
            "Semiconductor (^SOX)": (yf_df.get('^SOX'), "#AB63FA", True)
        }
        return mapping.get(asset_name, (None, "#FFFFFF", False))

    target_df, color, use_ma = get_data(selected_asset)
    
    if page == "📈 Equity Markets":
        tab1, tab2 = st.tabs(["🎯 Asset Analysis", "📊 Sector Performance (GICS Drill-down)"])
        with tab1:
            st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, color, selected_timeframe, show_ma=use_ma), use_container_width=True)
        with tab2:
            # --- 核心改造部分：层级化板块数据 ---
            current_year = str(datetime.date.today().year)
            
            # 定义层级结构 (Sector, Sub-Sector, Ticker, Approx Weight)
            hierarchy = [
                # 信息技术拆解
                ('Technology', 'Software', 'IGV', 15.0),
                ('Technology', 'Semiconductors', 'SOXX', 10.0),
                ('Technology', 'Hardware/Other', 'XLK', 5.0),
                # 金融拆解
                ('Financials', 'Regional Banks', 'KRE', 3.0),
                ('Financials', 'Diversified Banks', 'KBE', 5.0),
                ('Financials', 'Broker-Dealers', 'IAI', 2.0),
                ('Financials', 'Insurance', 'KIE', 3.1),
                # 其他一级板块 (不拆解)
                ('Health Care', 'Health Care', 'XLV', 12.6),
                ('Consumer Disc', 'Consumer Disc', 'XLY', 10.6),
                ('Comm Services', 'Comm Services', 'XLC', 8.9),
                ('Industrials', 'Industrials', 'XLI', 8.8),
                ('Cons Staples', 'Cons Staples', 'XLP', 6.1),
                ('Energy', 'Energy', 'XLE', 3.9),
                ('Utilities', 'Utilities', 'XLU', 2.5),
                ('Materials', 'Materials', 'XLB', 2.4),
                ('Real Estate', 'Real Estate', 'XLRE', 2.3)
            ]
            
            tree_rows = []
            for sector, sub_sector, ticker, weight in hierarchy:
                df = yf_df.get(ticker)
                if df is not None and not df.empty:
                    try:
                        ytd_start = df.loc[current_year].iloc[0]['Close']
                        ytd_now = df.iloc[-1]['Close']
                        perf = ((ytd_now - ytd_start) / ytd_start) * 100
                        tree_rows.append({
                            'Market': 'S&P 500', 
                            'Sector': sector, 
                            'Sub-Sector': sub_sector, 
                            'YTD (%)': perf, 
                            'Weight': weight
                        })
                    except: pass
            
            if tree_rows:
                df_tree = pd.DataFrame(tree_rows)
                # 使用 path 构建下钻层级
                fig_tree = px.treemap(
                    df_tree,
                    path=['Market', 'Sector', 'Sub-Sector'],
                    values='Weight',
                    color='YTD (%)',
                    color_continuous_scale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']],
                    color_continuous_midpoint=0
                )
                
                fig_tree.update_layout(
                    height=490, margin=dict(l=0, r=0, t=30, b=0),
                    template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)'
                )
                fig_tree.update_traces(
                    texttemplate="<b>%{label}</b><br>%{color:.2f}%",
                    hovertemplate="<b>%{label}</b><br>YTD: %{color:.2f}%<extra></extra>"
                )
                st.plotly_chart(fig_tree, use_container_width=True, config={'displayModeBar': False})
    else:
        st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, color, selected_timeframe, show_ma=use_ma), use_container_width=True)
