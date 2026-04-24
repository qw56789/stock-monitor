import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
import json
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
    page_title="溪城游资 Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 标题
st.title("📈 溪城游资 Pro")
st.markdown("---")

# 初始化session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['600559', '000001']

if 'alerts' not in st.session_state:
    st.session_state.alerts = {}  # {股票代码: {'price': 价格, 'type': 'above/below'}}

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
        # 超买超卖线
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
        period_select = st.selectbox("时间周期", ["日线", "60分钟", "30分钟", "15分钟", "5分钟"], index=0)
        days_select = st.slider("显示天数", 30, 120, 60)
        
        st.markdown("---")
        st.header("📈 技术指标")
        show_macd = st.checkbox("MACD", value=True)
        show_kdj = st.checkbox("KDJ", value=True)
        show_rsi = st.checkbox("RSI", value=True)

    # 主区域
    st.header("📊 实时行情 + K线分析")

    # 选择股票查看详情
    selected_stock = st.selectbox("选择股票查看K线", st.session_state.watchlist)

    # 刷新按钮
    if st.button("🔄 刷新数据", type="primary"):
        st.cache_data.clear()
        st.rerun()

    # 获取数据
    @st.cache_data(ttl=300)
    def get_all_stocks():
        try:
            df = ak.stock_zh_a_spot_em()
            return df
        except Exception as e:
            return None

    @st.cache_data(ttl=300)
    def get_stock_history(stock_code, period="daily", days=60):
        """获取历史数据"""
        try:
            if period == "日线":
                df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
            else:
                # 分钟线
                period_map = {"60分钟": "60", "30分钟": "30", "15分钟": "15", "5分钟": "5"}
                df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period=period_map.get(period, "60"), adjust="qfq")
            
            if df is not None and len(df) > 0:
                df = df.tail(days)
            return df
        except Exception as e:
            return None

    with st.spinner("正在获取数据..."):
        df = get_all_stocks()

    if df is not None and not df.empty:
        code_col = '代码' if '代码' in df.columns else 'code'
        name_col = '名称' if '名称' in df.columns else 'name'
        
        # 获取选中股票信息
        stock_data = df[df[code_col].astype(str) == selected_stock]
        
        if not stock_data.empty:
            row = stock_data.iloc[0]
            stock_name = str(row[name_col])
            
            # 实时行情卡片
            col1, col2, col3, col4, col5 = st.columns(5)
            
            price_col = '最新价' if '最新价' in df.columns else 'price'
            pct_col = '涨跌幅' if '涨跌幅' in df.columns else 'change_pct'
            high_col = '最高' if '最高' in df.columns else 'high'
            low_col = '最低' if '最低' in df.columns else 'low'
            open_col = '今开' if '今开' in df.columns else 'open'
            
            with col1:
                st.metric("最新价", f"¥{row[price_col]}")
            with col2:
                st.metric("涨跌幅", f"{row[pct_col]}%")
            with col3:
                st.metric("今开", f"¥{row[open_col]}")
            with col4:
                st.metric("最高", f"¥{row[high_col]}")
            with col5:
                st.metric("最低", f"¥{row[low_col]}")
            
            st.markdown("---")
            
            # K线图
            hist_df = get_stock_history(selected_stock, period_select, days_select)
            
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
                fig = plot_kline(hist_df, selected_stock, stock_name, show_macd, show_kdj, show_rsi)
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
    st.caption(f"数据来源: 东方财富 | 更新时间: {datetime.now().strftime('%H:%M:%S')}")

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
        with st.spinner("正在筛选..."):
            try:
                all_stocks = ak.stock_zh_a_spot_em()
                code_col = '代码' if '代码' in all_stocks.columns else 'code'
                name_col = '名称' if '名称' in all_stocks.columns else 'name'
                pct_col = '涨跌幅' if '涨跌幅' in all_stocks.columns else 'change_pct'
                price_col = '最新价' if '最新价' in all_stocks.columns else 'price'
                open_col = '今开' if '今开' in all_stocks.columns else 'open'
                
                all_stocks[code_col] = all_stocks[code_col].astype(str)
                main_board = all_stocks[all_stocks[code_col].str.match(r'^(60|00)')]
                main_board = main_board[~main_board[name_col].str.contains('ST|退市', case=False, na=False)]
                main_board = main_board[pd.to_numeric(main_board[pct_col], errors='coerce') >= min_rise]
                
                st.info(f"初步筛选: {len(main_board)} 只股票")
                
                results = []
                progress_bar = st.progress(0)
                
                for idx, (_, row) in enumerate(main_board.iterrows()):
                    if idx >= 150:
                        break
                    
                    progress_bar.progress((idx + 1) / 150)
                    
                    try:
                        stock_code = str(row[code_col])
                        stock_name = str(row[name_col])
                        
                        hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                        if hist is None or len(hist) < 60:
                            continue
                        
                        hist = hist.tail(60)
                        close = hist['收盘'].values
                        high = hist['最高'].values
                        low = hist['最低'].values
                        volume = hist['成交量'].values
                        
                        current_price = float(row[price_col])
                        rise_pct = float(row[pct_col])
                        open_price = float(row[open_col])
                        high_30d = max(high[-30:])
                        
                        ma3 = round(np.mean(close[-3:]), 2)
                        ma5 = round(np.mean(close[-5:]), 2)
                        ma13 = round(np.mean(close[-13:]), 2)
                        ma20 = round(np.mean(close[-20:]), 2)
                        ma60 = round(np.mean(close[-60:]), 2)
                        
                        reversal = close[-1] > close[-2] > close[-3]
                        
                        # 因子计算
                        factor_count = 0
                        factor_count += 1 if ma5 > ma10 else 0
                        factor_count += 1 if ma20 > ma60 else 0
                        
                        # KDJ
                        k, d, j = calculate_kdj(high, low, close)
                        factor_count += 1 if j[-1] > k[-1] else 0
                        
                        # MACD
                        dif, dea, macd = calculate_macd(close)
                        factor_count += 1 if dif[-1] > dea[-1] else 0
                        factor_count += 1 if macd[-1] > 0 else 0
                        
                        # 量
                        vol_ma60 = np.mean(volume[-60:])
                        factor_count += 1 if volume[-1] > vol_ma60 else 0
                        factor_count += 1 if rise_pct > 3 else 0
                        
                        is_yang = current_price > open_price
                        is_strong = rise_pct > 5 and is_yang
                        
                        if factor_count >= min_factor_count and reversal:
                            if not require_strong or is_strong:
                                results.append({
                                    '代码': stock_code,
                                    '名称': stock_name,
                                    '当前价': current_price,
                                    '涨幅%': rise_pct,
                                    'MA3': ma3,
                                    'MA5': ma5,
                                    'MA13': ma13,
                                    'MA20': ma20,
                                    '因子数': factor_count,
                                    '反转': '✅' if reversal else '❌',
                                    '强势': '✅' if is_strong else '❌'
                                })
                    except:
                        continue
                
                progress_bar.empty()
                
                if results:
                    result_df = pd.DataFrame(results).sort_values('因子数', ascending=False).head(max_results)
                    st.success(f"🎯 筛选出 {len(result_df)} 只股票")
                    st.dataframe(result_df, use_container_width=True, hide_index=True)
                    
                    csv = result_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 下载CSV", csv, f"选股结果_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
                else:
                    st.warning("未找到符合条件的股票")
                    
            except Exception as e:
                st.error(f"选股出错: {str(e)}")

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
                st.success(f"已添加预警: {alert_stock} {'突破' if alert_type == '突破上方' else '跌破'} {alert_price}")
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
                    all_stocks = ak.stock_zh_a_spot_em()
                    code_col = '代码' if '代码' in all_stocks.columns else 'code'
                    price_col = '最新价' if '最新价' in all_stocks.columns else 'price'
                    
                    triggered = []
                    for stock, info in st.session_state.alerts.items():
                        stock_data = all_stocks[all_stocks[code_col].astype(str) == stock]
                        if not stock_data.empty:
                            current_price = float(stock_data.iloc[0][price_col])
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
    
    # 持久化说明
    st.markdown("---")
    st.caption("💡 提示: 预警数据保存在浏览器会话中，刷新页面后会重置。云端持久化需配置数据库。")

# ========== 页脚 ==========
st.markdown("---")
st.caption("📈 股票盯盘助手 Pro | 数据来源: 东方财富 | ⚠️ 仅供学习参考，不构成投资建议")
