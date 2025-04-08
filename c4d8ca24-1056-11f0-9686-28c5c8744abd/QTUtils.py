class QTUtils:
    # 获取当前价格
    @staticmethod
    def get_current_price(context, symbol):
        current_data = context.data(symbol=symbol, frequency=context.frequency, count=1, fields='close')
        if len(current_data) == 0:
            print(f"未获取到 {symbol} 当前价格数据。")
            return None
        return current_data['close'].values[0]
    # 获取前一日收盘价
    @staticmethod
    def get_previous_close_price(context, symbol):
        previous_data = context.data(symbol=symbol, frequency='1d', count=2, fields='close')
        if len(previous_data) < 2:
            print(f"未获取到 {symbol} 前一日收盘价数据。")
            return None
        return previous_data['close'].values[1]
    # 计算涨跌幅
    @staticmethod
    def calculate_change_percentage(current_price, previous_close_price):
        return (current_price - previous_close_price) / previous_close_price * 100



    #  获取涨停价
    @staticmethod
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
    @staticmethod
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


# 使用示例
if __name__ == "__main__":
    None