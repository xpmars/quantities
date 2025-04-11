# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *
import math
import datetime

from QTUtils import *


'''
示例策略仅供参考，不建议直接实盘使用。

日内回转交易是指投资者就同一个标的（如股票）在同一个交易日内各完成多次买进和卖出的行为
其目的为维持股票数量不变，降低股票成本
本策略以1分钟MACD为基础，金叉时买入，死叉时卖出，尾盘回转至初始仓位
'''


def init(context):
    # 在init中增加择时参数
    context.risk_ratio = 0.02  # 单笔风险敞口2%
    context.atr_period = 14    # ATR计算周期
    context.trend_period = 10   # 趋势判定周期
    context.volume_ratio = 1.1  # 量能突破阈值

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
    context.trade_cash_ratio = 0.1  # 每次交易账户可用资金的10%
    # 使用的频率，60s为1分钟bar，300s为5分钟bar
    context.frequency = '300s'
    # 回溯数据长度（计算MACD)
    context.periods_time = 1000
    # 订阅数据
    subscribe(symbols=context.all_symbols,
              frequency=context.frequency,
              count=context.periods_time,
              fields='symbol,eob,close')
    # 订阅标的的日线数据，窗口长度设为15（14周期ATR+1）
    subscribe(symbols=context.all_symbols,
              frequency='1d',
              count=15)

    # 初始化ATR值存储到上下文
    context.atr_value = None

    schedule(schedule_func=algo, date_rule='1d', time_rule='14:55:00')

def algo(context):
    ''' 独立定时调仓函数 '''
    print("\n[尾盘调仓启动]")
    account = context.account()
    for symbol in context.all_symbols:
        # 获取当前持仓
        position = account.positions(symbol=symbol, side=PositionSide_Long)
        if position and len(position) > 0:
            current_vol = position[0]['volume']
            current_price = position[0]['price']
        else:
            current_vol = 0
            current_price = None  # 或使用行情接口获取最新价
            continue
            
        # 获取账户总资产
        available_cash = account.cash['nav']
        # 当日可交易总资金
        target_value = available_cash * context.total_cash_ratio 
        # 当日交易股票数
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
    
    # eod_position_summary(context)


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
    # 获取账户可用资金
    available_cash = account.cash['available']
    # 当日可交易总资金
    target_value = available_cash * context.total_cash_ratio 








    # 初始建仓
    if context.first[symbol] == 0 and current_price>0 :
        if not check_timing_buy_signal(context, symbol):
            print(f"{context.now} {symbol} 择时条件未满足，跳过建仓")
            return
        
        context.first[symbol] = 1
        order_value(symbol=symbol, 
                   value=target_value,
                   side=OrderSide_Buy,
                   order_type=OrderType_Market,
                   position_effect=PositionEffect_Open)
        print(f'{context.now}：{symbol}建底仓，投入资金={target_value:.2f}')
        return

#     # 计算ATR
#     atr = calculate_ATR(context, bars, period=14)
#     # 存储当前ATR值到上下文
#     context.atr_value = atr
#    # 打印带日期的ATR值（保留2位小数）
#     print(f"[{context.now}] {bars[0]['symbol']} ATR值: {atr:.4f}")  # 修改这里

    # 日内交易
    # 本次（单次）可交易总资金
    trade_value = available_cash * context.trade_cash_ratio
    trade_volume = int(trade_value / current_price) if current_price > 0 else 0
    

    # 修改on_bar中的交易量计算（新增动态交易量）
    trade_value = min(available_cash * context.trade_cash_ratio,
                    calculate_dynamic_position(context, symbol) * current_price) 
    print(f"[本次交易量] 计划交易量={available_cash * context.trade_cash_ratio:.2f}元 | 动态交易量={calculate_dynamic_position(context, symbol) * current_price:.2f}元 | 实际交易量={trade_value:.2f}")


    close = context.data(symbol=symbol,
                        frequency=context.frequency,
                        count=context.periods_time,
                        fields='close')['close'].values
    dif, dea, _ = MACD(close)
    if dif[-2] <= dea[-2] and dif[-1] > dea[-1] :  # 日内金叉
        if trade_volume >0:
            order_value(symbol=symbol,
                       value=trade_value,
                       side=OrderSide_Buy,
                       order_type=OrderType_Market,
                       position_effect=PositionEffect_Open)
    elif dif[-2] >= dea[-2] and dif[-1] < dea[-1]:  # 日内死叉
        if trade_volume >0:
            order_value(symbol=symbol,
                       value=trade_value,
                       side=OrderSide_Sell,
                       order_type=OrderType_Market,
                       position_effect=PositionEffect_Close)



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

