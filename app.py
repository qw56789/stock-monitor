import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
import warnings
import requests
import re
warnings.filterwarnings('ignore')

# 额外依赖：plotly用于交互式K线图
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
st.title("📈 股票盯盘助手")
st.markdown("---")

# 初始化session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['600559', '000001']

if 'alerts' not in st.session_state:
    st.session_state.alerts = {}

# ========== 新浪财经数据接口 ==========
class SinaStockAPI:
    """新浪财经数据接口"""
    
    BASE_URL = "https://hq.sinajs.cn"
    
    @staticmethod
    def get_realtime_quotes(codes):
        """
        获取实时行情（新浪接口）
        codes: 股票代码列表，如 ['600559', '000001']
        """
        # 构建请求URL
        # 上海股票加sh前缀，深圳股票加sz前缀
        code_list = []
        for code in codes:
            if code.startswith('6'):
                code_list.append(f"sh{code}")
            else:
                code_list.append(f"sz{code}")
        
        url = f"{SinaStockAPI.BASE_URL}/list={''.join(code_list)}"
        
        try:
            headers = {
                'Referer': 'https://finance.sina.com.cn',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            
            result = {}
            lines = response.text.strip().split('\n')
            
            for line in lines:
                # 解析：var hq_str_sh600559="老白干酒,13.50,13.20,..."
                match = re.match(r'var hq_str_(sh|sz)(\d+)="(.*)"', line)
                if match:
                    prefix = match.group(1)
                    code = match.group(2)
                    data = match.group(3).split(',')
                    
                    if len(data) >= 32:
                        result[code] = {
                            'code': code,
                            'name': data[0],
                            'open': float(data[1]) if data[1] else 0,
                            'prev_close': float(data[2]) if data[2] else 0,
                            'price': float(data[3]) if data[3] else 0,
                            'high': float(data[4]) if data[4] else 0,
                            'low': float(data[5]) if data[5] else 0,
                            'volume': float(data[8]) if data[8] else 0,
                            'amount': float(data[9]) if data[9] else 0,
                            'change': float(data[3]) - float(data[2]) if data[2] and data[3] else 0,
                            'change_pct': (float(data[3]) - float(data[2])) / float(data[2]) * 100 if data[2] and data[3] and float(data[2]) > 0 else 0,
                        }
            
            return result
        except Exception as e:
            print(f"新浪接口错误: {e}")
            return {}
    
    @staticmethod
    def get_history_data(code, days=60):
        """
        获取历史K线数据
        使用新浪历史数据接口
        """
        try:
            # 新浪历史数据接口
            if code.startswith('6'):
                symbol = f"sh{code}"
            else:
                symbol = f"sz{code}"
            
            url = f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
            params = {
                'symbol': symbol,
                'scale': '240',  # 日线
                'ma': 'no',
                'datalen': days
            }
            
            headers = {
                'Referer': 'https://finance.sina.com.cn',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            if data and isinstance(data, list):
                df = pd.DataFrame(data)
                df = df.rename(columns={
                    'day': '日期',
                    'open': '开盘',
                    'high': '最高',
                    'low': '最低',
                    'close': '收盘',
                    'volume': '成交量'
                })
                # 转换数据类型
                for col in ['开盘', '最高', '最低', '收盘', '成交量']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                return df
        except Exception as e:
            print(f"获取历史数据失败: {e}")
        
        # 如果新浪接口失败，尝试备用方案
        return SinaStockAPI._get_history_backup(code, days)
    
    @staticmethod
    def _get_history_backup(code, days=60):
        """备用：使用腾讯财经接口"""
        try:
            url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                '_var': 'kline_dayqfq',
                'param': f"{'sh' if code.startswith('6') else 'sz'}{code},day,,,{days},qfq",
                'r': int(time.time())
            }
            
            response = requests.get(url, params=params, timeout=10)
            json_data = response.json()
            
            if json_data and 'data' in json_data:
                stock_data = json_data['data'].get(f"{'sh' if code.startswith('6') else 'sz'}{code}", {})
                kline_data = stock_data.get('day', [])
                
                if kline_data:
                    df = pd.DataFrame(kline_data, columns=['日期', '开盘', '收盘', '最高', '最低', '成交量', ''])
                    df = df[['日期', '开盘', '收盘', '最高', '最低', '成交量']]
                    for col in ['开盘', '收盘', '最高', '最低', '成交量']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    return df
        except Exception as e:
            print(f"备用接口也失败: {e}")
        
        return None

# 创建API实例
sina_api = SinaStockAPI()

# ========== 技术指标计算函数 ==========
def calculate_ma(close, periods=[5, 10, 20, 60]):
    """计算均线"""
    mas = {}
    for p in periods:
        if len(close) >= p:
            mas[f'MA{p}'] = np.mean(close[-p:])
    return mas

def calculate_macd(close, fast=12, slow=26, signal=9):
    """计算MACD"""
    ema_fast = pd.Series(close).ewm(span=fast).mean()
    ema_slow = pd.Series(close).ewm(span=slow).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal).mean()
    macd = (dif - dea) * 2
    return dif.values, dea.values, macd.values

def calculate_kdj(high, low, close, n=9, m1=3, m2=3):
    """计算KDJ"""
    low_list = pd.Series(low).rolling(window=n, min_periods=1).min()
    high_list = pd.Series(high).rolling(window=n, min_periods=1).max()
    rsv = (pd.Series(close) - low_list) / (high_list - low_list + 0.0001) * 100
    k = rsv.ewm(com=m1-1, adjust=False).mean()
    d = k.ewm(com=m2-1, adjust=False).mean()
    j = 3 * k - 2 * d
    return k.values, d.values, j.values

def calculate_rsi(close, n=14):
    """计算RSI"""
    delta = pd.Series(close).diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=n).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=n).mean()
    rs = gain / (loss + 0.0001)
    rsi = 100 - (100 / (1 + rs))
    return rsi.values

# ========== K线图绘制 ==========
def plot_kline(df, stock_code, stock_name, show_macd=True, show_kdj=True, show_rsi=True):
    """绘制K线图和技术指标"""
    if not HAS_PLOTLY:
        st.warning("请安装plotly: pip install plotly")
        return None
    
    # 计算技术指标
    close = df['收盘'].values
    high = df['最高'].values
    low = df['最低'].values
    
    dif, dea, macd = calculate_macd(close)
    k, d, j = calculate_kdj(high, low, close)
    rsi = calculate_rsi(close)
    
    # 均线
    ma5 = pd.Series(close).rolling(5).mean()
    ma10 = pd.Series(close).rolling(10).mean()
    ma20 = pd.Series(close).rolling(20).mean()
    
    # 创建子图
    rows = 1 + show_macd + show_kdj + show_rsi
    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6] + [0.13] * (rows - 1),
        subplot_titles=(f'{stock_name} ({stock_code})', 
                       'MACD' if show_macd else None,
                       'KDJ' if show_kdj else None,
                       'RSI' if show_rsi else None)
    )
    
    # K线图
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['开盘'],
            high=df['最高'],
            low=df['最低'],
            close=df['收盘'],
            name='K线',
            increasing_line_color='red',
            decreasing_line_color='green'
        ),
        row=1, col=1
    )
    
    # 均线
    fig.add_trace(go.Scatter(x=df.index, y=ma5, name='MA5', line=dict(color='white', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ma10, name='MA10', line=dict(color='yellow', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ma20, name='MA20', line=dict(color='purple', width=1)), row=1, col=1)
    
    current_row = 2
    
    # MACD
    if show_macd:
        fig.add_trace(go.Scatter(x=df.index, y=dif, name='DIF', line=dict(color='white')), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=dea, name='DEA', line=dict(color='yellow')), row=current_row, col=1)
        colors = ['red' if v >= 0 else 'green' for v in macd]
        fig.add_trace(go.Bar(x=df.index, y=macd, name='MACD', marker_color=colors), row=current_row, col=1)
        current_row += 1
    
    # KDJ
    if show_kdj:
        fig.add_trace(go.Scatter(x=df.index, y=k, name='K', line=dict(color='white')), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=d, name='D', line=dict(color='yellow')), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=j, name='J', line=dict(color='purple')), row=current_row, col=1)
        current_row += 1
    
    # RSI
    if show_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI', line=dict(color='white')), row=current_row, col=1)
        fig.add_hline(y=80, line_dash="dash", line_color="red", row=current_row, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="green", row=current_row, col=1)
    
    # 布局
    fig.update_layout(
        template='plotly_dark',
        height=600,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_xaxes(type='category', tickangle=45)
    
    return fig

# ========== 页面导航 ==========
tab1, tab2, tab3 = st.tabs(["📊 实时行情", "🎯 多因子选股", "⏰ 价格预警"])

# ========== Tab1: 实时行情 ==========
with tab1:
    # 侧边栏
    with st.sidebar:
        st.header("📝 自选股管理")
        
        new_stock = st.text_input("添加股票代码", placeholder="如: 600519", key="add_stock_input")
        if st.button("添加", key="add_stock_btn"):
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

    # 主区域
    st.header("📊 实时行情 + K线分析（新浪数据源）")

    # 选择股票查看详情
    selected_stock = st.selectbox("选择股票查看K线", st.session_state.watchlist)

    # 刷新按钮
    if st.button("🔄 刷新数据", type="primary"):
        st.cache_data.clear()
        st.rerun()

    # 获取数据（使用新浪接口）
    @st.cache_data(ttl=60)
    def get_quotes(codes):
        return sina_api.get_realtime_quotes(codes)
    
    @st.cache_data(ttl=300)
    def get_history(code, days=60):
        return sina_api.get_history_data(code, days)

    with st.spinner("正在获取数据（新浪接口）..."):
        quotes = get_quotes(st.session_state.watchlist)
        hist_df = get_history(selected_stock, days_select)

    if quotes:
        # 获取选中股票信息
        if selected_stock in quotes:
            quote = quotes[selected_stock]
            
            # 实时行情卡片
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("最新价", f"¥{quote['price']}")
            with col2:
                st.metric("涨跌幅", f"{quote['change_pct']:.2f}%")
            with col3:
                st.metric("今开", f"¥{quote['open']}")
            with col4:
                st.metric("最高", f"¥{quote['high']}")
            with col5:
                st.metric("最低", f"¥{quote['low']}")
            
            st.markdown("---")
            
            # K线图
            if hist_df is not None and not hist_df.empty:
                # 计算技术指标数值显示
                close = hist_df['收盘'].values
                high = hist_df['最高'].values
                low = hist_df['最低'].values
                
                dif, dea, macd = calculate_macd(close)
                k, d, j = calculate_kdj(high, low, close)
                rsi = calculate_rsi(close)
                
                # 技术指标数值
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("MACD", f"{macd[-1]:.3f}", f"DIF:{dif[-1]:.2f} DEA:{dea[-1]:.2f}")
                with col2:
                    st.metric("KDJ", f"{j[-1]:.1f}", f"K:{k[-1]:.1f} D:{d[-1]:.1f}")
                with col3:
                    st.metric("RSI(14)", f"{rsi[-1]:.1f}")
                
                # 绘制K线图
                fig = plot_kline(hist_df, selected_stock, quote['name'], show_macd, show_kdj, show_rsi)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # 均线数据
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
    st.caption(f"数据来源: 新浪财经 | 更新时间: {datetime.now().strftime('%H:%M:%S')}")

# ========== Tab2: 多因子选股 ==========
with tab2:
    st.header("🎯 多因子共振选股")
    st.markdown("""
    **策略说明：**
    - 选股范围：60/00开头沪深主板，剔除ST
    - 反转形态：连续2日抬升
    - 多因子共振：8项满足≥7项
    - 强势条件：涨幅>5%，收阳线
    """)
    
    with st.expander("⚙️ 选股参数设置"):
        col1, col2 = st.columns(2)
        with col1:
            min_factor_count = st.slider("最少满足因子数", 5, 8, 7)
            min_rise = st.slider("最低涨幅要求(%)", 0, 10, 3)
        with col2:
            require_strong = st.checkbox("必须满足强势条件(涨幅>5%)", value=False)
            max_results = st.slider("最多显示结果数", 10, 100, 30)
    
    if st.button("🚀 开始选股", type="primary"):
        st.info("选股功能需要获取全市场数据，新浪接口暂时不支持，建议使用本地运行版本")
        st.code("""
# 选股功能建议：
# 1. 本地运行此程序，使用 akshare 库
# 2. 或使用其他支持全市场数据的接口
# 3. 新浪接口仅支持实时行情查询
        """)

# ========== Tab3: 价格预警 ==========
with tab3:
    st.header("⏰ 价格预警设置")
    
    st.markdown("""
    **使用说明：**
    1. 添加股票代码和目标价格
    2. 选择预警类型（突破/跌破）
    3. 点击检查预警，系统会扫描是否触发
    """)
    
    # 添加预警
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        alert_stock = st.text_input("股票代码", placeholder="600519", key="alert_stock")
    with col2:
        alert_price = st.number_input("目标价格", min_value=0.0, step=0.01, key="alert_price")
    with col3:
        alert_type = st.selectbox("预警类型", ["突破上方", "跌破下方"], key="alert_type")
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("添加预警", type="primary"):
            if alert_stock and alert_price > 0:
                st.session_state.alerts[alert_stock] = {
                    'price': alert_price,
                    'type': 'above' if alert_type == "突破上方" else 'below'
                }
                st.success(f"已添加预警: {alert_stock}")
                st.rerun()
    
    # 显示预警列表
    st.markdown("---")
    st.subheader("📋 当前预警列表")
    
    if st.session_state.alerts:
        for stock, info in list(st.session_state.alerts.items()):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            with col1:
                st.text(stock)
            with col2:
                st.text(f"¥{info['price']}")
            with col3:
                st.text("突破上方" if info['type'] == 'above' else "跌破下方")
            with col4:
                if st.button("删除", key=f"del_alert_{stock}"):
                    del st.session_state.alerts[stock]
                    st.rerun()
        
        # 检查预警按钮
        st.markdown("---")
        if st.button("🔍 检查预警状态", type="primary"):
            with st.spinner("正在检查..."):
                try:
                    quotes = sina_api.get_realtime_quotes(list(st.session_state.alerts.keys()))
                    
                    triggered = []
                    for stock, info in st.session_state.alerts.items():
                        if stock in quotes:
                            current_price = quotes[stock]['price']
                            target_price = info['price']
                            
                            if info['type'] == 'above' and current_price >= target_price:
                                triggered.append(f"🔔 {stock} 已突破 {target_price}，当前价 {current_price}")
                            elif info['type'] == 'below' and current_price <= target_price:
                                triggered.append(f"🔔 {stock} 已跌破 {target_price}，当前价 {current_price}")
                    
                    if triggered:
                        for msg in triggered:
                            st.success(msg)
                    else:
                        st.info("暂无触发预警")
                        
                except Exception as e:
                    st.error(f"检查失败: {str(e)}")
    else:
        st.info("暂无预警设置，请添加股票预警")

# ========== 页脚 ==========
st.markdown("---")
st.caption("📈 股票盯盘助手 | 数据来源: 新浪财经 | ⚠️ 仅供学习参考，不构成投资建议")
