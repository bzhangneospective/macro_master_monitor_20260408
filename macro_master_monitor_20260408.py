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

        # C. 构建 10 年历史核心数据库 (Data Warehouse)
        history = pd.DataFrame()
        history['S&P 500'] = yf_data['^GSPC']
        history['Gold/WTI'] = yf_data['GC=F'] / yf_data['CL=F']
        history['Gold/Silver'] = yf_data['GC=F'] / yf_data['SI=F']
        history['USD/CNH'] = yf_data['CNH=X']
        history['10Y-2Y Spread'] = fred_data['DGS10'] - fred_data['DGS2']
        # 注：SOFR 是 2018 年才有的，所以早期数据会是 NaN，Plotly 会自动处理空白
        history['SOFR-EFFR'] = (fred_data['SOFR'] - fred_data['EFFR']) * 100 
        
        # 清理空值并获取最新一天的截面数据
        latest = history.ffill().iloc[-1]

        return {
            "status": "✅ 10年期底层数据加载完毕 (FRED & Yahoo)",
            "latest": latest,
            "history": history
        }
    except Exception as e:
        return {"status": f"❌ 数据拉取失败: {e}"}

# 执行数据抓取
with st.spinner('📡 正在回溯全球市场过去 10 年历史数据...'):
    data_bundle = fetch_macro_data()

# ==========================================
# 3. 辅助函数：绘制机构级迷你图表
# ==========================================
def draw_sparkline(df, column_name, title, color, hline_zero=False, hline_mean=False):
    """绘制高度定制化的趋势图"""
    # 剔除空值以保证画线连续
    clean_df = df[[column_name]].dropna()
    fig = px.line(clean_df, x=clean_df.index, y=column_name)
    fig.update_traces(line_color=color, line_width=1.5)
    
    # 根据需求添加水平警戒线
    if hline_zero:
        fig.add_hline(y=0, line_dash="solid", line_color="red", line_width=1, annotation_text="倒挂界限 (Zero Line)")
    if hline_mean:
        mean_val = clean_df[column_name].mean()
        fig.add_hline(y=mean_val, line_dash="dash", line_color="gray", annotation_text=f"10Y Mean: {mean_val:.2f}")

    # 极简 UI 设置，隐去多余坐标轴网格
    fig.update_layout(
        title=title,
        margin=dict(l=0, r=0, t=30, b=0),
        height=220,
        xaxis_title="",
        yaxis_title="",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# ==========================================
# 4. 侧边栏：状态监控
# ==========================================
with st.sidebar:
    st.header("⚙️ 系统引擎状态")
    if "✅" in data_bundle.get("status", ""):
        st.success(data_bundle["status"])
        st.caption(f"数据量：每个指标含约 2500 个交易日数据。")
        st.caption(f"更新时间: {datetime.datetime.now().strftime('%H:%M:%S')}")
    else:
        st.error(data_bundle.get("status", "未知错误"))

    st.markdown("---")
    china_10y = st.number_input("China 10Y Yield (%)", value=1.8055, format="%.4f")

# ==========================================
# 5. 前端展示逻辑 (加入 10 年趋势图)
# ==========================================
st.title("🏛️ 宏观资产综合监控终端 (10-Year Dashboard)")
st.markdown("---")

if "✅" in data_bundle.get("status", ""):
    latest = data_bundle['latest']
    history = data_bundle['history']
    
    col1, col2 = st.columns(2)

    # --- 象限 1: 信用利差与期限结构 ---
    with col1:
        st.subheader("📡 Credit & Liquidity (10Y Trend)")
        c1, c2 = st.columns(2)
        spread = latest['10Y-2Y Spread']
        c1.metric("10Y-2Y Spread", f"{spread:.3f}%", delta="Un-inverting" if spread > -0.1 else "Inverted")
        c2.metric("SOFR-EFFR", f"{latest['SOFR-EFFR']:.1f} bps")
        
        # 核心改动：加入 10年期利差走势图，标出 0 轴（衰退警戒线）
        fig1 = draw_sparkline(history, '10Y-2Y Spread', "US Treasury 10Y-2Y Spread", "#FF4B4B", hline_zero=True)
        st.plotly_chart(fig1, use_container_width=True)

    # --- 象限 2: 权益水位 ---
    with col2:
        st.subheader("📈 Equity Markets (10Y Trend)")
        e1, e2 = st.columns(2)
        e1.metric("S&P 500 Close", f"{latest['S&P 500']:.2f}")
        
        # 加入标普 500 十年走势图
        fig2 = draw_sparkline(history, 'S&P 500', "S&P 500 Index Level", "#00CC96")
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    col3, col4 = st.columns(2)

    # --- 象限 3: 汇率锚点 ---
    with col3:
        st.subheader("💱 FX Anchor (10Y Trend)")
        f1, f2 = st.columns(2)
        f1.metric("USD/CNH", f"{latest['USD/CNH']:.4f}")
        f2.metric("China 10Y Yield", f"{china_10y:.4f}%", delta="Manual Input")
        
        # 加入人民币汇率十年走势图
        fig3 = draw_sparkline(history, 'USD/CNH', "USD/CNH Exchange Rate", "#FFA15A")
        st.plotly_chart(fig3, use_container_width=True)

    # --- 象限 4: 商品比例 ---
    with col4:
        st.subheader("⚒️ Commodity Ratios (10Y Trend)")
        r1, r2 = st.columns(2)
        r1.metric("Gold-WTI Ratio", f"{latest['Gold/WTI']:.2f}")
        r2.metric("Gold-Silver Ratio", f"{latest['Gold/Silver']:.2f}")
        
        # 加入金油比图表，自动计算并标出 10年平均值
        fig4 = draw_sparkline(history, 'Gold/WTI', "Gold-WTI Ratio (Recession Pricing)", "#AB63FA", hline_mean=True)
        st.plotly_chart(fig4, use_container_width=True)

else:
    st.error("数据加载失败，请检查系统状态。")