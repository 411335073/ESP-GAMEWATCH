import machine
import gc9a01
import vga1_8x16 as font
import time
import random
import network
import urequests
import ntptime
from machine import Pin, SPI, RTC

# 螢幕設定
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 240
BLOCK_SIZE = 10

# 顏色定義
BLACK = gc9a01.BLACK
WHITE = gc9a01.WHITE
RED = gc9a01.RED
GREEN = gc9a01.GREEN
BLUE = gc9a01.BLUE
YELLOW = gc9a01.color565(255, 255, 0)
GRAY = gc9a01.color565(128, 128, 128)
ORANGE = gc9a01.color565(255, 165, 0)

# 遊戲設定
GRID_WIDTH = 18
GRID_HEIGHT = 18
OFFSET_X = (SCREEN_WIDTH - (GRID_WIDTH * BLOCK_SIZE)) // 2
OFFSET_Y = (SCREEN_HEIGHT - (GRID_HEIGHT * BLOCK_SIZE)) // 2

# 方向定義
UP = 0
RIGHT = 1
DOWN = 2
LEFT = 3

# WiFi 設定
WIFI_SSID = ""  # 請替換成你的 WiFi SSID
WIFI_PASSWORD = ""  # 請替換成你的 WiFi 密碼

# 中央氣象局 API 設定
CWA_API_KEY = ""  # 請替換成你的 API Key
LOCATION_NAME = ""  # 可以改成你的城市

class RotaryEncoder:
    """滾輪編碼器類別"""
    def __init__(self, clk_pin, dt_pin, sw_pin=None):
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(sw_pin, Pin.IN, Pin.PULL_UP) if sw_pin else None
        
        self.clk_last = self.clk.value()
        self.dt_last = self.dt.value()
        self.counter = 0
        self.button_pressed = False
        self.last_rotation_time = 0
        self.debounce_time = 50
        
        self.clk.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._encoder_handler)
        if self.sw:
            self.sw.irq(trigger=Pin.IRQ_FALLING, handler=self._button_handler)
    
    def _encoder_handler(self, pin):
        current_time = time.ticks_ms()
        
        if time.ticks_diff(current_time, self.last_rotation_time) < self.debounce_time:
            return
        
        clk_state = self.clk.value()
        dt_state = self.dt.value()
        
        if clk_state == 0 and self.clk_last == 1:
            if dt_state == 1:
                self.counter += 1
            else:
                self.counter -= 1
            self.last_rotation_time = current_time
        
        self.clk_last = clk_state
        self.dt_last = dt_state
    
    def _button_handler(self, pin):
        time.sleep_ms(20)
        if self.sw.value() == 0:
            self.button_pressed = True
    
    def get_rotation(self):
        rotation = self.counter
        self.counter = 0
        return rotation
    
    def is_button_pressed(self):
        if self.button_pressed:
            self.button_pressed = False
            return True
        return False

class WeatherAPI:
    """中央氣象局 API 處理類別"""
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
        self.weather_data = None
        self.last_update = 0
        self.update_interval = 1800000  # 30分鐘更新一次
    
    def connect_wifi(self, ssid, password):
        """連接 WiFi"""
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        
        if not wlan.isconnected():
            print('連接 WiFi...')
            wlan.connect(ssid, password)
            
            timeout = 10
            while not wlan.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1
            
            if wlan.isconnected():
                print('WiFi 連接成功')
                print('IP:', wlan.ifconfig()[0])
                return True
            else:
                print('WiFi 連接失敗')
                return False
        return True
    
    def sync_time(self):
        """同步網路時間"""
        try:
            ntptime.settime()
            print("時間同步成功")
            return True
        except:
            print("時間同步失敗")
            return False
    
    def get_weather(self, location):
        """獲取天氣資料"""
        current_time = time.ticks_ms()
        
        # 檢查是否需要更新
        if self.weather_data and time.ticks_diff(current_time, self.last_update) < self.update_interval:
            return self.weather_data
        
        try:
            url = f"{self.base_url}?Authorization={self.api_key}&locationName={location}"
            response = urequests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                weather_element = data['records']['location'][0]['weatherElement']
                
                # 解析天氣資料
                weather_info = {}
                for element in weather_element:
                    param_name = element['elementName']
                    if param_name == 'Wx':  # 天氣現象
                        weather_info['description'] = element['time'][0]['parameter']['parameterName']
                    elif param_name == 'PoP':  # 降雨機率
                        weather_info['rain_prob'] = element['time'][0]['parameter']['parameterName']
                    elif param_name == 'MinT':  # 最低溫度
                        weather_info['min_temp'] = element['time'][0]['parameter']['parameterName']
                    elif param_name == 'MaxT':  # 最高溫度
                        weather_info['max_temp'] = element['time'][0]['parameter']['parameterName']
                
                self.weather_data = weather_info
                self.last_update = current_time
                response.close()
                return weather_info
            else:
                response.close()
                return None
        except Exception as e:
            print(f"獲取天氣資料失敗: {e}")
            return None

class SmartWatch:
    """智慧型手錶主類別"""
    def __init__(self, display, encoder):
        self.display = display
        self.encoder = encoder
        self.current_screen = 0  # 0: 主畫面, 1: 遊戲
        self.weather_api = WeatherAPI(CWA_API_KEY)
        self.rtc = RTC()
        self.weather_info = None
        self.wifi_connected = False
        
        # 初始化網路和時間
        self.init_network()
    
    def init_network(self):
        """初始化網路連接"""
        self.wifi_connected = self.weather_api.connect_wifi(WIFI_SSID, WIFI_PASSWORD)
        if self.wifi_connected:
            self.weather_api.sync_time()
            self.weather_info = self.weather_api.get_weather(LOCATION_NAME)
    
    def draw_clock_face(self):
        """繪製時鐘主畫面"""
        self.display.fill(BLACK)
        
        # 獲取當前時間
        year, month, day, weekday, hour, minute, second, _ = self.rtc.datetime()
        
        # 繪製時間 - 大字體
        time_str = f"{hour:02d}:{minute:02d}"
        self.display.text(font, time_str, 80, 80, WHITE)
        
        # 繪製日期
        date_str = f"{year}/{month:02d}/{day:02d}"
        self.display.text(font, date_str, 65, 110, GRAY)
        
        # 繪製星期
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        weekday_str = weekdays[weekday]
        self.display.text(font, weekday_str, 100, 130, GRAY)
        
        # 繪製天氣資訊
        if self.weather_info:
            # 天氣描述
            weather_desc = self.weather_info.get('description', 'N/A')
            # 簡化天氣描述以適應螢幕
            if len(weather_desc) > 8:
                weather_desc = weather_desc[:8]
            self.display.text(font, weather_desc, 70, 160, YELLOW)
            
            # 溫度範圍
            min_temp = self.weather_info.get('min_temp', 'N/A')
            max_temp = self.weather_info.get('max_temp', 'N/A')
            temp_str = f"{min_temp}~{max_temp}C"
            self.display.text(font, temp_str, 70, 180, ORANGE)
            
            # 降雨機率
            rain_prob = self.weather_info.get('rain_prob', 'N/A')
            rain_str = f"Rain:{rain_prob}%"
            self.display.text(font, rain_str, 70, 200, BLUE)
        else:
            self.display.text(font, "No Weather", 70, 160, GRAY)
        
        # 繪製導航提示
        self.display.text(font, ">>", 210, 110, WHITE)
        self.display.text(font, "Game", 195, 130, GRAY)
    
    def update_weather(self):
        """更新天氣資料"""
        if self.wifi_connected:
            new_weather = self.weather_api.get_weather(LOCATION_NAME)
            if new_weather:
                self.weather_info = new_weather
    
    def run(self):
        """主執行迴圈"""
        last_update = time.ticks_ms()
        last_minute = -1
        snake_game = None
        
        while True:
            current_time = time.ticks_ms()
            
            # 檢查旋轉
            rotation = self.encoder.get_rotation()
            
            if self.current_screen == 0:  # 主畫面
                # 獲取當前分鐘
                _, _, _, _, _, minute, _, _ = self.rtc.datetime()
                
                # 每分鐘更新一次畫面
                if minute != last_minute:
                    self.draw_clock_face()
                    last_minute = minute
                
                # 每30分鐘更新天氣
                if time.ticks_diff(current_time, last_update) > 1800000:
                    self.update_weather()
                    last_update = current_time
                
                # 向右旋轉進入遊戲
                if rotation > 0:
                    self.current_screen = 1
                    if snake_game is None:
                        snake_game = SnakeGame(self.display, self.encoder)
                    else:
                        snake_game.reset_game()
                    self.display.fill(BLACK)
                    snake_game.draw_boundary()
                    snake_game.draw()
            
            elif self.current_screen == 1:  # 遊戲畫面
                if snake_game:
                    # 遊戲邏輯
                    if snake_game.game_over:
                        # 檢查按鈕重新開始或向左旋轉返回主畫面
                        if self.encoder.is_button_pressed():
                            snake_game.reset_game()
                            self.display.fill(BLACK)
                            snake_game.draw_boundary()
                        elif rotation < 0:  # 向左旋轉返回主畫面
                            self.current_screen = 0
                            self.draw_clock_face()
                    else:
                        # 正常遊戲運行
                        snake_game.update_direction()
                        
                        if time.ticks_diff(current_time, snake_game.last_move) >= snake_game.game_speed:
                            snake_game.move_snake()
                            snake_game.last_move = current_time
                            snake_game.draw()
                        
                        # 遊戲中向左旋轉暫停並返回主畫面
                        if rotation < -2:  # 需要較大的旋轉值避免誤觸
                            self.current_screen = 0
                            self.draw_clock_face()
            
            time.sleep_ms(10)

class SnakeGame:
    def __init__(self, display, encoder):
        self.display = display
        self.encoder = encoder
        self.last_move = time.ticks_ms()
        self.reset_game()
        
    def reset_game(self):
        """重置遊戲"""
        start_x = GRID_WIDTH // 2
        start_y = GRID_HEIGHT // 2
        self.snake = [(start_x, start_y), (start_x - 1, start_y)]
        self.direction = RIGHT
        
        self.generate_food()
        
        self.game_over = False
        self.score = 0
        self.game_speed = 200
        
        self.old_snake = []
        self.old_food = None
        self.debug_mode = False
        
    def generate_food(self):
        """生成食物位置"""
        while True:
            self.food = (random.randint(0, GRID_WIDTH - 1), 
                        random.randint(0, GRID_HEIGHT - 1))
            if self.food not in self.snake:
                break
    
    def update_direction(self):
        """根據滾輪編碼器更新方向"""
        rotation = self.encoder.get_rotation()
        
        if rotation == 0:
            return
        
        if abs(rotation) >= 1:
            if rotation > 0:
                new_direction = (self.direction + 1) % 4
            else:
                new_direction = (self.direction - 1) % 4
            
            opposite_directions = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}
            if new_direction != opposite_directions[self.direction]:
                self.direction = new_direction
    
    def move_snake(self):
        """移動蛇"""
        if self.game_over:
            return
            
        head = self.snake[0]
        
        if self.direction == UP:
            new_head = (head[0], head[1] - 1)
        elif self.direction == DOWN:
            new_head = (head[0], head[1] + 1)
        elif self.direction == LEFT:
            new_head = (head[0] - 1, head[1])
        elif self.direction == RIGHT:
            new_head = (head[0] + 1, head[1])
        
        if (new_head[0] < 0 or new_head[0] >= GRID_WIDTH or
            new_head[1] < 0 or new_head[1] >= GRID_HEIGHT):
            self.game_over = True
            return
        
        if new_head in self.snake[:-1]:
            self.game_over = True
            return
        
        self.snake.insert(0, new_head)
        
        if new_head == self.food:
            self.score += 10
            self.generate_food()
            self.game_speed = max(80, self.game_speed - 3)
        else:
            self.snake.pop()
    
    def draw_boundary(self):
        """繪製遊戲邊界"""
        boundary_color = YELLOW
        
        game_left = OFFSET_X
        game_top = OFFSET_Y
        game_width = GRID_WIDTH * BLOCK_SIZE
        game_height = GRID_HEIGHT * BLOCK_SIZE
        
        self.display.rect(game_left - 2, game_top - 2, 
                         game_width + 4, game_height + 4, 
                         boundary_color)
        
        self.display.text(font, "<< Back", 5, 5, GRAY)
    
    def draw_block(self, x, y, color):
        """繪製一個方塊"""
        if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
            px = OFFSET_X + x * BLOCK_SIZE
            py = OFFSET_Y + y * BLOCK_SIZE
            self.display.fill_rect(px, py, BLOCK_SIZE, BLOCK_SIZE, color)
            if color != BLACK:
                self.display.rect(px, py, BLOCK_SIZE, BLOCK_SIZE, WHITE)
    
    def clear_block(self, x, y):
        """清除一個方塊"""
        if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
            px = OFFSET_X + x * BLOCK_SIZE
            py = OFFSET_Y + y * BLOCK_SIZE
            self.display.fill_rect(px, py, BLOCK_SIZE, BLOCK_SIZE, BLACK)
    
    def draw(self):
        """繪製遊戲畫面"""
        if self.game_over:
            if not hasattr(self, '_game_over_drawn') or not self._game_over_drawn:
                self.display.fill(BLACK)
                center_x = SCREEN_WIDTH // 2
                center_y = SCREEN_HEIGHT // 2
                self.display.text(font, "GAME OVER", center_x - 40, center_y - 30, WHITE)
                self.display.text(font, f"Score: {self.score}", center_x - 35, center_y - 10, WHITE)
                self.display.text(font, "Press button", center_x - 45, center_y + 10, WHITE)
                self.display.text(font, "or << Back", center_x - 40, center_y + 30, WHITE)
                self._game_over_drawn = True
        else:
            self._game_over_drawn = False
            
            for segment in self.old_snake:
                if segment not in self.snake:
                    self.clear_block(segment[0], segment[1])
            
            if self.old_food and self.old_food != self.food:
                self.clear_block(self.old_food[0], self.old_food[1])
            
            for i, segment in enumerate(self.snake):
                if i == 0:
                    self.draw_block(segment[0], segment[1], BLUE)
                else:
                    self.draw_block(segment[0], segment[1], GREEN)
            
            self.draw_block(self.food[0], self.food[1], RED)
            
            score_text = f"Score:{self.score}"
            score_x = OFFSET_X
            score_y = OFFSET_Y - 20
            self.display.fill_rect(score_x, score_y, 100, 16, BLACK)
            self.display.text(font, score_text, score_x, score_y, WHITE)
            
            self.old_snake = self.snake.copy()
            self.old_food = self.food

# 主程式
def main():
    # 初始化SPI和顯示器
    spi = SPI(2, baudrate=40000000, polarity=0, phase=0, 
              sck=Pin(18), mosi=Pin(23))
    
    dc_pin = Pin(27, Pin.OUT)
    cs_pin = Pin(5, Pin.OUT)
    reset_pin = Pin(26, Pin.OUT)
    backlight_pin = Pin(33, Pin.OUT)
    
    display = gc9a01.GC9A01(
        spi,
        dc_pin,
        cs_pin,
        reset_pin,
        backlight_pin,
        0
    )
    
    display.backlight.value(1)
    
    # 初始化滾輪編碼器
    encoder = RotaryEncoder(
        clk_pin=14,
        dt_pin=12,
        sw_pin=13
    )
    
    # 建立並執行智慧型手錶
    watch = SmartWatch(display, encoder)
    watch.run()

if __name__ == "__main__":
    main()