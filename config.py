# ===== API 設定 =====
BITFINEX_PUBLIC_API_URL = "https://api-pub.bitfinex.com"
FUND_CURRENCY = ["fUSD"]

# ===== 基本放貸參數 =====
MINIMUM_FUNDS = 150.0                # 最低放貸金額
MINIMUM_RATE = 0.0002              # 最小可接受利率
RETAIN_FUNDS = 0                   # 保留資金
RATE_ADJUSTMENT_RATIO = 1.07       # 手動調整比率

# ===== 階梯策略參數 =====
STEPS = 3                          # 預設階梯數（向後兼容）
HIGHEST_SENTIMENT = 8              # 最高情緒值（優化版提升至8）

# ===== 時間參數 =====
INTERVAL_SECONDS = 300             # 循環時間間隔（秒）向後兼容

# ===== 優化版新增參數 =====
ENABLE_DYNAMIC_OPTIMIZATION = True  # 啟用動態優化功能
EMOTION_ACCELERATION_THRESHOLD = 3.0 # 情緒加速器啟動閾值
MAX_STEPS = 7                    # 最大階梯數
MIN_STEPS = 3                    # 最小階梯數
FAST_REACTION_MODE = False       # 快速反應模式 (縮短執行間隔)
PANIC_DETECTION_ENABLED = True   # 啟用恐慌檢測

# ===== 執行時間配置 =====
REGULAR_STRATEGY_INTERVAL = INTERVAL_SECONDS  # 常規策略執行間隔（秒）繼承原有設定
OPPORTUNISTIC_MONITOR_INTERVAL = 10            # 機會性訂單監控間隔（秒）從10秒調整為30秒，平衡效能與機會捕捉

# ===== 機會性訂單配置 =====
INTEREST_RATE_DAYS = [
    {"rate": 0.0004,  "days": 10}, 
    {"rate": 0.0005,  "days": 30}, 
    {"rate": 0.0006,  "days": 60}, 
    {"rate": 0.0008,  "days": 90}, 
    {"rate": 0.001,   "days": 120},
]

# ===== 機會性訂單內部參數 =====
OPPORTUNISTIC_RATE_DISCOUNT = 0.999    # 比市場需求低0.1%確保搓合
ORDER_PROTECTION_MINUTES = 5          # 訂單保護時間（分鐘）
MAX_SINGLE_ORDER_RATIO = 0.3          # 單筆訂單最大資金比例
MARKET_AMOUNT_RATIO = 0.8              # 市場金額使用比例

# ===== 優先級計算參數 =====
AMOUNT_FACTOR_DIVISOR = 10000          # 金額係數除數
AMOUNT_FACTOR_MAX = 5.0                # 金額係數最大值
PERIOD_FACTOR_DIVISOR = 120            # 期限係數除數
LIQUIDITY_FACTOR_DIVISOR = 10          # 流動性係數除數
LIQUIDITY_FACTOR_MAX = 2.0             # 流動性係數最大值
PRIORITY_MULTIPLIER = 1000             # 優先級分數乘數

# ===== Discord 通知配置 =====
ENABLE_DISCORD_NOTIFICATIONS = True    # 啟用 Discord 通知
STATUS_NOTIFICATION_INTERVAL = 3600    # 狀態通知間隔（秒）預設1小時