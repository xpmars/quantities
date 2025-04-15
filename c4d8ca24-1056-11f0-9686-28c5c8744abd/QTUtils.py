import pandas as pd
import numpy as np

# 获取持仓
def get_position(symbol):
    position = list(filter(lambda x:x['symbol']==symbol,get_position()))
    if not position:  # 新增空值判断
        print(f"{symbol} 无持仓，跳过交易逻辑")
        return
    return position

# 获取当前价格
def get_current_price(context, symbol):
    current_data = context.data(symbol=symbol, frequency=context.frequency, count=1, fields='close')
    if len(current_data) == 0:
        print(f"未获取到 {symbol} 当前价格数据。")
        return None
    return current_data['close'].values[0]

# 获取前一日收盘价
def get_previous_close_price(context, symbol):
    previous_data = context.data(symbol=symbol, frequency='1d', count=2, fields='close')
    if len(previous_data) < 2:
        print(f"未获取到 {symbol} 前一日收盘价数据。")
        return None
    return previous_data['close'].values[1]


# 计算涨跌幅
def calculate_change_percentage(current_price, previous_close_price):
    return (current_price - previous_close_price) / previous_close_price * 100



#  获取涨停价
def get_limit_up_price(data, symbol):
    """
    此函数用于根据给定的股票数据和股票代码计算涨停价
    :param data: 包含股票历史数据的 DataFrame
    :param symbol: 股票代码
    :return: 涨停价，如果数据不足则返回 None
    """
    if len(data) >= 2:
        # 索引 0 是当前数据，索引 1 是前一日数据
        previous_close_price = data['close'].values[1]
        # 判断股票类型，确定涨停幅度
        if symbol.startswith('SHSE.688') or (symbol.startswith('SZSE.30') and 'SZSE.300' not in symbol):
            # 科创板和创业板股票，涨停幅度为 20%
            limit_up_ratio = 0.2
        elif 'ST' in symbol:
            # ST 股票，涨停幅度为 5%
            limit_up_ratio = 0.05
        else:
            # 普通股票，涨停幅度为 10%
            limit_up_ratio = 0.1

        # 计算涨停价
        limit_up_price = previous_close_price * (1 + limit_up_ratio)
        # 按照实际情况取整，A股价格保留两位小数
        limit_up_price = round(limit_up_price, 2)
        return limit_up_price
    else:
        print(f"未获取到 {symbol} 足够的历史数据。")
        return None



def eod_position_summary(context):
    """打印尾盘持仓明细及资产概况"""
    account = context.account()
    
    # 获取持仓列表并过滤有效持仓
    positions = [pos for pos in account.positions() if pos['volume'] > 0]
    
    if not positions:
        print(f"{context.now.strftime('%H:%M')} 无持仓")
        return
    
    # 打印持仓明细表头
    print(f"\n{'='*30} 尾盘持仓明细 {context.now.strftime('%Y-%m-%d %H:%M')} {'='*30}")
    print(f"{'标的代码':<7} | {'持仓数量':>7} | {'持仓成本':>6} | {'最新价':>6} | {'持仓市值':>7} | {'盈亏比例':>7}")
    
    total_market_value = 0
    total_profit_rate = 0
    
    for pos in positions:
        # 获取关键字段（根据QMT接口规范调整字段名）
        symbol = pos['symbol']                         # 标的代码
        volume = int(pos['volume'])                    # 持仓数量
        cost_price = pos['vwap']                       # 持仓均价[2](@ref)
        last_price = pos['price']                      # 最新行情价[2](@ref)
        market_value = volume * last_price             # 持仓市值
        profit_rate = (last_price - cost_price)/cost_price if cost_price else 0  # 盈亏比例
        
        # 累计统计
        total_market_value += market_value
        total_profit_rate += profit_rate * (market_value/total_market_value if total_market_value else 0)
        
        # 格式化输出
        print(f"{symbol:<10} | {volume:>10} | {cost_price:>10.2f} | {last_price:>10.2f} | "
            f"{market_value:>10.2f} | {profit_rate:>+8.2%}")

    # 打印资产概况（网页3风险管理要求）
    print(f"\n[资产概况] 总市值={total_market_value:.2f}元 | 组合收益率={total_profit_rate:.2%}")
    print(f"[资金状态] 可用资金={account.cash['available']:.2f}元 | 总资产={account.cash['nav']:.2f}元")
    print(f"[风险提示] 单票最大亏损={min((p['price']-p['vwap'])/p['vwap'] for p in positions):.2%}")
print('='*90)



def calculate_ATR(context, symbol):
    """动态仓位计算函数"""
    # 获取ATR波动率
    data = context.data(symbol=symbol, frequency='1d', count=context.atr_period+1, 
                       fields='high,low,close')
    high = data['high']
    low = data['low']
    close = data['close']
    prev_close = np.roll(close, shift=1)
    # 计算真实波幅TR
    tr = np.zeros(len(data))
    for i in range(1, len(data)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    tr = np.maximum(high - low, 
                   np.maximum(np.abs(high - prev_close), 
                             np.abs(low - prev_close)))
    atr = np.mean(tr[-context.atr_period:]).item()  # 标量化处理
    return atr


def EMA(S: np.ndarray, N: int) -> np.ndarray:
    '''指数移动平均,为了精度 S>4*N  EMA至少需要120周期     
    alpha=2/(span+1)

    Args:
        S (np.ndarray): 时间序列
        N (int): 指标周期

    Returns:
        np.ndarray: EMA
    '''
    return pd.Series(S).ewm(span=N, adjust=False).mean().values

#原始值：SHORT: int = 12,LONG: int = 26,M: int = 9
def MACD(CLOSE: np.ndarray,
        SHORT: int = 6,
        LONG: int = 38,
        M: int = 6) -> tuple:
    '''计算MACD
    EMA的关系，S取120日

    Args:
        CLOSE (np.ndarray): 收盘价时间序列
        SHORT (int, optional): ema 短周期. Defaults to 12.
        LONG (int, optional): ema 长周期. Defaults to 26.
        M (int, optional): macd 平滑周期. Defaults to 9.

    Returns:
        tuple: _description_
    '''
    DIF = EMA(CLOSE, SHORT) - EMA(CLOSE, LONG)
    DEA = EMA(DIF, M)
    MACD = (DIF - DEA) * 2
    return DIF, DEA, MACD


def calculate_dynamic_position(context, symbol):
    data = context.data(symbol=symbol, frequency='1d', count=context.atr_period+1, fields='high,low,close')
    """动态仓位计算函数"""
    atr = calculate_ATR(context, symbol)
    # 获取账户风险预算
    account = context.account()
    risk_budget = account.cash['nav'] * context.risk_ratio
    # 提取最新价格（标量值）
    
    current_price = data['close'].values[-1]  # 明确取最后一个元素
    # 动态仓位计算（整手数处理）
    if atr == 0 or current_price == 0:  # 异常值保护
        return 0
    position_value = risk_budget / (atr * 1.5)
    target_shares = (int(position_value / current_price)) / 100 * 100 # 按整手数调整
    return target_shares 



def check_timing_buy_signal(context, symbol):
    """三重验证择时信号(买)"""
    # 1. 趋势判定（双均线）
    close = context.data(symbol=symbol, frequency=context.frequency, 
                        count=context.trend_period, fields='close')['close']
    ma5 = pd.Series(close).rolling(5).mean().values[-1]
    ma10 = pd.Series(close).rolling(10).mean().values[-1]
    # trend_flag = ma5 > ma10 and ma5 > ma10 * 1.01  # 5日线上穿20日线1%
    trend_flag = ma5 > ma10   # 5日线上穿10日线
    # 2. 量能突破
    vol = context.data(symbol=symbol, frequency='1d', count=5, 
                      fields='volume')['volume']
    
    # 关键改进：数据长度与质量校验
    if len(vol) < 4:  # 至少需要4日数据（当前日+前3日）
        print(f"[警告] {symbol} 成交量数据不足4日（实际：{len(vol)}）")
        return False  # 或根据策略需求调整

    volume_signal = vol.iloc[-1] > np.mean(vol.iloc[:-1]) * context.volume_ratio
    
    # 3. MACD动量验证
    dif, dea, _ = MACD(close)
    # 数据长度校验（MACD默认需要26周期）
    if len(dif) < 2 or len(dea) < 2:
        print(f"[警告] {symbol} MACD数据不足")
        return False
    
    macd_signal = dif[-1] > dea[-1] and dif[-2] < dea[-2]  # 金叉确认
    
    return trend_flag and volume_signal and macd_signal 


def generate_sell_signal(context, symbol):
    """四维量化卖出信号生成器"""
    # ===== 数据校验层 =====
    # 获取基础行情数据
    data = context.data(symbol, '1d', count=50, 
                       fields=['close', 'high', 'low', 'volume'])
    
    flag = data['close'].values
    if len(flag) < 50:
        print(f"[风控] {symbol} 历史数据不足50日")
        return False
    
    # ===== 趋势反转层 =====
    # 三重均线系统
    ma5 = data['close'].rolling(5).mean().values
    ma10 = data['close'].rolling(10).mean().values
    ma20 = data['close'].rolling(20).mean().values
    # 趋势反转条件# 均线斜率向下
    trend_signal = (ma5[-1] < ma10[-1]) and \
                  (ma10[-1] < ma10[-5]) and \
                  (data['close'].iloc[-1] < ma20[-1] * 0.97)  # 收盘价破55日线3%

    # if trend_signal  :
    #     print(f"[均线斜率向下] ：{trend_signal} =========")

    # ===== 量价博弈层 =====
    # 动态量能分析
    vol_ma10 = data['volume'].rolling(10).mean().values
    current_vol = data['volume'].iloc[-1]  # 明确使用位置索引
    
    # 量价背离检测
    price_high = data['close'].iloc[-1] > data['close'].iloc[-5:-1].max()
    vol_low = current_vol < vol_ma10[-1] * 0.8
    volume_signal = (price_high and vol_low) or \
                   (current_vol > vol_ma10[-1] * 2.5 and data['close'].iloc[-1] < data['close'].iloc[-2])

    if volume_signal  :
        print(f"[量价背离] ：{volume_signal} =========")


    # ===== 动量衰减层 =====
    # MACD动量系统
    dif, dea, hist = MACD(data['close'])
    # 动量衰减条件
    momentum_signal = (dif[-1] < dea[-1]) and \
                     (hist[-1] < hist[-3] * 0.7) and \
                     (dif[-1] < np.mean(dif[-10:]) * 0.9)
    

    if momentum_signal  :
        print(f"[动能衰减] ：{momentum_signal} =========")


    # ===== 压力位博弈层 =====
    # 动态压力线计算
    resistance = dynamic_resistance(data['high'])  # 实现动态压力函数
    # 压力位博弈条件
    price_near_resistance = data['close'].iloc[-1] > resistance * 0.985
    false_break = (data['close'].iloc[-3] > resistance) and \
                 (data['close'].iloc[-1] < resistance * 0.97)
    pressure_signal = price_near_resistance or false_break

    if pressure_signal  :
            print(f"[压力位博弈] ：{pressure_signal} =========")


    # ===== 复合信号生成 =====
    # 四重条件触发机制

    # 初始值 3
    if (trend_signal + volume_signal + momentum_signal + pressure_signal) >= 2:
        # 附加波动率过滤
        atr = calculate_ATR(context, symbol)  # 实现ATR计算
        if (data['close'].iloc[-1] - data['close'].iloc[-5])/data['close'].iloc[-5] < atr * 2:
            return True
    return False



def dynamic_resistance(high_series):
    """动态压力线计算"""
    return high_series.rolling(30).max().shift(1).iloc[-1] * 0.987


# 使用示例
if __name__ == "__main__":
    
    None