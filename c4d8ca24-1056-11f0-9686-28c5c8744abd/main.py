# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *
import math
import datetime
import pandas as pd
import numpy as np
from QTUtils import *


'''
示例策略仅供参考，不建议直接实盘使用。

日内回转交易是指投资者就同一个标的（如股票）在同一个交易日内各完成多次买进和卖出的行为
其目的为维持股票数量不变，降低股票成本
本策略以1分钟MACD为基础，金叉时买入，死叉时卖出，尾盘回转至初始仓位
'''


def init(context):
    # 设置标的股票
    context.all_symbols = ['SHSE.600000','SHSE.688165']
    # 用于判定第一个仓位是否成功开仓
    context.first = {symbol:0 for symbol in context.all_symbols}
    # 需要保持的总仓位
    # context.total = 50000
    # 日内回转每次交易数量
    # context.trade_n = 25000
    # 初始资金比例（总仓位比例）
    context.total_cash_ratio = 0.25  # 总仓位占账户资金的50%
    # 每次交易资金比例（日内回转比例）
    context.trade_cash_ratio = 0.1  # 每次交易账户可用资金的20%
    # 使用的频率，60s为1分钟bar，300s为5分钟bar
    context.frequency = '300s'
    # 回溯数据长度（计算MACD)
    context.periods_time = 1000
    # 订阅数据
    subscribe(symbols=context.all_symbols,
              frequency=context.frequency,
              count=context.periods_time,
              fields='symbol,eob,close')
    #  # 增加对1d频率数据的订阅
    # subscribe(symbols=context.all_symbols,
    #           frequency='1d',
    #           count=2,
    #           fields='symbol,close')

    schedule(schedule_func=algo, date_rule='1d', time_rule='14:55:00')

def algo(context):
    ''' 独立定时调仓函数 '''
    print("\n[尾盘调仓启动]")
    account = context.account()
    for symbol in context.all_symbols:
        # 获取当前持仓
        position = account.positions(symbol=symbol, side=PositionSide_Long)
        current_vol = position[0]['volume'] if position else 0
        
        # 计算目标仓位
        current_price = position[0]['price']
        if not current_price:
            continue
            
        target_value = account.cash['nav'] * context.total_cash_ratio
        target_vol = math.ceil((target_value / current_price) / 200) * 200  # 整手数
        
        # 执行调仓
        delta = target_vol - current_vol
        if delta > 0:
            order_volume(symbol=symbol, 
                        volume=delta,
                        side=OrderSide_Buy,
                        order_type=OrderType_Limit,
                        price=current_price*1.005,  # 限价避免滑点
                        position_effect=PositionEffect_Open)
        elif delta < 0:
            order_volume(symbol=symbol,
                        volume=abs(delta),
                        side=OrderSide_Sell,
                        order_type=OrderType_Limit,
                        price=current_price*0.995,
                        position_effect=PositionEffect_Close)
    
    QTUtils.eod_position_summary(context)



# 订阅行情
def on_bar(context, bars):
    # 获取账户数据
    account = context.account()
    bar = bars[0]
    symbol = bar['symbol']
    # 获取当前价格
    current_price = bar['close']
    # 获取账户总资金
    total_cash = account.cash['nav']
    target_value = total_cash * context.total_cash_ratio # 可交易总资金
    

    # 初始建仓
    if context.first[symbol] == 0 and current_price>0:
        context.first[symbol] = 1
        order_value(symbol=symbol, 
                   value=target_value,
                   side=OrderSide_Buy,
                   order_type=OrderType_Market,
                   position_effect=PositionEffect_Open)
        print(f'{context.now}：{symbol}建底仓，投入资金={target_value:.2f}')
        return

    # 获取持仓
    position = list(filter(lambda x:x['symbol']==symbol,get_position()))
    if not position:  # 新增空值判断
        print(f"{symbol} 无持仓，跳过交易逻辑")
        return
    
    # 日内交易
    available_cash = context.account().cash['available']
    trade_value = available_cash * context.trade_cash_ratio
    trade_volume = int(trade_value / current_price) if current_price>0 else 0
    
    close = context.data(symbol=symbol,
                        frequency=context.frequency,
                        count=context.periods_time,
                        fields='close')['close'].values
    dif, dea, _ = MACD(close)
    
    if dif[-2] <= dea[-2] and dif[-1] > dea[-1]:  # 金叉
        if trade_volume >0:
            order_value(symbol=symbol,
                       value=trade_value,
                       side=OrderSide_Buy,
                       order_type=OrderType_Market,
                       position_effect=PositionEffect_Open)
    elif dif[-2] >= dea[-2] and dif[-1] < dea[-1]:  # 死叉
        if trade_volume >0:
            order_value(symbol=symbol,
                       value=trade_value,
                       side=OrderSide_Sell,
                       order_type=OrderType_Market,
                       position_effect=PositionEffect_Close)


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


def on_order_status(context, order):
    # 标的代码
    symbol = order['symbol']
    # 委托价格
    price = order['price']
    # 委托数量
    volume = order['volume']
    # 查看下单后的委托状态，等于3代表委托全部成交
    status = order['status']
    # 买卖方向，1为买入，2为卖出
    side = order['side']
    # 开平仓类型，1为开仓，2为平仓
    effect = order['position_effect']
    # 委托类型，1为限价委托，2为市价委托
    order_type = order['order_type']
    if status == 3:
        if effect == 1:
            if side == 1:
                side_effect = '开多仓'
            else:
                side_effect = '开空仓'
        else:
            if side == 1:
                side_effect = '平空仓'
            else:
                side_effect = '平多仓'
        order_type_word = '限价' if order_type == 1 else '市价'
        print('{}:标的：{}，操作：以{}{}，委托价格：{}，委托数量：{}'.format(
            context.now, symbol, order_type_word, side_effect, price, volume))


def on_backtest_finished(context, indicator):
    print('*' * 50)
    print('回测已完成，请通过右上角“回测历史”功能查询详情。')


if __name__ == '__main__':
    '''
    strategy_id策略ID,由系统生成
    filename文件名,请与本文件名保持一致
    mode实时模式:MODE_LIVE回测模式:MODE_BACKTEST
    token绑定计算机的ID,可在系统设置-密钥管理中生成
    backtest_start_time回测开始时间
    backtest_end_time回测结束时间
    backtest_adjust股票复权方式不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
    backtest_initial_cash回测初始资金
    backtest_commission_ratio回测佣金比例
    backtest_slippage_ratio回测滑点比例
    backtest_match_mode市价撮合模式，以下一tick/bar开盘价撮合:0，以当前tick/bar收盘价撮合：1
    '''
    backtest_start_time = str(datetime.datetime.now() - datetime.timedelta(days=180))[:19]
    backtest_end_time = str(datetime.datetime.now())[:19]
    run(strategy_id='c4d8ca24-1056-11f0-9686-28c5c8744abd',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='a39f0567e24a8c8a3d7f0cef38a71d619be4ee96',
        backtest_start_time=backtest_start_time,
        backtest_end_time=backtest_end_time,
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=1000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)

