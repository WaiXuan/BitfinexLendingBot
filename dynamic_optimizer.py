import math
import statistics
from typing import Dict, List, Tuple
import config

class DynamicOptimizer:
    """動態優化策略類別，提供高級利率優化功能"""
    
    def __init__(self):
        self.rate_history = []  # 存儲歷史利率用於計算波動度
        self.sentiment_history = []  # 存儲歷史情緒值
    
    def calculate_dynamic_safety_factor(self, sentiment: float, rate_volatility: float = None) -> float:
        """
        根據市場情緒和波動度動態計算安全係數
        
        Args:
            sentiment: 市場情緒值
            rate_volatility: 利率波動度 (可選)
            
        Returns:
            動態安全係數 (0.95-0.99)
        """
        base_factor = 0.97
        
        # 情緒調整: sentiment > 2.0 時更激進
        if sentiment > 3.0:
            emotion_adjustment = -0.02  # 更激進，係數降低
        elif sentiment > 2.0:
            emotion_adjustment = -0.015
        elif sentiment > 1.5:
            emotion_adjustment = -0.01
        elif sentiment < 0.8:
            emotion_adjustment = 0.015  # 更保守，係數增加
        else:
            emotion_adjustment = 0
            
        # 波動度調整: 高波動時更激進
        volatility_adjustment = 0
        if rate_volatility is not None:
            if rate_volatility > 0.1:  # 高波動
                volatility_adjustment = -0.01
            elif rate_volatility > 0.05:  # 中等波動
                volatility_adjustment = -0.005
        
        # 計算最終係數，限制在合理範圍內
        final_factor = base_factor + emotion_adjustment + volatility_adjustment
        return max(0.95, min(0.99, final_factor))
    
    def calculate_enhanced_sentiment_weight(self, sentiment: float, volume_change: float = 0) -> float:
        """
        增強版情緒權重計算，加入交易量變化因素
        
        Args:
            sentiment: 基礎市場情緒值
            volume_change: 交易量變化比例
            
        Returns:
            增強後的情緒權重
        """
        # 基礎情緒倍數
        base_multiplier = min(sentiment / config.HIGHEST_SENTIMENT, 2.0)
        
        # 情緒加速器 - 當情緒值超過閾值時啟動
        if sentiment > 3.0:
            acceleration_factor = 1.0 + (sentiment - 3.0) * 0.15  # 每超過1點增加15%
            base_multiplier *= acceleration_factor
            
        # 交易量變化調整
        volume_adjustment = 1.0 + max(-0.1, min(0.2, volume_change * 0.5))
        
        return base_multiplier * volume_adjustment
    
    def calculate_rate_volatility(self, recent_rates: List[float]) -> float:
        """
        計算最近利率的波動度 (標準差)
        
        Args:
            recent_rates: 最近的利率數據列表
            
        Returns:
            利率波動度
        """
        if len(recent_rates) < 2:
            return 0
        
        return statistics.stdev(recent_rates)
    
    def get_optimal_step_count(self, market_activity: float, competition_density: float) -> int:
        """
        根據市場活躍度和競爭密度決定最佳階梯數量
        
        Args:
            market_activity: 市場活躍度 (0-1)
            competition_density: 競爭密度 (0-1)
            
        Returns:
            最佳階梯數量 (3-7)
        """
        base_steps = config.STEPS
        
        # 市場活躍時增加階梯
        if market_activity > 0.8:
            activity_bonus = 2
        elif market_activity > 0.6:
            activity_bonus = 1
        else:
            activity_bonus = 0
            
        # 競爭激烈時適度增加階梯以提高成交機會
        if competition_density > 0.7:
            competition_bonus = 1
        else:
            competition_bonus = 0
            
        optimal_steps = base_steps + activity_bonus + competition_bonus
        return max(3, min(7, optimal_steps))
    
    def calculate_fibonacci_distribution(self, steps: int) -> List[float]:
        """
        使用斐波那契數列計算各階梯的資金分配比例
        
        Args:
            steps: 階梯數量
            
        Returns:
            各階梯的資金分配比例列表
        """
        # 生成斐波那契數列
        fib = [1, 1]
        for i in range(2, steps):
            fib.append(fib[i-1] + fib[i-2])
        
        # 反轉順序，讓高利率階梯獲得更多資金
        fib = fib[:steps][::-1]
        
        # 正規化為比例
        total = sum(fib)
        return [f / total for f in fib]
    
    def detect_panic_signal(self, sentiment_history: List[float], volume_history: List[float]) -> bool:
        """
        檢測市場恐慌信號
        
        Args:
            sentiment_history: 情緒值歷史
            volume_history: 交易量歷史
            
        Returns:
            是否檢測到恐慌信號
        """
        if len(sentiment_history) < 3 or len(volume_history) < 3:
            return False
        
        # 情緒急劇上升
        recent_sentiment_trend = sentiment_history[-1] - sentiment_history[-3]
        
        # 交易量急劇增加
        recent_volume_trend = volume_history[-1] / volume_history[-3] if volume_history[-3] > 0 else 1
        
        # 恐慌條件：情緒上升超過1.5且交易量增加超過50%
        return recent_sentiment_trend > 1.5 and recent_volume_trend > 1.5
    
    def get_dynamic_minimum_rate(self, market_24h_low: float, current_avg_rate: float) -> float:
        """
        動態調整最低利率下限
        
        Args:
            market_24h_low: 24小時市場最低利率
            current_avg_rate: 當前平均利率
            
        Returns:
            動態最低利率
        """
        # 基礎最低利率
        base_minimum = config.MINIMUM_RATE
        
        # 參考24小時最低利率，但不低於絕對最低值
        market_adjusted_minimum = max(base_minimum, market_24h_low * 0.8)
        
        # 考慮當前市場平均利率
        rate_adjusted_minimum = min(market_adjusted_minimum, current_avg_rate * 0.3)
        
        return max(base_minimum, rate_adjusted_minimum)