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
    # 设置标的股票
    context.all_symbols = ['SHSE.600000','SHSE.688165']
    # 用于判定第一个仓位是否成功开仓
    context.first = {symbol:0 for symbol in context.all_symbols}
     # 新增交易状态锁
    context.trading_blocked = {
        symbol: {
            'status': False,          # 交易锁状态
            'expire_time': None       # 过期时间
        } for symbol in context.all_symbols
    }

    # 需要保持的总仓位
    # context.total = 50000
    # 日内回转每次交易数量
    # context.trade_n = 25000
    # 初始资金比例（总仓位比例）
    context.total_cash_ratio = 0.25  # 总仓位占账户资金的50%
    # 每次交易资金比例（日内回转比例）
    context.trade_cash_ratio = 0.1  # 每次交易账户可用资金的10%
    # MACD日内分时使用的频率，60s为1分钟bar，300s为5分钟bar
    context.frequency = '300s'
    # MACD日内分时回溯数据长度（计算MACD)
    context.periods_time = 1000

    # 在init中增加择时参数
    context.risk_ratio = 0.02  # 单笔风险敞口2%
    context.atr_period = 14    # ATR计算周期
    context.trend_period = 10   # 趋势判定周期
    context.volume_ratio = 1.2  # 量能突破阈值

    # 初始化ATR值存储到上下文
    context.atr_value = None

    # 在策略初始化中设置
    context.sell_params = {
    'atr_multiplier': 2.2,      # AR波动过滤系数
    'resistance_buffer': 0.985, # 压力位检测缓冲
    'volume_threshold': 2.3     # 放量下跌阈值
    }

    
    # 订阅数据日内分时数据
    subscribe(symbols=context.all_symbols,
              frequency=context.frequency,
              count=context.periods_time,
              fields='symbol,eob,close')
    # 订阅标的的日线数据，窗口长度设为55（14周期ATR+1）
    subscribe(symbols=context.all_symbols,
              frequency='1d',
              count=55)

    # # 新增10:01定时卖出任务
    # schedule(schedule_func=daily_sell, 
    #         date_rule='1d', 
    #         time_rule='10:00:00')  # 网页8同花顺定时策略参考

    schedule(schedule_func=algo, date_rule='1d', time_rule='14:55:00')



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


    # 初始建仓(择时建仓)
    if context.first[symbol] == 0 and current_price>0 :
        # 重置交易锁
        if context.trading_blocked[symbol]['status']:
            unlock_trading(context, symbol)
            print(f"{symbol} ======新建仓触发交易锁解除=======")

        if not check_timing_buy_signal(context, symbol):
            print(f"{context.now} {symbol} 择时条件未满足，跳过建仓")
            return
        # 表示持仓该股票
        context.first[symbol] = 1
        order_value(symbol=symbol, 
                   value=target_value,
                   side=OrderSide_Buy,
                   order_type=OrderType_Market,
                   position_effect=PositionEffect_Open)
        print(f'{context.now}：{symbol}建底仓，投入资金={target_value:.2f}')
        return


    # # 在交易信号触发前增加锁状态检查

    
    if context.trading_blocked[symbol]['status'] and \
        context.trading_blocked[symbol]['expire_time'] < context.now:
        # print(f"{context.now} {symbol} 交易锁生效，跳过日内回转")
        return


    # 日内交易
    # 本次（单次）可交易总资金
    trade_value = available_cash * context.trade_cash_ratio
    trade_volume = int(trade_value / current_price) if current_price > 0 else 0
    

    # 修改on_bar中的交易量计算（新增动态交易量）
    trade_value = min(available_cash * context.trade_cash_ratio,
                    calculate_dynamic_position(context, symbol) * current_price) 
    # print(f"[本次交易量] 计划交易量={available_cash * context.trade_cash_ratio:.2f}元 \
    #     | 动态交易量={calculate_dynamic_position(context, symbol) * current_price:.2f}元 \
    #     | 实际交易量={trade_value:.2f}")

    close = context.data(symbol=symbol,
                        frequency=context.frequency,
                        count=context.periods_time,
                        fields='close')['close'].values
    dif, dea, _ = MACD(close)
    if dif[-2] <= dea[-2] and dif[-1] > dea[-1] and check_trading_permission(context, symbol):  # 日内金叉
        if trade_volume >0:
            order_value(symbol=symbol,
                       value=trade_value,
                       side=OrderSide_Buy,
                       order_type=OrderType_Market,
                       position_effect=PositionEffect_Open)
    elif dif[-2] >= dea[-2] and dif[-1] < dea[-1] and check_trading_permission(context, symbol):  # 日内死叉
        if trade_volume >0:
            order_value(symbol=symbol,
                       value=trade_value,
                       side=OrderSide_Sell,
                       order_type=OrderType_Market,
                       position_effect=PositionEffect_Close)



    # 分层卖出执行（减持）
    if generate_sell_signal(context, symbol):
        daily_data_close = context.data(symbol=symbol,
                                frequency='1d',
                                count=55,
                                fields='close')['close'].values
        # 第一层：触发基础信号
        print(f"====触发第1层卖出信号====，减持30%" )
        order_target_percent(symbol=symbol, percent=0.7,
                             position_side=PositionSide_Short,
                             order_type=OrderType_Market)  # 减持30%
                             
        on_order_status
        lock_trading(context, symbol)
        
        # 第二层：MACD零轴下强化
        dif, dea, _ = MACD(daily_data_close)
        if dif[-1] < 0:  
            print(f"====触发第2层卖出信号====，减持20%" )
            order_target_percent(symbol=symbol,percent=0.5,
                        position_side=PositionSide_Short,
                        order_type=OrderType_Market)  # 减持30%
            lock_trading(context, symbol)
            
        # 第三层：周线级别确认
        # 获取近一周收盘价（网页9周线处理逻辑）
        weekly_close = np.mean(daily_data_close[-5:]) if len(daily_data_close)>=5 else None
        daily_ma20 = np.mean(daily_data_close[-20:])
        if weekly_close < daily_ma20:
            print(f"====触发第3层卖出信号====，清仓" )
            temp = order_target_percent(symbol=symbol,percent=0.0,
                        position_side=PositionSide_Short,
                        order_type=OrderType_Market)  
            print(temp)
            lock_trading(context, symbol)
            # 清仓标记
            context.first[symbol] = 0
            eod_position_summary(context);
        

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

