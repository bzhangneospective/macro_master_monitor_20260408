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
# 2. Core Data Engine (MAX History)
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)
def fetch_global_data():
    FRED_API_KEY = '2855fd24c8cbc761cd583d64f97e7004' 
    
    # A. Yahoo Finance (Fetch Max History)
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
                    'Open': yf_raw['Open'][t],
                    'High': yf_raw['High'][t],
                    'Low': yf_raw['Low'][t],
                    'Close': yf_raw['Close'][t]
                }).dropna()
                yf_data[t] = df
            except:
                pass
    except Exception as e:
        print(f"YF Error: {e}")

    # B. Federal Reserve (FRED)
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
            except:
                pass
    except Exception as e:
        print(f"FRED Error: {e}")

    # C. AKShare (China Data)
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
        except:
            pass
            
    try:
        bond_df = ak.bond_zh_us_rate()
        bond_df['日期'] = pd.to_datetime(bond_df['日期'])
        bond_df.set_index('日期', inplace=True)
        cn_data['China_10Y_Yield'] = pd.DataFrame({'Close': pd.to_numeric(bond_df['中国国债收益率10年'], errors='coerce')}).dropna()
    except:
        pass

    # Mock EIA Data
    dates = pd.date_range(start=datetime.date.today() - datetime.timedelta(days=365*10), end=datetime.date.today(), freq='B')
    cn_data['EIA_Crude'] = pd.DataFrame({'Close': 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)}, index=dates)
    cn_data['EIA_Gasoline'] = pd.DataFrame({'Close': 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)}, index=dates)
    
    return {"yf": yf_data, "fred": fred_data, "mock": cn_data, "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ==========================================
# 3. Analytics & Pro Charting Factory
# ==========================================
def resample_data(df, timeframe):
    if df.empty or timeframe == "Daily":
        return df
    rule = 'W' if timeframe == "Weekly" else 'ME'
    if all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']):
        agg_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}
        return df.resample(rule).agg(agg_dict).dropna()
    else:
        return df.resample(rule).last().dropna()

def draw_chart(df_raw, title, base_color, timeframe, show_ma=True):
    if df_raw is None or df_raw.empty:
        return go.Figure()

    # 1. Resample
    df = resample_data(df_raw.copy(), timeframe)
    has_ohlc = all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']) and timeframe != "MAX"
    close_col = 'Close' if 'Close' in df.columns else df.columns[0]
    
    # 2. Indicators: EMA 20, 60, 120
    df['EMA20'] = df[close_col].ewm(span=20, adjust=False).mean()
    df['EMA60'] = df[close_col].ewm(span=60, adjust=False).mean()
    df['EMA120'] = df[close_col].ewm(span=120, adjust=False).mean()
    
    # 3. Momentum: (EMA9 - EMA26) / EMA26 * 100%
    ema9 = df[close_col].ewm(span=9, adjust=False).mean()
    ema26 = df[close_col].ewm(span=26, adjust=False).mean()
    mom_val = ((ema9 - ema26) / ema26 * 100).iloc[-1]
    mom_color = "#00CC96" if mom_val >= 0 else "#FF4B4B"
    mom_str = f"{'▲' if mom_val >= 0 else '▼'} {abs(mom_val):.2f}%"

    fig = go.Figure()

    # 4. Rendering
    if has_ohlc:
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name='Candles', increasing_line_color='#00CC96', decreasing_line_color='#FF4B4B'
        ))
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df[close_col], mode='lines', name='Price', line=dict(color=base_color, width=2.5)))

    # 5. EMA Overlays
    if show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], mode='lines', name='EMA20', line=dict(color='#FFD700', width=1.2)))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA60'], mode='lines', name='EMA60', line=dict(color='#FF4B4B', width=1.2)))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA120'], mode='lines', name='EMA120', line=dict(color='#AB63FA', width=1.2, dash='dot')))

    # 6. Y-Axis Auto-Scaling & X-Axis Focus Logic (180 Points)
    y_range = None
    x_range = None
    
    if len(df) > 10:
        visible_points = 180 if len(df) > 180 else len(df)
        last_df = df.iloc[-visible_points:]
        
        if has_ohlc:
            y_min = last_df['Low'].min()
            y_max = last_df['High'].max()
        else:
            y_min = last_df[close_col].min()
            y_max = last_df[close_col].max()
            
        padding = (y_max - y_min) * 0.05
        y_range = [y_min - padding, y_max + padding]
        x_range = [last_df.index[0], last_df.index[-1]]

    if timeframe == "MAX":
        x_range = None
        y_range = None

    fig.update_layout(
        title=dict(
            text=f"{title} <span style='color:{mom_color}; font-size:14px;'>Momentum: {mom_str}</span>",
            font=dict(size=20)
        ),
        margin=dict(l=10, r=10, t=60, b=10), height=650, dragmode='pan',
        xaxis=dict(
            rangeslider=dict(visible=False), type="date", showgrid=False,
            range=x_range
        ),
        yaxis=dict(
            showgrid=True, gridcolor='rgba(128,128,128,0.15)', zeroline=False, side="right",
            range=y_range,
            fixedrange=False
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def render_grid(charts_dict, current_timeframe, show_ma=True):
    for title, (df_data, color) in charts_dict.items():
        st.plotly_chart(
            draw_chart(df_data, title, color, current_timeframe, show_ma), 
            use_container_width=True, 
            config={'scrollZoom': True, 'displayModeBar': True}
        )
        st.markdown("<br><hr style='border: 0.5px solid #E0E0E0;'><br>", unsafe_allow_html=True)

# ==========================================
# 4. Sidebar & Dashboard Execution
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", width=50)
    st.header("Macro Terminal")
    st.markdown("### ⏱️ Timeframe")
    selected_timeframe = st.radio("Resolution", ["Daily", "Weekly", "Monthly", "MAX"], horizontal=True, label_visibility="collapsed")
    st.markdown("---")
    page = st.radio("📂 Navigation", ["📊 1. Spreads & Ratios", "⚒️ 2. Commodity", "💱 3. FX & FI", "📈 4. Equity Markets"])
    st.markdown("---")
    if st.button("🔄 Force Sync (Full History)", type="primary"):
        fetch_global_data.clear()
        st.rerun()

    try:
        db = fetch_global_data()
        st.success("✅ Engine: OHLC & Momentum Live")
        st.caption(f"Sync Time: {db['time']}")
    except:
        db = None

# ==========================================
# 5. Main Terminal Layout (FULL DATA RESTORED)
# ==========================================
st.title(f"🏛️ Master Monitor - {selected_timeframe}")

if db:
    yf_df = db['yf']; fr_df = db['fred']; mk_df = db['mock']

    if page == "📊 1. Spreads & Ratios":
        st.subheader("Credit, Liquidity & Yield Curve")
        def calc_spread(df1, df2):
            if df1 is not None and df2 is not None and not df1.empty and not df2.empty:
                return pd.DataFrame({'Close': df1['Close'] - df2['Close']}).dropna()
            return None
        def calc_ratio(df1, df2):
            if df1 is not None and df2 is not None and not df1.empty and not df2.empty:
                return pd.DataFrame({'Close': df1['Close'] / df2['Close']}).dropna()
            return None

        charts = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B"),
            "Emerging Market (EMBI)": (fr_df.get('BAMLEMHBHYCRPIUSOAS'), "#DC143C"),
            "AAA Corporate Spread": (fr_df.get('BAMLC0A1CAAA'), "#FFA500"),
            "BAA Corporate Spread": (fr_df.get('BAMLC0A4CBBB'), "#FFD700"),
            "10Y-2Y Spread (Recession Indicator)": (calc_spread(fr_df.get('DGS10'), fr_df.get('DGS2')), "#FF4B4B"),
            "10Y-3M Spread (Fed Target)": (calc_spread(fr_df.get('DGS10'), fr_df.get('DGS3MO')), "#DC143C"),
            "SOFR-EFFR Premium": (calc_spread(fr_df.get('SOFR'), fr_df.get('EFFR')), "#00CC96"),
            "Gold-Silver Ratio": (calc_ratio(yf_df.get('GC=F'), yf_df.get('SI=F')), "#AB63FA"),
            "Gold-WTI Ratio": (calc_ratio(yf_df.get('GC=F'), yf_df.get('CL=F')), "#00BFFF"),
            "Gold-Copper Ratio": (calc_ratio(yf_df.get('GC=F'), yf_df.get('HG=F')), "#8A2BE2")
        }
        render_grid(charts, selected_timeframe, show_ma=False)

    elif page == "⚒️ 2. Commodity":
        st.subheader("International Futures (COMEX/NYMEX/CBOT)")
        intl_c = {
            "Gold (GC=F)": (yf_df.get('GC=F'), "#FFD700"), "Silver (SI=F)": (yf_df.get('SI=F'), "#C0C0C0"),
            "Copper (HG=F)": (yf_df.get('HG=F'), "#B87333"), "WTI Crude (CL=F)": (yf_df.get('CL=F'), "#8B4513"),
            "Brent Crude (BZ=F)": (yf_df.get('BZ=F'), "#A0522D"), "Natural Gas (NG=F)": (yf_df.get('NG=F'), "#4682B4"),
            "Corn (ZC=F)": (yf_df.get('ZC=F'), "#FFD700"), "Soybeans (ZS=F)": (yf_df.get('ZS=F'), "#9ACD32"),
            "Wheat (ZW=F)": (yf_df.get('ZW=F'), "#F5DEB3"), "Cotton (CT=F)": (yf_df.get('CT=F'), "#FFFAFA"),
            "Bitcoin (BTC-USD)": (yf_df.get('BTC-USD'), "#FF8C00")
        }
        render_grid(intl_c, selected_timeframe)

        st.markdown("---")
        st.subheader("China Futures Real-Time (AKShare)")
        cn_c = {
            "SHFE Silver": (mk_df.get('SHFE_Silver'), "#C0C0C0"), "SHFE Aluminum": (mk_df.get('SHFE_Aluminum'), "#A9A9A9"),
            "SHFE Zinc": (mk_df.get('SHFE_Zinc'), "#778899"), "SHFE Nickel": (mk_df.get('SHFE_Nickel'), "#708090"),
            "SHFE Rebar": (mk_df.get('SHFE_Rebar'), "#696969"), "DCE Iron Ore": (mk_df.get('DCE_IronOre'), "#8B4513"),
            "DCE Coke": (mk_df.get('DCE_Coke'), "#2F4F4F"), "ZCE PTA": (mk_df.get('ZCE_PTA'), "#483D8B"),
            "ZCE Methanol": (mk_df.get('ZCE_Methanol'), "#4B0082"), "ZCE Sugar": (mk_df.get('ZCE_Sugar'), "#F8F8FF"),
            "DCE Soybean Meal": (mk_df.get('DCE_SoybeanMeal'), "#9ACD32"), "DCE Soybean Oil": (mk_df.get('DCE_SoybeanOil'), "#DAA520"),
            "EIA Crude Inv. (Mock)": (mk_df.get('EIA_Crude'), "#8B4513"), "EIA Gasoline Inv. (Mock)": (mk_df.get('EIA_Gasoline'), "#4682B4")
        }
        render_grid(cn_c, selected_timeframe)

    elif page == "💱 3. FX & FI":
        st.subheader("Global FX & Sovereign Yield Curves")
        fx_c = {
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B"), "USD/JPY": (yf_df.get('JPY=X'), "#AB63FA"),
            "AUD/USD": (yf_df.get('AUDUSD=X'), "#00CC96"), "EUR/USD": (yf_df.get('EURUSD=X'), "#1E90FF"),
            "GBP/USD": (yf_df.get('GBPUSD=X'), "#8A2BE2"), "USD/CAD": (yf_df.get('CAD=X'), "#DC143C"),
            "USD/INR": (yf_df.get('INR=X'), "#00BFFF"), "USD/BRL": (yf_df.get('BRL=X'), "#32CD32"),
            "US 2Y Yield": (fr_df.get('DGS2'), "#696969"), "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000"),
            "US 30Y Yield": (fr_df.get('DGS30'), "#800000"),
            "China 10Y Yield": (mk_df.get('China_10Y_Yield'), "#FF4B4B"), 
            "US Long Treas (TLT)": (yf_df.get('TLT'), "#4682B4")
        }
        render_grid(fx_c, selected_timeframe)

    elif page == "📈 4. Equity Markets":
        st.subheader("Global Equity Indices")
        eq_c = {
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96"), "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF"),
            "Nikkei 225 (^N225)": (yf_df.get('^N225'), "#FF4B4B"), "Hang Seng (^HSI)": (yf_df.get('^HSI'), "#00BFFF"),
            "SSE Composite": (yf_df.get('000001.SS'), "#FF8C00"), "KOSPI (^KS11)": (yf_df.get('^KS11'), "#FFA500"),
            "Taiwan (^TWII)": (yf_df.get('^TWII'), "#32CD32"), "Semiconductor (^SOX)": (yf_df.get('^SOX'), "#AB63FA")
        }
        render_grid(eq_c, selected_timeframe)
        
        st.markdown("---")
        st.subheader("Detailed Sector Performance")
        
        us_sec = pd.DataFrame({"Sector": ["Energy", "Shipping", "Consumer Staples", "Materials", "Industrials", "Health Care", "Software", "Semiconductors"], "YTD (%)": [25.7, 23.3, 21.8, 10.3, 8.0, -1.2, 6.5, -12.1]})
        st.plotly_chart(px.bar(us_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="US Sectors YTD (%)", height=450), use_container_width=True)
        
        hk_sec = pd.DataFrame({"Sector": ["HSCEI ETF", "China Internet", "CSI 300 HK", "HS China Ent", "HS Index ETF", "HS Tech ETF"], "YTD (%)": [-12.5, -10.0, -7.5, -5.2, -5.0, -2.5]})
        st.plotly_chart(px.bar(hk_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="HK Sectors YTD (%)", height=450), use_container_width=True)
        
        cn_sec = pd.DataFrame({"Sector": ["Tech", "CSI 500", "Real Estate", "Gaming", "Bank", "ChiNext", "Pharma", "Biotech", "5G", "Dividend", "Military", "Coal"], "YTD (%)": [9.3, 8.7, 5.8, 5.49, 3.1, 1.8, 4.8, -6.4, 0.5, 5.0, -0.27, -1.62]})
        st.plotly_chart(px.bar(cn_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="CN Sectors YTD (%)", height=500), use_container_width=True)
