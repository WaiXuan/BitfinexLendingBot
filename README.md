# Bitfinex 放貸機器人

一個基於 Python 的自動化 Bitfinex USD 放貸機器人，透過智慧策略分析市場情緒和利率波動，自動執行最佳化的放貸操作以最大化收益。

## 功能特色

- 🤖 **自動化放貸**: 全自動執行放貸策略，無需人工干預
- 📊 **市場分析**: 即時分析市場情緒、資金使用量和利率趨勢  
- 🎯 **智慧定價**: 基於歷史數據和市場狀況動態調整放貸利率
- 📈 **階梯報價**: 多層級利率設定，分散風險並最大化收益
- ⚡ **即時監控**: 每10分鐘檢查並調整策略，快速響應市場變化
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
pip install bfxapi aiohttp pandas schedule requests plotly
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
2. 分析當前市場狀況
3. 計算最佳放貸利率
4. 自動提交放貸訂單
5. 每10分鐘重複執行策略

### 數據分析 (可選)
使用 Jupyter notebook 進行數據分析：
```bash
jupyter notebook bitfinex.ipynb
```

## 配置說明

所有配置都可以透過環境變數調整，主要參數如下：

### 基本設定
| 參數 | 預設值 | 說明 |
|------|--------|------|
| `FUND_CURRENCY` | fUSD | 放貸幣種 |
| `MINIMUM_FUNDS` | 150.0 | 最低放貸金額 (USD) |
| `RETAIN_FUNDS` | 0 | 保留資金 (USD) |
| `INTERVAL_SECONDS` | 600 | 策略執行間隔 (秒) |

### 策略參數
| 參數 | 預設值 | 說明 |
|------|--------|------|
| `STEPS` | 3 | 階梯報價層數 |
| `HIGHEST_SENTIMENT` | 5 | 市場情緒最高值 |
| `RATE_ADJUSTMENT_RATIO` | 1.07 | 利率調整係數 |
| `MINIMUM_RATE` | 0.0003 | 最低可接受利率 (0.03%) |

### 進階設定
利率階梯可透過 `INTEREST_RATE_DAYS` 環境變數自訂 (JSON 格式)：
```json
[
  {"rate": 0.0008, "days": 10},
  {"rate": 0.001, "days": 15},
  {"rate": 0.01, "days": 30},
  {"rate": 0.1, "days": 60},
  {"rate": 0.2, "days": 90},
  {"rate": 0.3, "days": 120}
]
```

## 策略運作原理

### 1. 市場情緒分析
- 分析當前與過去12小時的資金使用量比較
- `sentiment > 1`: 市場恐慌，資金需求高
- `sentiment = 1`: 市場平穩
- `sentiment < 1`: 市場冷靜，資金需求低

### 2. 利率計算
- 獲取市場資金簿數據
- 分析不同期限 (2-120天) 的最高利率和加權平均利率
- 結合歷史利率和市場情緒預測最佳報價

### 3. 階梯報價
- 基於預測利率產生多層級報價
- 分散放貸期限，降低利率風險
- 自動調整訂單金額分配

### 4. 風險控制
- 設定最低利率限制
- 每6小時重置過時訂單
- 即時監控並調整策略

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
├── lending.py         # 主程式入口點
├── bitfinex.py        # Bitfinex API
├── common.py          # 共用函數和策略邏輯
├── config.py          # 配置管理
├── bitfinex.ipynb     # 數據分析 notebook
├── .env.example       # 環境變數範例
└── README.md          # 專案說明
```

## 免責聲明

本軟體僅供學習和研究用途。加密貨幣交易存在風險，使用者應：
- 充分了解放貸風險
- 僅投入可承受損失的資金
- 定期監控機器人運行狀況
- 根據市場變化及時調整策略

作者不對使用本軟體造成的任何損失負責。