# -*- coding: utf-8 -*-
import os, sys, platform
import asyncio
import schedule
import config
import common
import bitfinex
from datetime import datetime
from dotenv import load_dotenv
from order_book_monitor import OrderBookMonitor
from discord_notifier import discord_notifier
from lending_monitor import lending_monitor

# 載入環境變數
load_dotenv()

# 設定 Windows 控制台編碼為 UTF-8
if platform.system() == "Windows":
    os.system("chcp 65001")
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 全局變數
bfx = None
order_book_monitor = None

# 常數
SEPARATOR_LINE = f"\n{'-' * 50}\n"

def is_order_protected_by_opportunistic_monitor(currency, period):
    """檢查訂單是否受機會性監控器保護"""
    global order_book_monitor
    
    if order_book_monitor is None:
        return False
    
    order_key = f"{currency.replace('f', '')}_{period}"
    return order_book_monitor._is_order_protected(order_key)

async def lending_bot_strategy(currency):
    print(f"{SEPARATOR_LINE}現在時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 獲取基本市場分析資料 (簡化版)
    timeframe_analysis = {'market_activity_score': 0.5, 'should_accelerate': False}

    # 獲取市場情緒
    sentiment = await common.get_market_borrow_sentiment(bfx, currency)

    # 獲取市場利率
    volume_dict,rate_upper_dict,rate_avg_dict = await common.get_market_funding_book(bfx, currency)

    # 計算交易量變化 (用於增強情緒權重)
    volume_change = 0  # 這裡可以從 volume_dict 計算變化率
    
    # 猜測市場利率 (傳入交易量變化)
    guess_rate = await common.guess_funding_book(volume_dict,rate_upper_dict,rate_avg_dict,sentiment,volume_change)

    # 使用動態安全係數
    if config.ENABLE_DYNAMIC_OPTIMIZATION:
        last_hour_high_rate = await common.get_last_hour_high_rate(bfx, currency, sentiment, True)
    else:
        last_hour_high_rate = await common.get_last_hour_high_rate(bfx, currency, sentiment, False)
    
    last_12_hours_high_avg_rate = await common.get_last_12_hours_high_avg_rate(bfx)
    
    # 生成優化階梯策略
    new_levels = await common.generate_lending_levels(bfx,
        rate_avg_dict[2], guess_rate, last_hour_high_rate, last_12_hours_high_avg_rate,
        sentiment, timeframe_analysis['market_activity_score']
    )

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

    # 過濾受保護的訂單 (機會性訂單在設定時間內不被修改)
    protected_orders = []
    unprotected_orders = []
    
    for order in current_orders:
        if is_order_protected_by_opportunistic_monitor(currency, order['period']):
            protected_orders.append(order)
            print(f"訂單受保護: {order['period']}天 @ {order['rate']*365:.2%}")
        else:
            unprotected_orders.append(order)
    
    # 只對未受保護的訂單進行比較
    matched_orders, new_orders, cancel_orders = common.diff_lending_levels(new_levels, unprotected_orders)

    # 5. 取消不需要的舊訂單 (但不取消受保護的訂單)
    if cancel_orders:
        await common.cancel_lending_orders(bfx, cancel_orders)
        await asyncio.sleep(1)  # 等待資金回補

    # 記錄下單前的狀態，用於通知
    pre_place_offers_count = len(current_offers) - len(cancel_orders)
    
    await common.place_lending_orders(bfx, currency, new_orders)
    
    # 不發送掛單變動通知，避免訊息過多

    # 印出目前所有訂單
    current_offers = await bfx.get_funding_offers(currency)    
    for offer in current_offers:
        print(f"Offer Rate={offer.rate}, Apy={round(offer.rate * 100 * 365, 2)}%, Period={offer.period}, Amount={int(offer.amount)}")

async def opportunistic_order_monitor():
    """機會性訂單監控 - 只在利率更優時執行"""
    global order_book_monitor, bfx
    
    if order_book_monitor is None or bfx is None:
        return
    
    try:
        print(f"\n機會性訂單監控 - {datetime.now().strftime('%H:%M:%S')}")
        
        for currency in config.FUND_CURRENCY:
            # 獲取當前常規訂單作為比較基準
            current_offers = await bfx.get_funding_offers(currency)
            current_orders = [
                {"rate": float(o.rate), "amount": abs(float(o.amount)), "period": int(o.period), "id": o.id}
                for o in current_offers
                if hasattr(o, "rate") and hasattr(o, "amount") and hasattr(o, "period") and hasattr(o, "id")
            ]
            
            success = await order_book_monitor.monitor_and_act(currency, current_orders)
            if success:
                print(f"{currency} 執行機會性訂單成功")
            
    except Exception as e:
        print(f"機會性訂單監控錯誤: {e}")

async def send_status_notification(currency: str):
    """發送當前放貸狀態通知"""
    try:
        # 獲取掛單中的訂單
        current_offers = await bfx.get_funding_offers(currency)
        # 獲取放貸中的訂單
        funding_credits = await bfx.get_funding_credits(currency)
        # 獲取可用餘額
        available_balance = await bfx.get_balance(currency[1:])
        
        # 暫時設定 bfx 實例給 discord_notifier，用於獲取歷史收益
        discord_notifier._bfx_instance = bfx
        await discord_notifier.notify_orders_status(current_offers, funding_credits, currency, available_balance)
    except Exception as e:
        print(f"發送狀態通知失敗: {e}")

async def check_lending_status():
    """檢查放貸狀態變化（資金歸還/新成交）"""
    for currency in config.FUND_CURRENCY:
        await lending_monitor.check_lending_changes(bfx, currency)

async def daily_status_report():
    """每日資金配置狀態報告"""
    for currency in config.FUND_CURRENCY:
        await send_status_notification(currency)

async def run_schedule_task():
    for currency in config.FUND_CURRENCY:
        await lending_bot_strategy(currency)  # 執行放貸機器人策略任務
    
def format_interval(seconds):
    """格式化時間間隔顯示"""
    if seconds >= 60:
        minutes = seconds // 60
        return f"{seconds} 秒 ({minutes} 分鐘)"
    return f"{seconds} 秒"

async def main():
    global bfx, order_book_monitor
    bfx = bitfinex.Bitfinex(api_key=os.getenv("BF_API_KEY"), api_secret=os.getenv("BF_API_SECRET"))
    
    # 使用新的可配置時間參數
    regular_interval = config.REGULAR_STRATEGY_INTERVAL
    opportunistic_interval = config.OPPORTUNISTIC_MONITOR_INTERVAL

    print(f"常規放貸策略將每 {format_interval(regular_interval)} 執行一次")
    print(f"機會性訂單監控將每 {format_interval(opportunistic_interval)} 執行一次")
    print("每日 00:00 將自動發送資金配置狀態報告")

    # 初始化訂單簿監控器
    order_book_monitor = OrderBookMonitor(bfx)  # 直接傳入 bfx 實例

    # 清除既有訂單並發送啟動通知
    for currency in config.FUND_CURRENCY:
        await bfx.remove_all_lending_offer(currency[1:])
        
        # 獲取可用資金並發送啟動通知
        available_funds = await common.get_available_lending_funds(bfx, currency, config)
        await discord_notifier.notify_startup(available_funds, currency)

    # 直接執行一次任務
    await run_schedule_task()
    
    # 發送初始狀態通知
    for currency in config.FUND_CURRENCY:
        await send_status_notification(currency)

    # 定義 schedule 用的 callback
    def schedule_task():
        asyncio.create_task(run_schedule_task())
    
    def schedule_opportunistic_monitor():
        asyncio.create_task(opportunistic_order_monitor())
    
    def schedule_lending_status_check():
        asyncio.create_task(check_lending_status())
    
    def schedule_daily_status_report():
        asyncio.create_task(daily_status_report())

    # 設定排程
    schedule.every(regular_interval).seconds.do(schedule_task)
    schedule.every(opportunistic_interval).seconds.do(schedule_opportunistic_monitor)  # 機會性訂單監控
    schedule.every(30).seconds.do(schedule_lending_status_check)  # 每30秒檢查放貸狀態變化
    schedule.every().day.at("00:00").do(schedule_daily_status_report)  # 每日00:00資金配置狀態報告

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())

