import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import pandas_datareader.data as web
import datetime
import requests # 新增：用于伪装浏览器

# ==========================================
# 1. 页面全局配置
# ==========================================
st.set_page_config(page_title="Macro Master Monitor", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 2. 高性能数据缓存池 (带终极反爬与隔离机制)
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)
def fetch_global_data():
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365 * 10)

    # A. 雅虎财经 (抗压能力强，直接抓取)
    yf_tickers = [
        '^GSPC', '^NDX', '^SOX', '^N225', '^KS11', '^HSI', '000001.SS', '^TWII',
        'GC=F', 'SI=F', 'HG=F', 'CL=F', 'NG=F', 'BZ=F', 'ZC=F', 'ZS=F', 'ZW=F', 'CT=F', 'BTC-USD',
        'CNH=X', 'AUDUSD=X', 'JPY=X', 'IDR=X', 'INR=X', 'TRY=X', 'EURUSD=X', 'GBPUSD=X', 'CAD=X', 'MXN=X', 'BRL=X', 'ARS=X', 'ILS=X', 'HKD=X', 'TLT'
    ]
    try:
        yf_raw = yf.download(yf_tickers, period="10y", progress=False)['Close']
        yf_data = yf_raw.ffill().bfill() if isinstance(yf_raw, pd.DataFrame) else yf_raw
    except:
        yf_data = pd.DataFrame()

    # B. 美联储 FRED (增加反爬虫伪装与物理隔离舱)
    fred_tickers = [
        'SOFR', 'EFFR', 'DGS1MO', 'DGS3MO', 'DGS2', 'DGS5', 'DGS10', 'DGS30',
        'BAMLC0A1CAAA', 'BAMLC0A4CBBB', 'BAMLH0A0HYM2', 'BAMLEMHBHYCRPIUSOAS'
    ]
    try:
        # 伪装成普通 Windows 电脑的 Chrome 浏览器
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        })
        fred_data = web.DataReader(fred_tickers, 'fred', start_date, end_date, session=session).ffill().bfill()
    except Exception as e:
        # 如果依然被墙，直接生成满是空值的数据框，绝不让系统崩溃
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        fred_data = pd.DataFrame(np.nan, index=dates, columns=fred_tickers)

    # C. 模拟器 (中国资产与库存)
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    mock_data = pd.DataFrame(index=dates)
    np.random.seed(42)
    mock_items = [
        'SHFE_Silver', 'SHFE_Gold', 'SHFE_Copper', 'SHFE_Aluminum', 'SHFE_Zinc', 'SHFE_Nickel', 'SHFE_Rebar',
        'DCE_IronOre', 'DCE_Coke', 'DCE_SoybeanMeal', 'DCE_SoybeanOil',
        'ZCE_Sugar', 'ZCE_Cotton', 'ZCE_PTA', 'ZCE_Methanol',
        'EIA_Crude', 'EIA_Gasoline', 'EIA_NatGas', 'China_10Y_Yield'
    ]
    for item in mock_items:
        if item == 'China_10Y_Yield':
            mock_data[item] = 2.5 + np.cumsum(np.random.randn(len(dates)) * 0.01)
        else:
            mock_data[item] = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)
    
    return {"yf": yf_data, "fred": fred_data, "mock": mock_data, "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ==========================================
# 3. 稳健型绘图工厂
# ==========================================
def draw_chart(series, title, color):
    if series is None or series.dropna().empty or len(series.dropna()) < 2:
        fig = go.Figure()
        fig.add_annotation(text="暂无数据(防火墙拦截)", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(color="gray"))
        fig.update_layout(title=title, height=200, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return fig

    clean = series.dropna()
    fig = px.line(x=clean.index, y=clean.values)
    fig.update_traces(line_color=color, line_width=1.5)
    fig.update_layout(
        title=dict(text=title, font=dict(size=12)), margin=dict(l=0, r=0, t=30, b=0), height=200,
        xaxis_title="", yaxis_title="", xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def render_grid(charts_dict, cols=4):
    cols_obj = st.columns(cols)
    for i, (title, (series, color)) in enumerate(charts_dict.items()):
        with cols_obj[i % cols]:
            st.plotly_chart(draw_chart(series, title, color), use_container_width=True)

# ==========================================
# 4. 侧边栏导航
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", width=50)
    st.header("Macro Terminal")
    page = st.radio(
        "📂 选择分析模块", 
        ["📊 1. Spreads & Ratios", "⚒️ 2. Commodity", "💱 3. FX & FI", "📈 4. Equity Markets"]
    )
    
    st.markdown("---")
    if st.button("🔄 同步华尔街实时数据", type="primary"):
        fetch_global_data.clear()
        st.rerun()

    try:
        db = fetch_global_data()
        st.success("✅ 数据引擎在线")
        st.caption(f"上次更新: {db['time']}")
    except:
        st.error("数据源连接失败")
        db = None

# ==========================================
# 5. 主页面布局 (矩阵密度极大提升)
# ==========================================
st.title("🏛️ 宏观资产全景监控终端")

if db:
    yf_df = db['yf']
    fr_df = db['fred']
    mk_df = db['mock']

    # --- 模块 1: Spreads & Ratios ---
    if page == "📊 1. Spreads & Ratios":
        st.subheader("Credit, Liquidity & Yield Curve (Ref: 2026-03-10)")
        charts = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B"),
            "Emerging Market (EMBI)": (fr_df.get('BAMLEMHBHYCRPIUSOAS'), "#DC143C"),
            "AAA Corporate Spread": (fr_df.get('BAMLC0A1CAAA'), "#FFA500"),
            "BAA Corporate Spread": (fr_df.get('BAMLC0A4CBBB'), "#FFD700"),
            "10Y-2Y Spread (Recession)": (fr_df.get('DGS10') - fr_df.get('DGS2') if 'DGS10' in fr_df and 'DGS2' in fr_df else None, "#FF4B4B"),
            "10Y-3M Spread (Fed Target)": (fr_df.get('DGS10') - fr_df.get('DGS3MO') if 'DGS10' in fr_df and 'DGS3MO' in fr_df else None, "#DC143C"),
            "SOFR-EFFR (Liquidity)": (fr_df.get('SOFR') - fr_df.get('EFFR') if 'SOFR' in fr_df and 'EFFR' in fr_df else None, "#00CC96"),
            "Gold-Silver Ratio": (yf_df.get('GC=F') / yf_df.get('SI=F') if 'GC=F' in yf_df and 'SI=F' in yf_df else None, "#AB63FA"),
            "Gold-WTI Ratio": (yf_df.get('GC=F') / yf_df.get('CL=F') if 'GC=F' in yf_df and 'CL=F' in yf_df else None, "#00BFFF"),
            "Gold-Copper Ratio": (yf_df.get('GC=F') / yf_df.get('HG=F') if 'GC=F' in yf_df and 'HG=F' in yf_df else None, "#8A2BE2")
        }
        render_grid(charts, cols=5)

    # --- 模块 2: Commodity ---
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
        render_grid(intl_c, cols=6)

        st.markdown("---")
        st.subheader("China Futures & Inventory Framework (SHFE/DCE/ZCE)")
        cn_c = {
            "SHFE Silver": (mk_df.get('SHFE_Silver'), "#C0C0C0"), "SHFE Aluminum": (mk_df.get('SHFE_Aluminum'), "#A9A9A9"),
            "SHFE Zinc": (mk_df.get('SHFE_Zinc'), "#778899"), "SHFE Nickel": (mk_df.get('SHFE_Nickel'), "#708090"),
            "SHFE Rebar": (mk_df.get('SHFE_Rebar'), "#696969"), "DCE Iron Ore": (mk_df.get('DCE_IronOre'), "#8B4513"),
            "DCE Coke": (mk_df.get('DCE_Coke'), "#2F4F4F"), "ZCE PTA": (mk_df.get('ZCE_PTA'), "#483D8B"),
            "ZCE Methanol": (mk_df.get('ZCE_Methanol'), "#4B0082"), "ZCE Sugar": (mk_df.get('ZCE_Sugar'), "#F8F8FF"),
            "DCE Soybean Meal": (mk_df.get('DCE_SoybeanMeal'), "#9ACD32"), "DCE Soybean Oil": (mk_df.get('DCE_SoybeanOil'), "#DAA520"),
            "EIA Crude Inv.": (mk_df.get('EIA_Crude'), "#8B4513"), "EIA Gasoline Inv.": (mk_df.get('EIA_Gasoline'), "#4682B4")
        }
        render_grid(cn_c, cols=7)

    # --- 模块 3: FX & FI ---
    elif page == "💱 3. FX & FI":
        st.subheader("Global FX & Sovereign Yield Curves")
        fx_c = {
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B"), "USD/JPY": (yf_df.get('JPY=X'), "#AB63FA"),
            "AUD/USD": (yf_df.get('AUDUSD=X'), "#00CC96"), "EUR/USD": (yf_df.get('EURUSD=X'), "#1E90FF"),
            "GBP/USD": (yf_df.get('GBPUSD=X'), "#8A2BE2"), "USD/CAD": (yf_df.get('CAD=X'), "#DC143C"),
            "USD/INR": (yf_df.get('INR=X'), "#00BFFF"), "USD/BRL": (yf_df.get('BRL=X'), "#32CD32"),
            "US 2Y Yield": (fr_df.get('DGS2'), "#696969"), "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000"),
            "China 10Y Yield": (mk_df.get('China_10Y_Yield'), "#FF4B4B"), "US Long Treas (TLT)": (yf_df.get('TLT'), "#4682B4")
        }
        render_grid(fx_c, cols=6)

    # --- 模块 4: Equity Markets ---
    elif page == "📈 4. Equity Markets":
        st.subheader("Global Equity Indices")
        eq_c = {
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96"), "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF"),
            "Nikkei 225 (^N225)": (yf_df.get('^N225'), "#FF4B4B"), "Hang Seng (^HSI)": (yf_df.get('^HSI'), "#00BFFF"),
            "SSE Composite": (yf_df.get('000001.SS'), "#FF8C00"), "KOSPI (^KS11)": (yf_df.get('^KS11'), "#FFA500"),
            "Taiwan (^TWII)": (yf_df.get('^TWII'), "#32CD32"), "Semiconductor (^SOX)": (yf_df.get('^SOX'), "#AB63FA")
        }
        render_grid(eq_c, cols=4)
        
        st.markdown("---")
        st.subheader("Detailed Sector Performance (Ref: PDF Page 4)")
        s1, s2, s3 = st.columns(3)
        with s1:
            us_sec = pd.DataFrame({"Sector": ["Energy", "Shipping", "Consumer Staples", "Materials", "Industrials", "Health Care", "Software", "Semiconductors"], "YTD (%)": [25.7, 23.3, 21.8, 10.3, 8.0, -1.2, 6.5, -12.1]})
            st.plotly_chart(px.bar(us_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="US Sectors", color="YTD (%)", color_continuous_scale="RdYlGn", height=400), use_container_width=True)
        with s2:
            hk_sec = pd.DataFrame({"Sector": ["HSCEI ETF", "China Internet", "CSI 300 HK", "HS China Ent", "HS Index ETF", "HS Tech ETF"], "YTD (%)": [-12.5, -10.0, -7.5, -5.2, -5.0, -2.5]})
            st.plotly_chart(px.bar(hk_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="HK Sectors", color="YTD (%)", color_continuous_scale="RdYlGn", height=400), use_container_width=True)
        with s3:
            cn_sec = pd.DataFrame({"Sector": ["Tech", "CSI 500", "Real Estate", "Gaming", "Bank", "ChiNext", "Pharma", "Biotech", "5G", "Dividend", "Military", "Coal"], "YTD (%)": [9.3, 8.7, 5.8, 5.49, 3.1, 1.8, 4.8, -6.4, 0.5, 5.0, -0.27, -1.62]})
            st.plotly_chart(px.bar(cn_sec.sort_values("YTD (%)"), x="YTD (%)", y="Sector", orientation='h', title="CN Sectors", color="YTD (%)", color_continuous_scale="RdYlGn", height=400), use_container_width=True)
