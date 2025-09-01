import pandas as pd
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from bfxapi import Client
from bfxapi.types import (
    DepositAddress,
    LightningNetworkInvoice,
    Notification,
    Transfer,
    Wallet,
    Withdrawal,
    FundingOffer,
)
import config

class Bitfinex():
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = Client(api_key=self.api_key, api_secret=self.api_secret)
        self._http_session = None
        
    async def get_wallets(self):
        try:
            return self.client.rest.auth.get_wallets()
        except BaseException as err:            
            raise Exception(f"An error occurred in function {__name__}: {err}")

    """獲取融資可用資金"""
    async def get_balance(self, currency):
        try:
            wallets: List[Wallet] = self.client.rest.auth.get_wallets()
            for wallet in wallets:
                if wallet.wallet_type == "funding" and wallet.currency == currency:
                    return wallet.available_balance
            return 0
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0
        
    """ 移除我的所有報價 """
    async def remove_all_lending_offer(self, currency):
        try:
            return self.client.rest.auth.cancel_all_funding_offers(currency)
        except Exception as e:
            print(f"Error removing lending offers: {e}")
            return None         
        
    """ 獲取我的所有報價 """
    async def get_funding_offers(self, currency):
        try:
            return self.client.rest.auth.get_funding_offers(symbol=currency)
        except Exception as e:
            print(f"Error getting lending offers: {e}")
            return []              

    """ 獲取放貸中的訂單 (正在賺取利息) """
    async def get_funding_credits(self, currency):
        try:
            return self.client.rest.auth.get_funding_credits(symbol=currency)
        except Exception as e:
            print(f"Error getting funding credits: {e}")
            return []

    """ 提交訂單報價 """
    async def submit_order(self, order, currency):
        try:
            notification: Notification[FundingOffer] = self.client.rest.auth.submit_funding_offer(
                type="LIMIT", symbol=currency, amount=str(order['amount']), rate=order['rate'], period=order['period']
            )
            return True
        except Exception as e:
            print(f"Error submitting funding offer: {e}")
            return False            

    """ 取消特定訂單 """
    async def cancel_order(self, orderid):
        try:
            return self.client.rest.auth.cancel_funding_offer(orderid)
        except Exception as e:
            print(f"Error submitting funding offer: {e}")
            return False   

    """ 更新特定訂單 """
    async def update_order(self, orderid):
        try:
            return self.client.rest.auth.update_order(orderid)
        except Exception as e:
            print(f"Error submitting funding offer: {e}")
            return False
    
    """ 獲取放貸歷史帳本記錄 """
    async def get_funding_ledger_history(self, currency: str, hours: int = 24):
        """
        獲取過去N小時的放貸相關歷史記錄，包含時長計算
        
        Args:
            currency: 幣別 (如 USD)
            hours: 回溯小時數
            
        Returns:
            List: 放貸相關的歷史帳本記錄，包含配對的開始結束時間
        """
        try:
            from datetime import datetime, timedelta
            
            # 計算時間範圍 (擴大搜索範圍以找到配對記錄)
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours * 3)  # 擴大3倍搜索範圍
            
            # 轉換為毫秒時間戳記
            start_ts = int(start_time.timestamp() * 1000)
            end_ts = int(end_time.timestamp() * 1000)
            
            # 獲取帳本歷史
            ledger_data = self.client.rest.auth.get_ledgers(
                currency=currency,
                start=str(start_ts),
                end=str(end_ts),
                limit=200  # 增加限制以獲取更多記錄
            )
            
            # 分析所有放貸相關記錄
            funding_records = []
            for record in ledger_data:
                description = str(getattr(record, 'description', ''))
                amount = getattr(record, 'amount', 0)
                timestamp = getattr(record, 'mts', 0)
                
                record_info = {
                    'amount': amount,
                    'balance': getattr(record, 'balance', 0), 
                    'description': description,
                    'timestamp': timestamp,
                    'currency': getattr(record, 'currency', currency),
                    'datetime': datetime.fromtimestamp(timestamp / 1000) if timestamp else None
                }
                
                # 分類不同類型的放貸記錄
                if 'funding payment' in description.lower():
                    if amount > 0:
                        record_info['type'] = 'return'  # 歸還 (正數)
                    else:
                        record_info['type'] = 'start'   # 開始 (負數)
                elif 'funding' in description.lower():
                    record_info['type'] = 'funding_related'
                else:
                    continue
                    
                funding_records.append(record_info)
            
            # 按時間排序
            funding_records.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # 嘗試配對歸還與開始記錄
            paired_records = []
            for i, return_record in enumerate(funding_records):
                if return_record['type'] == 'return':
                    # 尋找對應的開始記錄（同等金額但為負數）
                    target_amount = -abs(return_record['amount'])
                    
                    for j, start_record in enumerate(funding_records[i+1:], i+1):
                        if (start_record['type'] == 'start' and 
                            abs(start_record['amount'] - target_amount) < 0.01):  # 允許小誤差
                            
                            # 計算時長
                            if return_record['datetime'] and start_record['datetime']:
                                duration = return_record['datetime'] - start_record['datetime']
                                duration_hours = duration.total_seconds() / 3600
                                duration_days = duration.days
                                
                                paired_record = {
                                    'amount': return_record['amount'],
                                    'description': return_record['description'],
                                    'return_timestamp': return_record['timestamp'],
                                    'start_timestamp': start_record['timestamp'],
                                    'return_datetime': return_record['datetime'],
                                    'start_datetime': start_record['datetime'],
                                    'duration_hours': duration_hours,
                                    'duration_days': duration_days,
                                    'currency': currency,
                                    'type': 'paired_return'
                                }
                                paired_records.append(paired_record)
                                break
                    else:
                        # 如果找不到配對，仍然記錄歸還記錄
                        unpaired_record = {
                            'amount': return_record['amount'],
                            'description': return_record['description'],
                            'return_timestamp': return_record['timestamp'],
                            'return_datetime': return_record['datetime'],
                            'currency': currency,
                            'type': 'unpaired_return'
                        }
                        paired_records.append(unpaired_record)
            
            return paired_records
            
        except Exception as e:
            print(f"獲取放貸歷史記錄失敗: {e}")
            return []
    
    # ===== 新增：統一的 HTTP 請求方法 =====
    
    async def _get_http_session(self):
        """獲取共用的 HTTP session"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session
    
    async def close_http_session(self):
        """關閉 HTTP session"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
    
    async def _make_public_api_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """
        統一的公開 API 請求方法
        
        Args:
            endpoint: API 端點 (如 '/v2/funding/stats/fUSD/hist')
            params: 查詢參數
            
        Returns:
            API 回應的 JSON 資料
        """
        url = f"{config.BITFINEX_PUBLIC_API_URL}{endpoint}"
        session = await self._get_http_session()
        
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            print(f"Public API 請求失敗 {endpoint}: {e}")
            return None
    
    # ===== 新增：Bitfinex 公開 API 方法 =====
    
    async def get_funding_stats(self, currency: str = 'fUSD') -> Optional[List]:
        """獲取融資統計資料 (用於市場情緒分析)"""
        endpoint = f"/v2/funding/stats/{currency}/hist"
        return await self._make_public_api_request(endpoint)
    
    async def get_funding_book_data(self, currency: str = 'fUST', pages: int = 5) -> List[Dict]:
        """獲取融資訂單簿資料"""
        all_data = []
        for page in range(pages):
            endpoint = f"/v2/book/{currency}/P{page}"
            params = {'len': 250}
            page_data = await self._make_public_api_request(endpoint, params)
            if page_data:
                all_data.extend(page_data)
        return all_data
    
    async def get_candle_data(self, symbol: str = 'fUSD', timeframe: str = '1h', 
                            params: str = 'a30:p2:p30', limit: int = None) -> Optional[List]:
        """獲取K線資料 (用於利率分析)"""
        endpoint = f"/v2/candles/trade:{timeframe}:{symbol}:{params}/hist"
        query_params = {}
        if limit:
            query_params['limit'] = limit
        return await self._make_public_api_request(endpoint, query_params)
    
    # ===== 新增：統一的資料轉換方法 =====
    
    @staticmethod
    def normalize_funding_offer(offer) -> Dict[str, Any]:
        """
        統一轉換 funding offer 為標準字典格式
        
        Args:
            offer: funding offer 物件
            
        Returns:
            標準化的訂單字典
        """
        try:
            return {
                'id': str(getattr(offer, 'id', '')),
                'rate': float(getattr(offer, 'rate', 0)),
                'amount': abs(float(getattr(offer, 'amount', 0))),
                'period': int(getattr(offer, 'period', 0)),
                'type': getattr(offer, 'type', 'LIMIT'),
                'status': getattr(offer, 'status', 'ACTIVE'),
                'annual_rate': float(getattr(offer, 'rate', 0)) * 365
            }
        except Exception as e:
            print(f"Funding offer 轉換失敗: {e}")
            return {
                'id': '', 'rate': 0.0, 'amount': 0.0, 'period': 0, 
                'type': 'ERROR', 'status': 'ERROR', 'annual_rate': 0.0
            }
    
    @staticmethod 
    def normalize_funding_credit(credit) -> Dict[str, Any]:
        """
        統一轉換 funding credit 為標準字典格式
        
        Args:
            credit: funding credit 物件
            
        Returns:
            標準化的放貸字典
        """
        try:
            # 處理金額：優先使用 amount，備用 amount_orig
            amount = abs(float(getattr(credit, 'amount', getattr(credit, 'amount_orig', 0))))
            rate = float(getattr(credit, 'rate', 0))
            
            result = {
                'id': str(getattr(credit, 'id', '')),
                'rate': rate,
                'amount': amount,
                'period': int(getattr(credit, 'period', 0)),
                'status': getattr(credit, 'status', 'ACTIVE'),
                'annual_rate': rate * 365
            }
            
            # 添加時間資訊 (如果存在)
            for time_field in ['mts_create', 'mts_update', 'mts_opening', 'mts_last_payout']:
                value = getattr(credit, time_field, None)
                if value:
                    result[time_field] = value
            
            return result
            
        except Exception as e:
            print(f"Funding credit 轉換失敗: {e}")
            return {
                'id': '', 'rate': 0.0, 'amount': 0.0, 'period': 0, 
                'status': 'ERROR', 'annual_rate': 0.0
            }
    
    @staticmethod
    def generate_order_id(rate: float, period: int, amount: float) -> str:
        """
        生成統一的訂單 ID (用於追蹤和比較)
        
        Args:
            rate: 利率
            period: 期限
            amount: 金額
            
        Returns:
            訂單 ID 字串
        """
        try:
            return f"{rate:.6f}_{period}_{amount:.2f}"
        except Exception:
            return f"error_{period}_0"
    
    @staticmethod
    def get_credit_unique_id(credit) -> str:
        """
        生成 funding credit 的唯一 ID (用於狀態追蹤)
        
        Args:
            credit: funding credit 物件
            
        Returns:
            唯一 ID 字串
        """
        try:
            credit_id = getattr(credit, 'id', None)
            if credit_id:
                return str(credit_id)
            
            # 如果沒有 ID，用其他屬性組合
            amount = getattr(credit, 'amount', getattr(credit, 'amount_orig', 0))
            rate = getattr(credit, 'rate', 0)
            period = getattr(credit, 'period', 0)
            mts_create = getattr(credit, 'mts_create', '')
            
            return f"{amount}_{rate}_{period}_{mts_create}"
            
        except Exception:
            return f"unknown_{hash(str(credit))}"
    
    @staticmethod
    def get_offer_unique_id(offer) -> str:
        """
        生成 funding offer 的唯一 ID
        
        Args:
            offer: funding offer 物件
            
        Returns:
            唯一 ID 字串
        """
        try:
            offer_id = getattr(offer, 'id', None)
            if offer_id:
                return str(offer_id)
            
            return f"{offer.rate}_{offer.period}_{offer.amount}"
        except Exception:
            return f"unknown_{hash(str(offer))}"
    
