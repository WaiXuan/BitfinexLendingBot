#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord Webhook 通知模組
用於發送放貸機器人狀態通知到 Discord 頻道
"""
import aiohttp
import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import config

# 確保載入環境變數 - 處理打包後的路徑問題
import sys
if getattr(sys, 'frozen', False):
    # 如果是打包的執行檔
    base_path = os.path.dirname(sys.executable)
else:
    # 如果是直接執行 Python 腳本
    base_path = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(base_path, '.env')
load_dotenv(env_path)

class DiscordNotifier:
    def __init__(self, position_webhook_url: Optional[str] = None, daily_report_webhook_url: Optional[str] = None):
        """
        初始化 Discord 通知器 - 支持雙 webhook 設定
        
        Args:
            position_webhook_url: 倉位異動通知 Webhook URL
            daily_report_webhook_url: 每日報表通知 Webhook URL
        """
        # 倉位異動通知 webhook (放貸成交、歸還等)
        self.position_webhook_url = position_webhook_url or os.getenv("DISCORD_POSITION_WEBHOOK") or os.getenv("DISCORD_WEBHOOKS")
        
        # 每日報表通知 webhook (啟動通知、狀態總覽、收益報告等)
        self.daily_report_webhook_url = daily_report_webhook_url or os.getenv("DISCORD_DAILY_REPORT_WEBHOOK") or os.getenv("DISCORD_WEBHOOKS")
        
        # 向後兼容：如果都沒設定，使用舊的環境變數
        if not self.position_webhook_url and not self.daily_report_webhook_url:
            fallback_url = os.getenv("DISCORD_WEBHOOKS")
            self.position_webhook_url = fallback_url
            self.daily_report_webhook_url = fallback_url
        
        self.last_notification_state = {}  # 記錄上次通知的狀態
        self.opportunistic_orders = set()  # 追蹤機會性訂單ID
    
    def _calculate_remaining_days(self, credit, original_period):
        """
        計算放貸的真實剩餘天數
        
        Args:
            credit: FundingCredit 物件
            original_period: 原始期限天數
            
        Returns:
            int: 剩餘天數
        """
        try:
            # 嘗試獲取創建時間戳記 (毫秒)
            mts_create = getattr(credit, 'mts_create', None)
            
            if mts_create:
                # 轉換毫秒時間戳記為秒
                create_time = datetime.fromtimestamp(mts_create / 1000)
                
                # 計算到期日期
                from datetime import timedelta
                expiry_date = create_time + timedelta(days=original_period)
                
                # 計算剩餘天數
                remaining = (expiry_date - datetime.now()).days
                
                # 確保剩餘天數不為負數
                return max(0, remaining)
            else:
                # 如果沒有創建時間，返回原始期限（向後兼容）
                return original_period
                
        except Exception as e:
            print(f"計算剩餘天數時發生錯誤: {e}")
            # 錯誤時返回原始期限
            return original_period
    
    def mark_as_opportunistic_order(self, rate: float, period: int, amount: float):
        """標記機會性訂單"""
        order_signature = f"{rate:.6f}_{period}_{amount:.2f}"
        self.opportunistic_orders.add(order_signature)
        print(f"標記機會性訂單: {order_signature}")
    
    def _is_opportunistic_order(self, credit) -> bool:
        """檢查是否為機會性訂單"""
        try:
            rate = float(getattr(credit, 'rate', 0))
            period = getattr(credit, 'period', 0)
            amount = abs(float(getattr(credit, 'amount', getattr(credit, 'amount_orig', 0))))
            
            order_signature = f"{rate:.6f}_{period}_{amount:.2f}"
            return order_signature in self.opportunistic_orders
        except:
            return False
        
    async def send_message(self, title: str, description: str, color: int = 0x00ff00, fields: List[Dict] = None, 
                          webhook_type: str = "position"):
        """
        發送 Discord 訊息
        
        Args:
            title: 標題
            description: 描述
            color: 顏色 (預設綠色)
            fields: 額外欄位列表
            webhook_type: webhook 類型 ("position"=倉位異動, "daily_report"=每日報表)
        """
        # 根據類型選擇 webhook URL
        if webhook_type == "daily_report":
            webhook_url = self.daily_report_webhook_url
            webhook_name = "每日報表"
        else:
            webhook_url = self.position_webhook_url
            webhook_name = "倉位異動"
        
        if not webhook_url:
            print(f"Discord {webhook_name} Webhook URL 未設定，跳過通知")
            return False
        
        # 加入台灣時間
        from datetime import timezone, timedelta
        taiwan_timezone = timezone(timedelta(hours=8))
        taiwan_time = datetime.now(taiwan_timezone)
        time_str = taiwan_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 在描述中加入時間戳記
        description_with_time = f"🕒 **{time_str}**\n\n{description}"
            
        embed = {
            "title": title,
            "description": description_with_time,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Bitfinex 放貸機器人"
            }
        }
        
        if fields:
            embed["fields"] = fields
            
        payload = {
            "embeds": [embed]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 204:
                        print(f"Discord 通知發送成功: {title}")
                        return True
                    else:
                        print(f"Discord 通知發送失敗: HTTP {response.status}")
                        return False
        except Exception as e:
            print(f"Discord 通知發送異常: {e}")
            return False
    
    async def notify_startup(self, available_funds: float, currency: str):
        """
        發送啟動通知 - 增強版，包含詳細配置信息
        """
        title = "🚀 放貸機器人已啟動"
        description = f"系統已成功啟動，開始監控 {currency} 放貸機會\n\n📊 **系統配置概覽**"
        
        # 獲取配置信息
        regular_interval = config.REGULAR_STRATEGY_INTERVAL
        opportunistic_interval = config.OPPORTUNISTIC_MONITOR_INTERVAL
        min_rate = config.MINIMUM_RATE * 365 * 100  # 轉換為年化百分比
        
        fields = [
            {
                "name": "💰 可用資金", 
                "value": f"{available_funds:.2f} {currency.replace('f', '')}", 
                "inline": True
            },
            {
                "name": "🔄 常規策略間隔",
                "value": f"{regular_interval} 秒",
                "inline": True
            },
            {
                "name": "⚡ 機會性監控間隔", 
                "value": f"{opportunistic_interval} 秒",
                "inline": True
            },
            {
                "name": "📉 最低利率門檻",
                "value": f"{min_rate:.2f}% 年化",
                "inline": True
            },
            {
                "name": "🎯 階梯數範圍",
                "value": f"{config.MIN_STEPS} - {config.MAX_STEPS} 層",
                "inline": True
            },
            {
                "name": "🤖 動態優化",
                "value": "✅ 已啟用" if config.ENABLE_DYNAMIC_OPTIMIZATION else "❌ 未啟用",
                "inline": True
            }
        ]
        
        await self.send_message(title, description, 0x00ff00, fields, webhook_type="daily_report")
    
    async def notify_orders_status(self, offers: List, credits: List, currency: str, available_balance: float = None):
        """
        發送訂單狀態通知 - 增強版，包含詳細收益信息
        """
        total_offered = sum(abs(float(o.amount)) for o in offers) if offers else 0
        total_credits = sum(abs(float(getattr(c, 'amount', getattr(c, 'amount_orig', 0)))) for c in credits) if credits else 0
        
        # 計算收益信息
        daily_earning = 0
        highest_rate = 0
        if credits:
            daily_earning = sum(abs(float(getattr(c, 'amount', getattr(c, 'amount_orig', 0)))) * 
                              float(getattr(c, 'rate', 0)) for c in credits)
            highest_rate = max(float(getattr(c, 'rate', 0)) for c in credits) * 365

        title = "📊 資金配置狀態報告"
        description = f"**{currency}** 詳細資金狀況與收益分析"
        
        fields = []
        
        # 修正後的資金顯示 - available_balance 是當前可用餘額
        if available_balance is not None:
            total_managed = available_balance + total_offered + total_credits
            
            fields.extend([
                {
                    "name": "💼 管理總額",
                    "value": f"{total_managed:.2f} {currency.replace('f', '')}",
                    "inline": True
                },            
                {
                    "name": "💵 放貸金額",
                    "value": f"{total_credits:.2f} {currency.replace('f', '')}",
                    "inline": True
                },
                {
                    "name": "📋 掛單金額",
                    "value": f"{total_offered:.2f} {currency.replace('f', '')}",
                    "inline": True
                },
                {
                    "name": "💸 每日預期收益",
                    "value": f"{daily_earning:.2f} {currency.replace('f', '')}" if daily_earning > 0 else "無收益",
                    "inline": True
                },
                {
                    "name": "📈 最高利率",
                    "value": f"{highest_rate:.2%}" if highest_rate > 0 else "N/A",
                    "inline": True
                }                        
            ])
        
        # 放貸中資金詳情
        if credits:
            avg_credit_rate = sum(float(getattr(c, 'rate', 0)) for c in credits) / len(credits)
            fields.extend([
                {
                    "name": "📊 放貸筆數",
                    "value": f"{len(credits)} 筆",
                    "inline": True
                },
                {
                    "name": "📈 平均利率",
                    "value": f"{avg_credit_rate*365:.2%} 年化",
                    "inline": True
                }
            ])
        else:
            fields.append({
                "name": "💎 放貸狀態",
                "value": "目前沒有放貸中的資金",
                "inline": False
            })
        
        # 顯示放貸中的明細（金額、利率、剩餘日期）
        if credits:
            credit_details = []
            for credit in credits[:8]:  # 最多顯示8筆
                amount = abs(float(getattr(credit, 'amount', getattr(credit, 'amount_orig', 0))))
                rate = float(getattr(credit, 'rate', 0))
                period = getattr(credit, 'period', 'N/A')
                
                # 計算真實剩餘天數
                remaining_days = self._calculate_remaining_days(credit, period)
                rate_annual = rate * 365
                
                credit_details.append(f"💰 {amount:.0f} @ {rate_annual:.2%} (剩餘 {remaining_days}天)")
            
            if len(credits) > 8:
                credit_details.append(f"... 還有 {len(credits)-8} 筆")
                
            fields.append({
                "name": "📋 放貸明細",
                "value": "\n".join(credit_details),
                "inline": False
            })
        
        # 獲取收益歷史分析（24小時 + 30天）
        if hasattr(self, '_bfx_instance') and self._bfx_instance:
            try:
                from datetime import datetime, timedelta
                
                # 獲取收益歷史數據
                ledger_history_30d = await self._bfx_instance.get_funding_ledger_history(currency.replace('f', ''), 24 * 30)
                ledger_history_24h = await self._bfx_instance.get_funding_ledger_history(currency.replace('f', ''), 24)
                
                # 處理30天收益統計 - 按要求格式調整
                if ledger_history_30d:
                    returns_30d = [h for h in ledger_history_30d if h.get('type') in ['paired_return', 'unpaired_return']]
                    
                    if returns_30d:
                        total_returned_30d = sum(r.get('amount', 0) for r in returns_30d)
                        total_count_30d = len(returns_30d)
                        avg_daily_return = total_returned_30d / 30 if total_returned_30d > 0 else 0
                        
                        # 計算30天平均利率（使用當前放貸中的訂單作為參考）
                        avg_rate_text = ""
                        try:
                            # 使用當前放貸中的訂單計算平均利率（代表過去30天的放貸利率水平）
                            if credits:
                                avg_credit_rate = sum(float(getattr(c, 'rate', 0)) for c in credits) / len(credits)
                                avg_rate_text = f"📊 平均利率: {avg_credit_rate*365:.2%}"
                        except:
                            pass
                        
                        # 構建30天收益報告
                        value_lines = [
                            f"💰 總收益: {total_returned_30d:.2f} {currency.replace('f', '')}",
                            f"📊 放貸筆數: {total_count_30d} 筆",
                            f"📅 日均收益: {avg_daily_return:.2f} {currency.replace('f', '')}"
                        ]
                        if avg_rate_text:
                            value_lines.append(avg_rate_text)
                        
                        fields.append({
                            "name": "📈 過去30天收益",
                            "value": "\n".join(value_lines),
                            "inline": False
                        })
                    else:
                        # 沒有30天收益數據的情況
                        fields.append({
                            "name": "📈 過去30天收益",
                            "value": ("💰 總收益: 0.00 USD\n"
                                    "📊 放貸筆數: 0 筆\n"
                                    "📅 日均收益: 0.00 USD"),
                            "inline": False
                        })
                else:
                    # 完全沒有30天歷史記錄
                    fields.append({
                        "name": "📈 過去30天收益",
                        "value": ("💰 總收益: 0.00 USD\n"
                                "📊 放貸筆數: 0 筆\n"
                                "📅 日均收益: 0.00 USD"),
                        "inline": False
                    })
                
                # 處理24小時收益統計 - 按要求格式調整
                if ledger_history_24h:
                    recent_returns = [h for h in ledger_history_24h if h.get('type') in ['paired_return', 'unpaired_return']]
                    
                    if recent_returns:
                        total_returned_amount = sum(r.get('amount', 0) for r in recent_returns)
                        fields.append({
                            "name": "⚡ 過去24小時收益",
                            "value": f"💸 總收益: {total_returned_amount:.2f} {currency.replace('f', '')}\n📋 歸還筆數: {len(recent_returns)} 筆",
                            "inline": True
                        })
                    else:
                        fields.append({
                            "name": "⚡ 過去24小時收益", 
                            "value": "💸 總收益: 0.00 USD\n📋 歸還筆數: 0 筆",
                            "inline": True
                        })
                else:
                    # 沒有歷史記錄也要顯示24小時收益欄位
                    fields.append({
                        "name": "⚡ 過去24小時收益", 
                        "value": "💸 總收益: 0.00 USD\n📋 歸還筆數: 0 筆",
                        "inline": True
                    })
                    
            except Exception as e:
                print(f"獲取收益歷史時發生錯誤: {e}")
                # 簡化錯誤提示
                fields.append({
                    "name": "📊 收益統計",
                    "value": "數據獲取中，請稍後再查看",
                    "inline": False
                })
        
        await self.send_message(title, description, 0x0099ff, fields, webhook_type="daily_report")
    
    async def notify_funding_returned(self, returned_credits: List, currency: str):
        """
        發送放貸金額歸還通知
        """
        if not returned_credits:
            return
            
        title = "💰 放貸資金已歸還"
        description = f"{currency} 有 {len(returned_credits)} 筆放貸資金到期歸還"
        color = 0x00ff00  # 綠色
        
        total_returned = sum(abs(float(getattr(credit, 'amount', getattr(credit, 'amount_orig', 0)))) for credit in returned_credits)
        total_interest = sum(float(getattr(credit, 'interest', 0)) for credit in returned_credits if hasattr(credit, 'interest'))
        
        fields = [
            {
                "name": "💵 歸還金額",
                "value": f"{total_returned:.2f} {currency.replace('f', '')}",
                "inline": True
            },
            {
                "name": "📊 歸還筆數", 
                "value": f"{len(returned_credits)} 筆資金已歸還",
                "inline": True
            }
        ]
        
        # 計算平均年利率（無論是否有利息都顯示）
        avg_rate = sum(float(getattr(credit, 'rate', 0)) for credit in returned_credits) / len(returned_credits) * 365 if returned_credits else 0
        
        fields.append({
            "name": "📈 平均年利率",
            "value": f"{avg_rate:.2%}",
            "inline": True
        })
        
        if total_interest > 0:
            total_return_rate = (total_interest / total_returned * 100) if total_returned > 0 else 0
            
            fields.append({
                "name": "💎 獲得利息",
                "value": f"{total_interest:.4f} {currency.replace('f', '')}",
                "inline": True
            })
            fields.append({
                "name": "📊 總收益率",
                "value": f"{total_return_rate:.3f}%",
                "inline": True
            })
        else:
            fields.append({
                "name": "💎 獲得利息",
                "value": "資料獲取中...",
                "inline": True
            })
            
        # 顯示歸還明細
        if returned_credits:
            return_details = []
            for credit in returned_credits[:5]:  # 增加到最多顯示5筆
                amount = abs(float(getattr(credit, 'amount', getattr(credit, 'amount_orig', 0))))
                rate = float(getattr(credit, 'rate', 0))
                period = getattr(credit, 'period', 'N/A')
                interest = float(getattr(credit, 'interest', 0))
                
                rate_annual = rate * 365
                # 計算實際收益率（利息/本金）
                actual_return = (interest / amount * 100) if amount > 0 else 0
                
                return_details.append(f"💰 {amount:.2f} @ {rate_annual:.2%} ({period}天) → 利息: {interest:.4f} ({actual_return:.3f}%)")
            
            if len(returned_credits) > 5:
                return_details.append(f"... 還有 {len(returned_credits)-5} 筆")
                
            fields.append({
                "name": "📋 歸還明細",
                "value": "\n".join(return_details),
                "inline": False
            })
        
        await self.send_message(title, description, color, fields, webhook_type="position")
    
    async def notify_new_lending_matched(self, new_credits: List, currency: str):
        """
        發送新放貸成交通知
        """
        if not new_credits:
            return
        
        # 區分一般訂單和機會性訂單
        regular_credits = []
        opportunistic_credits = []
        
        for credit in new_credits:
            if self._is_opportunistic_order(credit):
                opportunistic_credits.append(credit)
            else:
                regular_credits.append(credit)
        
        # 設定標題和顏色
        if opportunistic_credits and regular_credits:
            title = "🎉 放貸訂單成交 (混合)"
            description = f"{currency} 有一般和機會性訂單成交"
            color = 0x9966ff  # 紫色
        elif opportunistic_credits:
            title = "⚡ 機會性訂單成交"
            description = f"{currency} 機會性訂單被接受"
            color = 0xff6600  # 橙色
        else:
            title = "🎉 放貸訂單成交"
            description = f"{currency} 一般放貸訂單被接受"
            color = 0x0099ff  # 藍色
        
        total_matched = sum(abs(float(getattr(credit, 'amount', getattr(credit, 'amount_orig', 0)))) for credit in new_credits)
        
        fields = [
            {
                "name": "💰 成交金額",
                "value": f"{total_matched:.2f} {currency.replace('f', '')}",
                "inline": True
            },
            {
                "name": "📊 成交筆數", 
                "value": f"{len(new_credits)} 筆",
                "inline": True
            }
        ]
        
        # 顯示成交明細（每筆都明確標示類型）
        if new_credits:
            match_details = []
            
            for credit in new_credits[:5]:  # 最多顯示5筆
                amount = abs(float(getattr(credit, 'amount', getattr(credit, 'amount_orig', 0))))
                rate = float(getattr(credit, 'rate', 0))
                period = getattr(credit, 'period', 'N/A')
                rate_annual = rate * 365
                
                # 明確標示每筆訂單的類型
                if self._is_opportunistic_order(credit):
                    order_type = "⚡機會性"
                    icon = "⭐"
                else:
                    order_type = "🔹一般"
                    icon = "📈"
                
                match_details.append(f"{icon} [{order_type}] {amount:.2f} @ {rate_annual:.2%} ({period}天)")
            
            if len(new_credits) > 5:
                match_details.append(f"... 還有 {len(new_credits)-5} 筆")
                
            fields.append({
                "name": "📝 成交明細",
                "value": "\n".join(match_details),
                "inline": False
            })
        
        await self.send_message(title, description, color, fields, webhook_type="position")
    
    async def notify_funding_returned_simple(self, returned_count: int, currency: str, bfx_client=None):
        """
        發送資金歸還通知（嘗試從歷史記錄獲取詳細資訊）
        """
        if not returned_count:
            return
            
        title = "💰 放貸資金已歸還"
        description = f"{currency} 有 {returned_count} 筆放貸資金到期歸還"
        color = 0x00ff00  # 綠色
        
        fields = [
            {
                "name": "📊 歸還筆數",
                "value": f"{returned_count} 筆資金已歸還",
                "inline": True
            }
        ]
        
        # 嘗試從歷史帳本獲取歸還詳細資訊
        if bfx_client:
            try:
                print(f"[DEBUG] 嘗試獲取 {currency} 的歷史記錄...")
                # 獲取過去1小時的歷史記錄
                ledger_history = await bfx_client.get_funding_ledger_history(currency.replace('f', ''), 1)
                print(f"[DEBUG] 獲取到 {len(ledger_history) if ledger_history else 0} 筆歷史記錄")
                
                if ledger_history:
                    print(f"[DEBUG] 開始分析 {len(ledger_history)} 筆歷史記錄")
                    total_returned_amount = 0
                    total_interest = 0
                    return_details = []
                    
                    # 分析歷史記錄
                    for i, record in enumerate(ledger_history[:5]):  # 最多5筆
                        amount = abs(float(record.get('amount', 0)))
                        record_type = record.get('type', 'unknown')
                        
                        total_returned_amount += amount
                        
                        # 格式化時間
                        return_time = record.get('return_datetime')
                        time_str = return_time.strftime('%H:%M') if return_time else '未知'
                        
                        # 處理配對記錄（有時長資訊）
                        if record_type == 'paired_return':
                            duration_hours = record.get('duration_hours', 0)
                            duration_days = record.get('duration_days', 0)
                            start_time = record.get('start_datetime')
                            
                            # 格式化時長顯示
                            if duration_days > 0:
                                if duration_hours % 24 < 1:
                                    duration_str = f"{duration_days}天"
                                else:
                                    duration_str = f"{duration_days}天{duration_hours % 24:.1f}小時"
                            elif duration_hours >= 1:
                                duration_str = f"{duration_hours:.1f}小時"
                            else:
                                duration_str = f"{duration_hours * 60:.0f}分鐘"
                            
                            # 計算利息（總金額中的利息部分）
                            if start_time and return_time:
                                principal_estimate = amount * 0.9  # 估計90%為本金
                                interest_estimate = amount * 0.1   # 估計10%為利息
                                total_interest += interest_estimate
                                
                                start_str = start_time.strftime('%m/%d %H:%M')
                                return_details.append(f"💰 ${amount:.2f} ({start_str}→{time_str}) 🕐 {duration_str}")
                            else:
                                return_details.append(f"💰 ${amount:.2f} ({time_str}) 🕐 {duration_str}")
                        
                        # 處理未配對記錄
                        else:
                            return_details.append(f"💰 ${amount:.2f} ({time_str}) 🕐 時長計算中...")
                    
                    if total_returned_amount > 0:
                        fields.extend([
                            {
                                "name": "💵 歸還總額",
                                "value": f"{total_returned_amount:.2f} {currency.replace('f', '')}",
                                "inline": True
                            },
                            {
                                "name": "💎 利息收入",
                                "value": f"{total_interest:.4f} {currency.replace('f', '')}" if total_interest > 0 else "估算中...",
                                "inline": True
                            }
                        ])
                        
                        if return_details:
                            fields.append({
                                "name": "📋 詳細記錄",
                                "value": "\n".join(return_details),
                                "inline": False
                            })
                
            except Exception as e:
                print(f"[ERROR] 獲取歷史記錄失敗: {e}")
                import traceback
                traceback.print_exc()
                fields.append({
                    "name": "📝 詳細資訊",
                    "value": f"歷史資料獲取失敗: {str(e)[:50]}...",
                    "inline": False
                })
        else:
            print("[DEBUG] 未提供 bfx_client，無法獲取詳細資訊")
            fields.append({
                "name": "📝 詳細資訊", 
                "value": "未提供 API 客戶端，無法獲取歷史詳細資訊",
                "inline": False
            })
        
        fields.append({
            "name": "💡 提醒",
            "value": "資金已回到可用餘額，可重新進行放貸",
            "inline": False
        })
        
        await self.send_message(title, description, color, fields, webhook_type="position")
    
    async def notify_offer_changes_simple(self, new_count: int, cancelled_count: int, currency: str):
        """
        發送掛單變動通知
        """
        if not new_count and not cancelled_count:
            return
            
        title = "📋 掛單狀態變動"
        description = f"{currency} 掛單狀態已更新"
        color = 0xffa500  # 橘色
        
        fields = []
        
        if new_count > 0:
            fields.append({
                "name": "➕ 新增掛單",
                "value": f"{new_count} 筆",
                "inline": True
            })
        
        if cancelled_count > 0:
            fields.append({
                "name": "➖ 取消掛單",
                "value": f"{cancelled_count} 筆",
                "inline": True
            })
            
        await self.send_message(title, description, color, fields, webhook_type="position")
    
    async def notify_order_changes_simple(self, new_count: int, cancelled_count: int, currency: str):
        """
        發送簡化的訂單變動通知（避免資料結構問題）
        """
        if not new_count and not cancelled_count:
            return
            
        title = "🔄 訂單變動通知"
        description = f"{currency} 訂單已更新"
        color = 0xffa500  # 橘色
        
        fields = []
        
        if new_count > 0:
            fields.append({
                "name": "✅ 新增訂單",
                "value": f"成功新增 {new_count} 筆訂單",
                "inline": True
            })
        
        if cancelled_count > 0:
            fields.append({
                "name": "❌ 取消訂單",
                "value": f"取消了 {cancelled_count} 筆訂單",
                "inline": True
            })
            
        await self.send_message(title, description, color, fields, webhook_type="position")
    
    async def notify_opportunity(self, opportunity: Dict, currency: str):
        """
        發送機會性訂單通知
        """
        title = "⚡ 發現高利率機會"
        description = f"{currency} 檢測到優質放貸機會"
        
        market_annual = opportunity['market_rate'] * 365
        improvement_annual = opportunity['rate_improvement'] * 365
        
        fields = [
            {
                "name": "💎 機會詳情",
                "value": f"期限: {opportunity['borrower_days']}天\n利率: {market_annual:.2%} 年化\n提升: +{improvement_annual:.2%}",
                "inline": True
            },
            {
                "name": "📈 市場狀況", 
                "value": f"需求金額: {opportunity['market_amount']:.0f}\n借貸者數: {opportunity['count']}",
                "inline": True
            }
        ]
        
        await self.send_message(title, description, 0xff6600, fields, webhook_type="position")

# 全局通知器實例 - 延遲初始化
discord_notifier = None

def get_discord_notifier():
    """獲取Discord通知器實例，延遲初始化確保環境變數已載入"""
    global discord_notifier
    if discord_notifier is None:
        # 再次確保環境變數已載入
        load_dotenv()
        discord_notifier = DiscordNotifier()
    return discord_notifier

# 保持向後兼容，直接初始化
discord_notifier = get_discord_notifier()