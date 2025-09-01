#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
放貸狀態監控模組
監控 funding credits 的變化，檢測資金歸還和新放貸成交
"""
from typing import List, Dict, Set, Tuple
from datetime import datetime
from discord_notifier import discord_notifier

class LendingMonitor:
    def __init__(self):
        self.previous_credits = {}  # currency -> set of credit IDs
        self.previous_offers = {}   # currency -> set of offer IDs
        self.last_check_time = {}
        
    def _get_credit_id(self, credit) -> str:
        """生成 funding credit 的唯一ID (使用 bitfinex.py 的統一方法)"""
        from bitfinex import Bitfinex
        return Bitfinex.get_credit_unique_id(credit)
    
    def _get_offer_id(self, offer) -> str:
        """生成 funding offer 的唯一ID (使用 bitfinex.py 的統一方法)"""
        from bitfinex import Bitfinex
        return Bitfinex.get_offer_unique_id(offer)
    
    async def check_lending_changes(self, bfx, currency: str):
        """
        檢查放貸狀態變化並發送通知
        
        Args:
            bfx: Bitfinex 客戶端
            currency: 幣種
        """
        try:
            # 獲取當前的 funding credits 和 offers
            current_credits = await bfx.get_funding_credits(currency)
            current_offers = await bfx.get_funding_offers(currency)
            
            # 生成當前狀態的 ID 集合
            current_credit_ids = {self._get_credit_id(credit) for credit in current_credits}
            current_offer_ids = {self._get_offer_id(offer) for offer in current_offers}
            
            # 獲取上次的狀態
            previous_credit_ids = self.previous_credits.get(currency, set())
            previous_offer_ids = self.previous_offers.get(currency, set())
            
            # 如果是首次檢查，只記錄狀態，不發送通知
            if currency not in self.previous_credits:
                self.previous_credits[currency] = current_credit_ids
                self.previous_offers[currency] = current_offer_ids
                self.last_check_time[currency] = datetime.now()
                return
            
            # 檢測 funding credits 變化
            returned_credit_ids = previous_credit_ids - current_credit_ids  # 消失的credits（歸還）
            new_credit_ids = current_credit_ids - previous_credit_ids      # 新增的credits（成交）
            
            # 檢測 funding offers 變化
            cancelled_offer_ids = previous_offer_ids - current_offer_ids    # 消失的offers
            new_offer_ids = current_offer_ids - previous_offer_ids         # 新增的offers
            
            # 發送歸還通知
            if returned_credit_ids:
                # 嘗試從上一次的狀態重建歸還的credits資訊
                # 注意：由於credit已經消失，我們只能推估資訊
                await discord_notifier.notify_funding_returned_simple(
                    len(returned_credit_ids), currency, bfx)
            
            # 發送新放貸成交通知
            if new_credit_ids:
                new_credits = [credit for credit in current_credits 
                             if self._get_credit_id(credit) in new_credit_ids]
                await discord_notifier.notify_new_lending_matched(new_credits, currency)
            
            # 不發送掛單變動通知，避免訊息過多
            # 掛單變動是策略正常調整，不需要特別通知
            
            # 更新狀態
            self.previous_credits[currency] = current_credit_ids
            self.previous_offers[currency] = current_offer_ids
            self.last_check_time[currency] = datetime.now()
            
        except Exception as e:
            print(f"檢查放貸狀態變化時發生錯誤: {e}")
    
    async def get_current_status(self, bfx, currency: str) -> Dict:
        """獲取當前放貸狀態摘要"""
        try:
            credits = await bfx.get_funding_credits(currency)
            offers = await bfx.get_funding_offers(currency)
            
            total_lending = sum(abs(float(getattr(credit, 'amount', 
                                    getattr(credit, 'amount_orig', 0)))) for credit in credits)
            total_offered = sum(abs(float(offer.amount)) for offer in offers)
            
            return {
                'credits_count': len(credits),
                'offers_count': len(offers),
                'total_lending': total_lending,
                'total_offered': total_offered,
                'credits': credits,
                'offers': offers
            }
        except Exception as e:
            print(f"獲取放貸狀態時發生錯誤: {e}")
            return {}

# 全局監控實例
lending_monitor = LendingMonitor()