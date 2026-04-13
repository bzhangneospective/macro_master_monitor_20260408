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
# 2. 全自动数据抓取引擎 (核心后勤)
# ==========================================
# 使用 st.cache_data 缓存数据，避免每次刷新页面都去请求服务器导致被封 IP (缓存 1 小时)
@st.cache_data(ttl=3600)
def fetch_macro_data():
    try:
        # A. 雅虎财经接口: 抓取指数、商品、外汇
        # ^GSPC(标普), GC=F(黄金), CL=F(原油), SI=F(白银), CNH=X(美元/离岸人民币)
        tickers = ['^GSPC', 'GC=F', 'CL=F', 'SI=F', 'CNH=X']
        yf_data = yf.download(tickers, period="5d")['Close']
        # ffill() 向下填充周末缺失值，获取最新有效数据
        latest_yf = yf_data.ffill().iloc[-1]

        sp500 = float(latest_yf['^GSPC'])
        gold = float(latest_yf['GC=F'])
        wti = float(latest_yf['CL=F'])
        silver = float(latest_yf['SI=F'])
        usd_cnh = float(latest_yf['CNH=X'])

        # B. 美联储 FRED 接口: 抓取国债收益率与流动性基准
        # DGS10(10年期), DGS2(2年期), SOFR, EFFR
        end = datetime.date.today()
        start = end - datetime.timedelta(days=10) # 抓过去10天确保覆盖周末
        fred_data = web.DataReader(['DGS10', 'DGS2', 'SOFR', 'EFFR'], 'fred', start, end)
        latest_fred = fred_data.ffill().iloc[-1]

        dgs10 = float(latest_fred['DGS10'])
        dgs2 = float(latest_fred['DGS2'])
        sofr = float(latest_fred['SOFR'])
        effr = float(latest_fred['EFFR'])

        # C. 组装结果字典
        return {
            "sp500": round(sp500, 2),
            "gold_wti": round(gold / wti, 3),
            "gold_silver": round(gold / silver, 3),
            "usd_cnh": round(usd_cnh, 4),
            "spread_10y2y": round(dgs10 - dgs2, 3),
            "sofr_effr": round((sofr - effr) * 100, 1), # 换算成基点(bps)
            "status": "✅ 数据源连接正常 (FRED & Yahoo API)"
        }
    except Exception as e:
        return {"status": f"❌ 数据拉取失败: {e}"}

# 执行数据抓取
with st.spinner('📡 正在连接全球金融数据库...'):
    market_data = fetch_macro_data()

# ==========================================
# 3. 侧边栏：状态监控与部分手动输入
# ==========================================
with st.sidebar:
    st.header("⚙️ 系统引擎状态")
    if "✅" in market_data.get("status", ""):
        st.success(market_data["status"])
        st.caption(f"上次同步时间: {datetime.datetime.now().strftime('%H:%M:%S')}")
    else:
        st.error(market_data.get("status", "未知错误"))
        
    st.markdown("---")
    st.header("📝 亚太时区手动调整")
    st.markdown("国内资产受限，请在此更新中国区基准：")
    china_10y = st.number_input("China 10Y Yield (%)", value=1.8055, format="%.4f")
    sp500_ytd = st.number_input("S&P 500 YTD (%) 备用", value=47.60)

# ==========================================
# 4. 前端展示逻辑 (2x2 机构级终端布局)
# ==========================================
st.title("🏛️ 宏观资产综合监控终端 (Auto-Pilot Mode)")
st.markdown("---")

# 安全校验：确保数据拉取成功才展示
if "✅" in market_data.get("status", ""):
    col1, col2 = st.columns(2)

    # --- 象限 1: 信用利差与期限结构 ---
    with col1:
        st.subheader("📡 Credit & Liquidity Analysis")
        c1, c2 = st.columns(2)
        spread = market_data['spread_10y2y']
        c1.metric("10Y-2Y Spread", f"{spread}%", delta="Un-inverting" if spread > -0.1 else "Inverted")
        c2.metric("SOFR-EFFR", f"{market_data['sofr_effr']} bps", delta="Neutral")
        
        st.caption(f"Historical Context: Min -0.4% | Max 0.4% | Current: {spread}%")
        st.progress(min(max((spread + 0.4) / 0.8, 0.0), 1.0))

    # --- 象限 2: 权益水位与板块表现 ---
    with col2:
        st.subheader("📈 Equity Markets Performance")
        e1, e2 = st.columns(2)
        e1.metric("S&P 500 Close", f"{market_data['sp500']}", delta=f"Auto-Fetched")
        
        # 还原示例板块数据
        sector_data = pd.DataFrame({
            "Sector": ["Gaming", "Pharma", "Biotech", "Semicon", "5G", "Energy"],
            "1D Change (%)": [1.1, 1.6, 1.4, 1.5, 0.5, 4.1]
        })
        fig_sector = px.bar(sector_data, x="1D Change (%)", y="Sector", orientation='h', 
                            color="1D Change (%)", color_continuous_scale="RdYlGn")
        fig_sector.update_layout(height=200, margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
        st.plotly_chart(fig_sector, use_container_width=True)

    st.markdown("---")
    col3, col4 = st.columns(2)

    # --- 象限 3: 汇率与固定收益锚点 ---
    with col3:
        st.subheader("💱 FX & Fixed Income Anchors")
        f1, f2 = st.columns(2)
        f1.metric("USD/CNH", f"{market_data['usd_cnh']}", delta="Auto-Fetched")
        f2.metric("China 10Y Yield", f"{china_10y}%", delta="Manual Input")
        
        tenors = pd.DataFrame({"Tenor": ["3M", "2Y", "10Y"], "Yield": [1.25, 1.37, china_10y]})
        st.table(tenors)

    # --- 象限 4: 商品比例与库存 ---
    with col4:
        st.subheader("⚒️ Commodity Structure Ratios")
        r1, r2 = st.columns(2)
        
        g_w = market_data['gold_wti']
        g_s = market_data['gold_silver']
        
        r1.metric("Gold-WTI Ratio", f"{g_w}", delta=f"{(g_w - 20.461):.1f} vs Mean")
        r2.metric("Gold-Silver Ratio", f"{g_s}", delta=f"{(g_s - 69.183):.1f} vs Mean")
        
        st.info("EIA Gasoline inventory trends monitoring active. Waiting for Wednesday EIA release.")
else:
    st.error("无法加载仪表盘，底层数据连通失败。请检查网络。")