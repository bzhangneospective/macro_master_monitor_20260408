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
    page_title="Macro Terminal V2.4", 
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

    dates = pd.date_range(start=datetime.date.today() - datetime.timedelta(days=365*10), end=datetime.date.today(), freq='B')
    cn_data['EIA_Crude'] = pd.DataFrame({'Close': 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)}, index=dates)
    cn_data['EIA_Gasoline'] = pd.DataFrame({'Close': 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)}, index=dates)
    
    return {"yf": yf_data, "fred": fred_data, "mock": cn_data, "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ==========================================
# 2.1 Decoupled Heatmap Data Pipeline
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_gics_heatmap_data():
    # US GICS Level 1 & Level 2 Drill-down Map
    hierarchy = [
        ('Technology', 'Software (IGV)', 'IGV', 15.0),
        ('Technology', 'Semiconductors (SOXX)', 'SOXX', 10.0),
        ('Technology', 'Hardware/Broad (XLK)', 'XLK', 5.0), 
        ('Financials', 'Regional Banks (KRE)', 'KRE', 3.0),
        ('Financials', 'Diversified Banks (KBE)', 'KBE', 5.0),
        ('Financials', 'Broker-Dealers (IAI)', 'IAI', 2.0),
        ('Financials', 'Insurance (KIE)', 'KIE', 3.1),
        ('Health Care', 'Health Care (XLV)', 'XLV', 12.6),
        ('Consumer Disc', 'Consumer Disc (XLY)', 'XLY', 10.6),
        ('Comm Services', 'Comm Services (XLC)', 'XLC', 8.9),
        ('Industrials', 'Industrials (XLI)', 'XLI', 8.8),
        ('Cons Staples', 'Cons Staples (XLP)', 'XLP', 6.1),
        ('Energy', 'Energy (XLE)', 'XLE', 3.9),
        ('Utilities', 'Utilities (XLU)', 'XLU', 2.5),
        ('Materials', 'Materials (XLB)', 'XLB', 2.4),
        ('Real Estate', 'Real Estate (XLRE)', 'XLRE', 2.3)
    ]
    
    tickers = [item[2] for item in hierarchy]
    try:
        # Fast YTD request
        raw_data = yf.download(tickers, period="ytd", progress=False)['Close']
        tree_rows = []
        for sector, sub_sector, ticker, weight in hierarchy:
            if ticker in raw_data.columns:
                s_data = raw_data[ticker].dropna()
                if not s_data.empty and len(s_data) > 1:
                    ytd_start = s_data.iloc[0]
                    ytd_now = s_data.iloc[-1]
                    perf = ((ytd_now - ytd_start) / ytd_start) * 100
                    tree_rows.append({
                        'Market': 'S&P 500 Sub-Sectors', 
                        'Sector': sector, 
                        'Sub-Sector': sub_sector, 
                        'YTD (%)': perf, 
                        'Weight': weight
                    })
        return pd.DataFrame(tree_rows)
    except Exception:
        return pd.DataFrame()

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
    if df_raw is None or df_raw.empty: 
        fig = go.Figure()
        fig.update_layout(title="Awaiting Data", template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return fig
    
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
    mom_str = f"{'▲' if mom_val >= 0 else '▼'} {abs(mom_val):.2f}%"

    fig = go.Figure()
    if has_ohlc:
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Candles', increasing_line_color='#00CC96', decreasing_line_color='#FF4B4B'))
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df[close_col], mode='lines', name='Price', line=dict(color=base_color, width=2.5)))

    if show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], mode='lines', name='EMA20', line=dict(color='#FFD700', width=1.3)))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA60'], mode='lines', name='EMA60', line=dict(color='#FF4B4B', width=1.3)))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA120'], mode='lines', name='EMA120', line=dict(color='#AB63FA', width=1.3, dash='dot')))

    y_range, x_range = None, None
    if len(df) > 10:
        visible_points = 180 if len(df) > 180 else len(df)
        last_df = df.iloc[-visible_points:]
        y_min = last_df['Low'].min() if has_ohlc else last_df[close_col].min()
        y_max = last_df['High'].max() if has_ohlc else last_df[close_col].max()
        padding = (y_max - y_min) * 0.05
        y_range = [y_min - padding, y_max + padding]
        x_range = [last_df.index[0], last_df.index[-1]]

    if timeframe == "MAX": x_range, y_range = None, None

    fig.update_layout(
        title=dict(text=f"{title} <span style='color:{mom_color}; font-size:14px;'>Momentum [(EMA9-EMA26)/EMA26]: {mom_str}</span>", font=dict(size=24)),
        margin=dict(l=10, r=10, t=60, b=10), height=490, dragmode='pan', template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(rangeslider=dict(visible=False), type="date", showgrid=False, range=x_range),
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.15)', side="right", range=y_range, fixedrange=False),
        hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# ==========================================
# 4. Bloomberg Dashboard UI
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", width=40)
    st.title("Macro Terminal")
    st.markdown("---")
    
    page = st.selectbox("📂 Category", ["📊 Spreads & Ratios", "⚒️ Commodity", "💱 FX & FI", "📈 Equity Markets"])
    
    asset_list = []
    if page == "📊 Spreads & Ratios": asset_list = ["High-Yield Spread (OAS)", "Emerging Market (EMBI)", "AAA Corporate Spread", "BAA Corporate Spread", "10Y-2Y Spread", "10Y-3M Spread", "SOFR-EFFR Premium", "Gold-Silver Ratio", "Gold-WTI Ratio", "Gold-Copper Ratio"]
    elif page == "⚒️ Commodity": asset_list = ["Gold (GC=F)", "Silver (SI=F)", "Copper (HG=F)", "WTI Crude (CL=F)", "Brent Crude (BZ=F)", "Natural Gas (NG=F)", "Corn (ZC=F)", "Soybeans (ZS=F)", "Wheat (ZW=F)", "Cotton (CT=F)", "Bitcoin (BTC-USD)", "SHFE Silver", "SHFE Aluminum", "SHFE Zinc", "SHFE Nickel", "SHFE Rebar", "DCE Iron Ore", "DCE Coke", "ZCE PTA", "ZCE Methanol", "ZCE Sugar", "DCE Soybean Meal", "DCE Soybean Oil", "EIA Crude Inv. (Mock)", "EIA Gasoline Inv. (Mock)"]
    elif page == "💱 FX & FI": asset_list = ["USD/CNH", "USD/JPY", "AUD/USD", "EUR/USD", "GBP/USD", "USD/CAD", "USD/INR", "USD/BRL", "US 2Y Yield", "US 10Y Yield", "US 30Y Yield", "China 10Y Yield", "US Long Treas (TLT)"]
    elif page == "📈 Equity Markets": asset_list = ["S&P 500 (^GSPC)", "Nasdaq 100 (^NDX)", "Nikkei 225 (^N225)", "Hang Seng (^HSI)", "SSE Composite", "KOSPI (^KS11)", "Taiwan (^TWII)", "Semiconductor (^SOX)"]
    
    selected_asset = st.radio("🎯 Select Asset", asset_list)
    st.markdown("---")
    selected_timeframe = st.radio("Resolution", ["Daily", "Weekly", "Monthly", "MAX"], horizontal=True, label_visibility="collapsed")
    if st.button("🔄 Force Sync Data", type="primary", use_container_width=True):
        fetch_global_data.clear()
        fetch_gics_heatmap_data.clear()
        st.rerun()

    db = fetch_global_data()

# ==========================================
# 5. Main Execution
# ==========================================
if db:
    yf_df = db['yf']; fr_df = db['fred']; mk_df = db['mock']
    
    def safe_sub(df1, df2):
        if df1 is not None and df2 is not None and not df1.empty and not df2.empty: return pd.DataFrame({'Close': df1['Close'] - df2['Close']}).dropna()
        return None
    def safe_div(df1, df2):
        if df1 is not None and df2 is not None and not df1.empty and not df2.empty: return pd.DataFrame({'Close': df1['Close'] / df2['Close']}).dropna()
        return None

    def get_data(asset_name):
        mapping = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B", False),
            "Emerging Market (EMBI)": (fr_df.get('BAMLEMHBHYCRPIUSOAS'), "#DC143C", False),
            "AAA Corporate Spread": (fr_df.get('BAMLC0A1CAAA'), "#FFA500", False),
            "BAA Corporate Spread": (fr_df.get('BAMLC0A4CBBB'), "#FFD700", False),
            "10Y-2Y Spread": (safe_sub(fr_df.get('DGS10'), fr_df.get('DGS2')), "#FF4B4B", False),
            "10Y-3M Spread": (safe_sub(fr_df.get('DGS10'), fr_df.get('DGS3MO')), "#DC143C", False),
            "SOFR-EFFR Premium": (safe_sub(fr_df.get('SOFR'), fr_df.get('EFFR')), "#00CC96", False),
            "Gold-Silver Ratio": (safe_div(yf_df.get('GC=F'), yf_df.get('SI=F')), "#AB63FA", False),
            "Gold-WTI Ratio": (safe_div(yf_df.get('GC=F'), yf_df.get('CL=F')), "#00BFFF", False),
            "Gold-Copper Ratio": (safe_div(yf_df.get('GC=F'), yf_df.get('HG=F')), "#8A2BE2", False),
            "Gold (GC=F)": (yf_df.get('GC=F'), "#FFD700", True),
            "Silver (SI=F)": (yf_df.get('SI=F'), "#C0C0C0", True),
            "Copper (HG=F)": (yf_df.get('HG=F'), "#B87333", True),
            "WTI Crude (CL=F)": (yf_df.get('CL=F'), "#8B4513", True),
            "Brent Crude (BZ=F)": (yf_df.get('BZ=F'), "#A0522D", True),
            "Natural Gas (NG=F)": (yf_df.get('NG=F'), "#4682B4", True),
            "Corn (ZC=F)": (yf_df.get('ZC=F'), "#FFD700", True),
            "Soybeans (ZS=F)": (yf_df.get('ZS=F'), "#9ACD32", True),
            "Wheat (ZW=F)": (yf_df.get('ZW=F'), "#F5DEB3", True),
            "Cotton (CT=F)": (yf_df.get('CT=F'), "#FFFAFA", True),
            "Bitcoin (BTC-USD)": (yf_df.get('BTC-USD'), "#FF8C00", True),
            "SHFE Silver": (mk_df.get('SHFE_Silver'), "#C0C0C0", True),
            "SHFE Aluminum": (mk_df.get('SHFE_Aluminum'), "#A9A9A9", True),
            "SHFE Zinc": (mk_df.get('SHFE_Zinc'), "#778899", True),
            "SHFE Nickel": (mk_df.get('SHFE_Nickel'), "#708090", True),
            "SHFE Rebar": (mk_df.get('SHFE_Rebar'), "#696969", True),
            "DCE Iron Ore": (mk_df.get('DCE_IronOre'), "#8B4513", True),
            "DCE Coke": (mk_df.get('DCE_Coke'), "#2F4F4F", True),
            "ZCE PTA": (mk_df.get('ZCE_PTA'), "#483D8B", True),
            "ZCE Methanol": (mk_df.get('ZCE_Methanol'), "#4B0082", True),
            "ZCE Sugar": (mk_df.get('ZCE_Sugar'), "#F8F8FF", True),
            "DCE Soybean Meal": (mk_df.get('DCE_SoybeanMeal'), "#9ACD32", True),
            "DCE Soybean Oil": (mk_df.get('DCE_SoybeanOil'), "#DAA520", True),
            "EIA Crude Inv. (Mock)": (mk_df.get('EIA_Crude'), "#8B4513", True),
            "EIA Gasoline Inv. (Mock)": (mk_df.get('EIA_Gasoline'), "#4682B4", True),
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B", True),
            "USD/JPY": (yf_df.get('JPY=X'), "#AB63FA", True),
            "AUD/USD": (yf_df.get('AUDUSD=X'), "#00CC96", True),
            "EUR/USD": (yf_df.get('EURUSD=X'), "#1E90FF", True),
            "GBP/USD": (yf_df.get('GBPUSD=X'), "#8A2BE2", True),
            "USD/CAD": (yf_df.get('CAD=X'), "#DC143C", True),
            "USD/INR": (yf_df.get('INR=X'), "#00BFFF", True),
            "USD/BRL": (yf_df.get('BRL=X'), "#32CD32", True),
            "US 2Y Yield": (fr_df.get('DGS2'), "#696969", True),
            "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000", True),
            "US 30Y Yield": (fr_df.get('DGS30'), "#800000", True),
            "China 10Y Yield": (mk_df.get('China_10Y_Yield'), "#FF4B4B", True),
            "US Long Treas (TLT)": (yf_df.get('TLT'), "#4682B4", True),
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96", True),
            "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF", True),
            "Nikkei 225 (^N225)": (yf_df.get('^N225'), "#FF4B4B", True),
            "Hang Seng (^HSI)": (yf_df.get('^HSI'), "#00BFFF", True),
            "SSE Composite": (yf_df.get('000001.SS'), "#FF8C00", True),
            "KOSPI (^KS11)": (yf_df.get('^KS11'), "#FFA500", True),
            "Taiwan (^TWII)": (yf_df.get('^TWII'), "#32CD32", True),
            "Semiconductor (^SOX)": (yf_df.get('^SOX'), "#AB63FA", True)
        }
        return mapping.get(asset_name, (None, "#FFFFFF", False))

    target_df, color, use_ma = get_data(selected_asset)
    
    if page == "📈 Equity Markets":
        tab1, tab2 = st.tabs(["🎯 Asset Analysis", "📊 Sector Performance (GICS)"])
        with tab1:
            st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, color, selected_timeframe, show_ma=use_ma), use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
        with tab2:
            df_tree = fetch_gics_heatmap_data()
            
            if not df_tree.empty:
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
                    template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                )
                fig_tree.update_traces(
                    texttemplate="<b>%{label}</b><br>%{color:.2f}%",
                    hovertemplate="<b>%{label}</b><br>YTD: %{color:.2f}%<extra></extra>",
                    root_color="#000000"
                )
                st.plotly_chart(fig_tree, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})
            else:
                st.warning("Fetching GICS component data...")
    else:
        st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, color, selected_timeframe, show_ma=use_ma), use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
