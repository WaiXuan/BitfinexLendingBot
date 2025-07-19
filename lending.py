import os,sys,time,platform
import asyncio
import json
import aiohttp
import schedule
from concurrent.futures import ThreadPoolExecutor
import common

import bitfinex
from datetime import datetime

async def lending_bot_strategy(currency):
    print(f"\n----------------------------------\n現在時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 獲取市場情緒
    sentiment = await common.get_market_borrow_sentiment(currency)

    # 獲取市場利率
    volume_dict,rate_upper_dict,rate_avg_dict = await common.get_market_funding_book(currency)

    # 猜測市場利率
    guess_rate = await common.guess_funding_book(volume_dict,rate_upper_dict,rate_avg_dict,sentiment)

    # *0.95 避免過高利率
    last_hour_high_rate = await common.get_last_hour_high_rate() * 0.95 
    last_12_hours_high_avg_rate = await common.get_last_12_hours_high_avg_rate()
    new_levels = await common.generate_lending_levels(rate_avg_dict[2], guess_rate, last_hour_high_rate, last_12_hours_high_avg_rate)

    # 每6小時重置一次訂單
    now = datetime.now()
    if (now.hour % 6 == 0) and (now.minute == 6):
        await bfx.remove_all_lending_offer(currency)

    # 取得現有訂單
    current_offers = await bfx.get_funding_offers(currency)
    current_orders = [
        {"rate": float(o.rate), "amount": abs(float(o.amount)), "period": int(o.period), "id": o.id}
        for o in current_offers
        if hasattr(o, "rate") and hasattr(o, "amount") and hasattr(o, "period") and hasattr(o, "id")
    ]

    matched_orders, new_orders, cancel_orders = common.diff_lending_levels(new_levels, current_orders)

    # 5. 取消不需要的舊訂單
    if cancel_orders:
        await common.cancel_lending_orders(bfx, cancel_orders)
        await asyncio.sleep(1)  # 等待資金回補

    await common.place_lending_orders(bfx, currency, new_orders)

    # 印出目前所有訂單
    current_offers = await bfx.get_funding_offers(currency)    
    for offer in current_offers:
        print(f"Offer Rate={offer.rate}, Apy={round(offer.rate * 100 * 365, 2)}%, Period={offer.period}, Amount={offer.amount}")

# 環境變數配置
FUND_CURRENCY = [os.getenv("FUND_CURRENCY", "fUSD")]
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "600"))

async def run_schedule_task():
    for currency in FUND_CURRENCY:
        await lending_bot_strategy(currency)  # 執行放貸機器人策略任務
    
async def main():
    global bfx, interval_seconds  # 如果你在其他地方用到
    bfx = bitfinex.Bitfinex(api_key=os.getenv("BF_API_KEY"), api_secret=os.getenv("BF_API_SECRET"))
    interval_seconds = INTERVAL_SECONDS

    print(f"放貸機器人將每 {interval_seconds} 秒執行一次")

    for currency in FUND_CURRENCY:
        await bfx.remove_all_lending_offer(currency[1:])

    # 直接執行一次任務
    await run_schedule_task()

    # 定義一個 schedule 用的 callback，直接建立 async task
    def schedule_task():
        asyncio.create_task(run_schedule_task())

    # 設定排程
    schedule.every(interval_seconds).seconds.do(schedule_task)

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())

