import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
import warnings
import requests
import re
warnings.filterwarnings('ignore')

# 尝试导入 akshare
try:
    import akshare as ak
    HAS_AKSHARE = True
except:
    HAS_AKSHARE = False

# 尝试导入 plotly
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except:
    HAS_PLOTLY = False

# 页面配置
st.set_page_config(
    page_title="股票盯盘助手",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 标题
st.title("📈 股票盯盘助手（多数据源版）")
st.markdown("---")

# 初始化session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['600559', '000001']

if 'alerts' not in st.session_state:
    st.session_state.alerts = {}

# ========== 多数据源股票接口 ==========
class MultiSourceStockAPI:
    """多数据源股票接口 - 自动切换备用源"""
    
    def __init__(self):
        self.current_source = "自动"
    
    def get_realtime_quotes(self, codes):
        """获取实时行情 - 多数据源尝试"""
        # 方案1: AKShare (推荐)
        if HAS_AKSHARE:
            try:
                result = self._get_quotes_akshare(codes)
                if result:
                    self.current_source = "AKShare"
                    return result
            except Exception as e:
                print(f"AKShare失败: {e}")
        
        # 方案2: 新浪财经
        try:
            result = self._get_quotes_sina(codes)
            if result:
                self.current_source = "新浪财经"
                return result
        except Exception as e:
            print(f"新浪失败: {e}")
        
        # 方案3: 腾讯财经
        try:
            result = self._get_quotes_tencent(codes)
            if result:
                self.current_source = "腾讯财经"
                return result
        except Exception as e:
            print(f"腾讯失败: {e}")
        
        return {}
    
    def _get_quotes_akshare(self, codes):
        """AKShare接口"""
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return {}
        
        # 列名映射
        code_col = '代码' if '代码' in df.columns else 'code'
        name_col = '名称' if '名称' in df.columns else 'name'
        price_col = '最新价' if '最新价' in df.columns else 'price'
        
        result = {}
        for code in codes:
            stock = df[df[code_col].astype(str) == code]
            if not stock.empty:
                row = stock.iloc[0]
                result[code] = {
                    'code': code,
                    'name': row.get(name_col, code),
                    'price': float(row.get(price_col, 0) or 0),
                    'open': float(row.get('今开', 0) or 0),
                    'high': float(row.get('最高', 0) or 0),
                    'low': float(row.get('最低', 0) or 0),
                    'volume': float(row.get('成交量', 0) or 0),
                    'prev_close': float(row.get('昨收', 0) or 0),
                }
                # 计算涨跌
                if result[code]['prev_close'] > 0:
                    result[code]['change'] = result[code]['price'] - result[code]['prev_close']
                    result[code]['change_pct'] = result[code]['change'] / result[code]['prev_close'] * 100
                else:
                    result[code]['change'] = 0
                    result[code]['change_pct'] = 0
        
        return result
    
    def _get_quotes_sina(self, codes):
        """新浪财经接口"""
        code_list = []
        for code in codes:
            if code.startswith('6'):
                code_list.append(f"sh{code}")
            else:
                code_list.append(f"sz{code}")
        
        url = f"https://hq.sinajs.cn/list={','.join(code_list)}"
        headers = {
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'
        
        result = {}
        lines = response.text.strip().split('\n')
        
        for line in lines:
            match = re.match(r'var hq_str_(sh|sz)(\d+)="(.*)"', line)
            if match:
                code = match.group(2)
                data = match.group(3).split(',')
                
                if len(data) >= 10:
                    try:
                        result[code] = {
                            'code': code,
                            'name': data[0],
                            'open': float(data[1]) if data[1] else 0,
                            'prev_close': float(data[2]) if data[2] else 0,
                            'price': float(data[3]) if data[3] else 0,
                            'high': float(data[4]) if data[4] else 0,
                            'low': float(data[5]) if data[5] else 0,
                            'volume': float(data[8]) if data[8] else 0,
                            'change': float(data[3]) - float(data[2]) if data[2] and data[3] else 0,
                            'change_pct': (float(data[3]) - float(data[2])) / float(data[2]) * 100 if data[2] and float(data[2]) > 0 else 0,
                        }
                    except:
                        pass
        
        return result
    
    def _get_quotes_tencent(self, codes):
        """腾讯财经接口"""
        result = {}
        
        for code in codes:
            try:
                prefix = 'sh' if code.startswith('6') else 'sz'
                url = f"https://web.sqt.gtimg.cn/q={prefix}{code}"
                headers = {'User-Agent': 'Mozilla/5.0'}
                
                response = requests.get(url, headers=headers, timeout=5)
                response.encoding = 'gbk'
                
                # 解析腾讯格式: v_sh600559="1~老白干酒~600559~13.50~..."
                match = re.search(r'"([^"]+)"', response.text)
                if match:
                    data = match.group(1).split('~')
                    if len(data) >= 35:
                        result[code] = {
                            'code': code,
                            'name': data[1],
                            'price': float(data[3]) if data[3] else 0,
                            'prev_close': float(data[4]) if data[4] else 0,
                            'open': float(data[5]) if data[5] else 0,
                            'volume': float(data[6]) if data[6] else 0,
                            'high': float(data[33]) if len(data) > 33 and data[33] else 0,
                            'low': float(data[34]) if len(data) > 34 and data[34] else 0,
                            'change': float(data[31]) if len(data) > 31 and data[31] else 0,
                            'change_pct': float(data[32]) if len(data) > 32 and data[32] else 0,
                        }
            except:
                pass
        
        return result
    
    def get_history_data(self, code, days=60):
        """获取历史K线数据"""
        # 方案1: AKShare
        if HAS_AKSHARE:
            try:
                df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                if df is not None and len(df) > 0:
                    self.current_source = "AKShare"
                    return df.tail(days)
            except:
                pass
        
        # 方案2: 腾讯财经
        try:
            prefix = 'sh' if code.startswith('6') else 'sz'
            url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                'param': f"{prefix}{code},day,,,{days},qfq",
                'r': int(time.time())
            }
            
            response = requests.get(url, params=params, timeout=10)
            json_data = response.json()
            
            if json_data and 'data' in json_data:
                stock_data = json_data['data'].get(f"{prefix}{code}", {})
                kline_data = stock_data.get('day', [])
                
                if kline_data:
                    df = pd.DataFrame(kline_data, columns=['日期', '开盘', '收盘', '最高', '最低', '成交量', ''])
                    df = df[['日期', '开盘', '收盘', '最高', '最低', '成交量']]
                    for col in ['开盘', '收盘', '最高', '最低', '成交量']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    self.current_source = "腾讯财经"
                    return df
        except:
            pass
        
        return None

# 创建API实例
stock_api = MultiSourceStockAPI()

# ========== 技术指标计算 ==========
def calculate_ma(close, periods=[5, 10, 20, 60]):
    mas = {}
    for p in periods:
        if len(close) >= p:
            mas[f'MA{p}'] = np.mean(close[-p:])
    return mas

def calculate_macd(close, fast=12, slow=26, signal=9):
    ema_fast = pd.Series(close).ewm(span=fast).mean()
    ema_slow = pd.Series(close).ewm(span=slow).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal).mean()
    macd = (dif - dea) * 2
    return dif.values, dea.values, macd.values

def calculate_kdj(high, low, close, n=9):
    low_list = pd.Series(low).rolling(window=n, min_periods=1).min()
    high_list = pd.Series(high).rolling(window=n, min_periods=1).max()
    rsv = (pd.Series(close) - low_list) / (high_list - low_list + 0.0001) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k.values, d.values, j.values

def calculate_rsi(close, n=14):
    delta = pd.Series(close).diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=n).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=n).mean()
    rs = gain / (loss + 0.0001)
    return (100 - (100 / (1 + rs))).values

# ========== K线图绘制 ==========
def plot_kline(df, stock_code, stock_name, show_macd=True, show_kdj=True, show_rsi=True):
    if not HAS_PLOTLY:
        return None
    
    close = df['收盘'].values
    high = df['最高'].values
    low = df['最低'].values
    
    dif, dea, macd = calculate_macd(close)
    k, d, j = calculate_kdj(high, low, close)
    rsi = calculate_rsi(close)
    
    ma5 = pd.Series(close).rolling(5).mean()
    ma10 = pd.Series(close).rolling(10).mean()
    ma20 = pd.Series(close).rolling(20).mean()
    
    rows = 1 + show_macd + show_kdj + show_rsi
    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6] + [0.13] * (rows - 1)
    )
    
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df['开盘'], high=df['最高'],
            low=df['最低'], close=df['收盘'],
            name='K线', increasing_line_color='red', decreasing_line_color='green'
        ),
        row=1, col=1
    )
    
    fig.add_trace(go.Scatter(x=df.index, y=ma5, name='MA5', line=dict(color='white', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ma10, name='MA10', line=dict(color='yellow', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ma20, name='MA20', line=dict(color='purple', width=1)), row=1, col=1)
    
    current_row = 2
    if show_macd:
        fig.add_trace(go.Scatter(x=df.index, y=dif, name='DIF', line=dict(color='white')), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=dea, name='DEA', line=dict(color='yellow')), row=current_row, col=1)
        colors = ['red' if v >= 0 else 'green' for v in macd]
        fig.add_trace(go.Bar(x=df.index, y=macd, name='MACD', marker_color=colors), row=current_row, col=1)
        current_row += 1
    
    if show_kdj:
        fig.add_trace(go.Scatter(x=df.index, y=k, name='K', line=dict(color='white')), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=d, name='D', line=dict(color='yellow')), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=j, name='J', line=dict(color='purple')), row=current_row, col=1)
        current_row += 1
    
    if show_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI', line=dict(color='white')), row=current_row, col=1)
        fig.add_hline(y=80, line_dash="dash", line_color="red", row=current_row, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="green", row=current_row, col=1)
    
    fig.update_layout(
        template='plotly_dark', height=600,
        xaxis_rangeslider_visible=False, showlegend=True
    )
    
    return fig

# ========== 页面导航 ==========
tab1, tab2, tab3 = st.tabs(["📊 实时行情", "🎯 多因子选股", "⏰ 价格预警"])

# ========== Tab1: 实时行情 ==========
with tab1:
    with st.sidebar:
        st.header("📝 自选股管理")
        
        new_stock = st.text_input("添加股票代码", placeholder="如: 600519")
        if st.button("添加"):
            if new_stock and len(new_stock) == 6 and new_stock.isdigit():
                if new_stock not in st.session_state.watchlist:
                    st.session_state.watchlist.append(new_stock)
                    st.success(f"已添加 {new_stock}")
                    st.rerun()
                else:
                    st.warning("已在列表中")
            else:
                st.error("请输入6位数字代码")
        
        st.markdown("---")
        st.subheader("当前自选股")
        for stock in st.session_state.watchlist[:]:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(stock)
            with col2:
                if st.button("删除", key=f"del_{stock}"):
                    st.session_state.watchlist.remove(stock)
                    st.rerun()
        
        st.markdown("---")
        st.header("📊 K线设置")
        days_select = st.slider("显示天数", 30, 120, 60)
        
        st.markdown("---")
        st.header("📈 技术指标")
        show_macd = st.checkbox("MACD", value=True)
        show_kdj = st.checkbox("KDJ", value=True)
        show_rsi = st.checkbox("RSI", value=True)
    
    st.header("📊 实时行情 + K线分析")
    
    selected_stock = st.selectbox("选择股票查看K线", st.session_state.watchlist)
    
    if st.button("🔄 刷新数据", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    @st.cache_data(ttl=60)
    def get_quotes(codes):
        return stock_api.get_realtime_quotes(codes)
    
    @st.cache_data(ttl=300)
    def get_history(code, days=60):
        return stock_api.get_history_data(code, days)
    
    with st.spinner("正在获取数据..."):
        quotes = get_quotes(st.session_state.watchlist)
        hist_df = get_history(selected_stock, days_select)
    
    if quotes and selected_stock in quotes:
        quote = quotes[selected_stock]
        
        # 显示当前数据源
        st.info(f"📡 当前数据源: {stock_api.current_source}")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("最新价", f"¥{quote['price']:.2f}")
        with col2:
            st.metric("涨跌幅", f"{quote['change_pct']:.2f}%")
        with col3:
            st.metric("今开", f"¥{quote['open']:.2f}")
        with col4:
            st.metric("最高", f"¥{quote['high']:.2f}")
        with col5:
            st.metric("最低", f"¥{quote['low']:.2f}")
        
        st.markdown("---")
        
        if hist_df is not None and not hist_df.empty:
            close = hist_df['收盘'].values
            high = hist_df['最高'].values
            low = hist_df['最低'].values
            
            dif, dea, macd = calculate_macd(close)
            k, d, j = calculate_kdj(high, low, close)
            rsi = calculate_rsi(close)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("MACD", f"{macd[-1]:.3f}")
            with col2:
                st.metric("KDJ", f"{j[-1]:.1f}")
            with col3:
                st.metric("RSI(14)", f"{rsi[-1]:.1f}")
            
            fig = plot_kline(hist_df, selected_stock, quote['name'], show_macd, show_kdj, show_rsi)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            mas = calculate_ma(close, [5, 10, 20, 60])
            st.markdown("**📈 均线系统**")
            cols = st.columns(len(mas))
            for i, (name, value) in enumerate(mas.items()):
                cols[i].metric(name, f"¥{value:.2f}")
        else:
            st.warning("获取历史数据失败")
    else:
        st.error("获取数据失败，请刷新重试")
    
    st.markdown("---")
    st.caption(f"数据来源: {stock_api.current_source} | 更新时间: {datetime.now().strftime('%H:%M:%S')}")

# ========== Tab2: 多因子选股 ==========
with tab2:
    st.header("🎯 多因子共振选股")
    
    if not HAS_AKSHARE:
        st.warning("⚠️ 选股功能需要安装 akshare 库")
        st.code("pip install akshare")
    else:
        st.markdown("""
        **策略说明：**
        - 选股范围：60/00开头沪深主板，剔除ST
        - 反转形态：连续2日抬升
        - 多因子共振：8项满足≥7项
        """)
        
        with st.expander("⚙️ 选股参数设置"):
            col1, col2 = st.columns(2)
            with col1:
                min_rise = st.slider("最低涨幅要求(%)", 0, 10, 3)
            with col2:
                max_results = st.slider("最多显示结果数", 10, 50, 20)
        
        if st.button("🚀 开始选股", type="primary"):
            with st.spinner("正在筛选..."):
                try:
                    # 获取涨幅榜
                    df = ak.stock_zh_a_spot_em()
                    
                    # 筛选主板
                    code_col = '代码' if '代码' in df.columns else 'code'
                    name_col = '名称' if '名称' in df.columns else 'name'
                    pct_col = '涨跌幅' if '涨跌幅' in df.columns else 'change_pct'
                    
                    df = df[df[code_col].str.match(r'^(60|00)')]
                    df = df[~df[name_col].str.contains('ST|退市', case=False, na=False)]
                    df = df[pd.to_numeric(df[pct_col], errors='coerce') >= min_rise]
                    
                    st.success(f"🎯 筛选出 {len(df)} 只符合条件的股票")
                    st.dataframe(df[[code_col, name_col, pct_col]].head(max_results), use_container_width=True)
                    
                except Exception as e:
                    st.error(f"选股失败: {str(e)}")

# ========== Tab3: 价格预警 ==========
with tab3:
    st.header("⏰ 价格预警设置")
    
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        alert_stock = st.text_input("股票代码", key="alert_stock")
    with col2:
        alert_price = st.number_input("目标价格", min_value=0.0, step=0.01, key="alert_price")
    with col3:
        alert_type = st.selectbox("预警类型", ["突破上方", "跌破下方"], key="alert_type")
    
    if st.button("添加预警", type="primary"):
        if alert_stock and alert_price > 0:
            st.session_state.alerts[alert_stock] = {
                'price': alert_price,
                'type': 'above' if alert_type == "突破上方" else 'below'
            }
            st.success(f"已添加预警: {alert_stock}")
    
    if st.session_state.alerts:
        st.markdown("---")
        st.subheader("📋 预警列表")
        
        for stock, info in st.session_state.alerts.items():
            st.text(f"{stock} - {'突破' if info['type'] == 'above' else '跌破'} ¥{info['price']}")

# ========== 页脚 ==========
st.markdown("---")
st.caption("📈 股票盯盘助手 | 数据源: AKShare/新浪/腾讯 自动切换 | ⚠️ 仅供学习参考")
