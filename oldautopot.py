import time
import keyboard
import pyautogui
import threading
from PIL import ImageGrab, Image
import numpy as np
import cv2
import configparser
import os

class AutoPotController:
    def __init__(self):
        # Get screen resolution first
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Configuration
        self.config = self.load_config()
        
        # Thresholds
        self.health_threshold = self.config.getfloat('Thresholds', 'health', fallback=0.35)  # 35% by default
        self.mana_threshold = self.config.getfloat('Thresholds', 'mana', fallback=0.25)  # 25% by default
        
        # Hotkeys
        self.health_potion_key = self.config.get('Hotkeys', 'health_potion', fallback='1')
        self.mana_potion_key = self.config.get('Hotkeys', 'mana_potion', fallback='2')
        self.toggle_key = self.config.get('Hotkeys', 'toggle', fallback='F12')
        
        # Screen positions (normalized coordinates, will be adjusted based on screen resolution)
        self.health_bar_pos = self.parse_position(self.config.get('ScreenPositions', 'health_bar', fallback='0.08,0.95,0.25,0.98'))
        self.mana_bar_pos = self.parse_position(self.config.get('ScreenPositions', 'mana_bar', fallback='0.75,0.95,0.92,0.98'))
        
        # Colors
        self.health_color_lower = np.array([0, 100, 100])  # Red/orange in HSV
        self.health_color_upper = np.array([15, 255, 255])
        self.mana_color_lower = np.array([100, 100, 100])  # Blue in HSV
        self.mana_color_upper = np.array([140, 255, 255])
        
        # State
        self.active = False
        self.health_last_used = 0
        self.mana_last_used = 0
        self.health_cooldown = self.config.getfloat('Cooldowns', 'health_potion', fallback=4.0)  # seconds
        self.mana_cooldown = self.config.getfloat('Cooldowns', 'mana_potion', fallback=7.0)  # seconds
        
        # Initialize thread
        self.thread = None
        
        # Set up toggle key
        keyboard.add_hotkey(self.toggle_key, self.toggle)
        
        print(f"PoE2 Auto-Potion initialized. Press {self.toggle_key} to toggle.")

    def load_config(self):
        config = configparser.ConfigParser()
        config_path = 'poe2_autopot_config.ini'
        
        if os.path.exists(config_path):
            config.read(config_path)
        else:
            # Create default config
            config['Thresholds'] = {
                'health': '0.35',
                'mana': '0.25'
            }
            config['Hotkeys'] = {
                'health_potion': '1',
                'mana_potion': '2',
                'toggle': 'F12'
            }
            config['ScreenPositions'] = {
                'health_bar': '0.08,0.95,0.25,0.98',
                'mana_bar': '0.75,0.95,0.92,0.98'
            }
            config['Cooldowns'] = {
                'health_potion': '4.0',
                'mana_potion': '7.0'
            }
            
            with open(config_path, 'w') as f:
                config.write(f)
            
            print(f"Created default configuration file at {config_path}")
        
        return config

    def parse_position(self, pos_str):
        """Convert position string to screen coordinates"""
        x1, y1, x2, y2 = map(float, pos_str.split(','))
        return (
            int(x1 * self.screen_width),
            int(y1 * self.screen_height),
            int(x2 * self.screen_width),
            int(y2 * self.screen_height)
        )

    def toggle(self):
        """Toggle the auto-potion function on/off"""
        self.active = not self.active
        
        if self.active:
            print("Auto-potion activated!")
            self.thread = threading.Thread(target=self.monitor_loop)
            self.thread.daemon = True
            self.thread.start()
        else:
            print("Auto-potion deactivated.")
            if self.thread:
                self.thread = None

    def check_health_level(self):
        """Check current health level and use potion if needed"""
        try:
            # Capture health bar region
            health_img = np.array(ImageGrab.grab(bbox=self.health_bar_pos))
            
            # Convert to HSV and create mask for health color
            health_hsv = cv2.cvtColor(health_img, cv2.COLOR_RGB2HSV)
            health_mask = cv2.inRange(health_hsv, self.health_color_lower, self.health_color_upper)
            
            # Calculate health percentage
            total_pixels = health_mask.size
            health_pixels = np.count_nonzero(health_mask)
            health_percent = health_pixels / total_pixels if total_pixels > 0 else 0
            
            current_time = time.time()
            
            # Use health potion if below threshold and not on cooldown
            if health_percent < self.health_threshold and current_time - self.health_last_used > self.health_cooldown:
                keyboard.press_and_release(self.health_potion_key)
                self.health_last_used = current_time
                print(f"Health at {health_percent:.2%}, using health potion")
            
            return health_percent
        except Exception as e:
            print(f"Error checking health: {e}")
            return 1.0  # Assume full health on error

    def check_mana_level(self):
        """Check current mana level and use potion if needed"""
        try:
            # Capture mana bar region
            mana_img = np.array(ImageGrab.grab(bbox=self.mana_bar_pos))
            
            # Convert to HSV and create mask for mana color
            mana_hsv = cv2.cvtColor(mana_img, cv2.COLOR_RGB2HSV)
            mana_mask = cv2.inRange(mana_hsv, self.mana_color_lower, self.mana_color_upper)
            
            # Calculate mana percentage
            total_pixels = mana_mask.size
            mana_pixels = np.count_nonzero(mana_mask)
            mana_percent = mana_pixels / total_pixels if total_pixels > 0 else 0
            
            current_time = time.time()
            
            # Use mana potion if below threshold and not on cooldown
            if mana_percent < self.mana_threshold and current_time - self.mana_last_used > self.mana_cooldown:
                keyboard.press_and_release(self.mana_potion_key)
                self.mana_last_used = current_time
                print(f"Mana at {mana_percent:.2%}, using mana potion")
            
            return mana_percent
        except Exception as e:
            print(f"Error checking mana: {e}")
            return 1.0  # Assume full mana on error

    def monitor_loop(self):
        """Main monitoring loop"""
        while self.active:
            health_percent = self.check_health_level()
            mana_percent = self.check_mana_level()
            
            # Adjust sleep time based on how low health/mana are
            min_percent = min(health_percent, mana_percent)
            if min_percent < 0.2:
                sleep_time = 0.1  # Check more frequently when low
            elif min_percent < 0.5:
                sleep_time = 0.25
            else:
                sleep_time = 0.5  # Check less frequently when safe
            
            time.sleep(sleep_time)

    def calibrate(self):
        """Interactive calibration for screen positions"""
        print("Starting calibration mode...")
        print("Move your mouse to the BOTTOM of your health bar and press 'H'")
        
        def on_h_press(e):
            if e.name == 'h':
                x, y = pyautogui.position()
                self.health_bar_pos = (x, y, self.health_bar_pos[2], self.health_bar_pos[3])
                print(f"Health bar left edge set to {x}, {y}")
                keyboard.unhook_all()
                
                print("Move your mouse to the RIGHT edge of your health bar and press 'H'")
                keyboard.hook_key('h', on_h_press2)
        
        def on_h_press2(e):
            if e.name == 'h':
                x, y = pyautogui.position()
                self.health_bar_pos = (self.health_bar_pos[0], self.health_bar_pos[1], x, y)
                print(f"Health bar right edge set to {x}, {y}")
                keyboard.unhook_all()
                
                print("Move your mouse to the BOTTOM your mana bar and press 'M'")
                keyboard.hook_key('m', on_m_press)
        
        def on_m_press(e):
            if e.name == 'm':
                x, y = pyautogui.position()
                self.mana_bar_pos = (x, y, self.mana_bar_pos[2], self.mana_bar_pos[3])
                print(f"Mana bar left edge set to {x}, {y}")
                keyboard.unhook_all()
                
                print("Move your mouse to the RIGHT edge of your mana bar and press 'M'")
                keyboard.hook_key('m', on_m_press2)
        
        def on_m_press2(e):
            if e.name == 'm':
                x, y = pyautogui.position()
                self.mana_bar_pos = (self.mana_bar_pos[0], self.mana_bar_pos[1], x, y)
                print(f"Mana bar right edge set to {x}, {y}")
                keyboard.unhook_all()
                
                print("Calibration complete!")
                
                # Save to config
                norm_health = (
                    self.health_bar_pos[0]/self.screen_width,
                    self.health_bar_pos[1]/self.screen_height,
                    self.health_bar_pos[2]/self.screen_width,
                    self.health_bar_pos[3]/self.screen_height
                )
                norm_mana = (
                    self.mana_bar_pos[0]/self.screen_width,
                    self.mana_bar_pos[1]/self.screen_height,
                    self.mana_bar_pos[2]/self.screen_width,
                    self.mana_bar_pos[3]/self.screen_height
                )
                
                self.config['ScreenPositions']['health_bar'] = f"{norm_health[0]:.4f},{norm_health[1]:.4f},{norm_health[2]:.4f},{norm_health[3]:.4f}"
                self.config['ScreenPositions']['mana_bar'] = f"{norm_mana[0]:.4f},{norm_mana[1]:.4f},{norm_mana[2]:.4f},{norm_mana[3]:.4f}"
                
                with open('poe2_autopot_config.ini', 'w') as f:
                    self.config.write(f)
        
        keyboard.hook_key('h', on_h_press)

def main():
    controller = AutoPotController()
    
    print("\nCommands:")
    print(f"- Press {controller.toggle_key} to toggle auto-potion")
    print("- Press 'C' to start calibration")
    print("- Press Ctrl+C to exit\n")
    
    keyboard.add_hotkey('c', controller.calibrate)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")

if __name__ == "__main__":
    main()