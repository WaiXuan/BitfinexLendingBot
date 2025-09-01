import config
import asyncio
from dynamic_optimizer import DynamicOptimizer

# 初始化動態優化器
optimizer = DynamicOptimizer()

# ===== 業務邏輯方法：使用 bitfinex.py 的基礎 API =====

"""計算市場的恐慌程度 (使用 bitfinex.py 的 API)
sentiment > 1:表示當前資金使用量高於平均水平，市場對資金的需求增加，可能表示市場處於較為恐慌或活躍的狀態
sentiment = 1:表示當前資金使用量與平均水平相當，市場情緒平穩
sentiment < 1:表示當前資金使用量低於平均水平，市場對資金的需求減少，可能表示市場較為冷靜或不活躍
"""
async def get_market_borrow_sentiment(bfx, currency='fUSD'):
    """
    獲取市場借貸情緒 (使用 bitfinex.py 的基礎 API)
    
    Args:
        bfx: Bitfinex 客戶端實例
        currency: 幣種代碼
        
    Returns:
        情緒值 (當前資金使用量 / 平均資金使用量)
    """
    try:
        fdata = await bfx.get_funding_stats(currency)
        if not fdata or len(fdata) < 13:
            print(f"融資統計資料不足: {len(fdata) if fdata else 0} 筆")
            return 1.0
        
        funding_amount_used_current_hour = fdata[0][8]
        funding_amount_used_avg = 0
        
        # 獲取過去12小時的平均交易量
        for n in range(1, 13):
            funding_amount_used_avg += fdata[n][8]
        
        funding_amount_used_avg /= 12
        sentiment = funding_amount_used_current_hour / funding_amount_used_avg
        
        print(f"sentiment: {sentiment}")
        print(f"funding_amount_used_current_hour: {funding_amount_used_current_hour}, funding_amount_used_avg: {funding_amount_used_avg}")
        
        return sentiment
        
    except Exception as e:
        print(f"獲取市場借貸情緒失敗: {e}")
        return 1.0

"""從 Bitfinex 獲取資金簿數據 (使用 bitfinex.py 的基礎 API)"""
async def get_market_funding_book(bfx, currency='fUSD'):
    """
    獲取市場資金簿資料 (使用 bitfinex.py 的基礎 API)
    
    Args:
        bfx: Bitfinex 客戶端實例
        currency: 幣種代碼
        
    Returns:
        (volume_dict, rate_upper_dict, rate_avg_dict) 三個字典的元組
    """
    try:
        # 整個市場的總交易量
        market_fday_volume_dict = {2: 1, 30: 1, 60: 1, 120: 1}  # 不能為0
        # 每個日期設置的市場最高利率
        market_frate_upper_dict = {2: -999, 30: -999, 60: -999, 120: -999}
        # 每個日期設置的市場加權平均利率
        market_frate_ravg_dict = {2: 0, 30: 0, 60: 0, 120: 0}
        
        # 使用 bitfinex.py 的統一 API 方法獲取資料
        api_currency = 'fUST'  # API 使用的幣別名稱
        book_data = await bfx.get_funding_book_data(api_currency, pages=5)
        
        for offer in book_data:
            if len(offer) >= 4:
                numdays = offer[2]
                rate = offer[0]
                amount = abs(offer[3])
                
                if numdays == 2:
                    market_fday_volume_dict[2] += amount
                    market_frate_upper_dict[2] = max(market_frate_upper_dict[2], rate)
                    market_frate_ravg_dict[2] += rate * amount
                elif 29 < numdays < 61:
                    market_fday_volume_dict[30] += amount
                    market_frate_upper_dict[30] = max(market_frate_upper_dict[30], rate)
                    market_frate_ravg_dict[30] += rate * amount
                elif 60 < numdays < 120:
                    market_fday_volume_dict[60] += amount
                    market_frate_upper_dict[60] = max(market_frate_upper_dict[60], rate)
                    market_frate_ravg_dict[60] += rate * amount
                elif numdays > 120:
                    market_fday_volume_dict[120] += amount
                    market_frate_upper_dict[120] = max(market_frate_upper_dict[120], rate)
                    market_frate_ravg_dict[120] += rate * amount
        
        # 計算加權平均利率
        for days in [2, 30, 60, 120]:
            if market_fday_volume_dict[days] > 0:
                market_frate_ravg_dict[days] /= market_fday_volume_dict[days]
        
        # 邏輯修正：如果交易量過低，使用較短期的利率
        if market_fday_volume_dict[30] < market_frate_ravg_dict[2] * 1.5:
            market_frate_ravg_dict[30] = market_frate_ravg_dict[2]
        if market_fday_volume_dict[60] < market_frate_ravg_dict[30]:
            market_frate_ravg_dict[60] = market_frate_ravg_dict[30]
        if market_fday_volume_dict[120] < market_frate_ravg_dict[60]:
            market_frate_ravg_dict[120] = market_frate_ravg_dict[60]
        
        print("market_fday_volume_dict 總交易量:")
        print(market_fday_volume_dict)
        print("market_frate_upper_dict 最高利率:")
        print(market_frate_upper_dict)
        print("market_frate_ravg_dict 加權平均利率:")
        print(market_frate_ravg_dict)
        
        return market_fday_volume_dict, market_frate_upper_dict, market_frate_ravg_dict
        
    except Exception as e:
        print(f"獲取市場資金簿失敗: {e}")
        # 返回預設值
        default_volume = {2: 1, 30: 1, 60: 1, 120: 1}
        default_upper = {2: 0.0001, 30: 0.0001, 60: 0.0001, 120: 0.0001}
        default_avg = {2: 0.0001, 30: 0.0001, 60: 0.0001, 120: 0.0001}
        return default_volume, default_upper, default_avg

"""獲取近一小時最高利率 (使用 bitfinex.py 的基礎 API)"""
async def get_last_hour_high_rate(bfx, symbol='fUSD', sentiment=1.0, apply_dynamic_factor=True):
    """
    獲取近一小時最高利率 (使用 bitfinex.py 的基礎 API)
    
    Args:
        bfx: Bitfinex 客戶端實例
        symbol: 幣種，預設 fUSD
        sentiment: 市場情緒值，用於計算動態係數
        apply_dynamic_factor: 是否應用動態係數，預設為 True
        
    Returns:
        調整後的前一小時最高利率（float），若失敗回傳 None
    """
    try:
        data = await bfx.get_candle_data(symbol, '1h', 'a30:p2:p30')
        if not data or len(data[0]) < 4:
            print("API 回傳資料格式異常")
            return None
        
        high_rate = float(data[0][3])
        
        if apply_dynamic_factor:
            # 計算利率波動度
            recent_rates = [float(candle[3]) for candle in data[:5] if len(candle) > 3]
            rate_volatility = optimizer.calculate_rate_volatility(recent_rates)
            
            # 計算動態安全係數
            dynamic_factor = optimizer.calculate_dynamic_safety_factor(sentiment, rate_volatility)
            adjusted_rate = high_rate * dynamic_factor
            
            print(f"原始最高利率: {high_rate:.6f}, 動態係數: {dynamic_factor:.4f}, 調整後利率: {adjusted_rate:.6f}")
            return adjusted_rate
        else:
            # 原始邏輯 (固定 0.95 係數)
            return high_rate * 0.95
            
    except Exception as e:
        print(f"取得前一小時最高利率失敗: {e}")
        return None

"""獲取近12小時最高平均利率 (使用 bitfinex.py 的基礎 API)"""
async def get_last_12_hours_high_avg_rate(bfx, symbol='fUSD'):
    """
    獲取近12小時最高平均利率 (使用 bitfinex.py 的基礎 API)
    
    Args:
        bfx: Bitfinex 客戶端實例
        symbol: 幣種，預設 fUSD
        
    Returns:
        12小時最高平均利率（float），若失敗回傳 None
    """
    try:
        data = await bfx.get_candle_data(symbol, '1h', 'a30:p2:p30', limit=12)
        if not data or len(data) < 12:
            print("API 回傳資料不足 12 筆")
            return None
        
        # 取每一小時的 high 值（第4個欄位）
        high_rates = [float(item[3]) for item in data[:12]]
        avg_high_rate = sum(high_rates) / len(high_rates)
        return avg_high_rate
        
    except Exception as e:
        print(f"取得過去12小時最高平均利率失敗: {e}")
        return None

"""獲取24小時市場最低利率 (使用 bitfinex.py 的基礎 API)"""
async def get_24h_market_low_rate(bfx, symbol='fUSD'):
    """
    獲取24小時市場最低利率 (使用 bitfinex.py 的基礎 API)
    
    Args:
        bfx: Bitfinex 客戶端實例
        symbol: 幣種，預設 fUSD
        
    Returns:
        24小時最低利率（float），若失敗回傳 None
    """
    try:
        data = await bfx.get_candle_data(symbol, '1h', 'a30:p2:p30', limit=24)
        if not data or len(data) < 24:
            print("24小時資料不足")
            return None
        
        # 取每一小時的 low 值（第5個欄位）
        low_rates = [float(item[4]) for item in data[:24]]
        min_rate = min(low_rates)
        print(f"24小時最低利率: {min_rate:.6f}")
        return min_rate
        
    except Exception as e:
        print(f"取得24小時最低利率失敗: {e}")
        return None

"""從資金簿數據猜測報價利率 (優化版含增強情緒權重)"""
async def guess_funding_book(volume_dict,rate_upper_dict,rate_avg_dict,sentiment,volume_change=0):
    # 利率猜測，整合增強版情緒權重系統
    last_step_percentage = 1 + (config.RATE_ADJUSTMENT_RATIO - 1.0) * config.STEPS
    
    if config.ENABLE_DYNAMIC_OPTIMIZATION:
        # 使用增強版情緒權重計算
        enhanced_sentiment_weight = optimizer.calculate_enhanced_sentiment_weight(sentiment, volume_change)
        sentiment_ratio = max(1.0, enhanced_sentiment_weight)
        print(f"增強情緒權重: {enhanced_sentiment_weight:.4f} (原始情緒: {sentiment:.4f})")
    else:
        # 原始邏輯
        sentiment_ratio = max(1.0, sentiment/config.HIGHEST_SENTIMENT)
        print(f"傳統情緒權重: {sentiment_ratio:.4f}")
    
    rate_guess_2 = rate_avg_dict[2] * last_step_percentage * sentiment_ratio
    rate_guess_30 = rate_avg_dict[30] * last_step_percentage * sentiment_ratio
    rate_guess_60 = rate_avg_dict[60] * last_step_percentage * sentiment_ratio
    rate_guess_120 = rate_avg_dict[120] * last_step_percentage * sentiment_ratio
    rate_guess_upper = { 2: rate_guess_2, 30: rate_guess_30, 60: rate_guess_60, 120: rate_guess_120}
    print(f"rate_guess_upper: {rate_guess_upper}")
    return rate_guess_upper[2]

"""產生階梯利率 (優化版含動態調整)"""
async def generate_lending_levels(bfx, avg_rate, guess_rate, last_hour_high_rate, last_12_hours_high_avg_rate, 
                                  sentiment=1.0, market_activity=0.5):
    # 動態計算階梯數和最低利率
    if config.ENABLE_DYNAMIC_OPTIMIZATION:
        # 動態階梯數
        competition_density = 0.5  # 暫時固定，之後可從市場資料計算
        STEPS = optimizer.get_optimal_step_count(market_activity, competition_density)
        
        # 動態最低利率 (需要 bfx 實例)
        market_24h_low = await get_24h_market_low_rate(bfx)
        if market_24h_low:
            MINIMUM_RATE = optimizer.get_dynamic_minimum_rate(market_24h_low, avg_rate)
            print(f"動態最低利率: {MINIMUM_RATE:.6f} (原始: {config.MINIMUM_RATE:.6f})")
        else:
            MINIMUM_RATE = config.MINIMUM_RATE
        print(f"動態階梯數: {STEPS} (原始: {config.STEPS})")
    else:
        STEPS = config.STEPS
        MINIMUM_RATE = config.MINIMUM_RATE
        
    sorted_rate_days = sorted(config.INTEREST_RATE_DAYS, key=lambda x: x['rate'])
    base_rate = max(avg_rate, last_hour_high_rate, last_12_hours_high_avg_rate, MINIMUM_RATE)
    segment_rate = (guess_rate - avg_rate) / STEPS if STEPS > 0 else 0

    levels = []
    
    # 計算斐波那契資金分配比例 (如果啟用動態優化)
    if config.ENABLE_DYNAMIC_OPTIMIZATION:
        fib_ratios = optimizer.calculate_fibonacci_distribution(STEPS)
    else:
        fib_ratios = [1.0/STEPS] * STEPS  # 平均分配
    
    for i in range(1, STEPS + 1):
        rate = round(base_rate + i * segment_rate, 5)
        period = 2
        for item in sorted_rate_days:
            if rate >= item['rate']:
                period = item['days']
            else:
                break
        
        # 添加資金分配比例
        fund_ratio = fib_ratios[i-1] if config.ENABLE_DYNAMIC_OPTIMIZATION else 1.0/STEPS
        levels.append({"rate": rate, "period": period, "fund_ratio": fund_ratio})
        
    print(f"生成 {STEPS} 階利率，資金分配比例: {[f'{r:.3f}' for r in fib_ratios] if config.ENABLE_DYNAMIC_OPTIMIZATION else '平均分配'}")
    return levels

"""比對新舊訂單，只比對 rate 與 period，產生需新增與需取消的訂單"""
def diff_lending_levels(new_levels, current_orders):
    new_orders = []
    matched_orders = []
    current_orders_copy = current_orders.copy()
    for n in new_levels:
        found = False
        for c in current_orders_copy:
            if abs(n["rate"] - c["rate"]) < 1e-8 and n["period"] == c["period"]:
                matched_orders.append(c)
                current_orders_copy.remove(c)
                found = True
                break
        if not found:
            new_orders.append(n)
    cancel_orders = [c["id"] for c in current_orders_copy]
    return matched_orders, new_orders, cancel_orders

"""取消指定訂單報價"""
async def cancel_order(bfx, order_id):
    try:
        await bfx.cancel_order(order_id)
        return True
    except Exception as e:
        print(f"Error cancelling funding offer: {e}")
        return False

"""取消指定訂單報價"""
async def cancel_lending_orders(bfx, cancel_orders):
    tasks = [cancel_order(bfx, order_id) for order_id in cancel_orders]
    results = await asyncio.gather(*tasks)
    print(f"成功取消訂單數量: {sum(results)}")

"""移除所有訂單報價"""
async def remove_all_lending_offer(bfx, currency):
    try:
        return await bfx.remove_all_lending_offer(currency)
    except Exception as e:
        print(f"Error removing lending offers: {e}")
        return None

"""取得可用資金"""
async def get_available_lending_funds(bfx, currency, config):
    funds = await bfx.get_balance(currency[1:])
    return max(0, funds - config.RETAIN_FUNDS)

"""新增訂單 (優化版含智能資金分配)"""
async def place_lending_orders(bfx, currency, levels):
    available_funds = await get_available_lending_funds(bfx, currency, config)
    MINIMUM_FUNDS = config.MINIMUM_FUNDS
    n = len(levels)
    if n == 0:
        print("無需新增訂單")
        return
    elif available_funds < MINIMUM_FUNDS:
        print(f"資金不足：可用資金 {available_funds}，小於最小下單金額 {MINIMUM_FUNDS}")
        return

    successful_orders = 0
    remaining_funds = available_funds
    
    # 預先計算所有訂單的資金分配（整數金額）
    allocated_amounts = []
    available_funds_int = int(available_funds)  # 轉為整數
    
    if 'fund_ratio' in levels[0]:
        # 使用斐波那契分配
        for level in levels:
            target_amount = int(available_funds_int * level['fund_ratio'])
            allocated_amounts.append(max(int(MINIMUM_FUNDS), target_amount))
    else:
        # 平均分配
        for i in range(n):
            allocated_amounts.append(max(int(MINIMUM_FUNDS), int(available_funds_int / n)))
    
    # 檢查總分配金額是否超過可用資金，若超過則按比例縮減
    total_allocated = sum(allocated_amounts)
    if total_allocated > available_funds_int:
        # 從最後一筆開始減少金額，直到總額符合
        diff = total_allocated - available_funds_int
        for i in range(len(allocated_amounts) - 1, -1, -1):
            reduce_amount = min(diff, allocated_amounts[i] - int(MINIMUM_FUNDS))
            allocated_amounts[i] -= reduce_amount
            diff -= reduce_amount
            if diff <= 0:
                break
        print(f"資金分配調整後: {allocated_amounts}")
    
    # 改為循序下單，避免資金不足問題
    for i, level in enumerate(levels):
        amount = int(allocated_amounts[i])
        
        # 確保不低於最低金額，且不超過剩餘資金
        amount = max(int(MINIMUM_FUNDS), min(amount, int(remaining_funds)))
        
        # 最後一單分配所有剩餘資金（確保充分利用資金）
        if i == n - 1:
            amount = int(remaining_funds)
            
        if amount < MINIMUM_FUNDS:
            print(f"第 {i+1} 階資金不足: {amount} < {int(MINIMUM_FUNDS)}")
            break
            
        order_to_send = level.copy()
        order_to_send["amount"] = amount
        
        print(f"階梯 {i+1}: 利率 {level['rate']:.5f}, 金額 {amount}, 期限 {level['period']}天")
        
        try:
            result = await bfx.submit_order(order_to_send, currency)
            if result:
                successful_orders += 1
                remaining_funds -= amount
            else:
                print(f"第 {i+1} 階訂單提交失敗")
        except Exception as e:
            print(f"Error submitting funding offer: {e}")
            break  # 如果有錯誤，停止後續下單
            
        # 小延遲確保訂單處理完成
        await asyncio.sleep(0.1)
        
    print(f"成功新增訂單數量: {successful_orders}")