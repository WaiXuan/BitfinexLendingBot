import pandas as pd

from typing import List
from bfxapi import Client
from bfxapi.types import (
    DepositAddress,
    LightningNetworkInvoice,
    Notification,
    Transfer,
    Wallet,
    Withdrawal,
)

class Bitfinex():
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = Client(api_key=self.api_key, api_secret=self.api_secret)
        
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