import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import datetime
import akshare as ak
from fredapi import Fred
import traceback

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(page_title="Macro Terminal V2.0", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 2. Institutional Data Engine (MAX Period)
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)
def fetch_global_data():
    FRED_API_KEY = '2855fd24c8cbc761cd583d64f97e7004' 
    
    # A. Global Equities & Commodities (MAX Period)
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

    # B. Federal Reserve (FRED Max)
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

    # C. AKShare (China Futures & Bond)
    cn_data = {}
    ak_symbols = {
        'SHFE_Silver': 'ag0', 'SHFE_Gold': 'au0', 'SHFE_Copper': 'cu0', 'SHFE_Aluminum': 'al0', 
        'SHFE_Zinc': 'zn0', 'SHFE_Nickel': 'ni0', 'SHFE_Rebar': 'rb0',
        'DCE_IronOre': 'i0', 'DCE_Coke': 'j0', 'DCE_SoybeanMeal': 'm0', 'DCE_SoybeanOil': 'y0',
        'ZCE_Sugar': 'SR0', 'ZCE_Cotton': 'CF0', 'ZCE_PTA': 'TA0', 'ZCE_Methanol': 'MA0'
    }
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
# 3. Analytics & Pro Charting Factory
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
    
    # EMA 20, 60, 120
    df['EMA20'] = df[close_col].ewm(span=20, adjust=False).mean()
    df['EMA60'] = df[close_col].ewm(span=60, adjust=False).mean()
    df['EMA120'] = df[close_col].ewm(span=120, adjust=False).mean()
    
    # Momentum: (EMA9 - EMA26) / EMA26 * 100%
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

    # Focus View (180 pts) + Auto Scaling
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
        title=dict(
            text=f"{title} <span style='color:{mom_color}; font-size:14px;'>Momentum [(EMA9-EMA26)/EMA26]: {mom_str}</span>",
            font=dict(size=24)
        ),
        margin=dict(l=10, r=10, t=60, b=10), height=800, dragmode='pan',
        template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(rangeslider=dict(visible=False), type="date", showgrid=False, range=x_range),
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.15)', side="right", range=y_range, fixedrange=False),
        hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# ==========================================
# 4. Bloomberg Dashboard Layout
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", width=40)
    st.title("Macro Terminal")
    st.markdown("---")
    
    # Level 1: Category
    page = st.selectbox("📂 Category", ["📊 Spreads & Ratios", "⚒️ Commodity", "💱 FX & FI", "📈 Equity Markets"])
    
    # Dynamic Asset Selector Logic
    asset_list = []
    if page == "📊 Spreads & Ratios": asset_list = ["High-Yield Spread (OAS)", "Emerging Market (EMBI)", "10Y-2Y Spread", "10Y-3M Spread", "SOFR-EFFR Premium", "Gold-Silver Ratio", "Gold-WTI Ratio"]
    elif page == "⚒️ Commodity": asset_list = ["Gold (GC=F)", "Silver (SI=F)", "Copper (HG=F)", "WTI Crude (CL=F)", "Natural Gas (NG=F)", "Bitcoin (BTC-USD)", "SHFE Rebar", "DCE Iron Ore", "ZCE Sugar", "DCE Soybean Meal"]
    elif page == "💱 FX & FI": asset_list = ["USD/CNH", "USD/JPY", "AUD/USD", "EUR/USD", "US 2Y Yield", "US 10Y Yield", "China 10Y Yield", "TLT"]
    elif page == "📈 Equity Markets": asset_list = ["S&P 500 (^GSPC)", "Nasdaq 100 (^NDX)", "Semiconductor (^SOX)", "Hang Seng (^HSI)", "SSE Composite", "Nikkei 225"]
    
    # Level 2: Asset Selection
    selected_asset = st.radio("🎯 Select Asset", asset_list)
    
    st.markdown("---")
    st.markdown("### ⏱️ Timeframe")
    selected_timeframe = st.radio("Resolution", ["Daily", "Weekly", "Monthly", "MAX"], horizontal=True, label_visibility="collapsed")
    
    if st.button("🔄 Force Sync Data", type="primary", use_container_width=True):
        fetch_global_data.clear()
        st.rerun()

    db = fetch_global_data()
    if db: st.success("✅ Engine Live")

# ==========================================
# 5. Main Execution Area (Bloomberg Canvas)
# ==========================================
if db:
    yf_df = db['yf']; fr_df = db['fred']; mk_df = db['mock']
    
    # Helper for Spreads
    def get_data(asset_name):
        # Maps user-friendly names to actual dataframes
        mapping = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B", False),
            "Emerging Market (EMBI)": (fr_df.get('BAMLEMHBHYCRPIUSOAS'), "#DC143C", False),
            "10Y-2Y Spread": (pd.DataFrame({'Close': fr_df['DGS10']['Close'] - fr_df['DGS2']['Close']}).dropna() if 'DGS10' in fr_df and 'DGS2' in fr_df else None, "#FF4B4B", False),
            "SOFR-EFFR Premium": (pd.DataFrame({'Close': fr_df['SOFR']['Close'] - fr_df['EFFR']['Close']}).dropna() if 'SOFR' in fr_df and 'EFFR' in fr_df else None, "#00CC96", False),
            "Gold-Silver Ratio": (pd.DataFrame({'Close': yf_df['GC=F']['Close'] / yf_df['SI=F']['Close']}).dropna() if 'GC=F' in yf_df and 'SI=F' in yf_df else None, "#AB63FA", False),
            "Gold (GC=F)": (yf_df.get('GC=F'), "#FFD700", True),
            "WTI Crude (CL=F)": (yf_df.get('CL=F'), "#8B4513", True),
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B", True),
            "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000", True),
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96", True),
            "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF", True),
            "Hang Seng (^HSI)": (yf_df.get('^HSI'), "#00BFFF", True),
            "SHFE Rebar": (mk_df.get('SHFE_Rebar'), "#696969", True),
            "DCE Iron Ore": (mk_df.get('DCE_IronOre'), "#8B4513", True),
            # Add other mappings as needed...
        }
        # Fallback for dynamic ticker lookup
        if asset_name in mapping: return mapping[asset_name]
        
        # Check direct YF tickers
        clean_name = asset_name.split('(')[-1].replace(')', '') if '(' in asset_name else asset_name
        if clean_name in yf_df: return (yf_df[clean_name], "#1E90FF", True)
        if asset_name in mk_df: return (mk_df[asset_name], "#1E90FF", True)
        return (None, "#FFFFFF", False)

    target_df, color, use_ma = get_data(selected_asset)
    
    # 🚨 BLOOMBERG MODE: The entire main page is ONE chart
    st.plotly_chart(
        draw_bloomberg_chart(target_df, selected_asset, color, selected_timeframe, show_ma=use_ma),
        use_container_width=True,
        config={'scrollZoom': True, 'displayModeBar': True}
    )

    # Secondary Content (Sector Bars) only for Equity page
    if page == "📈 Equity Markets":
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            us_sec = pd.DataFrame({"Sector": ["Energy", "Shipping", "Materials", "Software"], "YTD (%)": [25.7, 23.3, 10.3, 6.5]})
            st.plotly_chart(px.bar(us_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="US Sectors", template="plotly_dark", height=300), use_container_width=True)
        with c2:
            hk_sec = pd.DataFrame({"Sector": ["China Internet", "HS Tech", "HS Index"], "YTD (%)": [-10.0, -2.5, -5.0]})
            st.plotly_chart(px.bar(hk_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="HK Sectors", template="plotly_dark", height=300), use_container_width=True)
        with c3:
            cn_sec = pd.DataFrame({"Sector": ["Tech", "Real Estate", "Bank"], "YTD (%)": [9.3, 5.8, 3.1]})
            st.plotly_chart(px.bar(cn_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="CN Sectors", template="plotly_dark", height=300), use_container_width=True)
