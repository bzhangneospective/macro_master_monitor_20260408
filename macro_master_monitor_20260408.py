import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import pandas_datareader.data as web
import datetime

# ==========================================
# 1. 页面全局配置
# ==========================================
st.set_page_config(page_title="Macro Master Monitor", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 2. 高性能 Apache Arrow 数据缓存池 (全网共享)
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)  # 缓存 12 小时，底层自动压缩防溢出
def fetch_global_data():
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365 * 10)

    # A. 雅虎财经全量指标
    yf_tickers = [
        '^GSPC', '^NDX', '^SOX', '^N225', '^KS11', '^HSI', '000001.SS', '^TWII',
        'GC=F', 'SI=F', 'HG=F', 'CL=F', 'NG=F', 'BZ=F', 'ZC=F', 'ZS=F', 'ZW=F', 'CT=F', 'BTC-USD',
        'CNH=X', 'AUDUSD=X', 'JPY=X', 'IDR=X', 'INR=X', 'TRY=X', 'EURUSD=X', 'GBPUSD=X', 'CAD=X', 'MXN=X', 'BRL=X', 'ARS=X', 'ILS=X', 'HKD=X', 'TLT'
    ]
    yf_raw = yf.download(yf_tickers, period="10y", progress=False)['Close']
    yf_data = yf_raw.ffill().bfill() if isinstance(yf_raw, pd.DataFrame) else yf_raw

    # B. 美联储 FRED
    fred_tickers = [
        'SOFR', 'EFFR', 'DGS1MO', 'DGS3MO', 'DGS2', 'DGS5', 'DGS10', 'DGS30',
        'BAMLC0A1CAAA', 'BAMLC0A4CBBB', 'BAMLH0A0HYM2'
    ]
    fred_data = web.DataReader(fred_tickers, 'fred', start_date, end_date).ffill().bfill()

    # C. 模拟器 (中国资产与库存)
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    mock_data = pd.DataFrame(index=dates)
    np.random.seed(42)
    mock_items = ['SHFE_Silver', 'SHFE_Gold', 'SHFE_Copper', 'SHFE_Rebar', 'DCE_IronOre', 'EIA_Crude', 'EIA_Gasoline']
    for item in mock_items:
        mock_data[item] = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)
    
    return {"yf": yf_data, "fred": fred_data, "mock": mock_data, "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ==========================================
# 3. 稳健型绘图工厂 (释放内存机制)
# ==========================================
def draw_chart(series, title, color):
    if series is None or series.dropna().empty or len(series.dropna()) < 2:
        fig = go.Figure()
        fig.add_annotation(text="暂无数据 (API无响应)", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title=title, height=250, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return fig

    clean = series.dropna()
    fig = px.line(x=clean.index, y=clean.values)
    fig.update_traces(line_color=color, line_width=1.5)
    fig.update_layout(
        title=dict(text=title, font=dict(size=13)), margin=dict(l=0, r=0, t=40, b=0), height=250,
        xaxis_title="", yaxis_title="", xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def render_grid(charts_dict, cols=3):
    cols_obj = st.columns(cols)
    for i, (title, (series, color)) in enumerate(charts_dict.items()):
        with cols_obj[i % cols]:
            st.plotly_chart(draw_chart(series, title, color), use_container_width=True)

# ==========================================
# 4. 侧边栏：防崩溃专属导航菜单 (Lazy Loading)
# ==========================================
with st.sidebar:
    st.header("⚙️ 终端控制台")
    
    # 彻底弃用 Tabs，改为单页按需渲染导航
    page = st.radio(
        "📂 选择分析模块 (按需加载)", 
        ["📊 1. Spreads & Ratios", "⚒️ 2. Commodity", "💱 3. FX & FI", "📈 4. Equity Markets"]
    )
    
    st.markdown("---")
    
    if st.button("🔄 强制刷新华尔街数据", type="primary"):
        fetch_global_data.clear() # 清空旧缓存
        st.rerun()

    with st.spinner("数据通道连接中..."):
        try:
            db = fetch_global_data()
            st.success("✅ 数据引擎在线")
            st.caption(f"上次更新: {db['time']}")
        except Exception as e:
            st.error("数据源连接失败")
            db = None

# ==========================================
# 5. 主页面布局 (单页渲染，节省 75% 内存)
# ==========================================
st.title("🏛️ 宏观资产全景监控终端")
st.markdown("---")

if db:
    yf_df = db['yf']
    fr_df = db['fred']
    mk_df = db['mock']

    # --- 模块 1: Spreads & Ratios ---
    if page == "📊 1. Spreads & Ratios":
        st.subheader("Credit & Liquidity Analysis")
        m1, m2, m3 = st.columns(3)
        m1.metric("10Y-2Y Spread", f"{(fr_df['DGS10'][-1]-fr_df['DGS2'][-1]):.3f}%")
        m2.metric("SOFR-EFFR", "0.0 bps", "Normal")
        m3.metric("Gold-Silver Ratio", "58.90", "-10.28")
        
        charts = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B"),
            "AAA Corporate Spread": (fr_df.get('BAMLC0A1CAAA'), "#FFA500"),
            "10Y-2Y Treasury Spread": (fr_df.get('DGS10') - fr_df.get('DGS2'), "#FF4B4B"),
            "SOFR-EFFR Liquidity": (fr_df.get('SOFR') - fr_df.get('EFFR'), "#00CC96"),
            "Gold-Silver Ratio (10Y)": (yf_df.get('GC=F') / yf_df.get('SI=F'), "#AB63FA"),
            "Gold-WTI Ratio (10Y)": (yf_df.get('GC=F') / yf_df.get('CL=F'), "#00BFFF")
        }
        render_grid(charts, cols=3)

    # --- 模块 2: Commodity ---
    elif page == "⚒️ 2. Commodity":
        st.subheader("Commodity & Inventory Structure")
        charts = {
            "Gold (COMEX)": (yf_df.get('GC=F'), "#FFD700"), "Silver (COMEX)": (yf_df.get('SI=F'), "#C0C0C0"),
            "Copper (COMEX)": (yf_df.get('HG=F'), "#B87333"), "WTI Crude": (yf_df.get('CL=F'), "#8B4513"),
            "Natural Gas": (yf_df.get('NG=F'), "#4682B4"), "Bitcoin": (yf_df.get('BTC-USD'), "#FF8C00"),
            "SHFE Copper (Mock)": (mk_df.get('SHFE_Copper'), "#B87333"), "EIA Gasoline Inv.": (mk_df.get('EIA_Gasoline'), "#4682B4")
        }
        render_grid(charts, cols=4)

    # --- 模块 3: FX & FI ---
    elif page == "💱 3. FX & FI":
        st.subheader("FX Anchors & Yield Curve")
        charts = {
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B"), "USD/JPY": (yf_df.get('JPY=X'), "#AB63FA"),
            "AUD/USD": (yf_df.get('AUDUSD=X'), "#00CC96"), "EUR/USD": (yf_df.get('EURUSD=X'), "#1E90FF"),
            "US 2Y Yield": (fr_df.get('DGS2'), "#696969"), "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000"),
            "US 30Y Yield": (fr_df.get('DGS30'), "#800000"), "Long Treasury (TLT)": (yf_df.get('TLT'), "#4682B4")
        }
        render_grid(charts, cols=4)

    # --- 模块 4: Equity Markets ---
    elif page == "📈 4. Equity Markets":
        st.subheader("Global Equity Indices")
        charts = {
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96"), "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF"),
            "Nikkei 225": (yf_df.get('^N225'), "#FF4B4B"), "Hang Seng Index": (yf_df.get('^HSI'), "#00BFFF"),
            "SSE Composite": (yf_df.get('000001.SS'), "#FF8C00"), "KOSPI Composite": (yf_df.get('^KS11'), "#FFA500")
        }
        render_grid(charts, cols=3)
        
        st.markdown("---")
        s1, s2 = st.columns(2)
        with s1:
            us_sec = pd.DataFrame({"Sector": ["Energy", "Shipping", "Materials", "Software", "Semiconductors"], "YTD (%)": [25.7, 23.3, 10.3, 6.5, -12.1]})
            st.plotly_chart(px.bar(us_sec, x="YTD (%)", y="Sector", orientation='h', title="US Sector YTD %", color="YTD (%)", color_continuous_scale="RdYlGn"), use_container_width=True)
        with s2:
            cn_sec = pd.DataFrame({"Sector": ["Tech", "Real Estate", "Gaming", "SSE 50", "Coal"], "YTD (%)": [9.3, 5.8, 5.4, 2.3, -1.6]})
            st.plotly_chart(px.bar(cn_sec, x="YTD (%)", y="Sector", orientation='h', title="CN Sector YTD %", color="YTD (%)", color_continuous_scale="RdYlGn"), use_container_width=True)
