# Bitfinex 放貸機器人

一個基於 Python 的自動化 Bitfinex USD 放貸機器人，透過智慧策略分析市場情緒和利率波動，自動執行最佳化的放貸操作以最大化收益。

## 功能特色

- 🤖 **自動化放貸**: 全自動執行放貸策略，無需人工干預
- 📊 **市場分析**: 即時分析市場情緒、資金使用量和利率趨勢  
- 🎯 **智慧定價**: 基於歷史數據和市場狀況動態調整放貸利率
- 📈 **階梯報價**: 多層級利率設定，分散風險並最大化收益
- ⚡ **即時監控**: 每5分鐘檢查並調整策略，快速響應市場變化
- 🎯 **機會性訂單**: 每10秒監控市場機會，自動捕捉高利率放貸機會
- 🎨 **智能優化**: 動態安全係數、斐波那契資金分配、情緒加速器
- 🔄 **自動重置**: 每6小時重置訂單，避免利率過時
- 📋 **詳細日誌**: 完整記錄所有操作和市場數據
- 📊 **數據視覺化**: 內建 Jupyter notebook 進行利率和價格分析

## 系統需求

- Python 3.7+
- Bitfinex API 帳戶 (需要交易權限)
- 最低資金: 150 USD (可調整)

## 安裝與設置

### 1. 克隆專案
```bash
git clone <repository-url>
cd BitfinexLendingBot
```

### 2. 安裝依賴套件
```bash
pip install -r requirements.txt
```

或手動安裝：
```bash
pip install aiohttp==3.10.3 schedule==1.2.2 requests==2.32.3 bitfinex-api-py==3.0.4 python-dotenv==1.0.1 pandas==2.3.1
```

### 3. 配置環境變數

複製範例環境檔案：
```bash
cp .env.example .env
```

編輯 `.env` 檔案，設定您的 Bitfinex API 憑證：
```bash
# Bitfinex API 憑證
BF_API_KEY=your_actual_api_key_here
BF_API_SECRET=your_actual_api_secret_here

# Discord 通知設定 (可選)
# 倉位異動通知 (放貸成交、歸還等即時倉位變化)
DISCORD_POSITION_WEBHOOK=your_discord_webhook_url

# 每日報表與狀態匯總通知 (啟動通知、每日收益報告、狀態總覽等)
DISCORD_DAILY_REPORT_WEBHOOK=your_discord_webhook_url
```

### 4. API 權限設置

在 Bitfinex 帳戶中創建 API 金鑰，確保開啟以下權限：
- ✅ Orders (訂單管理)
- ✅ Wallets (錢包查詢)
- ✅ Funding (放貸操作)

⚠️ **重要**: 不要開啟提現權限以確保資金安全

## 使用方法

### 啟動放貸機器人
```bash
python lending.py
```

機器人將會：
1. 連接到 Bitfinex API
2. 分析當前市場狀況與情緒
3. 使用智能優化算法計算最佳放貸利率
4. 生成多層級階梯報價策略
5. 自動提交放貸訂單並監控機會性訂單
6. 每5分鐘執行常規策略，每10秒監控市場機會

### 數據分析 (可選)
使用 Jupyter notebook 進行數據分析：
```bash
jupyter notebook bitfinex.ipynb
```

### 打包成執行檔案
```bash
python build_exe.py
```
打包後的執行檔位於 `dist/LendingBot.exe`

### Discord 通知 (可選)
如需要 Discord 通知功能，請在 `.env` 檔案中設定 Webhook URL：
```bash
# 倉位異動通知
DISCORD_POSITION_WEBHOOK=your_webhook_url

# 每日報表通知
DISCORD_DAILY_REPORT_WEBHOOK=your_webhook_url
```

## 配置說明

所有配置都可以透過環境變數調整，主要參數如下：

### 基本設定
| 參數 | 預設值 | 說明 |
|------|--------|------|
| `FUND_CURRENCY` | fUSD | 放貸幣種 |
| `MINIMUM_FUNDS` | 150.0 | 最低放貸金額 (USD) |
| `RETAIN_FUNDS` | 0 | 保留資金 (USD) |
| `INTERVAL_SECONDS` | 300 | 策略執行間隔 (秒) |

### 策略參數
| 參數 | 預設值 | 說明 |
|------|--------|------|
| `STEPS` | 3 | 階梯報價層數 |
| `HIGHEST_SENTIMENT` | 8 | 市場情緒最高值 (優化版) |
| `RATE_ADJUSTMENT_RATIO` | 1.07 | 利率調整係數 |
| `MINIMUM_RATE` | 0.0003 | 最低可接受利率 (0.03%) |

### 優化版新增設定
| 參數 | 預設值 | 說明 |
|------|--------|------|
| `ENABLE_DYNAMIC_OPTIMIZATION` | True | 啟用動態優化功能 |
| `MAX_STEPS` | 7 | 最大階梯數 |
| `MIN_STEPS` | 3 | 最小階梯數 |
| `FAST_REACTION_MODE` | False | 快速反應模式 |
| `PANIC_DETECTION_ENABLED` | True | 恐慌檢測機制 |

### 機會性訂單配置
利率階梯可在 `config.py` 中的 `INTEREST_RATE_DAYS` 調整：
```python
INTEREST_RATE_DAYS = [
    {"rate": 0.0004, "days": 10},   # 利率≥14.6%年化時，最高可放10天
    {"rate": 0.0005, "days": 30},   # 利率≥18.3%年化時，最高可放30天
    {"rate": 0.0006, "days": 60},   # 利率≥21.9%年化時，最高可放60天
    {"rate": 0.0008, "days": 90},   # 利率≥29.2%年化時，最高可放90天
    {"rate": 0.001,  "days": 120},  # 利率≥36.5%年化時，最高可放120天
]
```

## 策略運作原理

### 1. 增強市場情緒分析
- 分析當前與過去12小時的資金使用量比較
- 情緒加速器：當 `sentiment > 3.0` 時加速反應
- 恐慌檢測：自動識別市場異常狀態
- 動態情緒權重：最高提升至 8

### 2. 智能利率優化
- **動態安全係數**: 根據市場情緒和波動度動態調整 (0.95-0.99)
- **動態最低利率**: 根據 24 小時市場最低利率動態調整
- **歷史資料分析**: 結合歷史利率趨勢進行預測

### 3. 斐波那契階梯報價
- **黃金比例資金分配**: 使用斐波那契數列優化資金分配
- **動態階梯數**: 根據市場情緒動態調整 3-7 個階梯
- **智能期限分配**: 自動優化不同期限的放貸策略

### 4. 機會性訂單監控
- **即時市場監控**: 每 10 秒監控市場機會
- **智能需求匹配**: 自動識別高價值借貸需求
- **優先級評分系統**: 綜合考量利潤、金額、流動性

### 5. 增強風險控制
- 動態最低利率限制
- 訂單保護機制：機會性訂單 5 分鐘內不被修改
- 每 6 小時自動重設所有訂單
- 即時監控並智能調整策略

## 安全注意事項

⚠️ **重要安全提醒**:
- 絕不在程式碼或版本控制中包含 API 金鑰
- 使用最小權限原則設定 API 權限
- 定期檢查和更新 API 金鑰
- 建議使用專用的交易帳戶進行測試
- 初期建議使用小額資金測試策略效果

## 專案結構

```
BitfinexLendingBot/
├── lending.py              # 主程式入口點與策略排程器
├── bitfinex.py             # Bitfinex REST API 包裝類別
├── common.py               # 核心策略演算法與工具函式
├── config.py               # 全局參數設定
├── dynamic_optimizer.py    # 動態優化策略模組
├── order_book_monitor.py   # 機會性訂單監控系統
├── discord_notifier.py     # Discord 通知系統
├── lending_monitor.py      # 獨立放貸監控工具
├── build_exe.py            # 執行檔案打包腳本
├── bitfinex.ipynb          # 數據分析 Jupyter notebook
├── requirements.txt        # Python 依賴套件清單
├── .env.example            # 環境變數範例
├── CLAUDE.md               # 開發文件與指引
└── README.md               # 專案說明
```

## 免責聲明

本軟體僅供學習和研究用途。加密貨幣交易存在風險，使用者應：
- 充分了解放貸風險
- 僅投入可承受損失的資金
- 定期監控機器人運行狀況
- 根據市場變化及時調整策略

作者不對使用本軟體造成的任何損失負責。