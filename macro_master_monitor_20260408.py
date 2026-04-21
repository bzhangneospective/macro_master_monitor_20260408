import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import datetime
import akshare as ak
from fredapi import Fred
import warnings

# 忽略 Pandas 降采样的 Future Warning
warnings.filterwarnings('ignore')

# ==========================================
# 1. Page Configuration & Professional CSS
# ==========================================
st.set_page_config(
    page_title="Macro Terminal V3.13", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .block-container { 
            padding-top: 2.5rem !important; 
            padding-bottom: 0rem !important; 
            max-width: 100% !important; 
        }
        
        /* 暴力切除 Streamlit 绘图组件自带的底部垃圾空白 */
        div[data-testid="stPlotlyChart"] { 
            margin-bottom: -15px !important; 
        }
        
        #MainMenu {visibility: hidden;} 
        footer {visibility: hidden;}
        
        .stTabs [data-baseweb="tab-list"] { 
            gap: 24px; 
        }
        .stTabs [data-baseweb="tab"] { 
            height: 40px; 
            font-size: 16px; 
            font-weight: 600; 
        }
        
        div[data-testid="stRadio"] label { 
            white-space: nowrap; 
            font-size: 12px !important; 
            padding: 2px 0px; 
        }
        [data-testid="column"]:nth-child(2) { 
            padding-left: 0px !important; 
            padding-right: 0px !important; 
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Institutional Data Engine
# ==========================================
@st.cache_data(ttl=3600 * 12, show_spinner=False)
def fetch_global_data():
    FRED_API_KEY = '2855fd24c8cbc761cd583d64f97e7004' 
    
    yf_tickers = [
        '^GSPC', '^NDX', '^SOX', '^N225', '^KS11', '^HSI', '000001.SS', '^TWII',
        'GC=F', 'SI=F', 'HG=F', 'CL=F', 'NG=F', 'BZ=F', 'ZC=F', 'ZS=F', 'ZW=F', 'CT=F', 'BTC-USD',
        'USDCNY=X', 'AUDUSD=X', 'JPY=X', 'IDR=X', 'INR=X', 'TRY=X', 'EURUSD=X', 'GBPUSD=X', 
        'CAD=X', 'MXN=X', 'BRL=X', 'ARS=X', 'ILS=X', 'HKD=X', 'TLT',
        'DX-Y.NYB', '^VIX', 'EMB'
    ]
    
    yf_data = {}
    try:
        yf_raw = yf.download(yf_tickers, period="max", progress=False)
        for t in yf_tickers:
            try:
                df = pd.DataFrame({
                    'Open': yf_raw['Open'][t], 
                    'High': yf_raw['High'][t], 
                    'Low': yf_raw['Low'][t], 
                    'Close': yf_raw['Close'][t]
                }).dropna(how='all')
                if not df.empty: 
                    yf_data[t] = df.ffill().dropna()
            except: 
                pass
    except: 
        pass

    fred_tickers = [
        'SOFR', 'EFFR', 'DGS1MO', 'DGS3MO', 'DGS2', 'DGS5', 'DGS10', 'DGS30',
        'BAMLC0A1CAAA', 'BAMLC0A4CBBB', 'BAMLH0A0HYM2', 'DFII10', 'T10Y2Y', 'T10Y3M'
    ]
    
    fred_data = {}
    try:
        fred = Fred(api_key=FRED_API_KEY)
        for ticker in fred_tickers:
            try:
                series = fred.get_series(ticker)
                fred_data[ticker] = pd.DataFrame({'Close': series}).ffill().bfill().dropna()
            except: 
                pass
    except: 
        pass

    ak_symbols = {
        'SHFE_Silver': 'ag0', 'SHFE_Gold': 'au0', 'SHFE_Copper': 'cu0', 'SHFE_Aluminum': 'al0', 
        'SHFE_Zinc': 'zn0', 'SHFE_Nickel': 'ni0', 'SHFE_Rebar': 'rb0',
        'DCE_IronOre': 'i0', 'DCE_Coke': 'j0', 'DCE_SoybeanMeal': 'm0', 'DCE_SoybeanOil': 'y0',
        'ZCE_Sugar': 'SR0', 'ZCE_Cotton': 'CF0', 'ZCE_PTA': 'TA0', 'ZCE_Methanol': 'MA0'
    }
    
    cn_data = {}
    for name, symbol in ak_symbols.items():
        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'})
                cn_data[name] = df[['Open', 'High', 'Low', 'Close']].apply(pd.to_numeric, errors='coerce').dropna(how='all').ffill().dropna()
        except: 
            pass
            
    try:
        bond_df = ak.bond_zh_us_rate()
        if not bond_df.empty:
            bond_df['日期'] = pd.to_datetime(bond_df['日期'])
            bond_df.set_index('日期', inplace=True)
            cn_data['China_10Y_Yield'] = pd.DataFrame({'Close': pd.to_numeric(bond_df['中国国债收益率10年'], errors='coerce')}).dropna()
    except: 
        pass

    return {"yf": yf_data, "fred": fred_data, "mock": cn_data}

# ==========================================
# 2.1 Multi-Market Heatmap Pipeline
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_market_heatmap_raw(market_type):
    # 1. 标普 500: GICS 11 大行业
    if market_type == "US_SP500":
        hierarchy = [
            ('Tech', 'Info Tech (XLK)', 'XLK', 28.0), 
            ('Fin', 'Financials (XLF)', 'XLF', 13.0),
            ('Health', 'Health Care (XLV)', 'XLV', 12.0), 
            ('Cons Disc', 'Cons. Disc (XLY)', 'XLY', 10.0),
            ('Comm', 'Comm Svcs (XLC)', 'XLC', 8.0), 
            ('Indus', 'Industrials (XLI)', 'XLI', 8.0),
            ('Cons Stap', 'Cons. Staples (XLP)', 'XLP', 6.0), 
            ('Energy', 'Energy (XLE)', 'XLE', 4.0),
            ('Util', 'Utilities (XLU)', 'XLU', 2.5), 
            ('Mat', 'Materials (XLB)', 'XLB', 2.5), 
            ('RE', 'Real Estate (XLRE)', 'XLRE', 2.5)
        ]
    # 2. 纳指 100: 侧重科技细分
    elif market_type == "US_NAS100":
        hierarchy = [
            ('Tech', 'Semiconductors (SOXX)', 'SOXX', 25.0), 
            ('Tech', 'Software (IGV)', 'IGV', 20.0),
            ('Tech', 'Internet (FDN)', 'FDN', 15.0), 
            ('Health', 'Biotech (IBB)', 'IBB', 10.0),
            ('Comm', 'Comm Svcs (IYZ)', 'IYZ', 10.0), 
            ('Cons Disc', 'Retail (XRT)', 'XRT', 10.0),
            ('Indus', 'Aero/Def (ITA)', 'ITA', 10.0)
        ]
    # 3. 费城半导体: 产业链硬核拆解
    elif market_type == "US_SOX":
        hierarchy = [
            ('Fabless', 'Nvidia', 'NVDA', 20.0), ('Fabless', 'AMD', 'AMD', 10.0), ('Fabless', 'Qualcomm', 'QCOM', 8.0),
            ('Foundry', 'TSMC', 'TSM', 15.0),
            ('Equipment', 'ASML', 'ASML', 10.0), ('Equipment', 'Applied Mat', 'AMAT', 8.0), ('Equipment', 'Lam Rsch', 'LRCX', 6.0),
            ('IDM', 'Intel', 'INTC', 8.0), ('IDM', 'Texas Inst', 'TXN', 8.0), ('IDM', 'Micron', 'MU', 6.0),
            ('Broad/Net', 'Broadcom', 'AVGO', 15.0)
        ]
    # 4. 韩国 KOSPI: 财阀基本盘拆解
    elif market_type == "KR":
        hierarchy = [
            ('Tech', 'Samsung Elec', '005930.KS', 25.0), ('Tech', 'SK Hynix', '000660.KS', 15.0),
            ('Auto', 'Hyundai Motor', '005380.KS', 8.0), ('Auto', 'Kia', '000270.KS', 5.0),
            ('Chem/Batt', 'LG Chem', '051910.KS', 6.0), ('Chem/Batt', 'Samsung SDI', '006400.KS', 5.0),
            ('Finance', 'KB Fin', '105560.KS', 5.0), ('Finance', 'Shinhan', '055550.KS', 4.0),
            ('Comm', 'Naver', '035420.KS', 5.0), ('Comm', 'Kakao', '035720.KS', 4.0)
        ]
    # 5. 台湾加权: 半导体与代工帝国
    elif market_type == "TW":
        hierarchy = [
            ('Semiconductor', 'TSMC', '2330.TW', 35.0), ('Semiconductor', 'MediaTek', '2454.TW', 10.0),
            ('EMS/Hardware', 'Foxconn', '2317.TW', 12.0), ('EMS/Hardware', 'Quanta', '2382.TW', 8.0),
            ('EMS/Hardware', 'Delta Elec', '2308.TW', 6.0), ('EMS/Hardware', 'ASE Tech', '3711.TW', 5.0),
            ('Finance', 'Fubon Fin', '2881.TW', 6.0), ('Finance', 'Cathay Fin', '2882.TW', 5.0),
            ('Finance', 'CTBC Fin', '2891.TW', 4.0)
        ]
    # 6. A股 (SSE): 核心蓝筹时序追踪
    elif market_type == "CN":
        hierarchy = [
            ('Consumer', 'Moutai', '600519.SS', 15.0), ('Consumer', 'Wuliangye', '000858.SZ', 8.0),
            ('Finance', 'Merchants Bank', '600036.SS', 10.0), ('Finance', 'Ping An', '601318.SS', 8.0), ('Finance', 'ICBC', '601398.SS', 8.0),
            ('Tech/EV', 'CATL', '300750.SZ', 12.0), ('Tech/EV', 'BYD', '002594.SZ', 10.0), ('Tech/EV', 'Luxshare', '002475.SZ', 6.0),
            ('Health/Ind', 'Mindray', '300760.SZ', 6.0), ('Health/Ind', 'Wanhua', '600309.SS', 5.0)
        ]
    # 7. 日经 225: TOPIX 行业
    elif market_type == "JP":
        hierarchy = [
            ('Industry', 'IT & Services', '1627.T', 15.0), ('Industry', 'Elec. Appliances', '1625.T', 15.0),
            ('Industry', 'Transportation', '1622.T', 12.0), ('Finance', 'Banks', '1630.T', 10.0),
            ('Finance', 'Financials (Ex-Bank)', '1631.T', 5.0), ('Cons', 'Retail Trade', '1629.T', 8.0),
            ('Cons', 'Food', '1617.T', 5.0), ('Industry', 'Machinery', '1624.T', 7.0),
            ('Material', 'Steel/Nonferrous', '1623.T', 4.0), ('Material', 'Construction', '1619.T', 4.0),
            ('Utility', 'Energy', '1618.T', 5.0), ('Utility', 'Real Estate', '1632.T', 10.0)
        ]
    # 8. 恒生指数: 核心行业
    elif market_type == "HK":
        hierarchy = [
            ('Tech', 'HS Tech', '3033.HK', 25.0), ('Finance', 'HS Finance', '0005.HK', 20.0),
            ('Finance', 'HS Insurance', '1299.HK', 15.0), ('Cons', 'HS Consumer', '2318.HK', 15.0),
            ('RE', 'HS Property', '0016.HK', 10.0), ('Comm', 'HS Telecom', '0941.HK', 15.0)
        ]
    else: 
        return pd.DataFrame(), []

    tickers = [item[2] for item in hierarchy]
    try: 
        raw = yf.download(tickers, period="1y", progress=False)['Close']
        return raw, hierarchy
    except: 
        return pd.DataFrame(), hierarchy

def calculate_heatmap_performance(raw_data, hierarchy, lookback, market_type):
    if raw_data is None or raw_data.empty: 
        return pd.DataFrame()
        
    rows = []
    cur_yr = datetime.date.today().year
    
    # 统一使用降采样时序算法，抛弃原有的烂尾 A股快照逻辑
    for sec, sub, t, w in hierarchy:
        if t in raw_data.columns:
            s = raw_data[t].dropna()
            if len(s) < 2: 
                continue
            p_now = s.iloc[-1]
            
            if lookback == "1D": 
                p_old = s.iloc[-2]
            elif lookback == "5D": 
                p_old = s.iloc[-min(len(s), 6)]
            elif lookback == "1M": 
                p_old = s.iloc[-min(len(s), 22)]
            else:
                ytd = s[s.index.year == cur_yr]
                p_old = ytd.iloc[0] if not ytd.empty else s.iloc[0]
                
            rows.append({'Sector': sec, 'Sub': sub, 'Perf': ((p_now - p_old) / p_old) * 100, 'Weight': w})
            
    return pd.DataFrame(rows)

# ==========================================
# 3. Charting Factory
# ==========================================
def resample_data(df, timeframe):
    if df.empty or timeframe == "Daily": 
        return df
        
    rule = 'W' if timeframe == "Weekly" else 'ME'
    
    if all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']):
        return df.resample(rule).agg({
            'Open': 'first', 
            'High': 'max', 
            'Low': 'min', 
            'Close': 'last'
        }).dropna()
        
    return df.resample(rule).last().dropna()

def draw_bloomberg_chart(df_raw, title, base_color, timeframe, show_ma=True, unit=""):
    if df_raw is None or df_raw.empty: 
        return go.Figure()
        
    df = resample_data(df_raw.copy(), timeframe)
    
    # 性能保护：防止日线数据过多导致浏览器卡顿
    if timeframe == "Daily" and len(df) > 1500: 
        df = df.iloc[-1500:]
        
    has_ohlc = all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']) and timeframe != "MAX"
    close_col = 'Close' if 'Close' in df.columns else df.columns[0]
    
    fig = go.Figure()
    
    if has_ohlc: 
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
            increasing_line_color='#00CC96', decreasing_line_color='#FF4B4B'
        ))
    else: 
        fig.add_trace(go.Scattergl(
            x=df.index, y=df[close_col], mode='lines', 
            line=dict(color=base_color, width=2.5)
        ))

    last_price = df[close_col].iloc[-1]
    price_display = f"{last_price:,.2f} {unit}" if unit != "%" else f"{last_price:.4f}%"

    mom_val = 0
    mom_color = "#FFFFFF"
    
    if show_ma:
        df['EMA20'] = df[close_col].ewm(span=20, adjust=False).mean()
        df['EMA60'] = df[close_col].ewm(span=60, adjust=False).mean()
        df['EMA120'] = df[close_col].ewm(span=120, adjust=False).mean()
        
        # PPO 计算
        ema9 = df[close_col].ewm(span=9).mean()
        ema26 = df[close_col].ewm(span=26).mean()
        mom_val = (((ema9 - ema26) / ema26) * 100).iloc[-1]
        mom_color = "#00CC96" if mom_val >= 0 else "#FF4B4B"
        
        fig.add_trace(go.Scattergl(x=df.index, y=df['EMA20'], mode='lines', name='EMA20', line=dict(color='#FFD700', width=1.3)))
        fig.add_trace(go.Scattergl(x=df.index, y=df['EMA60'], mode='lines', name='EMA60', line=dict(color='#FF4B4B', width=1.3)))
        fig.add_trace(go.Scattergl(x=df.index, y=df['EMA120'], mode='lines', name='EMA120', line=dict(color='#AB63FA', width=1.3, dash='dot')))

    if len(df) > 10 and timeframe != "MAX":
        last_df = df.iloc[-min(len(df), 180):]
        y_min = last_df['Low'].min() if has_ohlc else last_df[close_col].min()
        y_max = last_df['High'].max() if has_ohlc else last_df[close_col].max()
        fig.update_layout(xaxis_range=[last_df.index[0], last_df.index[-1]], yaxis_range=[y_min*0.95, y_max*1.05])

    title_str = f"<b>{title}</b> &nbsp;&nbsp; <span style='font-size:22px;'>{price_display}</span>"
    if show_ma: 
        title_str += f" &nbsp;&nbsp; <span style='color:{mom_color}; font-size:14px;'>PPO: {mom_val:.2f}%</span>"
        
    fig.update_layout(
        height=470, 
        margin=dict(l=10, r=10, t=60, b=10), 
        template="plotly_dark", 
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)', 
        title=dict(text=title_str, font=dict(size=24)), 
        yaxis=dict(side="right", showgrid=True, gridcolor='rgba(128,128,128,0.15)', fixedrange=False), 
        xaxis=dict(rangeslider=dict(visible=False), showgrid=False), 
        hovermode="x unified", 
        dragmode='pan', 
        uirevision=title+timeframe
    )
    return fig

# ==========================================
# 4. Bloomberg Dashboard UI
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", width=40)
    st.title("Macro Terminal V3.13")
    st.markdown("---")
    
    page = st.selectbox("📂 Category", ["📊 Spreads & Ratios", "⚒️ Commodity", "💱 FX & FI", "📈 Equity Markets"])
    
    asset_list = []
    if page == "📊 Spreads & Ratios": 
        asset_list = [
            "High-Yield Spread (OAS)", "J.P. Morgan EMBI Bond (EMB)", "AAA Corporate Spread", 
            "BAA Corporate Spread", "10Y-2Y Spread", "10Y-3M Spread", "SOFR-EFFR Premium", 
            "Gold-Silver Ratio", "Gold-WTI Ratio", "Gold-Copper Ratio"
        ]
    elif page == "⚒️ Commodity": 
        asset_list = [
            "Gold (GC=F)", "Silver (SI=F)", "Copper (HG=F)", "WTI Crude (CL=F)", "Brent Crude (BZ=F)", 
            "Natural Gas (NG=F)", "Corn (ZC=F)", "Soybeans (ZS=F)", "Wheat (ZW=F)", "Cotton (CT=F)", 
            "Bitcoin (BTC-USD)", "SHFE Silver", "SHFE Aluminum", "SHFE Zinc", "SHFE Nickel", 
            "SHFE Rebar", "DCE Iron Ore", "DCE Coke", "ZCE PTA", "ZCE Methanol", "ZCE Sugar", 
            "DCE Soybean Meal", "DCE Soybean Oil"
        ]
    elif page == "💱 FX & FI": 
        asset_list = [
            "US Dollar Index (DXY)", "USD/CNH", "USD/JPY", "AUD/USD", "EUR/USD", "GBP/USD", 
            "USD/CAD", "USD/INR", "USD/BRL", "US 2Y Yield", "US 10Y Yield", "US 30Y Yield", 
            "US 10Y Real Yield", "China 10Y Yield", "US Long Treas (TLT)"
        ]
    elif page == "📈 Equity Markets": 
        asset_list = [
            "S&P 500 (^GSPC)", "Nasdaq 100 (^NDX)", "Volatility Index (VIX)", "Nikkei 225 (^N225)", 
            "Hang Seng (^HSI)", "SSE Composite", "KOSPI (^KS11)", "Taiwan (^TWII)", "Semiconductor (^SOX)"
        ]
        
    selected_asset = st.radio("🎯 Select Asset", asset_list)
    st.markdown("---")
    
    selected_timeframe = st.radio("Resolution", ["Daily", "Weekly", "Monthly", "MAX"], horizontal=True, label_visibility="collapsed")
    if st.button("🔄 Force Sync Data", type="primary", use_container_width=True):
        fetch_global_data.clear()
        fetch_market_heatmap_raw.clear()
        st.rerun()
        
    db = fetch_global_data()

# ==========================================
# 5. Main Execution
# ==========================================
if db:
    yf_df, fr_df, mk_df = db['yf'], db['fred'], db['mock']
    
    def safe_sub(df1, df2): 
        return pd.DataFrame({'Close': df1['Close'] - df2['Close']}).dropna() if df1 is not None and df2 is not None else None
        
    def safe_div(df1, df2): 
        return pd.DataFrame({'Close': df1['Close'] / df2['Close']}).dropna() if df1 is not None and df2 is not None else None

    def get_data(asset_name):
        mapping = {
            "High-Yield Spread (OAS)": (fr_df.get('BAMLH0A0HYM2'), "#FF4B4B", False, "%"),
            "J.P. Morgan EMBI Bond (EMB)": (yf_df.get('EMB'), "#DC143C", True, "USD"),
            "AAA Corporate Spread": (fr_df.get('BAMLC0A1CAAA'), "#FFA500", False, "%"),
            "BAA Corporate Spread": (fr_df.get('BAMLC0A4CBBB'), "#FFD700", False, "%"),
            "10Y-2Y Spread": (fr_df.get('T10Y2Y'), "#FF4B4B", False, "%"), 
            "10Y-3M Spread": (fr_df.get('T10Y3M'), "#DC143C", False, "%"), 
            "SOFR-EFFR Premium": (safe_sub(fr_df.get('SOFR'), fr_df.get('EFFR')), "#00CC96", False, "%"),
            "Gold-Silver Ratio": (safe_div(yf_df.get('GC=F'), yf_df.get('SI=F')), "#AB63FA", False, ""),
            "Gold-WTI Ratio": (safe_div(yf_df.get('GC=F'), yf_df.get('CL=F')), "#00BFFF", False, ""),
            "Gold-Copper Ratio": (safe_div(yf_df.get('GC=F'), yf_df.get('HG=F')), "#8A2BE2", False, ""),
            
            "Gold (GC=F)": (yf_df.get('GC=F'), "#FFD700", True, "USD"), 
            "Silver (SI=F)": (yf_df.get('SI=F'), "#C0C0C0", True, "USD"),
            "Copper (HG=F)": (yf_df.get('HG=F'), "#B87333", True, "USD"), 
            "WTI Crude (CL=F)": (yf_df.get('CL=F'), "#8B4513", True, "USD"),
            "Brent Crude (BZ=F)": (yf_df.get('BZ=F'), "#A0522D", True, "USD"), 
            "Natural Gas (NG=F)": (yf_df.get('NG=F'), "#4682B4", True, "USD"),
            "Corn (ZC=F)": (yf_df.get('ZC=F'), "#FFD700", True, "USD"), 
            "Soybeans (ZS=F)": (yf_df.get('ZS=F'), "#9ACD32", True, "USD"),
            "Wheat (ZW=F)": (yf_df.get('ZW=F'), "#F5DEB3", True, "USD"), 
            "Cotton (CT=F)": (yf_df.get('CT=F'), "#FFFAFA", True, "USD"),
            "Bitcoin (BTC-USD)": (yf_df.get('BTC-USD'), "#FF8C00", True, "USD"), 
            
            "SHFE Silver": (mk_df.get('SHFE_Silver'), "#C0C0C0", True, "CNY"),
            "SHFE Aluminum": (mk_df.get('SHFE_Aluminum'), "#A9A9A9", True, "CNY"), 
            "SHFE Zinc": (mk_df.get('SHFE_Zinc'), "#778899", True, "CNY"),
            "SHFE Nickel": (mk_df.get('SHFE_Nickel'), "#708090", True, "CNY"), 
            "SHFE Rebar": (mk_df.get('SHFE_Rebar'), "#696969", True, "CNY"),
            "DCE Iron Ore": (mk_df.get('DCE_IronOre'), "#8B4513", True, "CNY"), 
            "DCE Coke": (mk_df.get('DCE_Coke'), "#2F4F4F", True, "CNY"),
            "ZCE PTA": (mk_df.get('ZCE_PTA'), "#483D8B", True, "CNY"), 
            "ZCE Methanol": (mk_df.get('ZCE_Methanol'), "#4B0082", True, "CNY"),
            "ZCE Sugar": (mk_df.get('ZCE_Sugar'), "#F8F8FF", True, "CNY"), 
            "DCE Soybean Meal": (mk_df.get('DCE_SoybeanMeal'), "#9ACD32", True, "CNY"),
            "DCE Soybean Oil": (mk_df.get('DCE_SoybeanOil'), "#DAA520", True, "CNY"),
            
            "US Dollar Index (DXY)": (yf_df.get('DX-Y.NYB'), "#1E90FF", True, ""), 
            "USD/CNH": (yf_df.get('USDCNY=X'), "#FF4B4B", True, ""),
            "USD/JPY": (yf_df.get('JPY=X'), "#AB63FA", True, ""), 
            "AUD/USD": (yf_df.get('AUDUSD=X'), "#00CC96", True, ""),
            "EUR/USD": (yf_df.get('EURUSD=X'), "#1E90FF", True, ""), 
            "GBP/USD": (yf_df.get('GBPUSD=X'), "#8A2BE2", True, ""),
            "USD/CAD": (yf_df.get('CAD=X'), "#DC143C", True, ""), 
            "USD/INR": (yf_df.get('INR=X'), "#00BFFF", True, ""),
            "USD/BRL": (yf_df.get('BRL=X'), "#32CD32", True, ""), 
            
            "US 2Y Yield": (fr_df.get('DGS2'), "#696969", True, "%"),
            "US 10Y Yield": (fr_df.get('DGS10'), "#8B0000", True, "%"), 
            "US 30Y Yield": (fr_df.get('DGS30'), "#800000", True, "%"),
            "US 10Y Real Yield": (fr_df.get('DFII10'), "#00CC96", True, "%"), 
            "China 10Y Yield": (mk_df.get('China_10Y_Yield'), "#FF4B4B", True, "%"),
            "US Long Treas (TLT)": (yf_df.get('TLT'), "#4682B4", True, "USD"), 
            
            "S&P 500 (^GSPC)": (yf_df.get('^GSPC'), "#00CC96", True, "USD"),
            "Nasdaq 100 (^NDX)": (yf_df.get('^NDX'), "#1E90FF", True, "USD"), 
            "Volatility Index (VIX)": (yf_df.get('^VIX'), "#FF4B4B", True, ""),
            "Nikkei 225 (^N225)": (yf_df.get('^N225'), "#FF4B4B", True, "JPY"), 
            "Hang Seng (^HSI)": (yf_df.get('^HSI'), "#00BFFF", True, "HKD"),
            "SSE Composite": (yf_df.get('000001.SS'), "#FF8C00", True, "CNY"), 
            "KOSPI (^KS11)": (yf_df.get('^KS11'), "#FFA500", True, "KRW"),
            "Taiwan (^TWII)": (yf_df.get('^TWII'), "#32CD32", True, "TWD"), 
            "Semiconductor (^SOX)": (yf_df.get('^SOX'), "#AB63FA", True, "USD")
        }
        return mapping.get(asset_name, (None, "#FFFFFF", False, ""))

    target_df, color, use_ma, unit = get_data(selected_asset)
    plot_config = {'scrollZoom': True, 'displayModeBar': False, 'showTips': False, 'displaylogo': False}
    
    if page == "📈 Equity Markets":
        tab1, tab2 = st.tabs(["🎯 Asset Analysis", "📊 Sector X-Ray (Heatmap)"])
        
        with tab1:
            st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, color, selected_timeframe, show_ma=use_ma, unit=unit), use_container_width=True, config=plot_config)
            
        with tab2:
            # 差异化市场类型精准匹配路由
            if "^GSPC" in selected_asset: 
                m_type = "US_SP500"
            elif "^NDX" in selected_asset: 
                m_type = "US_NAS100"
            elif "^SOX" in selected_asset: 
                m_type = "US_SOX"
            elif "^HSI" in selected_asset: 
                m_type = "HK"
            elif "^N225" in selected_asset: 
                m_type = "JP"
            elif "^KS11" in selected_asset: 
                m_type = "KR"
            elif "^TWII" in selected_asset: 
                m_type = "TW"
            elif "SSE" in selected_asset: 
                m_type = "CN"
            else: 
                m_type = "US_SP500"
            
            c_tree, c_perf, c_period = st.columns([15, 0.8, 1.2])
            
            with c_period:
                st.markdown("<div style='height:40px;'></div><div style='color:gray; font-size:12px; font-weight:bold;'>Period</div>", unsafe_allow_html=True)
                lookback = st.radio("L", ["1D", "5D", "1M", "YTD"], index=3, label_visibility="collapsed")
                
            raw_h, hier = fetch_market_heatmap_raw(m_type)
            df_t = calculate_heatmap_performance(raw_h, hier, lookback, m_type)
            
            with c_tree:
                if not df_t.empty:
                    fig_t = px.treemap(
                        df_t, 
                        path=[px.Constant(f"{m_type}"), 'Sector', 'Sub'], 
                        values='Weight', 
                        color='Perf', 
                        color_continuous_scale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']], 
                        color_continuous_midpoint=0
                    )
                    fig_t.update_layout(height=470, margin=dict(l=0, r=0, t=0, b=0), template="plotly_dark", coloraxis_showscale=False)
                    fig_t.update_traces(customdata=df_t[['Perf']], texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%", root_color="#000")
                    st.plotly_chart(fig_t, use_container_width=True, config={'displayModeBar': False})
                    
            with c_perf:
                if not df_t.empty:
                    fig_p = go.Figure(go.Scatter(
                        x=[None], y=[None], mode='markers', 
                        marker=dict(
                            colorscale=[[0, '#FF4B4B'], [0.5, '#111111'], [1.0, '#00CC96']], 
                            cmin=df_t['Perf'].min(), 
                            cmax=df_t['Perf'].max(), 
                            showscale=True, 
                            colorbar=dict(
                                title=dict(text=f"{lookback}%", font=dict(size=12)), 
                                thickness=15, len=1.0, x=0, y=0.5, yanchor="middle"
                            )
                        )
                    ))
                    fig_p.update_layout(height=470, width=60, margin=dict(l=0, r=0, t=40, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(visible=False), yaxis=dict(visible=False))
                    st.plotly_chart(fig_p, use_container_width=False, config={'displayModeBar': False})
    else:
        st.plotly_chart(draw_bloomberg_chart(target_df, selected_asset, color, selected_timeframe, show_ma=use_ma, unit=unit), use_container_width=True, config=plot_config)
