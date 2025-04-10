# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
import numpy as np
from gm.api import *

import math
import datetime
import pandas as pd
from QTUtils import *

def init(context):
    # 订阅标的的日线数据，窗口长度设为15（14周期ATR+1）
    subscribe(symbols='SHSE.688165', frequency='1d', count=15)
    # 初始化ATR值存储到上下文
    context.atr_value = None

def on_bar(context, bars):

    
    # 计算ATR
    atr = calculate_ATR(context, bars, period=14)
    
    # 存储当前ATR值到上下文
    context.atr_value = atr
    # 获取当前bar的时间（格式化为日期字符串）
    current_date = bars[0]['eob'].strftime('%Y-%m-%d')  # 使用eob时间
    # 打印带日期的ATR值（保留2位小数）
    print(f"[{current_date}] {bars[0]['symbol']} ATR值: {atr:.4f}")  # 修改这里


    # 示例交易逻辑：当ATR突破阈值时发出信号
    if context.atr_value > 2.0:

        order_target_percent(symbol=bars[0]['symbol'], percent=0.1, position_side=PositionSide_Long, 
                             order_type=OrderType_Market)

        print(f"{bars[0]['symbol']} ATR突破阈值，买入10%仓位")

def calculate_ATR(context, bars, period):
    """
    计算平均真实波幅(ATR)
    :param data: DataFrame格式，包含high, low, close价格数据
    :param period: ATR计算周期
    :return: 最新ATR值
    """
    # 获取数据滑窗
    data = context.data(symbol=bars[0]['symbol'], frequency='1d', count=15)
    high = data['high'].values
    low = data['low'].values
    close = data['close'].values
    
    # 计算真实波幅TR
    tr = np.zeros(len(data))
    for i in range(1, len(data)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    # 计算ATR（简单移动平均）
    atr = np.convolve(tr, np.ones(period)/period, mode='valid')
    return atr[-1] if len(atr) > 0 else 0

if __name__ == '__main__':
    backtest_start_time = str(datetime.datetime.now() - datetime.timedelta(days=180))[:19]
    backtest_end_time = str(datetime.datetime.now())[:19]
    run(strategy_id='c4d8ca24-1056-11f0-9686-28c5c8744abd',
        filename='ATR.py',
        mode=MODE_BACKTEST,
        token='a39f0567e24a8c8a3d7f0cef38a71d619be4ee96',
        backtest_start_time=backtest_start_time,
        backtest_end_time=backtest_end_time,
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=1000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)