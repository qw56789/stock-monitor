import streamlit as st
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time

# 页面配置
st.set_page_config(
    page_title="徐老板盯盘",
    page_icon="📈",
    layout="wide"
)

# 标题
st.title("📈 徐老板盯盘")
st.markdown("---")

# 缓存：获取所有A股实时行情（5分钟缓存）
@st.cache_data(ttl=300, show_spinner=False)
def get_all_realtime_quotes():
    """批量获取所有A股实时行情（东方财富数据源，速度更快）"""
    try:
        # 使用东方财富接口，一次获取所有股票行情
        df = ak.stock_zh_a_spot_em()
        # 重命名列
        df = df.rename(columns={
            '代码': 'code',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'change_pct',
            '涨跌额': 'change',
            '成交量': 'volume',
            '成交额': 'amount',
            '最高': 'high',
            '最低': 'low',
            '今开': 'open',
            '昨收': 'pre_close',
            '换手率': 'turnover_rate',
            '市盈率-动态': 'pe',
            '市净率': 'pb'
        })
        return df
    except Exception as e:
        st.error(f"获取行情失败: {str(e)}")
        return None

# 从全部行情中提取指定股票
def get_stock_quote(stock_code, all_quotes):
    """从全部行情中提取指定股票"""
    if all_quotes is None:
        return None
    stock_data = all_quotes[all_quotes['code'] == stock_code]
    if stock_data.empty:
        return None
    return stock_data.iloc[0].to_dict()

# 缓存：获取历史数据用于均线计算
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_history(stock_code, days=30):
    """获取历史数据用于均线计算"""
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        df = df.tail(days)
        return df
    except Exception as e:
        return None

# 计算均线
def calculate_ma(hist_df, periods=[5, 13, 20]):
    """计算均线"""
    if hist_df is None or len(hist_df) < max(periods):
        return {}
    
    ma_dict = {}
    for period in periods:
        if len(hist_df) >= period:
            ma_dict[f'MA{period}'] = round(hist_df['收盘'].tail(period).mean(), 2)
    return ma_dict

# 初始化自选股列表
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['600559', '000001']  # 默认：老白干酒、平安银行

# 侧边栏：自选股管理
with st.sidebar:
    st.header("📝 自选股管理")
    
    # 添加股票
    new_stock = st.text_input("添加股票代码", placeholder="如: 600519")
    if st.button("添加"):
        if new_stock and len(new_stock) == 6 and new_stock.isdigit():
            if new_stock not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_stock)
                st.success(f"已添加 {new_stock}")
                st.rerun()
            else:
                st.warning("该股票已在自选列表中")
        else:
            st.error("请输入正确的6位股票代码")
    
    # 显示自选股列表
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

# 主区域：实时行情
st.header("📊 实时行情")

# 刷新按钮
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    if st.button("🔄 刷新数据", type="primary"):
        st.cache_data.clear()
        st.rerun()
with col2:
    auto_refresh = st.checkbox("自动刷新")
    if auto_refresh:
        refresh_interval = st.selectbox("刷新间隔", [30, 60, 120, 300], index=1, label_visibility="collapsed")
        time.sleep(0.1)
        st.rerun() if st.button("停止") else None

# 批量获取所有行情
with st.spinner("正在获取行情数据..."):
    all_quotes = get_all_realtime_quotes()

# 显示每只股票的行情
if all_quotes is not None:
    for stock_code in st.session_state.watchlist:
        quote = get_stock_quote(stock_code, all_quotes)
        
        if quote:
            # 股票名称和代码
            stock_name = quote.get('name', '未知')
            st.subheader(f"{stock_name} ({stock_code})")
            
            # 行情数据
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                price = quote.get('price', 0)
                change_pct = quote.get('change_pct', 0)
                color = "green" if change_pct >= 0 else "red"
                st.metric("最新价", f"¥{price}", f"{change_pct:+.2f}%")
            
            with col2:
                st.metric("今开", f"¥{quote.get('open', 0):.2f}")
                st.metric("昨收", f"¥{quote.get('pre_close', 0):.2f}")
            
            with col3:
                st.metric("最高", f"¥{quote.get('high', 0):.2f}")
                st.metric("最低", f"¥{quote.get('low', 0):.2f}")
            
            with col4:
                volume = quote.get('volume', 0)
                if volume > 100000000:
                    volume_str = f"{volume/100000000:.2f}亿"
                elif volume > 10000:
                    volume_str = f"{volume/10000:.2f}万"
                else:
                    volume_str = f"{volume}"
                st.metric("成交量", volume_str)
                st.metric("换手率", f"{quote.get('turnover_rate', 0):.2f}%")
            
            # 均线系统
            st.markdown("**📈 均线系统**")
            with st.spinner("计算均线..."):
                hist_df = get_stock_history(stock_code)
                ma_dict = calculate_ma(hist_df)
            
            if ma_dict:
                ma_col1, ma_col2, ma_col3 = st.columns(3)
                with ma_col1:
                    st.metric("MA5", f"¥{ma_dict.get('MA5', '-')}")
                with ma_col2:
                    st.metric("MA13", f"¥{ma_dict.get('MA13', '-')}")
                with ma_col3:
                    st.metric("MA20", f"¥{ma_dict.get('MA20', '-')}")
            
            # 量价分析
            st.markdown("**📊 量价分析**")
            if ma_dict and price:
                current_price = float(price)
                ma5 = ma_dict.get('MA5', 0)
                ma13 = ma_dict.get('MA13', 0)
                ma20 = ma_dict.get('MA20', 0)
                
                analysis = []
                if current_price > ma5 > ma13 > ma20:
                    analysis.append("✅ 多头排列，趋势向上")
                elif current_price < ma5 < ma13 < ma20:
                    analysis.append("⚠️ 空头排列，趋势向下")
                
                if change_pct and float(change_pct) > 3:
                    analysis.append("📈 大幅上涨")
                elif change_pct and float(change_pct) < -3:
                    analysis.append("📉 大幅下跌")
                
                if quote.get('turnover_rate', 0) > 10:
                    analysis.append("🔥 换手活跃")
                
                if analysis:
                    for item in analysis:
                        st.info(item)
            
            st.markdown("---")
        else:
            st.warning(f"股票 {stock_code} 未找到")
else:
    st.error("获取行情数据失败，请稍后重试")

# 页脚
st.markdown("---")
st.caption(f"数据来源: 东方财富 | 最后更新: {datetime.now().strftime('%H:%M:%S')}")
st.caption("⚠️ 免责声明: 本工具仅供学习交流，不构成投资建议")

# 自动刷新逻辑
if auto_refresh:
    import time
    time.sleep(refresh_interval)
    st.rerun()
