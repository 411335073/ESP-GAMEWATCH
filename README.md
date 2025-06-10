# ESP#@GAMEWATCH

基於 ESP32 開發板的桌面小廢物，具備時鐘、天氣顯示和貪吃蛇遊戲功能。

## 功能特色

- 🕐 **即時時鐘顯示**：顯示當前時間、日期和星期
- 🌤️ **天氣資訊**：透過中央氣象局 API 取得即時天氣資訊
- 🎮 **貪吃蛇遊戲**：經典貪吃蛇遊戲，使用旋轉編碼器控制
- 🎛️ **旋轉編碼器控制**：直覺的操作介面

## 硬體需求

### 必要元件
- ESP32 開發板
- GC9A01 圓形 LCD 顯示器（240x240 像素）
- 旋轉編碼器（含按鈕功能）
- 杜邦線若干

### 接線圖

#### LCD 顯示器（GC9A01）
| LCD 腳位 | ESP32 腳位 | 說明 |
|---------|-----------|------|
| VCC     | 3.3V      | 電源 |
| GND     | GND       | 接地 |
| SCL/SCK | GPIO 18   | SPI 時鐘 |
| SDA/MOSI| GPIO 23   | SPI 資料 |
| DC      | GPIO 27   | 資料/命令選擇 |
| CS      | GPIO 5    | 晶片選擇 |
| RST     | GPIO 26   | 重置 |
| BL      | GPIO 33   | 背光控制 |

#### 旋轉編碼器
| 編碼器腳位 | ESP32 腳位 | 說明 |
|-----------|-----------|------|
| CLK       | GPIO 14   | 時鐘信號 |
| DT        | GPIO 12   | 資料信號 |
| SW        | GPIO 13   | 按鈕開關 |
| +         | 3.3V      | 電源 |
| GND       | GND       | 接地 |

## 軟體需求

### MicroPython 韌體
- MicroPython v1.19 或更新版本
- 下載連結：[MicroPython 官網](https://micropython.org/download/esp32/)

### 必要函式庫
- `gc9a01` - LCD 顯示器驅動
- `vga1_8x16` - 字型檔案
- 內建函式庫：`machine`, `network`, `urequests`, `ntptime`

## 安裝步驟

### 1. 燒錄 MicroPython 韌體
```bash
# 清除 Flash
esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash

# 燒錄韌體
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 esp32-20220618-v1.19.1.bin
```

### 2. 安裝必要函式庫
使用 Thonny 或 ampy 上傳以下檔案到 ESP32：
- `gc9a01.py` - LCD 驅動程式
- `vga1_8x16.py` - 字型檔案

### 3. 設定 WiFi 和 API
編輯主程式中的設定：
```python
# WiFi 設定
WIFI_SSID = "你的WiFi名稱"
WIFI_PASSWORD = "你的WiFi密碼"

# 中央氣象局 API 設定
CWA_API_KEY = "你的API金鑰"  # 從 https://opendata.cwb.gov.tw 申請
LOCATION_NAME = "臺北市"      # 改成你的城市
```

### 4. 上傳主程式
將 `main.py` 上傳到 ESP32 根目錄

## 操作說明

### 主畫面
- 顯示當前時間、日期、星期
- 顯示天氣資訊（天氣狀況、溫度範圍、降雨機率）
- **順時針旋轉**：進入貪吃蛇遊戲

### 貪吃蛇遊戲
- **順時針旋轉**：蛇向右轉
- **逆時針旋轉**：蛇向左轉
- **按下按鈕**：遊戲結束後重新開始
- **逆時針旋轉**（遊戲結束時）：返回主畫面

## 程式架構

```
main.py
├── RotaryEncoder       # 旋轉編碼器控制類別
├── WeatherAPI         # 天氣 API 處理類別
├── SnakeGame          # 貪吃蛇遊戲類別
└── SmartWatch         # 主程式類別
    ├── init_network() # 網路初始化
    ├── draw_clock()   # 繪製時鐘畫面
    └── run()          # 主執行迴圈
```

## 故障排除

### 編碼器無反應
1. 檢查接線是否正確
2. 確認 GPIO 腳位設定
3. 執行編碼器測試模式查看原始訊號

### WiFi 連線失敗
1. 確認 SSID 和密碼正確
2. 檢查路由器是否支援 2.4GHz
3. 確認 ESP32 在路由器訊號範圍內

### 天氣資料無法顯示
1. 確認 API 金鑰有效
2. 檢查網路連線狀態
3. 確認城市名稱格式正確（如：臺北市、新北市）

### 顯示器無畫面
1. 檢查 SPI 接線
2. 確認背光是否開啟
3. 測試顯示器電源供應

## API 申請

### 中央氣象局開放資料平台
1. 前往 [https://opendata.cwb.gov.tw](https://opendata.cwb.gov.tw)
2. 註冊會員
3. 申請 API 授權碼
4. 將授權碼填入程式中的 `CWA_API_KEY`

## 自訂修改

### 更改遊戲速度
修改 `SnakeGame` 類別中的參數：
```python
self.game_speed = 200  # 初始速度（毫秒）
self.game_speed = max(80, self.game_speed - 3)  # 加速幅度
```

### 調整顯示顏色
在程式開頭的顏色定義區塊新增或修改：
```python
PURPLE = gc9a01.color565(128, 0, 128)
CYAN = gc9a01.color565(0, 255, 255)
```

### 新增功能
可以在 `SmartWatch` 類別中新增更多畫面：
- 計步器
- 鬧鐘
- 計時器
- 其他小遊戲

## 授權條款

MIT License

## 貢獻指南

歡迎提交 Issue 或 Pull Request！

## 版本歷史

- v1.0.0 (2024-01) - 初始版本
  - 基本時鐘功能
  - 天氣資訊顯示
  - 貪吃蛇遊戲

## 聯絡資訊

如有問題或建議，請透過 GitHub Issues 聯繫。

## 致謝

- MicroPython 社群
- 中央氣象局開放資料平台
- GC9A01 驅動程式開發者