# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
import gm.api as gm
import datetime
import pandas as pd

# 设置API令牌（请替换为您的实际令牌）
# 获取令牌: https://quant.10jqka.com.cn/platform/account/api
token='a39f0567e24a8c8a3d7f0cef38a71d619be4ee96'
gm.set_token(token)


def get_previous_trading_day():
    """获取上一个交易日日期"""
    today = datetime.datetime.today()
    # 先尝试获取昨日日期
    prev_day = today - datetime.timedelta(days=1)
    
    # 获取最近的交易日历
    calendar = gm.get_trading_dates(exchange='SHSE', start_date='2020-01-01', end_date=prev_day.strftime('%Y-%m-%d'))
    
    if calendar:
        # 返回格式化的日期时间 (YYYYMMDDHHMMSS)
        if len(calendar)>=2:
            # 格式化为YYYY-MM-DD HH:MM:SS
            prev_prev_date = calendar[-2].replace('-', '')
            prev_date = calendar[-1].replace('-', '')
            return f"{prev_prev_date[:4]}-{prev_prev_date[4:6]}-{prev_prev_date[6:8]} 00:00:00", f"{prev_date[:4]}-{prev_date[4:6]}-{prev_date[6:8]} 23:59:59"
        else:
            # 格式化为YYYY-MM-DD HH:MM:SS
            date_str = calendar[-1].replace('-', '')
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 00:00:00", f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 23:59:59"
    return prev_day.strftime('%Y-%m-%d')


def get_limit_up_stocks():
    """获取昨日涨停股票池"""
    # 获取上一个交易日
    prev_prev_day, prev_trading_day = get_previous_trading_day()
    print(f"正在获取 {prev_trading_day} 的涨停股票...")
    
    # 1. 获取所有A股股票
    all_stocks = gm.get_instruments(
        exchanges=['SHSE', 'SZSE'],
        sec_types=[gm.SEC_TYPE_STOCK],
        df=True
    )
    
    # 2. 股票筛选（排除ST、次新股、非主板股票）
    filtered_stocks = all_stocks[
        # 排除ST股票
        (~all_stocks['symbol'].str.contains('ST')) & 
        # 排除上市不满一年的次新股
        (all_stocks['listed_date'] < (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d')) &
        # 排除创业板(300)、科创板(688)、北交所(8开头)
        (~all_stocks['symbol'].str.startswith(('SZSE.300', 'SHSE.688', 'BJSE.8')))
    ]
    
    # 3. 批量获取股票日线数据（每次50个，避免API限制）
    limit_up_stocks = []
    batch_size = 50
    symbols = filtered_stocks['symbol'].tolist()
    
    for i in range(0, len(symbols), batch_size):
        batch_symbols = symbols[i:i+batch_size]
        
        try:
            # 获取昨日日线数据
            hist_data = gm.history(
                symbol=batch_symbols,
                frequency='1d',
                start_time=prev_prev_day,
                  end_time=prev_trading_day,
                fields='symbol,stock_name,close,limit_up,high_limit,change_percent',
                df=True
            )
            
            # 筛选涨停股票 (考虑0.1%的价格误差)
            if not hist_data.empty:
                # print(f"API返回字段: {hist_data.columns.tolist()}")
                # 按股票分组并计算涨停
                for symbol, group in hist_data.groupby('symbol'):
                    # 获取前两天收盘价
                    # 假设数据按日期排序，取最新的两个收盘价
                    if len(group) >= 2:
                        prev_prev_close = group['close'].iloc[-2]
                        prev_close = group['close'].iloc[-1]
                    else:
                        continue  # 确保有两天数据
                    
                    # 计算涨停价 (10%涨幅，保留两位小数)
                    limit_up_price = round(prev_prev_close * 1.1, 2)
                    
                    # 检查是否涨停 (允许0.01元误差)
                    if prev_close >= limit_up_price - 0.01:
                        limit_up_stocks.append(symbol)
                
        except Exception as e:
            print(f"批量获取数据失败: {str(e)}")
            continue
        
    # 处理结果
    result = []
    trade_date = prev_trading_day
    
    # 遍历每只涨停股票
    for symbol in limit_up_stocks:
        # 获取股票名称
        try:
            # 使用get_instruments获取股票基本信息
            instrument = gm.get_instruments(symbols=symbol, df=True)
            # 打印API返回的所有列名，用于调试
            # print(f"API返回的字段: {instrument.columns.tolist()}")
            # 尝试使用不同的字段名获取股票名称
            if 'sec_name' in instrument.columns:
                stock_name = instrument['sec_name'].values[0] if not instrument.empty else '未知'
            else:
                stock_name = '未知'
                print(f"无法找到股票名称字段: {symbol}, 可用字段: {instrument.columns.tolist()}")
        except Exception as e:
            print(f"获取股票名称失败: {symbol}, 错误: {str(e)}")
            stock_name = '未知'

        # 获取涨幅
        # 获取涨幅和昨日涨幅
        try:
            # 计算日期范围，获取最近3个交易日的数据
            # 不使用count参数，改用start_time和end_time
            end_time = prev_trading_day
            # 计算3天前的日期作为开始时间
            start_date = (datetime.datetime.strptime(end_time.split(' ')[0], '%Y-%m-%d') - datetime.timedelta(days=10)).strftime('%Y-%m-%d')
            start_time = f"{start_date} 00:00:00"

            hist_data = gm.history(
                symbol=symbol,
                frequency='1d',
                start_time=start_time,
                end_time=end_time,
                fields='close',
                df=True
            )

            if len(hist_data) >= 3:
                prev_prev_close = hist_data['close'].iloc[-3]
                prev_close = hist_data['close'].iloc[-2]
                current_close = hist_data['close'].iloc[-1]
                # 计算当日涨幅
                change_percent = round((current_close - prev_close) / prev_close * 100, 2)
                # 计算昨日涨幅
                previous_change_percent = round((prev_close - prev_prev_close) / prev_prev_close * 100, 2)
            elif len(hist_data) == 2:
                prev_close = hist_data['close'].iloc[0]
                current_close = hist_data['close'].iloc[1]
                change_percent = round((current_close - prev_close) / prev_close * 100, 2)
                previous_change_percent = 0.0
            else:
                current_close = 0.0
                change_percent = 0.0
                previous_change_percent = 0.0
                print(f"获取历史数据不足: {symbol}, 数据长度: {len(hist_data)}")
        except Exception as e:
            print(f"获取涨幅数据失败: {symbol}, 错误: {str(e)}")
            current_close = 0.0
            change_percent = 0.0
            previous_change_percent = 0.0
        
        # 添加到结果列表
        result.append({
            'date': trade_date.split(' ')[0],
            'symbol': symbol,
            'name': stock_name,
            'current_price': current_close,
            'change_percent': change_percent,
            'previous_change_percent': previous_change_percent
        })
    
    # 打印结果
    print(f"\n{trade_date} 涨停股票池 (共{len(result)}只):")
    for i, item in enumerate(result, 1):
        print(f"{i}. 日期: {item['date']} 代码: {item['symbol']} 名称: {item['name']} 当前价格: {item['current_price']} 今日涨幅: {item['change_percent']}% 昨日涨幅: {item['previous_change_percent']}%")
    
    # 导出为CSV文件
    if result:
        # 明确指定列顺序，确保包含所有要求的字段
        df = pd.DataFrame(result, columns=['date', 'symbol', 'name', 'current_price', 'change_percent', 'previous_change_percent'])
        df.to_csv(f'limit_up_stocks_{trade_date.split(" ")[0]}.csv', index=False)
        print(f"\n股票池已导出至: limit_up_stocks_{trade_date.split(" ")[0]}.csv")
    
    return prev_trading_day, limit_up_stocks


if __name__ == '__main__':
    # 获取涨停股票池
    trade_date, stocks = get_limit_up_stocks()