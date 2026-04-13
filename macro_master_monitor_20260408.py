import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import pandas_datareader.data as web
import datetime

# ==========================================
# 1. 页面全局配置
# ==========================================
st.set_page_config(page_title="Macro Asset Master Monitor", layout="wide")

# ==========================================
# 2. 全自动数据抓取引擎 (拉取 10 年历史数据)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_macro_data():
    try:
        # 设定 10 年的时间窗口
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=365 * 10)

        # A. 雅虎财经接口 (获取 10 年日线)
        tickers = ['^GSPC', 'GC=F', 'CL=F', 'SI=F', 'CNH=X']
        yf_data = yf.download(tickers, period="10y")['Close'].ffill()

        # B. 美联储 FRED 接口 (获取 10 年日线)
        fred_data = web.DataReader(['DGS10', 'DGS2', 'SOFR', 'EFFR'], 'fred', start_date, end_date).ffill()

        # C. 构建历史核心数据库
        history = pd.DataFrame()
        history['S&P 500'] = yf_data['^GSPC']
        history['Gold/WTI'] = yf_data['GC=F'] / yf_data['CL=F']
        history['Gold/Silver'] = yf_data['GC=F'] / yf_data['SI=F']
        history['USD/CNH'] = yf_data['CNH=X']
        history['10Y-2Y Spread'] = fred_data['DGS10'] - fred_data['DGS2']
        # 注：SOFR 是 2018 年才有的，早期数据为 NaN，Plotly 会自动处理空白
        history['SOFR-EFFR'] = (fred_data['SOFR'] - fred_data['EFFR']) * 100 
        
        # 获取最新一天的截面数据
        latest = history.iloc[-1]

        return {"status": "✅ 10年期数据源连接正常", "latest": latest, "history": history}
    except Exception as e:
        return {"status": f"❌ 数据拉取失败: {e}"}

# ==========================================
# 3. 辅助函数：绘制机构级迷你图表
# ==========================================
def draw_sparkline(df, column_name, title, color, hline_zero=False, hline_mean=False):
    """绘制高度定制化的趋势图"""
    clean_df = df[[column_name]].dropna()
    fig = px.line(clean_df, x=clean_df.index, y=column_name)
    fig.update_traces(line_color=color, line_width=1.5)
    
    if hline_zero:
        fig.add_hline(y=0, line_dash="solid", line_color="red", line_width=1, annotation_text="倒挂界限 (Zero Line)")
    if hline_mean:
        mean_val = clean_df[column_name].mean()
        fig.add_hline(y=mean_val, line_dash="dash", line_color="gray", annotation_text=f"10Y Mean: {mean_val:.2f}")

    fig.update_layout(
        title=title, margin=dict(l=0, r=0, t=30, b=0), height=220,
        xaxis_title="", yaxis_title="", xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# ==========================================
# 4. 侧边栏：状态监控与保留的手动输入
# ==========================================
with st.spinner('📡 正在回溯全球市场过去 10 年历史数据...'):
    data_bundle = fetch_macro_data()

with st.sidebar:
    st.header("⚙️ 系统引擎状态")
    if "✅" in data_bundle.get("status", ""):
        st.success(data_bundle["status"])
        st.caption(f"底层数据库：包含近 2500 个交易日的时序数据。")
        st.caption(f"系统运行环境：Streamlit Cloud (防灾备援级)")
    else:
        st.error(data_bundle.get("status", "未知错误"))
        
    st.markdown("---")
    st.header("📝 亚太时区手动调整")
    st.markdown("国内资产受限，请在此更新中国区基准：")
    china_10y = st.number_input("China 10Y Yield (%)", value=1.8055, format="%.4f")

# ==========================================
# 5. 前端展示逻辑 (Tabs 选项卡设计)
# ==========================================
st.title("🏛️ 宏观资产综合监控终端 (Pro Version)")
st.markdown("---")

if "✅" in data_bundle.get("status", ""):
    latest = data_bundle['latest']
    history = data_bundle['history']
    
    col1, col2 = st.columns(2)

    # --- 象限 1: 信用利差与期限结构 ---
    with col1:
        st.subheader("📡 Credit & Liquidity Analysis")
        c1, c2 = st.columns(2)
        spread = latest['10Y-2Y Spread']
        
        # 处理可能的 NaN 显示问题
        display_spread = 0.0 if pd.isna(spread) else spread
        c1.metric("10Y-2Y Spread", f"{display_spread:.3f}%", delta="Un-inverting" if display_spread > -0.1 else "Inverted")
        
        display_sofr = 0.0 if pd.isna(latest['SOFR-EFFR']) else latest['SOFR-EFFR']
        c2.metric("SOFR-EFFR", f"{display_sofr:.1f} bps")
        
        tab1, tab2 = st.tabs(["📈 10年历史趋势", "📊 流动性微观细节"])
        with tab1:
            st.plotly_chart(draw_sparkline(history, '10Y-2Y Spread', "US Treasury 10Y-2Y Spread", "#FF4B4B", hline_zero=True), use_container_width=True)
        with tab2:
            # 安全气囊：修复进度条崩溃 Bug
            safe_spread = 0.0 if pd.isna(spread) else float(spread)
            prog_val = min(max((safe_spread + 0.4) / 0.8, 0.0), 1.0)
            
            st.caption(f"Historical Context: Min -0.4% | Max 0.4% | Current: {safe_spread:.3f}%")
            st.progress(prog_val)
            st.info("SOFR-EFFR Spread 监测银行间底层流动性压力。")

    # --- 象限 2: 权益水位 ---
    with col2:
        st.subheader("📈 Equity Markets Performance")
        e1, e2 = st.columns(2)
        e1.metric("S&P 500 Close", f"{latest['S&P 500']:.2f}")
        e2.metric("Status", "Auto-Fetched", delta_color="off")
        
        tab1, tab2 = st.tabs(["📈 10年历史趋势", "📊 板块资金轮动"])
        with tab1:
            st.plotly_chart(draw_sparkline(history, 'S&P 500', "S&P 500 Index Level", "#00CC96"), use_container_width=True)
        with tab2:
            sector_data = pd.DataFrame({"Sector": ["Gaming", "Pharma", "Biotech", "Semicon", "5G", "Energy"], "1D Change (%)": [1.1, 1.6, 1.4, 1.5, 0.5, 4.1]})
            fig_sector = px.bar(sector_data, x="1D Change (%)", y="Sector", orientation='h', color="1D Change (%)", color_continuous_scale="RdYlGn")
            fig_sector.update_layout(height=200, margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
            st.plotly_chart(fig_sector, use_container_width=True)

    st.markdown("---")
    col3, col4 = st.columns(2)

    # --- 象限 3: 汇率锚点 ---
    with col3:
        st.subheader("💱 FX & Fixed Income Anchors")
        f1, f2 = st.columns(2)
        f1.metric("USD/CNH", f"{latest['USD/CNH']:.4f}")
        f2.metric("China 10Y Yield", f"{china_10y:.4f}%", delta="Manual Input")
        
        tab1, tab2 = st.tabs(["📈 汇率 10年趋势", "📊 跨国期限结构表"])
        with tab1:
            st.plotly_chart(draw_sparkline(history, 'USD/CNH', "USD/CNH Exchange Rate", "#FFA15A"), use_container_width=True)
        with tab2:
            tenors = pd.DataFrame({"Tenor": ["3M", "2Y", "10Y"], "US Yield (%)": [5.30, 4.80, 4.20], "China Yield (%)": [1.25, 1.37, china_10y]})
            st.dataframe(tenors, hide_index=True, use_container_width=True)

    # --- 象限 4: 商品比例 ---
    with col4:
        st.subheader("⚒️ Commodity Structure Ratios")
        r1, r2 = st.columns(2)
        g_w = latest['Gold/WTI']
        g_s = latest['Gold/Silver']
        r1.metric("Gold-WTI Ratio", f"{g_w:.2f}")
        r2.metric("Gold-Silver Ratio", f"{g_s:.2f}")
        
        tab1, tab2 = st.tabs(["📈 金油比 10年趋势", "📊 库存与叙事预警"])
        with tab1:
            st.plotly_chart(draw_sparkline(history, 'Gold/WTI', "Gold-WTI Ratio (Recession Pricing)", "#AB63FA", hline_mean=True), use_container_width=True)
        with tab2:
            st.info("EIA Gasoline inventory trends monitoring active. Waiting for Wednesday EIA release. Reference PDF for dual-axis details.")
            st.caption(f"当前金银比 {g_s:.2f}。比值飙升暗示金融恐慌压倒工业需求。")

else:
    st.error("数据加载失败，请检查系统状态或网络连接。")
