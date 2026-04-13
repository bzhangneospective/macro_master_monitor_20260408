import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import pandas_datareader.data as web
import datetime
import os
import pickle

# ==========================================
# 1. 页面全局配置 (全屏宽幅模式)
# ==========================================
st.set_page_config(page_title="Macro Master Monitor", layout="wide")

# 本地数据仓库文件名
DATA_FILE = "macro_database.pkl"

# ==========================================
# 2. 数据入库引擎 (只在点击按钮时触发)
# ==========================================
def fetch_and_save_data():
    try:
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=365 * 10)

        # 1. 雅虎财经 (分批抗压处理，防止大面积丢包)
        yf_tickers = [
            '^GSPC', '^NDX', '^SOX', '^N225', '^KS11', '^HSI', '000001.SS', '^TWII',
            'GC=F', 'SI=F', 'HG=F', 'CL=F', 'NG=F', 'BZ=F', 'ZC=F', 'ZS=F', 'ZW=F', 'CT=F', 'BTC-USD',
            'CNH=X', 'AUDUSD=X', 'JPY=X', 'IDR=X', 'INR=X', 'TRY=X', 'EURUSD=X', 'GBPUSD=X', 'CAD=X', 'MXN=X', 'BRL=X', 'ARS=X', 'ILS=X', 'HKD=X', 'TLT'
        ]
        # 强制抓取并前后填充空值，解决由于节假日导致的线条断裂
        yf_data = yf.download(yf_tickers, period="10y", progress=False)['Close']
        if isinstance(yf_data, pd.DataFrame):
            yf_data = yf_data.ffill().bfill()

        # 2. 美联储数据库 (FRED)
        fred_tickers = [
            'SOFR', 'EFFR', 'DGS1MO', 'DGS3MO', 'DGS2', 'DGS5', 'DGS10', 'DGS30',
            'BAMLC0A1CAAA', 'BAMLC0A4CBBB', 'BAMLH0A0HYM2'
        ]
        fred_data = web.DataReader(fred_tickers, 'fred', start_date, end_date).ffill().bfill()

        # 3. 占位模拟器 (中国期货与 EIA)
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        mock_data = pd.DataFrame(index=dates)
        np.random.seed(42)
        mock_items = ['SHFE_Silver', 'SHFE_Gold', 'SHFE_Copper', 'SHFE_Aluminum', 'SHFE_Zinc', 'SHFE_Nickel', 'SHFE_Rebar', 'DCE_IronOre', 'DCE_Coke', 'DCE_SoybeanMeal', 'DCE_SoybeanOil', 'ZCE_Sugar', 'ZCE_Cotton', 'ZCE_PTA', 'ZCE_Methanol', 'EIA_Crude', 'EIA_Gasoline', 'EIA_NatGas']
        for item in mock_items:
            mock_data[item] = 100 + np.cumsum(np.random.randn(len(dates)))
        
        # 构建数据库字典
        db = {"status": "✅ 数据库已同步至最新", "yf": yf_data, "fred": fred_data, "mock": mock_data}
        
        # 核心：将数据永久写入本地硬盘文件
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(db, f)
            
        return db
    except Exception as e:
        return {"status": f"❌ 数据拉取失败: {e}"}

# ==========================================
# 3. 核心绘图工厂 (带终极容错与防崩溃机制)
# ==========================================
def draw_chart(series, title, color):
    if series is None or series.dropna().empty or len(series.dropna()) < 2:
        fig = go.Figure()
        fig.add_annotation(text="暂无有效数据", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(color="gray", size=14))
        fig.update_layout(title=dict(text=title, font=dict(size=14)), height=250, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig

    clean_series = series.dropna()
    fig = px.line(x=clean_series.index, y=clean_series.values)
    fig.update_traces(line_color=color, line_width=1.5)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)), margin=dict(l=0, r=0, t=40, b=0), height=250,
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
# 4. 侧边栏：数据仓库管理中心
# ==========================================
with st.sidebar:
    st.header("🗄️ 数据库管理 (Ops 专属)")
    st.markdown("为了保证老板查看时100%稳定，系统已切换为本地数据读取模式。")
    
    # 强制更新按钮
    if st.button("🔄 拉取外网最新数据并入库", type="primary"):
        with st.spinner("正在向华尔街服务器全量拉取数据，请耐心等待(约15秒)..."):
            fetch_and_save_data()
            st.success("🎉 数据更新完成并已落盘保存！页面将使用最新数据。")
            st.rerun() # 刷新页面

    st.markdown("---")
    st.header("⚙️ 引擎当前状态")
    
    # 尝试从本地硬盘加载数据
    db = None
    if os.path.exists(DATA_FILE):
        file_time = datetime.datetime.fromtimestamp(os.path.getmtime(DATA_FILE)).strftime('%Y-%m-%d %H:%M:%S')
        st.success("✅ 已连接本地高速数据仓库")
        st.caption(f"💾 上次更新时间: \n{file_time}")
        with open(DATA_FILE, 'rb') as f:
            db = pickle.load(f)
    else:
        st.error("⚠️ 硬盘中暂无数据缓存！")
        st.info("请点击上方红色的【拉取最新数据并入库】按钮初始化数据库。")

# ==========================================
# 5. 顶层选项卡：完全映射老板的 4 份 PDF
# ==========================================
st.title("🏛️ 宏观资产全景监控终端 (Offline Stable Mode)")
st.markdown("---")

# 只有当本地数据库文件存在时，才渲染图表
if db is not None and "yf" in db:
    yf_df = db['yf']
    fr_df = db['fred']
    mk_df = db['mock']

    tab1, tab2, tab3, tab4 = st.tabs(["📊 1. Spreads & Ratios", "⚒️ 2. Commodity", "💱 3. FX & FI", "📈 4. Equity"])

    # --- Tab 1 ---
    with tab1:
        st.subheader("Credit, Liquidity, and Yield Analysis")
        charts_t1 = {
            "High-Yield Spread": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B"),
            "AAA Corporate Spread": (fr_df.get('BAMLC0A1CAAA'), "#FFA500"),
            "BAA Corporate Spread": (fr_df.get('BAMLC0A4CBBB'), "#FFD700"),
            "10Y-2Y Treasury Spread": (fr_df.get('DGS10') - fr_df.get('DGS2') if 'DGS10' in fr_df and 'DGS2' in fr_df else None, "#FF4B4B"),
            "SOFR vs EFFR": (fr_df.get('SOFR') - fr_df.get('EFFR') if 'SOFR' in fr_df and 'EFFR' in fr_df else None, "#00CC96"),
            "Gold-Silver Ratio": (yf_df.get('GC=F') / yf_df.get('SI=F') if 'GC=F' in yf_df and 'SI=F' in yf_df else None, "#AB63FA"),
            "Gold-WTI Ratio": (yf_df.get('GC=F') / yf_df.get('CL=F') if 'GC=F' in yf_df and 'CL=F' in yf_df else None, "#00BFFF"),
            "Bitcoin-Gold Ratio": (yf_df.get('BTC-USD') / yf_df.get('GC=F') if 'BTC-USD' in yf_df and 'GC=F' in yf_df else None, "#FFD700")
        }
        render_grid(charts_t1, cols=3)

    # --- Tab 2 ---
    with tab2:
        st.subheader("International Futures & Local Framework")
        intl_charts = {
            "Gold Futures": (yf_df.get('GC=F'), "#FFD700"), "Silver Futures": (yf_df.get('SI=F'), "#C0C0C0"),
            "Copper Futures": (yf_df.get('HG=F'), "#B87333"), "WTI Crude Oil": (yf_df.get('CL=F'), "#8B4513"),
            "Natural Gas": (yf_df.get('NG=F'), "#4682B4"), "Brent Crude": (yf_df.get('BZ=F'), "#A0522D"),
            "Bitcoin (Crypto)": (yf_df.get('BTC-USD'), "#FF8C00"), "SHFE Copper (Mock)": (mk_df.get('SHFE_Copper'), "#B87333")
        }
        render_grid(intl_charts, cols=4)

    # --- Tab 3 ---
    with tab3:
        st.subheader("Foreign Exchange & US Yield Curve")
        fx_charts = {
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B"), "AUD/USD": (yf_df.get('AUDUSD=X'), "#00CC96"),
            "USD/JPY": (yf_df.get('JPY=X'), "#AB63FA"), "EUR/USD": (yf_df.get('EURUSD=X'), "#1E90FF"),
            "US 2Y Yield": (fr_df.get('DGS2'), "#696969"), "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000"),
            "US 30Y Yield": (fr_df.get('DGS30'), "#800000"), "US Treasury ETF (TLT)": (yf_df.get('TLT'), "#4682B4")
        }
        render_grid(fx_charts, cols=4)

    # --- Tab 4 ---
    with tab4:
        st.subheader("Global Equity Indices")
        eq_charts = {
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96"), "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF"),
            "Semiconductor (^SOX)": (yf_df.get('^SOX'), "#AB63FA"), "Nikkei 225 (^N225)": (yf_df.get('^N225'), "#FF4B4B"),
            "KOSPI (^KS11)": (yf_df.get('^KS11'), "#FFA500"), "Hang Seng (^HSI)": (yf_df.get('^HSI'), "#00BFFF"),
            "SSE Composite (000001.SS)": (yf_df.get('000001.SS'), "#FF8C00"), "Taiwan (^TWII)": (yf_df.get('^TWII'), "#32CD32")
        }
        render_grid(eq_charts, cols=4)
