"""
股票盯盘工具 - Streamlit版
================================================================================
功能：
- 实时行情监控
- 均线系统（5日、13日、20日）
- 成交量监控
- 自选股管理
- 自动刷新

使用方法：
1. 安装依赖：pip install streamlit akshare pandas
2. 运行：streamlit run app.py
3. 浏览器打开 http://localhost:8501

作者：扣子
日期：2026年4月24日
================================================================================
"""

import streamlit as st
import akshare as ak
import pandas as pd
import time
from datetime import datetime, timedelta

# ============================================================================
# 页面配置
# ============================================================================
st.set_page_config(
    page_title="股票盯盘助手",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# 数据获取函数
# ============================================================================
@st.cache_data(ttl=60)
def get_realtime_quote(stock_code):
    """
    获取实时行情
    """
    try:
        # 判断市场
        if stock_code.startswith('6'):
            symbol = f"sh{stock_code}"
        else:
            symbol = f"sz{stock_code}"
        
        # 获取实时行情
        df = ak.stock_zh_a_spot_em()
        stock_data = df[df['代码'] == stock_code]
        
        if len(stock_data) == 0:
            return None
        
        row = stock_data.iloc[0]
        
        return {
            'code': row['代码'],
            'name': row['名称'],
            'price': float(row['最新价']),
            'change_pct': float(row['涨跌幅']),
            'change': float(row['涨跌额']),
            'open': float(row['今开']),
            'high': float(row['最高']),
            'low': float(row['最低']),
            'volume': float(row['成交量']),
            'amount': float(row['成交额']),
            'volume_ratio': float(row.get('量比', 0)),
            'turnover_rate': float(row.get('换手率', 0)),
        }
    except Exception as e:
        st.error(f"获取行情失败: {e}")
        return None


@st.cache_data(ttl=300)
def get_stock_history(stock_code, days=30):
    """
    获取历史数据（用于计算均线）
    """
    try:
        # 判断市场
        if stock_code.startswith('6'):
            symbol = f"sh{stock_code}"
        else:
            symbol = f"sz{stock_code}"
        
        # 获取历史数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if df is None or len(df) == 0:
            return None
        
        return df
    except Exception as e:
        st.error(f"获取历史数据失败: {e}")
        return None


def calculate_ma(df, periods=[5, 13, 20]):
    """
    计算均线
    """
    if df is None or len(df) == 0:
        return {}
    
    ma_values = {}
    for period in periods:
        if len(df) >= period:
            ma_values[f'MA{period}'] = df['收盘'].tail(period).mean()
        else:
            ma_values[f'MA{period}'] = df['收盘'].mean()
    
    return ma_values


def get_volume_info(df):
    """
    获取成交量信息
    """
    if df is None or len(df) == 0:
        return None
    
    today_volume = df['成交量'].iloc[-1] if len(df) > 0 else 0
    avg_volume_30 = df['成交量'].tail(30).mean() if len(df) >= 30 else df['成交量'].mean()
    max_volume_30 = df['成交量'].tail(30).max() if len(df) >= 30 else df['成交量'].max()
    
    return {
        'today_volume': today_volume,
        'avg_volume_30': avg_volume_30,
        'max_volume_30': max_volume_30,
        'volume_ratio': today_volume / avg_volume_30 if avg_volume_30 > 0 else 0
    }


# ============================================================================
# 主应用
# ============================================================================
def main():
    st.title("📈 股票盯盘助手")
    st.markdown("---")
    
    # 侧边栏：自选股管理
    with st.sidebar:
        st.header("📝 自选股管理")
        
        # 初始化session state
        if 'watchlist' not in st.session_state:
            st.session_state.watchlist = ['600519', '000001', '300750']
        
        # 添加股票
        new_stock = st.text_input("添加股票代码", placeholder="如：600519")
        if st.button("添加"):
            if new_stock and new_stock not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_stock)
                st.success(f"已添加 {new_stock}")
                st.rerun()
        
        # 显示自选股列表
        st.subheader("当前自选股")
        for i, code in enumerate(st.session_state.watchlist):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(code)
            with col2:
                if st.button("删除", key=f"del_{i}"):
                    st.session_state.watchlist.remove(code)
                    st.rerun()
        
        st.markdown("---")
        
        # 刷新设置
        st.subheader("⚙️ 设置")
        auto_refresh = st.checkbox("自动刷新", value=True)
        refresh_interval = st.slider("刷新间隔(秒)", 5, 60, 30)
    
    # 主内容区
    st.header("📊 实时行情")
    
    # 手动刷新按钮
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 刷新数据"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        st.caption(f"最后更新: {datetime.now().strftime('%H:%M:%S')}")
    
    # 显示股票数据
    for stock_code in st.session_state.watchlist:
        with st.container():
            # 获取数据
            quote = get_realtime_quote(stock_code)
            history = get_stock_history(stock_code, days=30)
            ma_values = calculate_ma(history) if history is not None else {}
            volume_info = get_volume_info(history) if history is not None else None
            
            if quote is None:
                st.warning(f"无法获取 {stock_code} 的数据")
                continue
            
            # 股票卡片
            change_color = "green" if quote['change_pct'] >= 0 else "red"
            
            st.markdown(f"""
            <div style='background-color: #1a1a2e; padding: 20px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid {change_color};'>
                <h2 style='color: white; margin: 0;'>{quote['name']} <span style='font-size: 0.7em; color: #888;'>({quote['code']})</span></h2>
                <div style='margin-top: 10px;'>
                    <span style='font-size: 2.5em; font-weight: bold; color: {change_color};'>{quote['price']:.2f}</span>
                    <span style='font-size: 1.2em; color: {change_color}; margin-left: 10px;'>{quote['change_pct']:+.2f}%</span>
                    <span style='font-size: 1em; color: {change_color}; margin-left: 5px;'>({quote['change']:+.2f})</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 详细数据
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("开盘价", f"{quote['open']:.2f}")
                st.metric("最高价", f"{quote['high']:.2f}")
                st.metric("最低价", f"{quote['low']:.2f}")
            
            with col2:
                st.metric("MA5", f"{ma_values.get('MA5', 0):.2f}")
                st.metric("MA13", f"{ma_values.get('MA13', 0):.2f}")
                st.metric("MA20", f"{ma_values.get('MA20', 0):.2f}")
            
            with col3:
                if volume_info:
                    vol_ratio = volume_info['volume_ratio']
                    st.metric("成交量", f"{volume_info['today_volume']/10000:.0f}万手")
                    st.metric("量比", f"{vol_ratio:.2f}")
                    st.metric("换手率", f"{quote['turnover_rate']:.2f}%")
            
            with col4:
                if volume_info:
                    st.metric("30日均量", f"{volume_info['avg_volume_30']/10000:.0f}万手")
                    st.metric("30日高量", f"{volume_info['max_volume_30']/10000:.0f}万手")
                    
                    # 量价关系判断
                    current_price = quote['price']
                    ma5 = ma_values.get('MA5', 0)
                    
                    if current_price > ma5 and vol_ratio > 1.5:
                        st.success("放量上涨 ✅")
                    elif current_price < ma5 and vol_ratio > 1.5:
                        st.error("放量下跌 ⚠️")
                    elif vol_ratio < 0.5:
                        st.info("缩量 📉")
            
            st.markdown("---")
    
    # 自动刷新
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
