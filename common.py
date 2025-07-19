import os
import json
import aiohttp
import asyncio
import requests

# 環境變數配置
BITFINEX_PUBLIC_API_URL = os.getenv("BITFINEX_PUBLIC_API_URL", "https://api-pub.bitfinex.com")
STEPS = int(os.getenv("STEPS", "3"))
HIGHEST_SENTIMENT = int(os.getenv("HIGHEST_SENTIMENT", "5"))
RATE_ADJUSTMENT_RATIO = float(os.getenv("RATE_ADJUSTMENT_RATIO", "1.07"))
MINIMUM_RATE = float(os.getenv("MINIMUM_RATE", "0.0003"))
MINIMUM_FUNDS = float(os.getenv("MINIMUM_FUNDS", "150.0"))
RETAIN_FUNDS = float(os.getenv("RETAIN_FUNDS", "0"))

# 利率階梯設定
_default_interest_rate_days = [
    {"rate": 0.0008, "days": 10},
    {"rate": 0.001, "days": 15},
    {"rate": 0.01, "days": 30},
    {"rate": 0.1, "days": 60},
    {"rate": 0.2, "days": 90},
    {"rate": 0.3, "days": 120},    
]

try:
    INTEREST_RATE_DAYS = json.loads(os.getenv("INTEREST_RATE_DAYS", json.dumps(_default_interest_rate_days)))
except (json.JSONDecodeError, TypeError):
    INTEREST_RATE_DAYS = _default_interest_rate_days

"""計算市場的恐慌程度
sentiment > 1:表示當前資金使用量高於平均水平，市場對資金的需求增加，可能表示市場處於較為恐慌或活躍的狀態
sentiment = 1:表示當前資金使用量與平均水平相當，市場情緒平穩
sentiment < 1:表示當前資金使用量低於平均水平，市場對資金的需求減少，可能表示市場較為冷靜或不活躍
"""
async def get_market_borrow_sentiment(currency='fUSD'):
    #TODO: 從 https://report.bitfinex.com/api/json-rpc 獲取匹配簿
    url = f"{BITFINEX_PUBLIC_API_URL}/v2/funding/stats/{currency}/hist"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            fdata = await response.json()
            funding_amount_used_current_hour = fdata[0][8]
            funding_amount_used_avg = 0
            # 獲取過去12小時的平均交易量
            for n in range(1,13):
                rate = fdata[n][3]
                funding_amount_used_avg += fdata[n][8]
                
            funding_amount_used_avg /= 12
            sentiment = funding_amount_used_current_hour/funding_amount_used_avg
            print(f"sentiment: {sentiment}")
            print(f"funding_amount_used_current_hour: {funding_amount_used_current_hour}, funding_amount_used_avg: {funding_amount_used_avg}")
            return sentiment
        
"""從Bitfinex獲取資金簿數據"""
async def get_market_funding_book(currency='fUSD'):
    # 整個市場的總交易量
    market_fday_volume_dict = {2: 1, 30: 1, 60: 1, 120: 1}  # 不能為0
    # 每個日期設置的市場最高利率
    market_frate_upper_dict = {2: -999, 30: -999, 60: -999, 120: -999}
    # 每個日期設置的市場加權平均利率
    market_frate_ravg_dict = {2: 0, 30: 0, 60: 0, 120: 0}

    """從Bitfinex獲取資金簿數據"""
    for page in range(5):
        url = f"{BITFINEX_PUBLIC_API_URL}/v2/book/fUST/P{page}?len=250"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                book_data = await response.json()
                for offer in book_data:
                    numdays = offer[2]
                    if(numdays == 2):
                        market_fday_volume_dict[2] += abs(offer[3]) 
                        market_frate_upper_dict[2] = max(market_frate_upper_dict[2], offer[0])
                        market_frate_ravg_dict[2] += offer[0] * abs(offer[3]) 
                    elif(numdays > 29) and (numdays < 61):
                        market_fday_volume_dict[30] += abs(offer[3])
                        market_frate_upper_dict[30] = max(market_frate_upper_dict[30], offer[0])
                        market_frate_ravg_dict[30] += offer[0] * abs(offer[3]) 
                    elif(numdays > 60) and (numdays < 120):
                        market_fday_volume_dict[60] += abs(offer[3])
                        market_frate_upper_dict[60] = max(market_frate_upper_dict[60], offer[0])
                        market_frate_ravg_dict[60] += offer[0] * abs(offer[3])
                    elif(numdays > 120):
                        market_fday_volume_dict[120] += abs(offer[3])
                        market_frate_upper_dict[120] = max(market_frate_upper_dict[120], offer[0])
                        market_frate_ravg_dict[120] += offer[0] * abs(offer[3])

    # 計算加權平均利率
    market_frate_ravg_dict[2] /= market_fday_volume_dict[2]
    market_frate_ravg_dict[30] /= market_fday_volume_dict[30]
    if market_fday_volume_dict[30] < market_frate_ravg_dict[2]*1.5:
        market_frate_ravg_dict[30] = market_frate_ravg_dict[2]
    market_frate_ravg_dict[60] /= market_fday_volume_dict[60]
    if market_fday_volume_dict[60] < market_frate_ravg_dict[30]:
        market_frate_ravg_dict[60] = market_frate_ravg_dict[30]
    market_frate_ravg_dict[120] /= market_fday_volume_dict[120]
    if market_fday_volume_dict[120] < market_frate_ravg_dict[60]:
        market_frate_ravg_dict[120] = market_frate_ravg_dict[60]

    print("market_fday_volume_dict 總交易量:")
    print(market_fday_volume_dict)
    print("market_frate_upper_dict 最高利率:")
    print(market_frate_upper_dict)
    print("market_frate_ravg_dict 加權平均利率:")
    print(market_frate_ravg_dict)
    # 返回總交易量、最高利率、最低利率
    return market_fday_volume_dict,market_frate_upper_dict,market_frate_ravg_dict

"""獲取近一小時最高利率"""
async def get_last_hour_high_rate(symbol='fUSD'):
    """
    取得前一小時的最高利率
    :param symbol: 幣種，預設 fUSD
    :return: 前一小時最高利率（float），若失敗回傳 None
    """
    url = f"{BITFINEX_PUBLIC_API_URL}/v2/candles/trade:1h:{symbol}:a30:p2:p30/hist"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data or len(data[0]) < 3:
            print("API 回傳資料格式異常")
            return None
        high_rate = float(data[0][3])
        return high_rate
    except Exception as e:
        print(f"取得前一小時最高利率失敗: {e}")
        return None

"""獲取近12小時最高平均利率"""
async def get_last_12_hours_high_avg_rate(symbol='fUSD'):
    """
    取得過去12小時的最高平均利率
    :param symbol: 幣種，預設 fUSD
    :return: 12小時最高平均利率（float），若失敗回傳 None
    """
    url = f"{BITFINEX_PUBLIC_API_URL}/v2/candles/trade:1h:{symbol}:a30:p2:p30/hist?limit=12"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
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

"""從資金簿數據猜測報價利率"""
async def guess_funding_book(volume_dict,rate_upper_dict,rate_avg_dict,sentiment):
    # 利率猜測，這裡只使用市場最高值
    last_step_percentage = 1 + (RATE_ADJUSTMENT_RATIO - 1.0) * STEPS
    sentiment_ratio = max(1.0,sentiment/HIGHEST_SENTIMENT)
    rate_guess_2 = rate_avg_dict[2] * last_step_percentage * sentiment_ratio
    rate_guess_30 = rate_avg_dict[30] * last_step_percentage * sentiment_ratio
    rate_guess_60 = rate_avg_dict[60] * last_step_percentage * sentiment_ratio
    rate_guess_120 = rate_avg_dict[120] * last_step_percentage * sentiment_ratio
    rate_guess_upper = { 2: rate_guess_2, 30: rate_guess_30, 60: rate_guess_60, 120: rate_guess_120}
    print(f"rate_guess_upper: {rate_guess_upper}")
    return rate_guess_upper[2]

"""產生階梯利率"""
async def generate_lending_levels(avg_rate, guess_rate, last_hour_high_rate, last_12_hours_high_avg_rate):
    steps = STEPS
    minimum_rate = MINIMUM_RATE
    sorted_rate_days = sorted(INTEREST_RATE_DAYS, key=lambda x: x['rate'])
    # base_rate = max(avg_rate, last_hour_high_rate, last_12_hours_high_avg_rate, MINIMUM_RATE)
    base_rate = max(avg_rate, last_hour_high_rate, last_12_hours_high_avg_rate)
    segment_rate = (guess_rate - avg_rate) / steps if steps > 0 else 0

    levels = []
    for i in range(1, steps + 1):
        rate = round(base_rate + i * segment_rate, 5)
        period = 2
        for item in sorted_rate_days:
            if rate >= item['rate']:
                period = item['days']
            else:
                break
        levels.append({"rate": rate, "period": period})
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
        return bfx.rest.auth.cancel_all_funding_offers(currency)
    except Exception as e:
        print(f"Error removing lending offers: {e}")
        return None

"""取得可用資金"""
async def get_available_lending_funds(bfx, currency):
    funds = await bfx.get_balance(currency[1:])
    return max(0, funds - RETAIN_FUNDS)

"""新增訂單"""
async def place_lending_orders(bfx, currency, levels):
    available_funds = await get_available_lending_funds(bfx, currency)
    minimum_funds = MINIMUM_FUNDS
    n = len(levels)
    if n == 0:
        print("無需新增訂單")
        return
    elif available_funds < minimum_funds:
        print(f"資金不足：可用資金 {available_funds}，小於最小下單金額 {minimum_funds}")
        return

    split_fund = max(minimum_funds, round(available_funds / n, 2))
    tasks = []
    for i, level in enumerate(levels):
        if i < n - 1:
            amount = min(split_fund, available_funds)
        else:
            amount = available_funds  # 最後一單吃掉所有剩餘資金
        if amount < minimum_funds:
            break
        order_to_send = level.copy()
        order_to_send["amount"] = amount
        available_funds -= amount

        async def submit_order(order):
            try:
                result = await bfx.submit_order(order, currency)
                return result
            except Exception as e:
                print(f"Error submitting funding offer: {e}")
                return False

        # 這裡直接建立 task
        tasks.append(submit_order(order_to_send))

    # 最後一次性等待所有送單結果
    results = await asyncio.gather(*tasks)
    print(f"成功新增訂單數量: {sum(results)}")