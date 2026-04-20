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
# 1. Page Configuration & Professional CSS
# ==========================================
st.set_page_config(page_title="Macro Terminal V2.12", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; max-width: 100% !important; }
        header {visibility: hidden;} footer {visibility: hidden;}
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] { height: 40px; font-size: 16px; font-weight: 600; }
        div[data-testid="stRadio"] label { white-space: nowrap; font-size: 12px !important; padding: 2px 0px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Institutional Data Engine
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)
def fetch_global_data():
    FRED_API_KEY = '2855fd24c8cbc761cd583d64f97e7004' 
    yf_tickers = ['^GSPC', '^NDX', '^SOX', '^N225', '^HSI', '000001.SS', '399001.SZ', 'TLT', 'GC=F', 'CL=F', 'CNH=X']
    yf_data = {}
    try:
        yf_raw = yf.download(yf_tickers, period="max", progress=False)
        for t in yf_tickers:
            df = pd.DataFrame({'Open': yf_raw['Open'][t], 'High': yf_raw['High'][t], 'Low': yf_raw['Low'][t], 'Close': yf_raw['Close'][t]}).dropna()
            yf_data[t] = df
    except: pass
    return {"yf": yf_data}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_market_heatmap_raw(market_type):
    """根据市场类型获取对应的板块配置"""
    if market_type == "US":
        hierarchy = [
            ('Technology', 'Software (IGV)', 'IGV', 12.0), ('Technology', 'Semis (SOXX)', 'SOXX', 11.0),
            ('Financials', 'Banks (KBE)', 'KBE', 4.0), ('Financials', 'Insurance (KIE)', 'KIE', 4.0),
            ('Health Care', 'Biotech (IBB)', 'IBB', 5.0), ('Health Care', 'Pharma (PPH)', 'PPH', 5.0),
            ('Cons Disc', 'Retail (XRT)', 'XRT', 6.0), ('Comm Svcs', 'Internet (FDN)', 'FDN', 6.0),
            ('Energy', 'E&P (XOP)', 'XOP', 4.0), ('Industrials', 'Broad (XLI)', 'XLI', 6.0)
        ]
        tickers = [item[2] for item in hierarchy]
        raw_df = yf.download(tickers, period="1y", progress=False)['Close']
        return raw_df, hierarchy
    
    elif market_type == "HK":
        # 恒生行业分类映射 (HSIC)
        hk_map = {
            'HSITI.HK': ('Technology', 'IT'), 'HSHFI.HK': ('Financials', 'Finance'), 'HSCPI.HK': ('Property', 'Real Estate'),
            'HSCNI.HK': ('Cons Disc', 'Consumer'), 'HSHCI.HK': ('Health Care', 'Healthcare'), 'HSEII.HK': ('Energy', 'Energy'),
            'HSMBI.HK': ('Materials', 'Materials'), 'HSUTI.HK': ('Utilities', 'Utilities'), 'HSTLI.HK': ('Telecomm', 'Telecom')
        }
        tickers = list(hk_map.keys())
        raw_df = yf.download(tickers, period="1y", progress=False)['Close']
        hierarchy = [(hk_map[t][0], hk_map[t][1], t, 10.0) for t in tickers]
        return raw_df, hierarchy

    elif market_type == "CN":
        # A股通过 akshare 抓取实时板块
        try:
            df_cn = ak.stock_board_industry_summary_ths()
            # 简化逻辑：取前12个大行业模拟 GICS
            df_cn = df_cn.head(12)
            hierarchy = [('A-Share', row['板块'], row['板块'], 10.0) for _, row in df_cn.iterrows()]
            # A股数据结构特殊，直接返回处理好的涨跌幅
            return df_cn, hierarchy
        except: return pd.DataFrame(), []

def calculate_heatmap_performance(raw_data, hierarchy, lookback, market_type):
    if raw_data.empty: return pd.DataFrame()
    rows = []; cur_yr = datetime.date.today().year
    
    if market_type in ["US", "HK"]:
        for sec, sub, t, w in hierarchy:
            if t in raw_data.columns:
                s = raw_data[t].dropna()
                if len(s) < 2: continue
                p_now = s.iloc[-1]
                if lookback == "1D": p_old = s.iloc[-2]
                elif lookback == "5D": p_old = s.iloc[-min(len(s), 6)]
                elif lookback == "1M": p_old = s.iloc[-min(len(s), 22)]
                else:
                    ytd = s[s.index.year == cur_yr]
                    p_old = ytd.iloc[0] if not ytd.empty else s.iloc[0]
                perf = ((p_now - p_old) / p_old) * 100
                rows.append({'Sector': sec, 'Sub': sub, 'Perf': perf, 'Weight': w})
    else: # CN Market 特殊处理
        for _, row in raw_data.iterrows():
            # A股 akshare 默认返回的是 1D 涨跌幅，复杂回溯需进一步开发，此处演示 1D
            perf = float(row['涨跌幅'])
            rows.append({'Sector': 'China', 'Sub': row['板块'], 'Perf': perf, 'Weight': 10.0})
            
    return pd.DataFrame(rows)

# ==========================================
# 3. UI Framework
# ==========================================
with st.sidebar:
    st.title("Macro Terminal V2.12")
    market_sel = st.selectbox("🌍 Select Market", ["US Equity", "HK Equity", "CN Equity"])
    
    # 建立资产关联
    asset_map = {
        "US Equity": ["S&P 500 (^GSPC)", "Nasdaq 100 (^NDX)", "Semiconductor (^SOX)"],
        "HK Equity": ["Hang Seng Index (^HSI)", "HS Tech Index"],
        "CN Equity": ["SSE Composite (000001.SS)", "CSI 300"]
    }
    sel_asset = st.radio("🎯 Focus Asset", asset_map[market_sel])
    sel_res = st.radio("Res", ["Daily", "Weekly", "Monthly", "MAX"], horizontal=True, index=0)
    db = fetch_global_data()

if db:
    # 确定当前绘图资产（此处简化逻辑）
    ticker_map = {"S&P 500 (^GSPC)": "^GSPC", "Hang Seng Index (^HSI)": "^HSI", "SSE Composite (000001.SS)": "000001.SS"}
    ticker = ticker_map.get(sel_asset, "^GSPC")
    target_df = db['yf'].get(ticker)

    tab1, tab2 = st.tabs(["🎯 Asset Analysis", "📊 Sector Performance"])
    
    with tab1:
        # 复用之前的 draw_bloomberg_chart
        if target_df is not None:
            fig = go.Figure(go.Candlestick(x=target_df.index, open=target_df['Open'], high=target_df['High'], low=target_df['Low'], close=target_df['Close']))
            fig.update_layout(height=490, template="plotly_dark", margin=dict(t=30), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # --- 核心：多市场热力图逻辑 ---
        m_type = market_sel.split(" ")[0] # US, HK, CN
        
        c_tree, c_perf, c_period = st.columns([15, 0.8, 1.2])
        
        with c_period:
            st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
            lookback = st.radio("L", ["1D", "5D", "1M", "YTD"], index=3, label_visibility="collapsed")

        raw_h, hier = fetch_market_heatmap_raw(m_type)
        df_t = calculate_heatmap_performance(raw_h, hier, lookback, m_type)

        with c_tree:
            if not df_t.empty:
                # 绘制热力图
                fig_t = px.treemap(df_t, path=[px.Constant(market_sel), 'Sector', 'Sub'], values='Weight', color='Perf',
                                   color_continuous_scale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']], color_continuous_midpoint=0)
                fig_t.update_layout(height=490, margin=dict(l=0, r=0, t=0, b=0), template="plotly_dark", coloraxis_showscale=False)
                fig_t.update_traces(customdata=df_t[['Perf']], texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%", root_color="#000")
                st.plotly_chart(fig_t, use_container_width=True, config={'displayModeBar': False})
        
        with c_perf:
            if not df_t.empty:
                # 渲染右侧 Bar
                fig_p = go.Figure(go.Scatter(x=[None], y=[None], mode='markers',
                    marker=dict(colorscale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']],
                                cmin=df_t['Perf'].min(), cmax=df_t['Perf'].max(), showscale=True,
                                colorbar=dict(title=dict(text=f"{lookback}%", font=dict(size=12)),
                                              thickness=15, len=1.0, x=0, y=0.5))))
                fig_p.update_layout(height=490, width=60, margin=dict(l=0, r=0, t=40, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_visible=False, yaxis_visible=False)
                st.plotly_chart(fig_p, use_container_width=False, config={'displayModeBar': False})
