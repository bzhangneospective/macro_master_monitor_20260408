import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import pandas_datareader.data as web
import datetime

# ==========================================
# 1. 页面全局配置
# ==========================================
st.set_page_config(page_title="Macro Hedge Dashboard", layout="wide")

# ==========================================
# 2. 全自动数据抓取引擎 (扩充更多底层指标)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_macro_data():
    try:
        # 设定 10 年的时间窗口
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=365 * 10)

        # 雅虎财经接口：增加 VIX 恐慌指数
        tickers = ['^GSPC', 'GC=F', 'CL=F', 'SI=F', 'CNH=X', '^VIX']
        yf_data = yf.download(tickers, period="10y")['Close'].ffill()

        # 美联储 FRED 接口：增加美国高收益债利差 (BAMLH0A0HYM2)
        fred_data = web.DataReader(['DGS10', 'DGS2', 'SOFR', 'EFFR', 'BAMLH0A0HYM2'], 'fred', start_date, end_date).ffill()

        # 构建历史核心数据库
        history = pd.DataFrame()
        history['S&P 500'] = yf_data['^GSPC']
        history['VIX'] = yf_data['^VIX']
        history['Gold/WTI'] = yf_data['GC=F'] / yf_data['CL=F']
        history['Gold/Silver'] = yf_data['GC=F'] / yf_data['SI=F']
        history['USD/CNH'] = yf_data['CNH=X']
        history['10Y-2Y Spread'] = fred_data['DGS10'] - fred_data['DGS2']
        history['SOFR-EFFR'] = (fred_data['SOFR'] - fred_data['EFFR']) * 100 
        history['US High Yield Spread'] = fred_data['BAMLH0A0HYM2']
        
        # 获取最新一天的截面数据
        latest = history.iloc[-1]

        return {"status": "✅ 10年期数据源连接正常", "latest": latest, "history": history}
    except Exception as e:
        return {"status": f"❌ 数据拉取失败: {e}"}

# ==========================================
# 3. 辅助函数：绘制机构级图表 (尺寸放大)
# ==========================================
def draw_sparkline(df, column_name, title, color, hline_zero=False, hline_mean=False):
    clean_df = df[[column_name]].dropna()
    fig = px.line(clean_df, x=clean_df.index, y=column_name)
    fig.update_traces(line_color=color, line_width=1.5)
    
    if hline_zero:
        fig.add_hline(y=0, line_dash="solid", line_color="red", line_width=1, annotation_text="0 Line")
    if hline_mean:
        mean_val = clean_df[column_name].mean()
        fig.add_hline(y=mean_val, line_dash="dash", line_color="gray", annotation_text=f"10Y Mean: {mean_val:.2f}")

    fig.update_layout(
        title=title, margin=dict(l=0, r=0, t=30, b=0), height=350, # 增加图表高度
        xaxis_title="", yaxis_title="", xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# ==========================================
# 4. 侧边栏：状态监控
# ==========================================
with st.spinner('📡 正在回溯全球市场并构建四大主题...'):
    data_bundle = fetch_macro_data()

with st.sidebar:
    st.header("⚙️ 引擎状态")
    if "✅" in data_bundle.get("status", ""):
        st.success(data_bundle["status"])
    else:
        st.error(data_bundle.get("status", "未知错误"))
        
    st.markdown("---")
    china_10y = st.number_input("China 10Y Yield (%)", value=1.8055, format="%.4f")

# ==========================================
# 5. 前端展示：四大沉浸式选项卡
# ==========================================
st.title("🏛️ 宏观对冲综合监控终端")
st.markdown("---")

if "✅" in data_bundle.get("status", ""):
    latest = data_bundle['latest']
    history = data_bundle['history']
    
    # 核心改动：建立四个顶级 Tab
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏦 1. 信用利差与流动性 (Credit & Liquidity)", 
        "📈 2. 权益市场水位 (Equity Markets)", 
        "💱 3. 汇率与固定收益 (FX & Fixed Income)", 
        "⚒️ 4. 商品微观结构 (Commodity Ratios)"
    ])
    
    # --- Tab 1: 信用利差与流动性 ---
    with tab1:
        st.subheader("Credit & Liquidity Analysis")
        c1, c2, c3 = st.columns(3)
        spread = latest['10Y-2Y Spread']
        safe_spread = 0.0 if pd.isna(spread) else float(spread)
        c1.metric("10Y-2Y Spread", f"{safe_spread:.3f}%", delta="Un-inverting" if safe_spread > -0.1 else "Inverted")
        
        display_sofr = 0.0 if pd.isna(latest['SOFR-EFFR']) else latest['SOFR-EFFR']
        c2.metric("SOFR-EFFR", f"{display_sofr:.1f} bps")
        
        hy_spread = 0.0 if pd.isna(latest['US High Yield Spread']) else latest['US High Yield Spread']
        c3.metric("US High Yield Spread", f"{hy_spread:.2f}%", delta="Risk Warning" if hy_spread > 5.0 else "Safe")
        
        st.plotly_chart(draw_sparkline(history, '10Y-2Y Spread', "US Treasury 10Y-2Y Spread (Recession Indicator)", "#FF4B4B", hline_zero=True), use_container_width=True)
        st.plotly_chart(draw_sparkline(history, 'US High Yield Spread', "US High Yield Option-Adjusted Spread (Default Risk)", "#FFA500"), use_container_width=True)

    # --- Tab 2: 权益市场水位 ---
    with tab2:
        st.subheader("Equity Markets Performance")
        e1, e2 = st.columns(2)
        e1.metric("S&P 500 Close", f"{latest['S&P 500']:.2f}")
        e2.metric("VIX Volatility Index", f"{latest['VIX']:.2f}")
        
        st.plotly_chart(draw_sparkline(history, 'S&P 500', "S&P 500 Index 10Y Trend", "#00CC96"), use_container_width=True)
        st.plotly_chart(draw_sparkline(history, 'VIX', "VIX Volatility Index (Market Fear)", "#FF00FF"), use_container_width=True)
        
        sector_data = pd.DataFrame({"Sector": ["Gaming", "Pharma", "Biotech", "Semicon", "5G", "Energy"], "1D Change (%)": [1.1, 1.6, 1.4, 1.5, 0.5, 4.1]})
        fig_sector = px.bar(sector_data, x="1D Change (%)", y="Sector", orientation='h', color="1D Change (%)", color_continuous_scale="RdYlGn", title="Sector Rotation Snapshot")
        st.plotly_chart(fig_sector, use_container_width=True)

    # --- Tab 3: 汇率与固定收益 ---
    with tab3:
        st.subheader("FX & Fixed Income Anchors")
        f1, f2 = st.columns(2)
        f1.metric("USD/CNH", f"{latest['USD/CNH']:.4f}")
        f2.metric("China 10Y Yield", f"{china_10y:.4f}%", delta="Manual Input")
        
        st.plotly_chart(draw_sparkline(history, 'USD/CNH', "USD/CNH Exchange Rate", "#FFA15A"), use_container_width=True)
        
        st.markdown("#### Cross-Border Yield Curve Structure")
        tenors = pd.DataFrame({"Tenor": ["3M", "2Y", "10Y"], "US Yield (%)": [5.30, 4.80, 4.20], "China Yield (%)": [1.25, 1.37, china_10y]})
        st.dataframe(tenors, hide_index=True, use_container_width=True)

    # --- Tab 4: 商品微观结构 ---
    with tab4:
        st.subheader("Commodity Structure Ratios")
        r1, r2 = st.columns(2)
        g_w = latest['Gold/WTI']
        g_s = latest['Gold/Silver']
        r1.metric("Gold-WTI Ratio", f"{g_w:.2f}")
        r2.metric("Gold-Silver Ratio", f"{g_s:.2f}")
        
        st.plotly_chart(draw_sparkline(history, 'Gold/WTI', "Gold-WTI Ratio (Recession Pricing / Risk-Off)", "#AB63FA", hline_mean=True), use_container_width=True)
        st.plotly_chart(draw_sparkline(history, 'Gold/Silver', "Gold-Silver Ratio (Monetary vs Industrial Demand)", "#00BFFF", hline_mean=True), use_container_width=True)

else:
    st.error("数据加载失败，请检查网络或刷新页面。")
