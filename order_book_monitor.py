"""
訂單簿監控模組
監控 Bitfinex 放貸訂單簿，分析借貸者需求，動態調整訂單
使用 bitfinex.py 的基礎 API
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import config


class OrderBookMonitor:
    def __init__(self, bfx=None):
        self.bfx = bfx  # Bitfinex API 實例
        self.last_order_time = {}  # 記錄各期限的最後下單時間
        self.protected_orders = {}  # 受保護的訂單
        self.tracked_borrowers = {}  # 追蹤借貸者ID和條件變化
    
    def set_bitfinex_client(self, bfx_client):
        """設定 Bitfinex 客戶端"""
        self.bfx = bfx_client
    
    async def get_funding_book(self, currency: str = "fUSD", pages: int = 5) -> Dict[str, Any]:
        """
        獲取放貸訂單簿 - 使用 bitfinex.py 的基礎 API
        
        Args:
            currency: 幣別 (如 fUSD)
            pages: 獲取頁數 (預設5頁)
        
        Returns:
            Dict: 訂單簿資料，包含借貸方需求和借貸ID
        """
        if not self.bfx:
            print("錯誤: 未提供 Bitfinex API 實例")
            return {}
        
        try:
            # 使用 bitfinex.py 的統一 API 方法 - 修正為正確的貨幣代碼
            if currency == "fUSD":
                api_currency = "fUSD"  # 使用正確的 USD 融資代碼
            else:
                api_currency = currency  # 其他貨幣直接使用
            
            print(f"正在獲取 {api_currency} 的訂單簿資料...")
            all_data = await self.bfx.get_funding_book_data(api_currency, pages)
            
            if all_data:
                print(f"總共獲取 {len(all_data)} 筆訂單簿記錄")
                return await self._parse_funding_book_async(all_data)
            else:
                print("未獲取到任何訂單簿資料")
                return {}
            
        except Exception as e:
            print(f"訂單簿 API請求錯誤: {e}")
            return {}
    
    
    async def _parse_funding_book_async(self, raw_data: List) -> Dict[str, Any]:
        """
        非同步解析放貸訂單簿資料 - 專注於借貸方需求
        
        Funding Book 格式: [Rate, Period, Count, Amount]
        - Rate: 利率
        - Period: 期限(天)
        - Count: 訂單數量  
        - Amount: 總金額 (負數=借貸方需求)
        """
        borrowers = []  # 只關注借貸方需求
        
        for entry in raw_data:
            if len(entry) >= 4:
                rate, period, count, amount = entry[0], entry[1], entry[2], entry[3]
                
                # 只處理借貸方需求 (負數金額)
                if amount < 0:
                    rate_val = float(rate)
                    period_val = int(period)
                    amount_val = abs(float(amount))
                    
                    # 只做基本的數據類型驗證，不過濾利率範圍
                    if period_val <= 0 or amount_val <= 0:
                        continue
                    
                    borrower_info = {
                        'rate': rate_val,
                        'period': period_val,
                        'count': int(count),
                        'amount': amount_val,
                        'borrower_id': f"{rate_val}_{period_val}_{count}",  # 生成借貸ID
                        'annual_rate': rate_val * 365,  # 年化利率
                        'priority_score': self._calculate_borrower_priority(rate_val, period_val, amount_val)
                    }
                    borrowers.append(borrower_info)
        
        # 按優先級排序 - 利率高的優先
        borrowers.sort(key=lambda x: x['priority_score'], reverse=True)
        
        # 調試：檢查前幾個借貸者的數據
        if borrowers:
            print(f"前3個借貸者數據檢查:")
            for i, b in enumerate(borrowers[:3]):
                print(f"  {i+1}. 利率: {b['rate']:.6f} ({b['annual_rate']:.2%}), "
                      f"期限: {b['period']}天, 金額: {b['amount']:.2f}")
        
        return {
            'borrowers': borrowers,
            'timestamp': datetime.now(),
            'total_demand': sum(b['amount'] for b in borrowers)
        }
    
    def _calculate_borrower_priority(self, rate: float, period: int, amount: float) -> float:
        """
        計算借貸方的優先級分數
        主要考慮：利率(權重最高)、金額大小、期限適合度
        """
        # 利率權重 80%
        rate_score = rate * 1000 * 0.8
        
        # 金額權重 15% (大額更有吸引力但避免過度集中)
        amount_score = min(amount / config.AMOUNT_FACTOR_DIVISOR, config.AMOUNT_FACTOR_MAX) * 0.15
        
        # 期限適合度 5% (中短期更靈活)
        period_score = max(0, (120 - period) / config.PERIOD_FACTOR_DIVISOR) * 0.05
        
        return rate_score + amount_score + period_score
    
    def _parse_funding_book(self, raw_data: List) -> Dict[str, Any]:
        """
        解析放貸訂單簿資料
        
        Funding Book 格式: [Rate, Period, Count, Amount]
        - Rate: 利率
        - Period: 期限(天)
        - Count: 訂單數量
        - Amount: 總金額 (正數=放貸方, 負數=借貸方)
        """
        lenders = []  # 放貸方 (正數)
        borrowers = []  # 借貸方 (負數)
        
        for entry in raw_data:
            if len(entry) >= 4:
                rate, period, count, amount = entry[0], entry[1], entry[2], entry[3]
                
                order_info = {
                    'rate': float(rate),
                    'period': int(period),
                    'count': int(count),
                    'amount': abs(float(amount))
                }
                
                if amount > 0:
                    lenders.append(order_info)
                else:
                    borrowers.append(order_info)
        
        return {
            'lenders': lenders,
            'borrowers': borrowers,
            'timestamp': datetime.now()
        }
    
    async def analyze_borrower_demand(self, book_data: Dict[str, Any], current_orders: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        分析借貸者需求，找出比一般模組訂單更好的機會
        
        Args:
            book_data: 訂單簿資料(已按優先級排序)
            current_orders: 目前的常規訂單列表
        
        Returns:
            List: 符合條件且比常規訂單更好的借貸需求
        """
        if 'borrowers' not in book_data:
            return []
        
        opportunities = []
        borrowers = book_data['borrowers']  # 已按優先級排序
        
        # 獲取常規模組的最高利率作為比較基準
        current_max_rate = 0.0
        if current_orders:
            current_max_rate = max(order.get('rate', 0.0) for order in current_orders)
        
        # 分析每個借貸者的需求 (增強調試輸出)
        debug_count = 0
        total_analyzed = 0
        skipped_tracked = 0
        no_match_config = 0
        below_threshold = 0
        
        print(f"開始分析 {len(borrowers)} 個借貸者需求...")
        print(f"當前配置有 {len(config.INTEREST_RATE_DAYS)} 個利率區間")
        
        for borrower in borrowers:
            borrower_rate = borrower['rate']
            borrower_days = borrower['period']
            borrower_id = borrower['borrower_id']
            total_analyzed += 1
            
            # 檢查是否已經追蹤此借貸ID
            if borrower_id in self.tracked_borrowers:
                previous_data = self.tracked_borrowers[borrower_id]
                # 如果借貸條件沒有改善，跳過
                if borrower_rate <= previous_data.get('rate', 0):
                    skipped_tracked += 1
                    continue
            
            # 查找適合的配置
            best_match = None
            for target in config.INTEREST_RATE_DAYS:
                if borrower_rate >= target['rate'] and borrower_days <= target['days']:
                    if best_match is None or target['rate'] > best_match['rate']:
                        best_match = target
            
            if not best_match:
                no_match_config += 1
            
            # 調試：只顯示前3個分析結果
            if debug_count < 3:
                print(f"調試 - 借貸者 {debug_count+1}: 利率 {borrower_rate:.8f} ({borrower_rate*365:.2%}), "
                      f"期限 {borrower_days}天, 常規最高利率: {current_max_rate:.8f} ({current_max_rate*365:.2%})")
                debug_count += 1
            
            # 降低比較門檻，讓更多機會被發現
            rate_threshold = current_max_rate * 1.00005  # 降低至 0.005% (原本是 0.01%)
            
            # 如果沒有常規訂單，則使用最低利率作為基準
            if not current_orders:
                rate_threshold = config.MINIMUM_RATE
            
            if not (best_match and borrower_rate > rate_threshold):
                below_threshold += 1
            
            if best_match and borrower_rate > rate_threshold:
                opportunity = {
                    'borrower_id': borrower_id,
                    'target_rate': best_match['rate'],
                    'max_days': best_match['days'],
                    'borrower_days': borrower_days,
                    'market_rate': borrower_rate,
                    'market_amount': borrower['amount'],
                    'count': borrower['count'],
                    'profit_margin': borrower_rate - current_max_rate,
                    'annual_return': borrower_rate * 365,
                    'priority_score': borrower['priority_score'],  # 使用預計算的分數
                    'rate_improvement': borrower_rate - current_max_rate
                }
                
                opportunities.append(opportunity)
                
                # 更新追蹤記錄
                self.tracked_borrowers[borrower_id] = {
                    'rate': borrower_rate,
                    'amount': borrower['amount'],
                    'last_seen': datetime.now()
                }
        
        # 輸出詳細的分析統計
        print(f"分析完成統計:")
        print(f"  總共分析: {total_analyzed} 個借貸者")
        print(f"  已追蹤跳過: {skipped_tracked}")
        print(f"  不符合配置: {no_match_config}")
        print(f"  低於門檻: {below_threshold}")
        print(f"  找到機會: {len(opportunities)}")
        
        if opportunities:
            print(f"機會詳情:")
            for i, opp in enumerate(opportunities[:3]):  # 只顯示前3個
                print(f"  {i+1}. {opp['borrower_days']}天 @ {opp['market_rate']*365:.2%} 年化")
        
        # 按優先級排序
        opportunities.sort(key=lambda x: x['priority_score'], reverse=True)
        return opportunities
    
    def _calculate_priority_score(self, borrower: Dict, target: Dict) -> float:
        """
        計算機會的優先級分數
        考慮因素: 利潤邊際、金額大小、期限、訂單數量
        """
        profit_margin = borrower['rate'] - target['rate']
        amount_factor = min(borrower['amount'] / config.AMOUNT_FACTOR_DIVISOR, config.AMOUNT_FACTOR_MAX)
        period_factor = 1.0 + (borrower['period'] / config.PERIOD_FACTOR_DIVISOR)
        liquidity_factor = min(borrower['count'] / config.LIQUIDITY_FACTOR_DIVISOR, config.LIQUIDITY_FACTOR_MAX)
        
        score = profit_margin * config.PRIORITY_MULTIPLIER + amount_factor + period_factor + liquidity_factor
        return score
    
    async def place_opportunistic_order(self, opportunity: Dict[str, Any], currency: str = "USD") -> bool:
        """
        下達機會性訂單
        """
        target_rate = opportunity['target_rate']
        borrower_days = opportunity['borrower_days']  # 使用借貸者實際需要的期限
        market_rate = opportunity['market_rate']
        
        # 檢查是否在保護期內
        order_key = f"{currency}_{borrower_days}"
        if self._is_order_protected(order_key):
            print(f"訂單受保護期限制: {borrower_days}天期限")
            return False
        
        # 計算下單利率 (略低於市場需求以確保搓合)
        optimal_rate = market_rate * config.OPPORTUNISTIC_RATE_DISCOUNT
        optimal_rate = max(optimal_rate, target_rate)  # 不低於目標利率
        
        # 計算可用資金
        available_funds = await self._get_available_funds(currency)
        
        # 如果資金不足，取消最差的常規訂單來騰出資金
        cancelled_order_id = None
        if available_funds < config.MINIMUM_FUNDS:
            cancelled_order_id = await self._cancel_worst_regular_order(currency, market_rate)
            if cancelled_order_id:
                # 等待資金釋放
                await asyncio.sleep(2)
                available_funds = await self._get_available_funds(currency)
                print(f"已取消低利率訂單，騰出資金: {available_funds:.2f}")
        
        if available_funds < config.MINIMUM_FUNDS:
            print(f"即使取消低利率訂單，資金仍不足: {available_funds:.2f} < {config.MINIMUM_FUNDS}")
            return False
        
        # 限制單筆訂單最大金額
        max_single_order = min(
            available_funds * config.MAX_SINGLE_ORDER_RATIO, 
            opportunity['market_amount'] * config.MARKET_AMOUNT_RATIO
        )
        order_amount = int(max(config.MINIMUM_FUNDS, max_single_order))  # 轉為整數
        
        print(f"發現機會性訂單機會:")
        print(f"   期限: {borrower_days}天")
        print(f"   目標利率: {target_rate*365:.2%} (年化)")
        print(f"   市場需求: {market_rate*365:.2%} (年化)")
        print(f"   下單利率: {optimal_rate*365:.2%} (年化)")
        print(f"   下單金額: ${order_amount:,}")
        
        # 執行下單 (這裡需要整合到主要的下單系統)
        success = await self._execute_funding_order(
            currency=currency,
            rate=optimal_rate,
            amount=order_amount,
            period=borrower_days
        )
        
        if success:
            # 記錄下單時間，啟動保護機制
            self.last_order_time[order_key] = datetime.now()
            self.protected_orders[order_key] = datetime.now() + timedelta(minutes=config.ORDER_PROTECTION_MINUTES)
            
            # 標記為機會性訂單
            from discord_notifier import discord_notifier
            discord_notifier.mark_as_opportunistic_order(optimal_rate, borrower_days, order_amount)
            
            print(f"機會性訂單下單成功")
            return True
        else:
            print(f"機會性訂單下單失敗")
            return False
    
    def _is_order_protected(self, order_key: str) -> bool:
        """檢查訂單是否在保護期內"""
        if order_key not in self.protected_orders:
            return False
        
        return datetime.now() < self.protected_orders[order_key]
    
    async def _get_available_funds(self, currency: str) -> float:
        """獲取可用資金 - 使用 bitfinex.py 的基礎 API"""
        try:
            if not self.bfx:
                print("Bitfinex 客戶端未設定")
                return 0.0
                
            # 使用 common.py 中的方法 (它已經使用 bitfinex.py 的 API)
            import common
            available_funds = await common.get_available_lending_funds(self.bfx, currency, config)
            return available_funds
        except Exception as e:
            print(f"獲取可用資金錯誤: {e}")
            return 0.0
    
    async def _execute_funding_order(self, currency: str, rate: float, amount: float, period: int) -> bool:
        """執行放貸訂單 - 使用 bitfinex.py 的基礎 API"""
        try:
            if not self.bfx:
                print("Bitfinex 客戶端未設定")
                return False
                
            order = {
                'rate': rate,
                'amount': amount,
                'period': period
            }
            
            result = await self.bfx.submit_order(order, f"f{currency}")
            if result:
                print(f"機會性訂單提交成功: {currency} {rate:.6f} ${int(amount)} {period}天")
                return True
            else:
                print(f"機會性訂單提交失敗")
                return False
        except Exception as e:
            print(f"下單錯誤: {e}")
            return False
    
    def cleanup_protected_orders(self):
        """清理過期的保護訂單"""
        current_time = datetime.now()
        expired_keys = [
            key for key, expire_time in self.protected_orders.items()
            if current_time >= expire_time
        ]
        
        for key in expired_keys:
            del self.protected_orders[key]
    
    def cleanup_expired_borrowers(self):
        """清理過期的借貸者追蹤記錄 (超過1小時)"""
        current_time = datetime.now()
        expired_keys = [
            borrower_id for borrower_id, data in self.tracked_borrowers.items()
            if current_time - data.get('last_seen', current_time) > timedelta(hours=1)
        ]
        
        for key in expired_keys:
            del self.tracked_borrowers[key]
    
    async def _cancel_worst_regular_order(self, currency: str, target_rate: float) -> Optional[str]:
        """
        取消利率最低的常規訂單，為機會性訂單騰出資金
        使用 bitfinex.py 的基礎 API
        
        Args:
            currency: 幣種
            target_rate: 機會性訂單的目標利率
            
        Returns:
            str: 被取消的訂單ID，若無適合訂單則返回None
        """
        try:
            # 獲取當前所有訂單
            current_offers = await self.bfx.get_funding_offers(f"f{currency}")
            if not current_offers:
                return None
            
            # 過濾出未受保護的常規訂單
            regular_orders = []
            for offer in current_offers:
                period = getattr(offer, 'period', 0)
                rate = getattr(offer, 'rate', 0)
                order_key = f"{currency}_{period}"
                # 只考慮未受保護且利率低於機會性訂單的常規訂單
                if not self._is_order_protected(order_key) and float(rate) < target_rate:
                    regular_orders.append({
                        'id': getattr(offer, 'id', ''),
                        'rate': float(rate),
                        'amount': abs(float(getattr(offer, 'amount', 0))),
                        'period': int(period)
                    })
            
            if not regular_orders:
                print("沒有可取消的低利率常規訂單")
                return None
            
            # 找出利率最低的訂單
            worst_order = min(regular_orders, key=lambda x: x['rate'])
            
            # 取消訂單
            import common
            success = await common.cancel_order(self.bfx, worst_order['id'])
            
            if success:
                print(f"取消低利率訂單: {worst_order['period']}天 @ {worst_order['rate']*365:.2%} 年化, "
                      f"金額: {int(worst_order['amount'])}")
                return worst_order['id']
            else:
                print("取消訂單失敗")
                return None
                
        except Exception as e:
            print(f"取消最差訂單時發生錯誤: {e}")
            return None
    
    async def monitor_and_act(self, currency: str = "fUSD", current_orders: List[Dict] = None) -> bool:
        """
        監控並執行機會性訂單的主要方法
        
        Args:
            currency: 幣種
            current_orders: 當前常規訂單列表
            
        Returns:
            bool: 是否有執行訂單
        """
        try:
            # 清理過期的保護訂單和追蹤記錄
            self.cleanup_protected_orders()
            self.cleanup_expired_borrowers()
            
            # 獲取訂單簿
            book_data = await self.get_funding_book(currency)
            if not book_data:
                return False
            
            borrower_count = len(book_data.get('borrowers', []))
            total_demand = book_data.get('total_demand', 0)
            
            print(f"訂單簿分析 - 借貸方: {borrower_count}, 總需求: {total_demand:.2f}")
            
            # 分析機會（只考慮比常規訂單更好的）
            opportunities = await self.analyze_borrower_demand(book_data, current_orders)
            
            # 提供更詳細的分析信息
            current_max_rate = 0.0
            if current_orders:
                current_max_rate = max(order.get('rate', 0.0) for order in current_orders)
            
            print(f"發現 {len(opportunities)} 個符合條件的機會")
            if current_orders:
                print(f"當前常規訂單最高利率: {current_max_rate*365:.2%} 年化")
            
            if not opportunities:
                print("暫無符合條件的機會性訂單")
                return False
            
            # 執行最優機會 (每次只執行一個)
            best_opportunity = opportunities[0]
            
            # 安全的年化利率計算和顯示
            market_annual = best_opportunity['market_rate'] * 365
            improvement_annual = best_opportunity['rate_improvement'] * 365
            
            # 防止異常數據顯示
            if market_annual > 10:  # 超過1000%認為異常
                market_annual_str = f"{market_annual:.6f} (異常數據)"
            else:
                market_annual_str = f"{market_annual:.2%}"
                
            if improvement_annual > 10:  # 超過1000%認為異常  
                improvement_annual_str = f"{improvement_annual:.6f} (異常數據)"
            else:
                improvement_annual_str = f"{improvement_annual:.2%}"
            
            print(f"最佳機會: {best_opportunity['borrower_days']}天 @ {market_annual_str} 年化")
            print(f"預期提升: {improvement_annual_str}")
            print(f"原始利率: {best_opportunity['market_rate']:.8f}")
            
            success = await self.place_opportunistic_order(best_opportunity, currency.replace('f', ''))
            
            # 只在確實執行成功且利率提升顯著時才發送通知
            if success and best_opportunity['rate_improvement'] * 365 > 0.05:  # 提升超過5%才通知
                from discord_notifier import discord_notifier
                await discord_notifier.notify_opportunity(best_opportunity, currency)
            
            return success
            
        except Exception as e:
            print(f"訂單簿監控錯誤: {e}")
            return False


async def test_order_book_monitor():
    """測試訂單簿監控功能"""
    print("=== 測試訂單簿監控模組 ===")
    
    # 需要 Bitfinex 客戶端進行測試
    from bitfinex import Bitfinex
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("BF_API_KEY")
    api_secret = os.getenv("BF_API_SECRET")
    
    if not api_key or not api_secret:
        print("缺少 API 金鑰，跳過測試")
        return
    
    bfx = Bitfinex(api_key, api_secret)
    monitor = OrderBookMonitor(bfx)
    
    # 測試獲取訂單簿
    book_data = await monitor.get_funding_book("fUSD")
    if book_data:
        print(f"訂單簿獲取成功")
        print(f"   借貸方數量: {len(book_data.get('borrowers', []))}")
        
        # 測試需求分析
        opportunities = await monitor.analyze_borrower_demand(book_data)
        print(f"   發現機會: {len(opportunities)} 個")
        
        if opportunities:
            best = opportunities[0]
            print(f"   最佳機會: {best['borrower_days']}天 @ {best['market_rate']*365:.2%}")
    else:
        print("訂單簿獲取失敗")
    
    # 關閉 HTTP session
    await bfx.close_http_session()


if __name__ == "__main__":
    asyncio.run(test_order_book_monitor())