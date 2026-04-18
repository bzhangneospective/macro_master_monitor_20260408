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
    page_title="Macro Terminal V2.10", 
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
# 2. Institutional Data Engine (Main Charts)
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
                df = pd.DataFrame({
                    'Open': yf_raw['Open'][t], 'High': yf_raw['High'][t],
                    'Low': yf_raw['Low'][t], 'Close': yf_raw['Close'][t]
                }).dropna()
                yf_data[t] = df
            except: pass
    except: pass

    fred_tickers = [
        'SOFR', 'EFFR', 'DGS1MO', 'DGS3MO', 'DGS2', 'DGS5', 'DGS10', 'DGS30',
        'BAMLC0A1CAAA', 'BAMLC0A4CBBB', 'BAMLH0A0HYM2', 'BAMLEMHBHYCRPIUSOAS'
    ]
    fred_data = {}
    try:
        fred = Fred(api_key=FRED_API_KEY)
        for ticker in fred_tickers:
            try:
                series = fred.get_series(ticker)
                fred_data[ticker] = pd.DataFrame({'Close': series}).ffill().bfill()
            except: pass
    except: pass

    ak_symbols = {
        'SHFE_Silver': 'ag0', 'SHFE_Gold': 'au0', 'SHFE_Copper': 'cu0', 'SHFE_Aluminum': 'al0', 
        'SHFE_Zinc': 'zn0', 'SHFE_Nickel': 'ni0', 'SHFE_Rebar': 'rb0',
        'DCE_IronOre': 'i0', 'DCE_Coke': 'j0', 'DCE_SoybeanMeal': 'm0', 'DCE_SoybeanOil': 'y0',
        'ZCE_Sugar': 'SR0', 'ZCE_Cotton': 'CF0', 'ZCE_PTA': 'TA0', 'ZCE_Methanol': 'MA0'
    }
    cn_data = {}
    for name, symbol in ak_symbols.items():
        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'})
            cn_data[name] = df[['Open', 'High', 'Low', 'Close']].apply(pd.to_numeric, errors='coerce').dropna()
        except: pass
            
    try:
        bond_df = ak.bond_zh_us_rate()
        bond_df['日期'] = pd.to_datetime(bond_df['日期'])
        bond_df.set_index('日期', inplace=True)
        cn_data['China_10Y_Yield'] = pd.DataFrame({'Close': pd.to_numeric(bond_df['中国国债收益率10年'], errors='coerce')}).dropna()
    except: pass

    return {"yf": yf_data, "fred": fred_data, "mock": cn_data, "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ==========================================
# 2.1 Decoupled Heatmap Data Pipeline (V2.10)
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_gics_heatmap_raw():
    hierarchy = [
        ('Technology', 'Software (IGV)', 'IGV', 12.0),
        ('Technology', 'Semiconductors (SOXX)', 'SOXX', 11.0),
        ('Technology', 'Hardware/Equip (IYW)', 'IYW', 6.0),
        ('Financials', 'Banks (KBE)', 'KBE', 4.0),
        ('Financials', 'Regional Banks (KRE)', 'KRE', 2.0),
        ('Financials', 'Broker/Dealers (IAI)', 'IAI', 3.0),
        ('Financials', 'Insurance (KIE)', 'KIE', 4.0),
        ('Health Care', 'Biotech (IBB)', 'IBB', 4.0),
        ('Health Care', 'Medical Devices (IHI)', 'IHI', 4.0),
        ('Health Care', 'Pharma/Providers (PPH)', 'PPH', 5.0),
        ('Cons Disc', 'Retail (XRT)', 'XRT', 6.0),
        ('Cons Disc', 'Homebuilders (ITB)', 'ITB', 2.0),
        ('Cons Disc', 'Broad Disc (XLY)', 'XLY', 3.0),
        ('Comm Svcs', 'Internet (FDN)', 'FDN', 6.0),
        ('Comm Svcs', 'Telecom/Media (IYZ)', 'IYZ', 3.0),
        ('Industrials', 'Aero & Defense (ITA)', 'ITA', 3.0),
        ('Industrials', 'Transport (IYT)', 'IYT', 3.0),
        ('Industrials', 'Broad Industrials (XLI)', 'XLI', 3.0),
        ('Cons Staples', 'Food & Bev (PBJ)', 'PBJ', 3.0),
        ('Cons Staples', 'Broad Staples (XLP)', 'XLP', 3.0),
        ('Energy', 'E&P (XOP)', 'XOP', 2.0),
        ('Energy', 'Oil Services (OIH)', 'OIH', 2.0),
        ('Materials', 'Metals & Mining (XME)', 'XME', 1.0),
        ('Materials', 'Broad Materials (XLB)', 'XLB', 1.5),
        ('Real Estate', 'Real Estate (VNQ)', 'VNQ', 2.5),
        ('Utilities', 'Utilities (XLU)', 'XLU', 2.5)
    ]
    tickers = [item[2] for item in hierarchy]
    try:
        raw_df = yf.download(tickers, period="1y", progress=False)['Close']
        return raw_df, hierarchy
    except:
        return pd.DataFrame(), hierarchy

def calculate_heatmap_performance(raw_df, hierarchy, lookback):
    if raw_df.empty: return pd.DataFrame()
    
    tree_rows = []
    current_year = datetime.date.today().year
    
    for sector, sub_sector, ticker, weight in hierarchy:
        if ticker in raw_df.columns:
            s_data = raw_df[ticker].dropna()
            if len(s_data) < 2: continue
            
            try:
                price_now = s_data.iloc[-1]
                if lookback == "1D": price_old = s_data.iloc[-2]
                elif lookback == "5D": price_old = s_data.iloc[-min(len(s_data), 6)]
                elif lookback == "1M": price_old = s_data.iloc[-min(len(s_data), 22)]
                elif lookback == "YTD":
                    ytd_df = s_data[s_data.index.year == current_year]
                    price_old = ytd_df.iloc[0] if not ytd_df.empty else s_data.iloc[0]
                
                perf = ((price_now - price_old) / price_old) * 100
                tree_rows.append({
                    'Market': 'S&P 500 X-Ray', 'Sector': sector, 
                    'Sub-Sector': sub_sector, 'Perf (%)': perf, 'Weight': weight
                })
            except: pass
    return pd.DataFrame(tree_rows)

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
    
    df['EMA20'] = df[close_col].ewm(span=20, adjust=False).mean()
    df['EMA60'] = df[close_col].ewm(span=60, adjust=False).mean()
    df['EMA120'] = df[close_col].ewm(span=120, adjust=False).mean()
    
    ema9 = df[close_col].ewm(span=9, adjust=False).mean()
    ema26 = df[close_col].ewm(span=26, adjust=False).mean()
    mom_val = ((ema9 - ema26) / ema26 * 100).iloc[-1]
    mom_color = "#00CC96" if mom_val >= 0 else "#FF4B4B"

    fig = go.Figure()
    if has_ohlc:
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#00CC96', decreasing_line_color='#FF4B4B'))
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df[close_col], mode='lines', line=dict(color=base_color, width=2.5)))

    if show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], mode='lines', name='EMA20', line=dict(color='#FFD700', width=1.3)))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA60'], mode='lines', name='EMA60', line=dict(color='#FF4B4B', width=1.3)))

    if len(df) > 10 and timeframe != "MAX":
        last_df = df.iloc[-min(len(df), 180):]
        y_min = last_df['Low'].min() if has_ohlc else last_df[close_col].min()
        y_max = last_df['High'].max() if has_ohlc else last_df[close_col].max()
        fig.update_layout(xaxis_range=[last_df.index[0], last_df.index[-1]], yaxis_range=[y_min*0.97, y_max*1.03])

    fig.update_layout(
        height=490, margin=dict(l=10, r=10, t=60, b=10), template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        title=f"{title} <span style='color:{mom_color}; font-size:14px;'>PPO: {mom_val:.2f}%</span>",
        yaxis=dict(side="right", fixedrange=False, gridcolor='rgba(128,128,128,0.1)'),
        xaxis=dict(rangeslider=dict(visible=False), showgrid=False)
    )
    return fig

# ==========================================
# 4. Bloomberg Dashboard UI
# ==========================================
with st.sidebar:
    st.title("Macro Terminal V2.10")
    page = st.selectbox("📂 Category", ["📈 Equity Markets", "📊 Spreads & Ratios", "⚒️ Commodity", "💱 FX & FI"])
    
    asset_list = []
    if page == "📈 Equity Markets": asset_list = ["S&P 500 (^GSPC)", "Nasdaq 100 (^NDX)", "Semiconductor (^SOX)", "Nikkei 225 (^N225)", "Hang Seng (^HSI)"]
    elif page == "📊 Spreads & Ratios": asset_list = ["High-Yield Spread (OAS)", "10Y-2Y Spread"]
    elif page == "⚒️ Commodity": asset_list = ["Gold (GC=F)", "WTI Crude (CL=F)", "Bitcoin (BTC-USD)"]
    elif page == "💱 FX & FI": asset_list = ["USD/CNH", "USD/JPY", "US 10Y Yield"]
    
    selected_asset = st.radio("🎯 Select Asset", asset_list)
    st.markdown("---")
    selected_res = st.radio("Resolution", ["Daily", "Weekly", "Monthly", "MAX"], horizontal=True)
    if st.button("🔄 Force Sync Data", type="primary", use_container_width=True):
        fetch_global_data.clear(); fetch_gics_heatmap_raw.clear(); st.rerun()

    db = fetch_global_data()

# ==========================================
# 5. Main Execution
# ==========================================
if db:
    yf_df = db['yf']; fr_df = db['fred']
    
    def get_data(asset_name):
        mapping = {
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96", True),
            "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF", True),
            "Semiconductor (^SOX)": (yf_df.get('^SOX'), "#AB63FA", True),
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B", False),
            "Gold (GC=F)": (yf_df.get('GC=F'), "#FFD700", True),
            "WTI Crude (CL=F)": (yf_df.get('CL=F'), "#8B4513", True),
            "Bitcoin (BTC-USD)": (yf_df.get('BTC-USD'), "#FF8C00", True),
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B", True),
            "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000", True)
        }
        return mapping.get(asset_name, (None, "#FFFFFF", False))

    target_df, color, use_ma = get_data(selected_asset)
    
    if page == "📈 Equity Markets":
        tab1, tab2 = st.tabs(["🎯 Asset Analysis", "📊 Sector X-Ray (GICS)"])
        with tab1:
            st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, color, selected_res, show_ma=use_ma), use_container_width=True)
        with tab2:
            # --- V2.10 视觉革命：统一右侧控制台 ---
            # 采用 13:1 极致分栏比例，把图表空间撑到最大
            c_tree, c_ctrl = st.columns([13, 1])
            
            with c_ctrl:
                # 彻底去掉 150px 空白，仅仅留 5px 为了与左侧图表顶部边缘对齐
                st.markdown("<div style='padding-top: 5px;'></div>", unsafe_allow_html=True)
                st.markdown("<span style='font-size:12px; font-weight:bold; color:gray;'>Period</span>", unsafe_allow_html=True)
                lookback = st.radio("Lookback Window", ["1D", "5D", "1M", "YTD"], index=3, label_visibility="collapsed")
            
            with c_tree:
                raw_h_df, hierarchy = fetch_gics_heatmap_raw()
                df_tree = calculate_heatmap_performance(raw_h_df, hierarchy, lookback)
                
                if not df_tree.empty:
                    fig_tree = px.treemap(
                        df_tree,
                        path=['Market', 'Sector', 'Sub-Sector'],
                        values='Weight',
                        color='Perf (%)',
                        color_continuous_scale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']],
                        color_continuous_midpoint=0
                    )
                    
                    fig_tree.update_layout(
                        height=490, 
                        # 核心点 1：0 Margin，图表直接顶格渲染，不留一丝废余空间
                        margin=dict(l=0, r=40, t=0, b=0), 
                        template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)',
                        
                        # 核心点 2：将 Colorbar 锚定在右下角，与右上角的 Radio 按钮形成完美上下拼接
                        coloraxis_colorbar=dict(
                            title=dict(text=f"Perf", side="top"),
                            thickness=12,
                            len=0.55,          # 仅占下半区高度
                            yanchor="bottom",  # 底部对齐
                            y=0.02,            # 紧贴下边线
                            xanchor="left",    # 左对齐到基准线
                            x=1.01             # 微推到图表最右侧外沿，正好落在右侧控制台的正下方
                        )
                    )
                    
                    fig_tree.update_traces(
                        customdata=df_tree[['Perf (%)']],
                        texttemplate="<span style='font-size:11px'><b>%{label}</b></span><br>%{customdata[0]:.2f}%",
                        hovertemplate=f"<b>%{{label}}</b><br>{lookback} Perf: %{{customdata[0]:.2f}}%<extra></extra>",
                        root_color="#000000"
                    )
                    st.plotly_chart(fig_tree, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.warning("Fetching GICS component data...")
    else:
        st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, color, selected_res, show_ma=use_ma), use_container_width=True)
