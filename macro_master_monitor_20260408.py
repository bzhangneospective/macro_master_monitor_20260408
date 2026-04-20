import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import datetime
import akshare as ak
from fredapi import Fred

# ==========================================
# 1. 架构核心：页面配置与 Bloomberg 样式表
# ==========================================
st.set_page_config(
    page_title="Macro Master Monitor V3.0", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; max-width: 100% !important; }
        header {visibility: hidden;} footer {visibility: hidden;}
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] { height: 40px; font-size: 16px; font-weight: 600; }
        div[data-testid="stRadio"] label { white-space: nowrap; font-size: 12px !important; padding: 2px 0px; }
        /* 隐藏纵向 Colorbar 的容器边距 */
        [data-testid="column"]:nth-child(2) { padding-left: 0px !important; padding-right: 0px !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 数据管道：全量资产抓取 (主图表)
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)
def fetch_global_data():
    FRED_API_KEY = '2855fd24c8cbc761cd583d64f97e7004' 
    
    # --- 资产列表定义 ---
    yf_tickers = [
        '^GSPC', '^NDX', '^SOX', '^N225', '^KS11', '^HSI', '000001.SS', '^TWII',
        'GC=F', 'SI=F', 'HG=F', 'CL=F', 'NG=F', 'BZ=F', 'ZC=F', 'ZS=F', 'ZW=F', 'CT=F', 'BTC-USD',
        'CNH=X', 'AUDUSD=X', 'JPY=X', 'IDR=X', 'INR=X', 'TRY=X', 'EURUSD=X', 'GBPUSD=X', 'CAD=X', 'MXN=X', 'BRL=X', 'TLT'
    ]
    fred_tickers = [
        'SOFR', 'EFFR', 'DGS3MO', 'DGS2', 'DGS10', 'DGS30',
        'BAMLC0A1CAAA', 'BAMLC0A4CBBB', 'BAMLH0A0HYM2', 'BAMLEMHBHYCRPIUSOAS'
    ]
    
    data_store = {"yf": {}, "fred": {}, "cn": {}}
    
    # 抓取 Yahoo Finance
    try:
        yf_raw = yf.download(yf_tickers, period="max", progress=False)
        for t in yf_tickers:
            df = pd.DataFrame({
                'Open': yf_raw['Open'][t], 'High': yf_raw['High'][t],
                'Low': yf_raw['Low'][t], 'Close': yf_raw['Close'][t]
            }).dropna()
            data_store["yf"][t] = df
    except: pass

    # 抓取 FRED
    try:
        fred = Fred(api_key=FRED_API_KEY)
        for t in fred_tickers:
            series = fred.get_series(t)
            data_store["fred"][t] = pd.DataFrame({'Close': series}).ffill().bfill()
    except: pass

    # 抓取 AKShare (中国债市与内盘期货)
    try:
        bond_df = ak.bond_zh_us_rate()
        bond_df['日期'] = pd.to_datetime(bond_df['日期'])
        bond_df.set_index('日期', inplace=True)
        data_store["cn"]['China_10Y'] = pd.DataFrame({'Close': pd.to_numeric(bond_df['中国国债收益率10年'], errors='coerce')}).dropna()
        
        # 内盘商品示例 (焦炭)
        j_df = ak.futures_zh_daily_sina(symbol="j0")
        j_df['date'] = pd.to_datetime(j_df['date']); j_df.set_index('date', inplace=True)
        data_store["cn"]['DCE_Coke'] = j_df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close'}).apply(pd.to_numeric).dropna()
    except: pass
    
    return data_store

# ==========================================
# 2.1 专项管线：多市场热力图配置
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_heatmap_data(market_type):
    # 配置各市场的行业代理
    configs = {
        "US": [
            ('Tech', 'Software', 'IGV', 12), ('Tech', 'Semis', 'SOXX', 11), ('Tech', 'Hardware', 'IYW', 6),
            ('Fin', 'Banks', 'KBE', 5), ('Fin', 'Insurance', 'KIE', 4), ('Fin', 'Reg.Banks', 'KRE', 3),
            ('Health', 'Biotech', 'IBB', 6), ('Health', 'Pharma', 'PPH', 6),
            ('Disc', 'Retail', 'XRT', 8), ('Disc', 'Broad', 'XLY', 5),
            ('Comm', 'Internet', 'FDN', 9), ('Industrials', 'Aero', 'ITA', 8),
            ('Energy', 'E&P', 'XOP', 5), ('Utilities', 'Utils', 'XLU', 5), ('Materials', 'Mining', 'XME', 4)
        ],
        "HK": [
            ('Tech', 'IT', 'HSITI.HK', 10), ('Fin', 'Finance', 'HSHFI.HK', 10), ('Property', 'RE', 'HSCPI.HK', 10),
            ('Cons', 'Consumer', 'HSCNI.HK', 10), ('Health', 'Healthcare', 'HSHCI.HK', 10), ('Energy', 'Energy', 'HSEII.HK', 10),
            ('Telecom', 'Telecom', 'HSTLI.HK', 10), ('Utils', 'Utilities', 'HSUTI.HK', 10)
        ]
    }
    
    if market_type in configs:
        hierarchy = configs[market_type]
        tickers = [h[2] for h in hierarchy]
        raw_df = yf.download(tickers, period="1y", progress=False)['Close']
        return raw_df, hierarchy
    
    elif market_type == "CN":
        # A股通过东方财富/同花顺接口抓取行业
        try:
            df_cn = ak.stock_board_industry_summary_ths().head(15)
            # 伪造层级以符合 Treemap
            hierarchy = [('China', row['板块'], row['板块'], 10) for _, row in df_cn.iterrows()]
            return df_cn, hierarchy
        except: return pd.DataFrame(), []

# ==========================================
# 3. 核心算法：数据降采样与绘图引擎
# ==========================================
def draw_bloomberg_chart(df, title, color, res):
    if df is None or df.empty: return go.Figure()
    
    # 1. 降采样逻辑 (Pandas 2.2+)
    if res == "Weekly": df = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
    elif res == "Monthly": df = df.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
    
    # 2. 指标计算
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
    df['EMA120'] = df['Close'].ewm(span=120, adjust=False).mean()
    
    # 3. 动能 (PPO) 公式
    ema9 = df['Close'].ewm(span=9, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    ppo = ((ema9 - ema26) / ema26 * 100).iloc[-1]
    ppo_color = "#00CC96" if ppo >= 0 else "#FF4B4B"

    # 4. 绘图
    fig = go.Figure()
    has_ohlc = all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']) and res != "MAX"
    
    if has_ohlc:
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#00CC96', decreasing_line_color='#FF4B4B'))
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color=color, width=2.5)))
    
    # 叠加 EMA
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#FFD700', width=1.1), name='EMA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA60'], line=dict(color='#FF4B4B', width=1.1), name='EMA60'))

    # 5. 视野锁定 (180 周期)
    if res != "MAX" and len(df) > 10:
        ldf = df.iloc[-min(len(df), 180):]
        y_min, y_max = ldf['Low'].min() if has_ohlc else ldf['Close'].min(), ldf['High'].max() if has_ohlc else ldf['Close'].max()
        fig.update_layout(xaxis_range=[ldf.index[0], ldf.index[-1]], yaxis_range=[y_min*0.97, y_max*1.03])

    fig.update_layout(
        height=490, template="plotly_dark", margin=dict(l=10, r=10, t=50, b=10),
        title=f"<b>{title}</b> <span style='color:{ppo_color}; font-size:14px;'>PPO: {ppo:.2f}%</span>",
        yaxis=dict(side="right", showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
        xaxis=dict(rangeslider_visible=False, showgrid=False),
        hovermode="x unified"
    )
    return fig

# ==========================================
# 4. 终端 UI：Sidebar 资产导航
# ==========================================
with st.sidebar:
    st.title("Macro Terminal V3.0")
    st.markdown("---")
    
    m_sel = st.selectbox("📂 Category", ["📊 Spreads & Ratios", "⚒️ Commodity", "💱 FX & FI", "📈 Equity Markets"])
    
    # 资产映射 (归口管理)
    asset_dict = {
        "📊 Spreads & Ratios": ["OAS Spread", "10Y-2Y Spread", "10Y-3M Spread", "Gold-Silver Ratio", "Gold-WTI Ratio"],
        "⚒️ Commodity": ["Gold (GC=F)", "Silver (SI=F)", "WTI Crude (CL=F)", "Natural Gas (NG=F)", "Bitcoin (BTC-USD)", "DCE Coke (CN)"],
        "💱 FX & FI": ["USD/CNH", "USD/JPY", "EUR/USD", "US 2Y Yield", "US 10Y Yield", "China 10Y Yield", "US Long Treas (TLT)"],
        "📈 Equity Markets": ["S&P 500 (^GSPC)", "Nasdaq 100 (^NDX)", "Semiconductor (^SOX)", "Nikkei 225 (^N225)", "Hang Seng Index", "SSE Composite"]
    }
    
    selected_asset = st.radio("🎯 Select Asset", asset_dict[m_sel])
    selected_res = st.radio("Resolution", ["Daily", "Weekly", "Monthly", "MAX"], horizontal=True)
    
    if st.button("🔄 Force Data Sync", type="primary", use_container_width=True):
        fetch_global_data.clear(); st.rerun()

# ==========================================
# 5. 主画布：渲染引擎
# ==========================================
db = fetch_global_data()

if db:
    # --- 资产逻辑映射 ---
    def get_asset_target(name):
        yf, fr, cn = db['yf'], db['fred'], db['cn']
        # 特殊计算逻辑
        if name == "10Y-2Y Spread": return pd.DataFrame({'Close': fr['DGS10']['Close'] - fr['DGS2']['Close']}).dropna(), "#FF4B4B"
        if name == "Gold-Silver Ratio": return pd.DataFrame({'Close': yf['GC=F']['Close'] / yf['SI=F']['Close']}).dropna(), "#AB63FA"
        # 直接映射
        m = {
            "OAS Spread": (fr.get('BAMLH0A0HYM2'), "#FF4B4B"),
            "Gold (GC=F)": (yf.get('GC=F'), "#FFD700"),
            "WTI Crude (CL=F)": (yf.get('CL=F'), "#8B4513"),
            "USD/CNH": (yf.get('CNH=X'), "#FF4B4B"),
            "US 10Y Yield": (fr.get('DGS10'), "#8B0000"),
            "China 10Y Yield": (cn.get('China_10Y'), "#FF4B4B"),
            "S&P 500 (^GSPC)": (yf.get('^GSPC'), "#00CC96"),
            "Nasdaq 100 (^NDX)": (yf.get('^NDX'), "#1E90FF"),
            "Semiconductor (^SOX)": (yf.get('^SOX'), "#AB63FA"),
            "Hang Seng Index": (yf.get('^HSI'), "#00BFFF"),
            "SSE Composite": (yf.get('000001.SS'), "#FF8C00")
        }
        return m.get(name, (None, "#FFF"))

    target_df, theme_color = get_asset_target(selected_asset)

    if m_sel == "📈 Equity Markets":
        t1, t2 = st.tabs(["🎯 Asset Analysis", "📊 Sector X-Ray (Heatmap)"])
        with t1:
            st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, theme_color, selected_res), use_container_width=True)
        with t2:
            # --- V2.11+ 终极三栏布局 ---
            m_type = "US" if "S&P" in selected_asset or "Nasdaq" in selected_asset or "Semi" in selected_asset else ("HK" if "Hang" in selected_asset else "CN")
            
            c_tree, c_bar, c_ctrl = st.columns([15, 0.8, 1.2])
            
            with c_ctrl:
                st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
                st.markdown("<p style='color:gray; font-size:12px; margin-bottom:5px;'>Period</p>", unsafe_allow_html=True)
                lk = st.radio("Lookback", ["1D", "5D", "1M", "YTD"], index=3, label_visibility="collapsed")
            
            # 数据计算
            raw_h, hier = fetch_heatmap_data(m_type)
            # 计算表现 (复用逻辑)
            def calc_perf(df_r, h_list, look):
                if df_r.empty: return pd.DataFrame()
                res_rows = []
                for sec, sub, tk, wt in h_list:
                    if tk in df_r.columns:
                        s = df_r[tk].dropna()
                        if len(s) < 2: continue
                        now = s.iloc[-1]
                        if look == "1D": old = s.iloc[-2]
                        elif look == "5D": old = s.iloc[-min(len(s),6)]
                        elif look == "1M": old = s.iloc[-min(len(s),22)]
                        else: 
                            ytd = s[s.index.year == datetime.date.today().year]
                            old = ytd.iloc[0] if not ytd.empty else s.iloc[0]
                        res_rows.append({'Sector':sec, 'Sub':sub, 'Perf':((now-old)/old)*100, 'Weight':wt})
                return pd.DataFrame(res_rows)
            
            if m_type != "CN": df_final = calc_perf(raw_h, hier, lk)
            else: 
                # CN 接口直接带涨跌幅
                df_final = pd.DataFrame([{'Sector':'China', 'Sub':r['板块'], 'Perf':float(r['涨跌幅']), 'Weight':10} for _,r in raw_h.iterrows()])
            
            with c_tree:
                if not df_final.empty:
                    fig_tree = px.treemap(df_final, path=[px.Constant(m_type), 'Sector', 'Sub'], values='Weight', color='Perf',
                                          color_continuous_scale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']], color_continuous_midpoint=0)
                    fig_tree.update_layout(height=490, margin=dict(l=0, r=0, t=0, b=0), template="plotly_dark", coloraxis_showscale=False)
                    fig_tree.update_traces(customdata=df_final[['Perf']], texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%", root_color="#000")
                    st.plotly_chart(fig_tree, use_container_width=True, config={'displayModeBar': False})
            
            with c_bar:
                if not df_final.empty:
                    fig_bar = go.Figure(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(
                        colorscale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']],
                        cmin=df_final['Perf'].min(), cmax=df_final['Perf'].max(), showscale=True,
                        colorbar=dict(title=dict(text=f"{lk}%", font=dict(size=11)), thickness=15, len=1.0, x=0, y=0.5))))
                    fig_bar.update_layout(height=490, width=60, margin=dict(l=0, r=0, t=40, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_visible=False, yaxis_visible=False)
                    st.plotly_chart(fig_bar, use_container_width=False, config={'displayModeBar': False})

    else:
        # 非权益市场，直接显示主图
        st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, theme_color, selected_res), use_container_width=True)
