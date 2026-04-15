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
        # 默认聚焦最近的 180 根 K 线
        visible_points = 180 if len(df) > 180 else len(df)
        last_df = df.iloc[-visible_points:]
        
        # 计算该视窗内的最高/最低价实现 Y 轴自适应
        if has_ohlc:
            y_min = last_df['Low'].min()
            y_max = last_df['High'].max()
        else:
            y_min = last_df[close_col].min()
            y_max = last_df[close_col].max()
            
        # 留出 5% 的边距空间
        padding = (y_max - y_min) * 0.05
        y_range = [y_min - padding, y_max + padding]
        x_range = [last_df.index[0], last_df.index[-1]]

    # MAX 模式下取消视窗限制，展示全局趋势
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
            fixedrange=False # 🚨 关键：允许用户在右侧 Y 轴上手动拉伸高度
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
    except:
        db = None

st.title(f"🏛️ Master Monitor - {selected_timeframe}")

if db:
    yf_df = db['yf']; fr_df = db['fred']; mk_df = db['mock']

    if page == "📊 1. Spreads & Ratios":
        def calc_spread(df1, df2):
            if df1 is not None and df2 is not None:
                return pd.DataFrame({'Close': df1['Close'] - df2['Close']}).dropna()
            return None
        charts = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B"),
            "10Y-2Y Spread": (calc_spread(fr_df.get('DGS10'), fr_df.get('DGS2')), "#FF4B4B"),
            "SOFR-EFFR Premium": (calc_spread(fr_df.get('SOFR'), fr_df.get('EFFR')), "#00CC96")
        }
        render_grid(charts, selected_timeframe, show_ma=False)

    elif page == "⚒️ 2. Commodity":
        intl_c = {
            "Gold (GC=F)": (yf_df.get('GC=F'), "#FFD700"), "WTI Crude (CL=F)": (yf_df.get('CL=F'), "#8B4513"),
            "SHFE Rebar": (mk_df.get('SHFE_Rebar'), "#696969"), "DCE Iron Ore": (mk_df.get('DCE_IronOre'), "#8B4513")
        }
        render_grid(intl_c, selected_timeframe)

    elif page == "💱 3. FX & FI":
        fx_c = {
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B"), "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000"),
            "China 10Y Yield": (mk_df.get('China_10Y_Yield'), "#FF4B4B")
        }
        render_grid(fx_c, selected_timeframe)

    elif page == "📈 4. Equity Markets":
        eq_c = {
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96"), "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF"),
            "Hang Seng (^HSI)": (yf_df.get('^HSI'), "#00BFFF")
        }
        render_grid(eq_c, selected_timeframe)
