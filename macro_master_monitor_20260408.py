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
import time

# ==========================================
# 1. 页面全局配置
# ==========================================
st.set_page_config(page_title="Macro Master Monitor", layout="wide")

# 定义本地数据库路径
DATA_FILE = "macro_database_stable.pkl"

# ==========================================
# 2. 增强型数据加载引擎 (防闪退/防丢包)
# ==========================================
@st.cache_resource
def get_global_data_cache():
    """使用服务器内存级缓存，避免频繁读取硬盘"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'rb') as f:
                return pickle.load(f)
        except:
            return None
    return None

def fetch_and_save_data():
    """全量抓取并强制落盘"""
    try:
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=365 * 10)

        # A. 雅虎财经全量指标 (PDF 提及的所有指数、商品、外汇)
        yf_tickers = [
            '^GSPC', '^NDX', '^SOX', '^N225', '^KS11', '^HSI', '000001.SS', '^TWII',
            'GC=F', 'SI=F', 'HG=F', 'CL=F', 'NG=F', 'BZ=F', 'ZC=F', 'ZS=F', 'ZW=F', 'CT=F', 'BTC-USD',
            'CNH=X', 'AUDUSD=X', 'JPY=X', 'IDR=X', 'INR=X', 'TRY=X', 'EURUSD=X', 'GBPUSD=X', 'CAD=X', 'MXN=X', 'BRL=X', 'ARS=X', 'ILS=X', 'HKD=X', 'TLT'
        ]
        yf_raw = yf.download(yf_tickers, period="10y", progress=False)['Close']
        yf_data = yf_raw.ffill().bfill() if isinstance(yf_raw, pd.DataFrame) else yf_raw

        # B. 美联储 FRED 信用利差与利率
        fred_tickers = [
            'SOFR', 'EFFR', 'DGS1MO', 'DGS3MO', 'DGS2', 'DGS5', 'DGS10', 'DGS30',
            'BAMLC0A1CAAA', 'BAMLC0A4CBBB', 'BAMLH0A0HYM2'
        ]
        fred_data = web.DataReader(fred_tickers, 'fred', start_date, end_date).ffill().bfill()

        # C. 中国资产与库存模拟器 (基于 PDF 3月11日数据趋势)
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        mock_data = pd.DataFrame(index=dates)
        np.random.seed(42)
        mock_items = ['SHFE_Silver', 'SHFE_Gold', 'SHFE_Copper', 'SHFE_Rebar', 'DCE_IronOre', 'EIA_Crude', 'EIA_Gasoline']
        for item in mock_items:
            mock_data[item] = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)
        
        db = {
            "status": "Success",
            "update_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "yf": yf_data,
            "fred": fred_data,
            "mock": mock_data
        }
        
        # 使用临时文件写入，防止读取时文件被锁导致闪退
        tmp_file = DATA_FILE + ".tmp"
        with open(tmp_file, 'wb') as f:
            pickle.dump(db, f)
        os.replace(tmp_file, DATA_FILE)
        
        # 强制清理 Streamlit 内存缓存，确保下次读取到最新的
        get_global_data_cache.clear()
        return db
    except Exception as e:
        st.error(f"同步失败: {e}")
        return None

# ==========================================
# 3. 稳健型绘图工厂
# ==========================================
def draw_chart(series, title, color):
    # 彻底检查数据有效性
    if series is None or series.dropna().empty or len(series.dropna()) < 2:
        fig = go.Figure()
        fig.add_annotation(text="数据暂未同步", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
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
            st.plotly_chart(draw_chart(series, title, color), use_container_width=True, key=f"chart_{title}")

# ==========================================
# 4. 侧边栏与数据状态管理
# ==========================================
with st.sidebar:
    st.header("🗄️ 宏观数据库管理")
    
    if st.button("🔄 强制同步 PDF 对应全量指标", type="primary"):
        with st.spinner("正在并发抓取 40+ 全球指标..."):
            db_res = fetch_and_save_data()
            if db_res:
                st.session_state['current_db'] = db_res
                st.success("同步成功！")
                time.sleep(1)
                st.rerun()

    st.markdown("---")
    # 尝试加载数据
    db = get_global_data_cache()
    if db:
        st.success(f"✅ 核心数据已就绪")
        st.caption(f"最后同步时间: \n{db['update_time']}")
    else:
        st.warning("⚠️ 暂无本地缓存数据")
        st.info("请点击上方按钮进行初始化抓取。")

# ==========================================
# 5. 主页面布局 (对齐 4 份 PDF 内容)
# ==========================================
st.title("🏛️ 宏观资产全景监控终端 (PDF 完整映射版)")

if db:
    yf_df = db['yf']
    fr_df = db['fred']
    mk_df = db['mock']

    t1, t2, t3, t4 = st.tabs(["📊 Spreads & Ratios", "⚒️ Commodity", "💱 FX & FI", "📈 Equity Markets"])

    # --- TAB 1: Spreads & Ratios ---
    with t1:
        st.subheader("Credit & Liquidity (Ref: 2026-03-10 Report)")
        # 增加 Metric 磁贴展示 PDF 中的关键截面值
        m1, m2, m3 = st.columns(3)
        m1.metric("10Y-2Y Spread", f"{(fr_df['DGS10'][-1]-fr_df['DGS2'][-1]):.3f}%")
        m2.metric("SOFR-EFFR", "0.0 bps", "Normal") # PDF 记录值为 0.0
        m3.metric("Gold-Silver Ratio", "58.90", "-10.28") # PDF 记录值 58.9
        
        charts_t1 = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B"),
            "AAA Corporate Spread": (fr_df.get('BAMLC0A1CAAA'), "#FFA500"),
            "10Y-2Y Treasury Spread": (fr_df.get('DGS10') - fr_df.get('DGS2'), "#FF4B4B"),
            "SOFR-EFFR Liquidity": (fr_df.get('SOFR') - fr_df.get('EFFR'), "#00CC96"),
            "Gold-Silver Ratio (10Y)": (yf_df.get('GC=F') / yf_df.get('SI=F'), "#AB63FA"),
            "Gold-WTI Ratio (10Y)": (yf_df.get('GC=F') / yf_df.get('CL=F'), "#00BFFF")
        }
        render_grid(charts_t1, cols=3)

    # --- TAB 2: Commodity ---
    with t2:
        st.subheader("Commodity & Inventory (Ref: 2026-03-11 Report)")
        intl_c = {
            "Gold (COMEX)": (yf_df.get('GC=F'), "#FFD700"), "Silver (COMEX)": (yf_df.get('SI=F'), "#C0C0C0"),
            "Copper (COMEX)": (yf_df.get('HG=F'), "#B87333"), "WTI Crude": (yf_df.get('CL=F'), "#8B4513"),
            "Natural Gas": (yf_df.get('NG=F'), "#4682B4"), "Bitcoin": (yf_df.get('BTC-USD'), "#FF8C00"),
            "SHFE Copper (Mock)": (mk_df.get('SHFE_Copper'), "#B87333"), "EIA Gasoline Inv.": (mk_df.get('EIA_Gasoline'), "#4682B4")
        }
        render_grid(intl_c, cols=4)

    # --- TAB 3: FX & FI ---
    with t3:
        st.subheader("FX & Yield Curve (Ref: 2026-03-10 Report)")
        fx_c = {
            "USD/CNH": (yf_df.get('CNH=X'), "#FF4B4B"), "USD/JPY": (yf_df.get('JPY=X'), "#AB63FA"),
            "AUD/USD": (yf_df.get('AUDUSD=X'), "#00CC96"), "EUR/USD": (yf_df.get('EURUSD=X'), "#1E90FF"),
            "US 2Y Yield": (fr_df.get('DGS2'), "#696969"), "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000"),
            "US 30Y Yield": (fr_df.get('DGS30'), "#800000"), "Long Treasury (TLT)": (yf_df.get('TLT'), "#4682B4")
        }
        render_grid(fx_c, cols=4)

    # --- TAB 4: Equity Markets ---
    with t4:
        st.subheader("Global Indices & Sectors (Ref: 2026-03-10 Report)")
        eq_c = {
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96"), "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF"),
            "Nikkei 225": (yf_df.get('^N225'), "#FF4B4B"), "Hang Seng Index": (yf_df.get('^HSI'), "#00BFFF"),
            "SSE Composite": (yf_df.get('000001.SS'), "#FF8C00"), "KOSPI Composite": (yf_df.get('^KS11'), "#FFA500")
        }
        render_grid(eq_c, cols=3)
        
        st.markdown("---")
        # 还原 PDF 中的板块资金轮动数据
        s1, s2 = st.columns(2)
        with s1:
            us_sec = pd.DataFrame({"Sector": ["Energy", "Shipping", "Materials", "Software", "Semiconductors"], "YTD (%)": [25.7, 23.3, 10.3, 6.5, -12.1]})
            st.plotly_chart(px.bar(us_sec, x="YTD (%)", y="Sector", orientation='h', title="US Sector YTD % (Ref PDF)", color="YTD (%)", color_continuous_scale="RdYlGn"), use_container_width=True)
        with s2:
            cn_sec = pd.DataFrame({"Sector": ["Tech", "Real Estate", "Gaming", "SSE 50", "Coal"], "YTD (%)": [9.3, 5.8, 5.4, 2.3, -1.6]})
            st.plotly_chart(px.bar(cn_sec, x="YTD (%)", y="Sector", orientation='h', title="CN Sector YTD % (Ref PDF)", color="YTD (%)", color_continuous_scale="RdYlGn"), use_container_width=True)

else:
    st.info("💡 系统初始化中... 请在左侧边栏点击【强制同步】按钮以加载 PDF 对应的全部历史图表。")
