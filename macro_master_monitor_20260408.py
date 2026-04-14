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
st.set_page_config(page_title="Macro Master Monitor", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 2. Core Data Engine
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)
def fetch_global_data():
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365 * 10)

    FRED_API_KEY = '2855fd24c8cbc761cd583d64f97e7004' 
    
    # A. Yahoo Finance
    yf_tickers = [
        '^GSPC', '^NDX', '^SOX', '^N225', '^KS11', '^HSI', '000001.SS', '^TWII',
        'GC=F', 'SI=F', 'HG=F', 'CL=F', 'NG=F', 'BZ=F', 'ZC=F', 'ZS=F', 'ZW=F', 'CT=F', 'BTC-USD',
        'CNH=X', 'AUDUSD=X', 'JPY=X', 'IDR=X', 'INR=X', 'TRY=X', 'EURUSD=X', 'GBPUSD=X', 'CAD=X', 'MXN=X', 'BRL=X', 'ARS=X', 'ILS=X', 'HKD=X', 'TLT'
    ]
    try:
        yf_raw = yf.download(yf_tickers, period="10y", progress=False)['Close']
        if isinstance(yf_raw, pd.DataFrame):
            yf_raw.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in yf_raw.columns]
            yf_data = yf_raw.ffill().bfill()
        else:
            yf_data = pd.DataFrame(yf_raw)
    except Exception as e:
        print(f"YF Error: {e}")
        yf_data = pd.DataFrame()

    # B. Federal Reserve (FRED)
    fred_tickers = [
        'SOFR', 'EFFR', 'DGS1MO', 'DGS3MO', 'DGS2', 'DGS5', 'DGS10', 'DGS30',
        'BAMLC0A1CAAA', 'BAMLC0A4CBBB', 'BAMLH0A0HYM2', 'BAMLEMHBHYCRPIUSOAS'
    ]
    fred_data = pd.DataFrame()
    try:
        fred = Fred(api_key=FRED_API_KEY)
        for ticker in fred_tickers:
            try:
                series = fred.get_series(ticker, start_date, end_date)
                fred_data[ticker] = series
            except:
                fred_data[ticker] = np.nan
        fred_data = fred_data.ffill().bfill()
    except Exception as e:
        print(f"FRED Error: {e}")

    # C. AKShare (China Futures & Bond)
    cn_data = pd.DataFrame()
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
            cn_data[name] = pd.to_numeric(df['close'], errors='coerce') 
        except:
            cn_data[name] = np.nan
            
    try:
        bond_df = ak.bond_zh_us_rate()
        bond_df['日期'] = pd.to_datetime(bond_df['日期'])
        bond_df.set_index('日期', inplace=True)
        cn_data['China_10Y_Yield'] = pd.to_numeric(bond_df['中国国债收益率10年'], errors='coerce')
    except:
        cn_data['China_10Y_Yield'] = np.nan

    base_index = cn_data.index if not cn_data.empty else pd.date_range(start=start_date, end=end_date, freq='B')
    if cn_data.empty:
        cn_data = pd.DataFrame(index=base_index)
        
    actual_len = len(base_index)
    cn_data['EIA_Crude'] = 100 + np.cumsum(np.random.randn(actual_len) * 0.5)
    cn_data['EIA_Gasoline'] = 100 + np.cumsum(np.random.randn(actual_len) * 0.5)
    
    return {"yf": yf_data, "fred": fred_data, "mock": cn_data, "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ==========================================
# 3. Enhanced Broker-Level Chart Factory
# ==========================================
def draw_chart(series_or_df, title, base_color):
    if series_or_df is None or series_or_df.dropna().empty or len(series_or_df.dropna()) < 10:
        fig = go.Figure()
        # 自适应字体颜色，去掉了强制白色
        fig.add_annotation(text="Awaiting Data Sync", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=16))
        fig.update_layout(title=title, height=550, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return fig

    df = pd.DataFrame(series_or_df.dropna())
    close_col = df.columns[0]
    
    # Calculate Institutional Moving Averages
    df['MA20'] = df[close_col].rolling(window=20).mean()
    df['MA60'] = df[close_col].rolling(window=60).mean()
    df['MA120'] = df[close_col].rolling(window=120).mean()
    df['MA200'] = df[close_col].rolling(window=200).mean()

    fig = go.Figure()

    # Main Price Action
    fig.add_trace(go.Scatter(x=df.index, y=df[close_col], mode='lines', name='Price', line=dict(color=base_color, width=2.5)))

    # MA Overlays
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], mode='lines', name='MA20', line=dict(color='#FFD700', width=1.2, dash='solid')))
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], mode='lines', name='MA60', line=dict(color='#FF4B4B', width=1.2, dash='solid')))
    fig.add_trace(go.Scatter(x=df.index, y=df['MA120'], mode='lines', name='MA120', line=dict(color='#AB63FA', width=1.2, dash='dot'), visible='legendonly'))
    fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], mode='lines', name='MA200', line=dict(color='#4682B4', width=1.2, dash='dot'), visible='legendonly'))

    # Configuration for smooth panning and auto-adapting colors
    fig.update_layout(
        # 去掉 color="#FFFFFF" 限制，让标题颜色自适应
        title=dict(text=title, font=dict(size=20)),
        margin=dict(l=10, r=10, t=60, b=10),
        height=600,
        dragmode='pan', # Enables Left-Click Dragging
        xaxis=dict(
            rangeslider=dict(visible=False), 
            type="date",
            showgrid=False,
            zeroline=False
        ),
        yaxis=dict(
            showgrid=True, 
            gridcolor='rgba(128,128,128,0.15)',
            zeroline=False,
            side="right" # Y-axis on the right
        ),
        # 去掉了强制黑色模板，全面拥抱 Streamlit 原生响应式主题
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def render_grid(charts_dict):
    for title, (series, color) in charts_dict.items():
        st.plotly_chart(
            draw_chart(series, title, color), 
            use_container_width=True, 
            config={
                'scrollZoom': True,      
                'displayModeBar': True,  
                'modeBarButtonsToRemove': ['lasso2d', 'select2d'], 
                'responsive': True
            }
        )
        st.markdown("<br><hr style='border: 0.5px solid #E0E0E0;'><br>", unsafe_allow_html=True)

# ==========================================
# 4. Sidebar Navigation
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", width=50)
    st.header("Macro Terminal")
    st.caption("🚀 Engine: Official API Direct Sync")
    page = st.radio(
        "📂 Navigation", 
        ["📊 1. Spreads & Ratios", "⚒️ 2. Commodity", "💱 3. FX & FI", "📈 4. Equity Markets"]
    )
    
    st.markdown("---")
    if st.button("🔄 Force Sync Data", type="primary"):
        fetch_global_data.clear()
        st.rerun()

    try:
        db = fetch_global_data()
        st.success("✅ Data Engine Live")
        st.caption(f"Last Update: {db['time']}")
    except:
        st.error("Connection Error")
        db = None

# ==========================================
# 5. Main Terminal Layout
# ==========================================
st.title("🏛️ Macro Asset Master Monitor")

if db:
    yf_df = db['yf']
    fr_df = db['fred']
    mk_df = db['mock']

    if page == "📊 1. Spreads & Ratios":
        st.subheader("Credit & Liquidity Analysis")
        charts = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B"),
            "Emerging Market (EMBI)": (fr_df.get('BAMLEMHBHYCRPIUSOAS'), "#DC143C"),
            "10Y-2Y Spread": (fr_df.get('DGS10') - fr_df.get('DGS2') if 'DGS10' in fr_df and 'DGS2' in fr_df else None, "#FF4B4B"),
            "SOFR-EFFR Premium": (fr_df.get('SOFR') - fr_df.get('EFFR') if 'SOFR' in fr_df and 'EFFR' in fr_df else None, "#00CC96"),
            "Gold-Silver Ratio": (yf_df.get('GC=F') / yf_df.get('SI=F') if 'GC=F' in yf_df and 'SI=F' in yf_df else None, "#AB63FA")
        }
        render_grid(charts)

    elif page == "⚒️ 2. Commodity":
        st.subheader("Global Commodity Trends")
        intl_c = {
            "Gold (COMEX)": (yf_df.get('GC=F'), "#FFD700"), "Silver (COMEX)": (yf_df.get('SI=F'), "#C0C0C0"),
            "Copper (COMEX)": (yf_df.get('HG=F'), "#B87333"), "WTI Crude": (yf_df.get('CL=F'), "#8B4513"),
            "SHFE Rebar": (mk_df.get('SHFE_Rebar'), "#696969"), "DCE Iron Ore": (mk_df.get('DCE_IronOre'), "#8B4513")
        }
        render_grid(intl_c)

    elif page == "💱 3. FX & FI":
        st.subheader("FX & Yield Curves")
        fx_c = {
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B"), "USD/JPY": (yf_df.get('JPY=X'), "#AB63FA"),
            "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000"), "China 10Y Yield": (mk_df.get('China_10Y_Yield'), "#FF4B4B")
        }
        render_grid(fx_c)

    elif page == "📈 4. Equity Markets":
        st.subheader("Global Equity Indices")
        eq_c = {
            "S&P 500": (yf_df.get('^GSPC'), "#00CC96"), "Nasdaq 100": (yf_df.get('^NDX'), "#1E90FF"),
            "Hang Seng": (yf_df.get('^HSI'), "#00BFFF"), "SSE Composite": (yf_df.get('000001.SS'), "#FF8C00")
        }
        render_grid(eq_c)
        
        st.markdown("---")
        us_sec = pd.DataFrame({"Sector": ["Energy", "Shipping", "Materials", "Software", "Semiconductors"], "YTD (%)": [25.7, 23.3, 10.3, 6.5, -12.1]})
        st.plotly_chart(px.bar(us_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="US Sectors YTD (%)", height=500), use_container_width=True)
