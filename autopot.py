import time
import keyboard
import threading
from PIL import ImageGrab
import numpy as np
import configparser
import os
import sys
import colorama
from colorama import Fore, Back, Style
import logging
import traceback

# Initialize colorama with autoreset
colorama.init(autoreset=True)

# Set up logging to file and console
def setup_logging():
    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")
        
    # Create a unique log filename with timestamp
    log_filename = f"logs/autopot_{time.strftime('%Y%m%d_%H%M%S')}.log"
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    logging.info(f"Logging started. Log file: {log_filename}")
    return log_filename

# Global exception handler to catch and log all unhandled exceptions
def global_exception_handler(exc_type, exc_value, exc_traceback):
    logging.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
    # Call the default exception handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Set the global exception handler
sys.excepthook = global_exception_handler

class AutoPotController:
    def __init__(self):
        # Set up logging
        self.log_filename = setup_logging()
        logging.info("Initializing AutoPotController")
        
        # Screen resolution
        self.screen_width = 1920
        self.screen_height = 1080
        
        try:
            import pyautogui
            self.screen_width, self.screen_height = pyautogui.size()
            logging.info(f"Screen resolution: {self.screen_width}x{self.screen_height}")
        except Exception as e:
            logging.warning(f"Could not detect screen resolution: {e}")
            logging.info(f"Using default resolution: {self.screen_width}x{self.screen_height}")

        # Configuration
        self.config = self.load_config()

        # Thresholds
        self.health_threshold = self.config.getfloat("Thresholds", "health", fallback=0.35)
        self.mana_threshold = self.config.getfloat("Thresholds", "mana", fallback=0.25)

        # Hotkeys
        self.health_potion_key = self.config.get("Hotkeys", "health_potion", fallback="1")
        self.mana_potion_key = self.config.get("Hotkeys", "mana_potion", fallback="2")
        self.toggle_key = self.config.get("Hotkeys", "toggle", fallback="f12").lower()

        # Screen positions
        self.health_bar_pos = self.parse_position(
            self.config.get("ScreenPositions", "health_bar", fallback="0.08,0.95,0.09,0.98")
        )
        self.mana_bar_pos = self.parse_position(
            self.config.get("ScreenPositions", "mana_bar", fallback="0.75,0.95,0.76,0.98")
        )
        
        logging.info(f"Health bar position: {self.health_bar_pos}")
        logging.info(f"Mana bar position: {self.mana_bar_pos}")

        # State
        self.active = False
        self.health_last_used = 0
        self.mana_last_used = 0
        self.health_cooldown = self.config.getfloat("Cooldowns", "health_potion", fallback=4.0)
        self.mana_cooldown = self.config.getfloat("Cooldowns", "mana_potion", fallback=7.0)

        # Current values
        self.current_health = 1.0
        self.current_mana = 1.0
        
        # Debug mode
        self.debug_mode = self.config.getboolean("Debug", "enabled", fallback=False)
        
        # Message log
        self.messages = []
        self.max_messages = 3  # Fewer messages for compact display

        # Initialize monitor thread variable (FIXED: was missing this initialization)
        self.monitor_thread = None

        # Start display thread
        self.display_active = True
        self.display_thread = threading.Thread(target=self.display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()
        
        # Add welcome message
        self.add_message(f"{Fore.GREEN}Auto-Potion ready! Press {Fore.YELLOW}{self.toggle_key.upper()}{Fore.GREEN} to toggle.")
        self.add_message(f"{Fore.CYAN}Logs are being saved to: {os.path.basename(self.log_filename)}")

        # IMPORTANT: Set up hotkeys AFTER starting the display thread
        # This is crucial for F12 to work properly
        # Delay the hotkey setup slightly to ensure it works
        time.sleep(0.5)
        self.setup_hotkeys()

    def load_config(self):
        config = configparser.ConfigParser()
        config_path = "poe2_autopot_config.ini"

        if os.path.exists(config_path):
            config.read(config_path)
            logging.info(f"Loaded configuration from {config_path}")
        else:
            # Create default config
            config["Thresholds"] = {"health": "0.65", "mana": "0.25"}
            config["Hotkeys"] = {
                "health_potion": "1",
                "mana_potion": "2",
                "toggle": "F12",
            }
            config["ScreenPositions"] = {
                "health_bar": "0.08,0.95,0.09,0.98",
                "mana_bar": "0.75,0.95,0.76,0.98",
            }
            config["Cooldowns"] = {"health_potion": "2.0", "mana_potion": "4.0"}
            config["Debug"] = {"enabled": "false"}

            with open(config_path, "w") as f:
                config.write(f)
            logging.info(f"Created default configuration file at {config_path}")

        return config

    def parse_position(self, pos_str):
        """Convert position string to screen coordinates"""
        try:
            x1, y1, x2, y2 = map(float, pos_str.split(","))
            x1_px = max(0, min(int(x1 * self.screen_width), self.screen_width))
            y1_px = max(0, min(int(y1 * self.screen_height), self.screen_height))
            x2_px = max(0, min(int(x2 * self.screen_width), self.screen_width))
            y2_px = max(0, min(int(y2 * self.screen_height), self.screen_height))
            
            # Ensure valid rectangle
            if x1_px >= x2_px:
                x2_px = x1_px + 5
            if y1_px >= y2_px:
                y2_px = y1_px + 10
                
            return (x1_px, y1_px, x2_px, y2_px)
        except Exception as e:
            logging.error(f"Error parsing position '{pos_str}': {e}")
            return (0, 0, 10, 10)

    def setup_hotkeys(self):
        """
        Set up keyboard hotkeys with robust error handling
        """
        try:
            # Define global hooks for key functions
            global toggle_function, calibrate_function, debug_function
            
            # Store reference to the controller instance
            controller = self
            
            # Define global functions to handle key presses
            def toggle_function():
                try:
                    logging.info("F12 pressed - toggling auto-potion")
                    controller.toggle()
                except Exception as e:
                    logging.error(f"Error in toggle function: {e}")
                    logging.error(traceback.format_exc())
                
            def calibrate_function():
                try:
                    logging.info("C pressed - starting calibration")
                    controller.start_calibration()
                except Exception as e:
                    logging.error(f"Error in calibration function: {e}")
                    logging.error(traceback.format_exc())
                
            def debug_function():
                try:
                    logging.info("D pressed - toggling debug mode")
                    controller.toggle_debug()
                except Exception as e:
                    logging.error(f"Error in debug function: {e}")
                    logging.error(traceback.format_exc())
            
            # Clear any existing hotkeys
            keyboard.unhook_all()
            
            # Register the hotkeys with the global functions
            keyboard.add_hotkey(self.toggle_key, toggle_function)
            keyboard.add_hotkey('c', calibrate_function)
            keyboard.add_hotkey('d', debug_function)
            
            logging.info(f"Hotkeys set up: {self.toggle_key} toggle, C calibrate, D debug")
        except Exception as e:
            logging.error(f"Error setting up hotkeys: {e}")
            logging.error(traceback.format_exc())

    def toggle_debug(self):
        """Toggle debug mode"""
        try:
            self.debug_mode = not self.debug_mode
            self.config["Debug"]["enabled"] = str(self.debug_mode)
            with open("poe2_autopot_config.ini", "w") as f:
                self.config.write(f)
                
            self.add_message(f"{Fore.MAGENTA}Debug mode {'ON' if self.debug_mode else 'OFF'}")
            logging.info(f"Debug mode {'enabled' if self.debug_mode else 'disabled'}")
            
            # Create debug folder if debug mode is enabled
            if self.debug_mode and not os.path.exists("debug"):
                os.makedirs("debug")
        except Exception as e:
            logging.error(f"Error toggling debug mode: {e}")
            logging.error(traceback.format_exc())

    def add_message(self, message):
        """Add a message to the log"""
        try:
            timestamp = time.strftime("%H:%M:%S")
            self.messages.append(f"[{timestamp}] {message}")
            if len(self.messages) > self.max_messages:
                self.messages.pop(0)  # Remove oldest message
            print(message)  # Also print to console for immediate feedback
            
            # Add to log file if it's important
            if "error" in message.lower() or "fail" in message.lower():
                logging.error(message)
            else:
                logging.info(message)
        except Exception as e:
            logging.error(f"Error adding message: {e}")

    def toggle(self):
        """Toggle auto-potion on/off with enhanced error logging"""
        try:
            logging.info(f"Toggle called, current state: {self.active}")
            
            if self.active:
                self.active = False
                self.add_message(f"{Fore.RED}Auto-potion DEACTIVATED")
                logging.info("Auto-potion deactivated")
                # FIXED: This line had the error - using monitor_thread
                if self.monitor_thread and self.monitor_thread.is_alive():
                    logging.info("Stopping monitor thread")
                    self.monitor_thread = None
            else:
                self.active = True
                self.add_message(f"{Fore.GREEN}Auto-potion ACTIVATED")
                self.add_message(f"{Fore.YELLOW}Thresholds: HP {self.health_threshold*100:.0f}% MP {self.mana_threshold*100:.0f}%")
                logging.info(f"Auto-potion activated. HP threshold: {self.health_threshold:.0%} MP threshold: {self.mana_threshold:.0%}")
                
                # Start monitoring in a new thread
                # FIXED: This line had the error - using monitor_thread
                if not self.monitor_thread or not self.monitor_thread.is_alive():
                    logging.info("Starting monitor thread")
                    self.monitor_thread = threading.Thread(target=self.monitor_loop)
                    self.monitor_thread.daemon = True
                    self.monitor_thread.start()
                    logging.info("Monitor thread started")
        except Exception as e:
            logging.error(f"Error in toggle function: {e}")
            logging.error(traceback.format_exc())
            self.add_message(f"{Fore.RED}Error toggling: {str(e)[:50]}")

    def save_debug_image(self, img, name):
        """Save an image for debugging"""
        if self.debug_mode:
            try:
                if not os.path.exists("debug"):
                    os.makedirs("debug")
                img.save(f"debug/{name}")
                logging.debug(f"Saved debug image: {name}")
            except Exception as e:
                logging.error(f"Error saving debug image: {e}")

    def check_health_level(self):
        """Health level detection specially optimized for POE2"""
        try:
            # Capture health bar region
            img = ImageGrab.grab(bbox=self.health_bar_pos)
            if not img:
                logging.warning("Failed to capture health bar region")
                return self.current_health
                    
            # Save debug image
            if self.debug_mode:
                self.save_debug_image(img, "health_capture.png")
                    
            # Convert to numpy array
            img_array = np.array(img)
            if img_array.size == 0:
                logging.warning("Empty health bar image")
                return self.current_health
            
            # POE2-specific detection based on red pixels
            height, width, _ = img_array.shape
            
            # First pass: detect if any red pixels exist (to handle the 0% case)
            has_red_pixels = False
            for y in range(height):
                for x in range(width):
                    r, g, b = img_array[y, x]
                    if r > 60 and r > g*1.5 and r > b*1.5:
                        has_red_pixels = True
                        break
                if has_red_pixels:
                    break
            
            if not has_red_pixels:
                # No red pixels at all - health is likely 0%
                if self.debug_mode:
                    self.add_message(f"{Fore.MAGENTA}No health pixels detected - possible 0%")
                return 0.0
            
            # Simple approach: Count red pixels and compare to total size
            red_pixels = 0
            total_pixels = height * width
            
            # POE2 health is typically red
            for y in range(height):
                for x in range(width):
                    r, g, b = img_array[y, x]
                    # Less strict red detection - POE2 health can be various shades
                    if r > 60 and r > max(g, b)*1.3:
                        red_pixels += 1
            
            # Calculate percentage - POE2 health bar may not fill entire capture area
            health_percent = min(1.0, max(0.0, red_pixels / (total_pixels * 0.8)))
            
            # Adjust for POE2's health bar visual characteristics
            health_percent = health_percent * 1.2  # Scale to account for partially filled capture area
            health_percent = min(1.0, health_percent)  # Cap at 100%
            
            # Apply light smoothing to avoid jitter
            if abs(health_percent - self.current_health) < 0.4:
                smoothed_health = 0.7 * health_percent + 0.3 * self.current_health
            else:
                # For larger jumps, check if health seems to be very low or very high
                if health_percent < 0.1 or health_percent > 0.9:
                    # Give more weight to extreme values as they're likely correct
                    smoothed_health = 0.85 * health_percent + 0.15 * self.current_health
                else:
                    # For mid-range jumps, be more conservative
                    logging.warning(f"Health jump: {self.current_health:.2f} -> {health_percent:.2f}")
                    smoothed_health = 0.5 * health_percent + 0.5 * self.current_health
            
            health_percent = smoothed_health
            
            if self.debug_mode:
                self.add_message(f"{Fore.MAGENTA}Health: {red_pixels}/{total_pixels} = {health_percent:.2f}")
                logging.debug(f"Health calculation: {red_pixels}/{total_pixels} = {health_percent:.2f}")
            
            # Use health potion if needed
            current_time = time.time()
            if (health_percent < self.health_threshold and 
                current_time - self.health_last_used > self.health_cooldown):
                # Add a small delay to verify reading is stable
                time.sleep(0.1)
                verification = self.quick_check_health()
                if verification < self.health_threshold * 1.2:  # 20% safety margin
                    self.add_message(f"{Fore.RED}Using health potion at {health_percent:.0%}")
                    logging.info(f"Using health potion at {health_percent:.0%}")
                    keyboard.press_and_release(self.health_potion_key)
                    self.health_last_used = current_time
            
            return health_percent
        
        except Exception as e:
            logging.error(f"Error checking health level: {e}")
            logging.error(traceback.format_exc())
            if self.debug_mode:
                self.add_message(f"{Fore.RED}Health error: {str(e)[:50]}")
            return self.current_health

    def quick_check_health(self):
        """Quick verification check for health level - simpler method"""
        try:
            img = ImageGrab.grab(bbox=self.health_bar_pos)
            if not img:
                return self.current_health
            
            img_array = np.array(img)
            if img_array.size == 0:
                return self.current_health
            
            # Very simple check - just count red pixels
            red_pixels = 0
            total_pixels = img_array.shape[0] * img_array.shape[1]
            
            for y in range(img_array.shape[0]):
                for x in range(img_array.shape[1]):
                    r, g, b = img_array[y, x]
                    if r > 60 and r > max(g, b)*1.3:
                        red_pixels += 1
            
            return min(1.0, max(0.0, red_pixels / (total_pixels * 0.7)))
        
        except Exception:
            return self.current_health

    def check_mana_level(self):
        """Mana level detection optimized for POE2"""
        try:
            # Capture mana bar region
            img = ImageGrab.grab(bbox=self.mana_bar_pos)
            if not img:
                logging.warning("Failed to capture mana bar region")
                return self.current_mana
                    
            # Save debug image
            if self.debug_mode:
                self.save_debug_image(img, "mana_capture.png")
                    
            # Convert to numpy array
            img_array = np.array(img)
            if img_array.size == 0:
                logging.warning("Empty mana bar image")
                return self.current_mana
            
            # POE2-specific detection based on blue pixels
            height, width, _ = img_array.shape
            
            # First pass: detect if any blue pixels exist (to handle the 0% case)
            has_blue_pixels = False
            for y in range(height):
                for x in range(width):
                    r, g, b = img_array[y, x]
                    if b > 60 and b > r*1.5 and b > g*1.5:
                        has_blue_pixels = True
                        break
                if has_blue_pixels:
                    break
            
            if not has_blue_pixels:
                # No blue pixels at all - mana is likely 0%
                if self.debug_mode:
                    self.add_message(f"{Fore.MAGENTA}No mana pixels detected - possible 0%")
                return 0.0
            
            # Simple approach: Count blue pixels and compare to total size
            blue_pixels = 0
            total_pixels = height * width
            
            # POE2 mana is typically blue
            for y in range(height):
                for x in range(width):
                    r, g, b = img_array[y, x]
                    # Less strict blue detection - POE2 mana can be various shades
                    if b > 60 and b > max(r, g)*1.3:
                        blue_pixels += 1
            
            # Calculate percentage - POE2 mana bar may not fill entire capture area
            mana_percent = min(1.0, max(0.0, blue_pixels / (total_pixels * 0.8)))
            
            # Adjust for POE2's mana bar visual characteristics
            mana_percent = mana_percent * 1.2  # Scale to account for partially filled capture area
            mana_percent = min(1.0, mana_percent)  # Cap at 100%
            
            # Apply light smoothing to avoid jitter
            if abs(mana_percent - self.current_mana) < 0.4:
                smoothed_mana = 0.7 * mana_percent + 0.3 * self.current_mana
            else:
                # For larger jumps, check if mana seems to be very low or very high
                if mana_percent < 0.1 or mana_percent > 0.9:
                    # Give more weight to extreme values as they're likely correct
                    smoothed_mana = 0.85 * mana_percent + 0.15 * self.current_mana
                else:
                    # For mid-range jumps, be more conservative
                    logging.warning(f"Mana jump: {self.current_mana:.2f} -> {mana_percent:.2f}")
                    smoothed_mana = 0.5 * mana_percent + 0.5 * self.current_mana
            
            mana_percent = smoothed_mana
            
            if self.debug_mode:
                self.add_message(f"{Fore.MAGENTA}Mana: {blue_pixels}/{total_pixels} = {mana_percent:.2f}")
                logging.debug(f"Mana calculation: {blue_pixels}/{total_pixels} = {mana_percent:.2f}")
            
            # Use mana potion if needed
            current_time = time.time()
            if (mana_percent < self.mana_threshold and 
                current_time - self.mana_last_used > self.mana_cooldown):
                # Add a small delay to verify reading is stable
                time.sleep(0.1)
                verification = self.quick_check_mana()
                if verification < self.mana_threshold * 1.2:  # 20% safety margin
                    self.add_message(f"{Fore.BLUE}Using mana potion at {mana_percent:.0%}")
                    logging.info(f"Using mana potion at {mana_percent:.0%}")
                    keyboard.press_and_release(self.mana_potion_key)
                    self.mana_last_used = current_time
            
            return mana_percent
        
        except Exception as e:
            logging.error(f"Error checking mana level: {e}")
            logging.error(traceback.format_exc())
            if self.debug_mode:
                self.add_message(f"{Fore.RED}Mana error: {str(e)[:50]}")
            return self.current_mana

    def quick_check_mana(self):
        """Quick verification check for mana level - simpler method"""
        try:
            img = ImageGrab.grab(bbox=self.mana_bar_pos)
            if not img:
                return self.current_mana
            
            img_array = np.array(img)
            if img_array.size == 0:
                return self.current_mana
            
            # Very simple check - just count blue pixels
            blue_pixels = 0
            total_pixels = img_array.shape[0] * img_array.shape[1]
            
            for y in range(img_array.shape[0]):
                for x in range(img_array.shape[1]):
                    r, g, b = img_array[y, x]
                    if b > 60 and b > max(r, g)*1.3:
                        blue_pixels += 1
            
            return min(1.0, max(0.0, blue_pixels / (total_pixels * 0.7)))
        
        except Exception:
            return self.current_mana
    def display_loop(self):
        """More compact and efficient display with HP and MP on separate lines"""
        last_display = ""
        last_display_time = 0
        display_refresh_rate = 0.5  # Update display twice per second
        
        try:
            while self.display_active:
                try:
                    current_time = time.time()
                    
                    # Only update display at refresh rate
                    if current_time - last_display_time < display_refresh_rate:
                        time.sleep(0.1)
                        continue
                        
                    last_display_time = current_time
                    
                    # Create a compact but informative display
                    display = "\n"
                    display += f"{Fore.CYAN}{'=' * 50}\n"
                    
                    # Status with color - more compact format
                    status = "ACTIVE" if self.active else "INACTIVE"
                    status_color = Fore.GREEN if self.active else Fore.RED
                    display += f"{Fore.CYAN}POE2 AUTO-POTION: {status_color}{status}{Style.RESET_ALL}\n"
                    
                    # Health bar on its own line
                    health_percent = int(self.current_health * 100)
                    health_color = Fore.GREEN
                    if health_percent < 30:
                        health_color = Fore.RED
                    elif health_percent < 70:
                        health_color = Fore.YELLOW
                    
                    # More compact bar display
                    bar_width = 25  # Slightly longer bars for separate lines
                    health_filled = int(bar_width * self.current_health)
                    health_bar = f"{health_color}{'#' * health_filled}{'-' * (bar_width - health_filled)}{Style.RESET_ALL}"
                    display += f"HP: {health_bar} {health_percent}%\n"
                    
                    # Mana bar on its own line
                    mana_percent = int(self.current_mana * 100)
                    mana_filled = int(bar_width * self.current_mana)
                    mana_bar = f"{Fore.BLUE}{'#' * mana_filled}{'-' * (bar_width - mana_filled)}{Style.RESET_ALL}"
                    display += f"MP: {mana_bar} {mana_percent}%\n"
                    
                    # Cooldowns on one line
                    health_cooldown = max(0, self.health_cooldown - (current_time - self.health_last_used))
                    mana_cooldown = max(0, self.mana_cooldown - (current_time - self.mana_last_used))
                    
                    display += f"Cooldowns - HP: {health_cooldown:.1f}s | MP: {mana_cooldown:.1f}s\n"
                    
                    # Compact monitoring regions
                    if self.debug_mode:
                        display += f"HP Region: {self.health_bar_pos} | MP Region: {self.mana_bar_pos}\n"
                    
                    # Log file information
                    display += f"Log: {os.path.basename(self.log_filename)}\n"
                    
                    # Message log with minimal decoration
                    display += f"{Fore.CYAN}{'=' * 50}\n"
                    
                    for msg in self.messages:
                        display += msg + "\n"
                        
                    # Controls in compact form
                    display += f"{Fore.CYAN}{'=' * 50}\n"
                    display += f"{self.toggle_key.upper()}: Toggle | C: Calibrate | D: Debug | Ctrl+C: Exit\n"
                    
                    # Only update if display has changed
                    if display != last_display:
                        # Clear console and show new display
                        if os.name == 'nt':  # Windows
                            os.system('cls')
                        else:  # Unix/Linux/MacOS
                            os.system('clear')
                        
                        print(display, end='')
                        last_display = display
                    
                    time.sleep(0.1)
                except Exception as e:
                    logging.error(f"Error updating display: {e}")
                    logging.error(traceback.format_exc())
                    time.sleep(1)  # Wait a bit before trying again
                
        except Exception as e:
            logging.error(f"Fatal error in display loop: {e}")
            logging.error(traceback.format_exc())
            
    def monitor_loop(self):
        """Main monitoring loop with error logging"""
        try:
            self.add_message(f"{Fore.GREEN}Monitoring started...")
            logging.info("Monitoring loop started")
            
            last_status_time = 0
            status_update_interval = 5.0  # Update status every 5 seconds
            
            while self.active:
                try:
                    current_time = time.time()
                    
                    # Check health and use potion if needed
                    health_percent = self.check_health_level()
                    self.current_health = health_percent
                    
                    # Check mana and use potion if needed
                    mana_percent = self.check_mana_level()
                    self.current_mana = mana_percent
                    
                    # Update status periodically
                    if current_time - last_status_time > status_update_interval and not self.debug_mode:
                        # Only update status message occasionally to avoid spam
                        self.add_message(f"HP: {health_percent:.0%} MP: {mana_percent:.0%}")
                        last_status_time = current_time
                    
                    # Sleep between checks
                    time.sleep(0.2)
                except Exception as e:
                    logging.error(f"Error in monitoring cycle: {e}")
                    logging.error(traceback.format_exc())
                    self.add_message(f"{Fore.RED}Monitor error: {str(e)[:50]}")
                    time.sleep(1)  # Wait a bit before continuing
            
            logging.info("Monitoring loop ended (deactivated)")
        except Exception as e:
            logging.error(f"Fatal error in monitor loop: {e}")
            logging.error(traceback.format_exc())
            self.active = False
            self.add_message(f"{Fore.RED}Fatal monitor error: {str(e)[:50]}")

    def start_calibration(self):
        """Start the calibration process with error logging"""
        try:
            # Stop monitoring if active
            was_active = self.active
            if was_active:
                self.toggle()  # Turn off
            
            logging.info("Starting calibration process")
            
            # Clear terminal to make sure directions are visible
            if os.name == 'nt':  # Windows
                os.system('cls')
            else:  # Unix/Linux/MacOS
                os.system('clear')
            
            print(f"{Fore.YELLOW}{'=' * 50}")
            print(f"{Fore.YELLOW}POE2 CALIBRATION STARTED")
            print(f"{Fore.YELLOW}{'=' * 50}\n")
            
            print(f"{Fore.WHITE}This tool will help you calibrate your HP/MP positions.")
            print(f"{Fore.WHITE}Follow the instructions carefully.\n")
            
            # Run the calibration
            self.run_calibration()
            
            # Reload configuration after calibration
            self.config = self.load_config()
            
            # Update positions
            self.health_bar_pos = self.parse_position(
                self.config.get("ScreenPositions", "health_bar")
            )
            self.mana_bar_pos = self.parse_position(
                self.config.get("ScreenPositions", "mana_bar")
            )
            
            logging.info(f"Calibration complete. New positions - Health: {self.health_bar_pos}, Mana: {self.mana_bar_pos}")
            self.add_message(f"{Fore.GREEN}Calibration complete!")
            
            # Restore monitoring if it was active
            if was_active:
                self.toggle()
        except Exception as e:
            logging.error(f"Error in calibration startup: {e}")
            logging.error(traceback.format_exc())
            self.add_message(f"{Fore.RED}Calibration error: {str(e)[:50]}")
            
            # Make sure we restore hotkeys
            self.setup_hotkeys()

    def run_calibration(self):
        """Enhanced calibration that precisely identifies the bar positions"""
        # Clear existing hotkeys during calibration
        try:
            keyboard.unhook_all()
            logging.info("Keyboard hooks cleared for calibration")
        except Exception as e:
            logging.error(f"Error clearing keyboard hooks: {e}")
                
        try:
            # Get screen resolution
            pyautogui_available = False
            try:
                import pyautogui
                pyautogui_available = True
                print(f"{Fore.GREEN}Mouse position detection is available.\n")
                logging.info("PyAutoGUI is available for calibration")
            except ImportError:
                pyautogui_available = False
                print(f"{Fore.YELLOW}PyAutoGUI not installed - manual coordinate entry required.\n")
                logging.warning("PyAutoGUI not installed - using manual coordinate entry")
            
            # Health bar calibration
            print(f"{Fore.RED}{'=' * 50}")
            print(f"{Fore.RED}HEALTH BAR CALIBRATION")
            print(f"{Fore.RED}{'=' * 50}\n")
            
            health_bar_pos = None
            
            if pyautogui_available:
                # Health bar - top position
                print(f"{Fore.WHITE}1. Move your cursor to the TOP of your health bar")
                print(f"{Fore.WHITE}   Be as precise as possible with placement")
                input(f"{Fore.WHITE}2. Press Enter when ready...")
                health_top = pyautogui.position()
                print(f"{Fore.GREEN}Position recorded: {health_top}\n")
                logging.info(f"Health top position: {health_top}")
                
                # Health bar - bottom position
                print(f"{Fore.WHITE}1. Move your cursor to the BOTTOM of your health bar")
                print(f"{Fore.WHITE}   Be as precise as possible with placement")
                input(f"{Fore.WHITE}2. Press Enter when ready...")
                health_bottom = pyautogui.position()
                print(f"{Fore.GREEN}Position recorded: {health_bottom}\n")
                logging.info(f"Health bottom position: {health_bottom}")
                
                # Auto-refine health bar position
                health_bar_pos = self.refine_bar_position(health_top, health_bottom, "health")
                
                if health_bar_pos:
                    print(f"\n{Fore.GREEN}Refined health bar position: {health_bar_pos}")
                    logging.info(f"Refined health bar position: {health_bar_pos}")
                else:
                    # Fallback to manual calculation if auto-refine fails
                    health_center_x = (health_top[0] + health_bottom[0]) // 2
                    strip_width = 5
                    y_min = min(health_top[1], health_bottom[1])
                    y_max = max(health_top[1], health_bottom[1])
                    
                    health_bar_pos = (
                        health_center_x - strip_width // 2,
                        y_min,
                        health_center_x + strip_width // 2,
                        y_max
                    )
            else:
                # Manual input of coordinates (unchanged)
                print(f"{Fore.WHITE}Enter health bar coordinates manually:\n")
                try:
                    x1 = int(input(f"{Fore.WHITE}Health bar LEFT edge (x): {Fore.YELLOW}"))
                    x2 = int(input(f"{Fore.WHITE}Health bar RIGHT edge (x): {Fore.YELLOW}"))
                    y1 = int(input(f"{Fore.WHITE}Health bar TOP edge (y): {Fore.YELLOW}"))
                    y2 = int(input(f"{Fore.WHITE}Health bar BOTTOM edge (y): {Fore.YELLOW}"))
                    
                    # Calculate center strip
                    center_x = (x1 + x2) // 2
                    strip_width = 5
                    
                    health_bar_pos = (
                        center_x - strip_width // 2,
                        y1,
                        center_x + strip_width // 2,
                        y2
                    )
                    logging.info(f"Manual health bar coordinates: ({x1},{y1}) to ({x2},{y2})")
                except ValueError as e:
                    logging.error(f"Invalid input for health bar: {e}")
                    print(f"{Fore.RED}Invalid input. Please enter numbers only.")
                    return
            
            print(f"\n{Fore.GREEN}Health bar monitoring region: {health_bar_pos}")
            logging.info(f"Final health bar region: {health_bar_pos}")
            
            # Mana bar calibration
            print(f"\n{Fore.BLUE}{'=' * 50}")
            print(f"{Fore.BLUE}MANA BAR CALIBRATION")
            print(f"{Fore.BLUE}{'=' * 50}\n")
            
            mana_bar_pos = None
            
            if pyautogui_available:
                # Mana bar - top position
                print(f"{Fore.WHITE}1. Move your cursor to the TOP of your mana bar")
                print(f"{Fore.WHITE}   Be as precise as possible with placement")
                input(f"{Fore.WHITE}2. Press Enter when ready...")
                mana_top = pyautogui.position()
                print(f"{Fore.GREEN}Position recorded: {mana_top}\n")
                logging.info(f"Mana top position: {mana_top}")
                
                # Mana bar - bottom position
                print(f"{Fore.WHITE}1. Move your cursor to the BOTTOM of your mana bar")
                print(f"{Fore.WHITE}   Be as precise as possible with placement")
                input(f"{Fore.WHITE}2. Press Enter when ready...")
                mana_bottom = pyautogui.position()
                print(f"{Fore.GREEN}Position recorded: {mana_bottom}\n")
                logging.info(f"Mana bottom position: {mana_bottom}")
                
                # Auto-refine mana bar position
                mana_bar_pos = self.refine_bar_position(mana_top, mana_bottom, "mana")
                
                if mana_bar_pos:
                    print(f"\n{Fore.GREEN}Refined mana bar position: {mana_bar_pos}")
                    logging.info(f"Refined mana bar position: {mana_bar_pos}")
                else:
                    # Fallback to manual calculation if auto-refine fails
                    mana_center_x = (mana_top[0] + mana_bottom[0]) // 2
                    strip_width = 5
                    y_min = min(mana_top[1], mana_bottom[1])
                    y_max = max(mana_top[1], mana_bottom[1])
                    
                    mana_bar_pos = (
                        mana_center_x - strip_width // 2,
                        y_min,
                        mana_center_x + strip_width // 2,
                        y_max
                    )
            else:
                # Manual input of coordinates (unchanged)
                print(f"{Fore.WHITE}Enter mana bar coordinates manually:\n")
                try:
                    x1 = int(input(f"{Fore.WHITE}Mana bar LEFT edge (x): {Fore.YELLOW}"))
                    x2 = int(input(f"{Fore.WHITE}Mana bar RIGHT edge (x): {Fore.YELLOW}"))
                    y1 = int(input(f"{Fore.WHITE}Mana bar TOP edge (y): {Fore.YELLOW}"))
                    y2 = int(input(f"{Fore.WHITE}Mana bar BOTTOM edge (y): {Fore.YELLOW}"))
                    
                    # Calculate center strip
                    center_x = (x1 + x2) // 2
                    strip_width = 5
                    
                    mana_bar_pos = (
                        center_x - strip_width // 2,
                        y1,
                        center_x + strip_width // 2,
                        y2
                    )
                    logging.info(f"Manual mana bar coordinates: ({x1},{y1}) to ({x2},{y2})")
                except ValueError as e:
                    logging.error(f"Invalid input for mana bar: {e}")
                    print(f"{Fore.RED}Invalid input. Please enter numbers only.")
                    return
            
            print(f"\n{Fore.GREEN}Mana bar monitoring region: {mana_bar_pos}")
            logging.info(f"Final mana bar region: {mana_bar_pos}")
            
            # Save configuration
            try:
                # Convert to normalized coordinates
                norm_health = (
                    health_bar_pos[0]/self.screen_width,
                    health_bar_pos[1]/self.screen_height,
                    health_bar_pos[2]/self.screen_width,
                    health_bar_pos[3]/self.screen_height
                )
                
                norm_mana = (
                    mana_bar_pos[0]/self.screen_width,
                    mana_bar_pos[1]/self.screen_height,
                    mana_bar_pos[2]/self.screen_width,
                    mana_bar_pos[3]/self.screen_height
                )
                
                self.config['ScreenPositions']['health_bar'] = f"{norm_health[0]:.4f},{norm_health[1]:.4f},{norm_health[2]:.4f},{norm_health[3]:.4f}"
                self.config['ScreenPositions']['mana_bar'] = f"{norm_mana[0]:.4f},{norm_mana[1]:.4f},{norm_mana[2]:.4f},{norm_mana[3]:.4f}"
                
                with open('poe2_autopot_config.ini', 'w') as f:
                    self.config.write(f)
                    
                print(f"\n{Fore.GREEN}Configuration saved successfully!")
                logging.info("Calibration configuration saved")
                
                # Update the positions in the current instance
                self.health_bar_pos = health_bar_pos
                self.mana_bar_pos = mana_bar_pos
                
                # Test calibration
                print(f"\n{Fore.CYAN}Testing calibration...")
                
                # Test health level
                health_img = ImageGrab.grab(bbox=self.health_bar_pos)
                if health_img:
                    if self.debug_mode:
                        self.save_debug_image(health_img, "health_calibration.png")
                    health_percent = self.check_health_level()
                    print(f"{Fore.RED}Health level: {health_percent:.0%}")
                    logging.info(f"Calibration test - Health level: {health_percent:.0%}")
                
                # Test mana level
                mana_img = ImageGrab.grab(bbox=self.mana_bar_pos)
                if mana_img:
                    if self.debug_mode:
                        self.save_debug_image(mana_img, "mana_calibration.png")
                    mana_percent = self.check_mana_level()
                    print(f"{Fore.BLUE}Mana level: {mana_percent:.0%}")
                    logging.info(f"Calibration test - Mana level: {mana_percent:.0%}")
                
                print(f"\n{Fore.CYAN}{'=' * 50}")
                print(f"{Fore.CYAN}CALIBRATION COMPLETE")
                print(f"{Fore.CYAN}{'=' * 50}")
                
            except Exception as e:
                logging.error(f"Error saving calibration configuration: {e}")
                logging.error(traceback.format_exc())
                print(f"\n{Fore.RED}Error saving configuration: {e}")
            
            # Wait for user acknowledgment
            input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL}")
            
        except Exception as e:
            logging.error(f"Error during calibration: {e}")
            logging.error(traceback.format_exc())
            print(f"\n{Fore.RED}Error during calibration: {e}")
            input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL}")
        
        # Restore hotkeys with a direct call to re-initialize them
        try:
            self.setup_hotkeys()
            logging.info("Hotkeys restored after calibration")
        except Exception as e:
            logging.error(f"Error restoring hotkeys after calibration: {e}")

    def refine_bar_position(self, top_pos, bottom_pos, bar_type):
        """
        Automatically refines the bar position by scanning for the exact bar edges
        
        Args:
            top_pos: (x,y) tuple of user-indicated top position
            bottom_pos: (x,y) tuple of user-indicated bottom position
            bar_type: "health" or "mana" to determine color to scan for
            
        Returns:
            Tuple of (x1, y1, x2, y2) for the refined bar position or None if detection fails
        """
        try:
            logging.info(f"Starting auto-refinement for {bar_type} bar")
            
            # Get approximate position
            center_x = (top_pos[0] + bottom_pos[0]) // 2
            y_min = min(top_pos[1], bottom_pos[1])
            y_max = max(top_pos[1], bottom_pos[1])
            
            # Add some margin for scanning
            scan_width = 50  # Wider area to scan for the bar
            scan_x_min = max(0, center_x - scan_width)
            scan_x_max = min(self.screen_width, center_x + scan_width)
            
            # Extend y range slightly
            scan_y_min = max(0, y_min - 5)
            scan_y_max = min(self.screen_height, y_max + 5)
            
            # Capture a larger area to analyze
            scan_area = (scan_x_min, scan_y_min, scan_x_max, scan_y_max)
            img = ImageGrab.grab(bbox=scan_area)
            
            if not img:
                logging.warning(f"Failed to capture {bar_type} bar scan area")
                return None
                
            # Save debug image
            if self.debug_mode:
                self.save_debug_image(img, f"{bar_type}_scan_area.png")
                
            # Convert to numpy array
            img_array = np.array(img)
            if img_array.size == 0:
                logging.warning(f"Empty {bar_type} bar image")
                return None
                
            # Define color thresholds based on bar type
            if bar_type == "health":
                # For health (red)
                def is_target_color(r, g, b):
                    return r > 50 and r > max(g, b) * 1.5
            else:
                # For mana (blue)
                def is_target_color(r, g, b):
                    return b > 50 and b > max(r, g) * 1.5
                    
            # Find the exact center of the bar (x-coordinate)
            color_counts_by_x = {}
            for x in range(img_array.shape[1]):
                count = 0
                for y in range(img_array.shape[0]):
                    r, g, b = img_array[y, x]
                    if is_target_color(r, g, b):
                        count += 1
                color_counts_by_x[x] = count
                
            # Find the x with maximum color count
            if not color_counts_by_x:
                logging.warning(f"No {bar_type} color found in scan area")
                return None
                
            max_count_x = max(color_counts_by_x.items(), key=lambda x: x[1])
            if max_count_x[1] == 0:
                logging.warning(f"No {bar_type} color found in scan area")
                return None
                
            refined_center_x = scan_x_min + max_count_x[0]
            logging.info(f"Refined {bar_type} bar center X: {refined_center_x}")
            
            # Find the exact top and bottom of the bar (y-coordinates)
            # Start by scanning from the center x position
            y_scan_width = 2  # Check a small x range around the center
            y_scan_min = max(0, refined_center_x - y_scan_width)
            y_scan_max = min(img_array.shape[1] - 1, refined_center_x + y_scan_width)
            
            # Find top edge
            refined_top = None
            for y in range(img_array.shape[0]):
                for x_offset in range(y_scan_min, y_scan_max + 1):
                    x = min(max(0, x_offset), img_array.shape[1] - 1)
                    r, g, b = img_array[y, x]
                    if is_target_color(r, g, b):
                        refined_top = scan_y_min + y
                        break
                if refined_top is not None:
                    break
                    
            # Find bottom edge
            refined_bottom = None
            for y in range(img_array.shape[0] - 1, -1, -1):
                for x_offset in range(y_scan_min, y_scan_max + 1):
                    x = min(max(0, x_offset), img_array.shape[1] - 1)
                    r, g, b = img_array[y, x]
                    if is_target_color(r, g, b):
                        refined_bottom = scan_y_min + y
                        break
                if refined_bottom is not None:
                    break
                    
            if refined_top is None or refined_bottom is None:
                logging.warning(f"Could not find {bar_type} bar edges")
                return None
                
            logging.info(f"Refined {bar_type} bar Y range: {refined_top} to {refined_bottom}")
            
            # Create a narrow strip centered on the detected bar
            strip_width = 5
            refined_bar_pos = (
                refined_center_x - strip_width // 2,
                refined_top,
                refined_center_x + strip_width // 2,
                refined_bottom
            )
            
            return refined_bar_pos
        
        except Exception as e:
            logging.error(f"Error refining {bar_type} bar position: {e}")
            logging.error(traceback.format_exc())
            return None

def main():
    """
    Main function with error logging
    """
    try:
        # Clear terminal
        if os.name == 'nt':  # Windows
            os.system('cls')
        else:  # Unix/Linux/MacOS
            os.system('clear')
        
        print(f"{Fore.CYAN}{'=' * 50}")
        print(f"{Fore.CYAN}POE2 AUTO-POTION UTILITY")
        print(f"{Fore.CYAN}{'=' * 50}\n")
        
        # Create the controller
        controller = AutoPotController()
        
        # Keep the program running
        print(f"{Fore.YELLOW}Press Ctrl+C to exit")
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        logging.info("Program terminated by user (Ctrl+C)")
        print(f"\n{Fore.YELLOW}Exiting...")
    except Exception as e:
        logging.error(f"Unhandled error in main: {e}")
        logging.error(traceback.format_exc())
        print(f"\n{Fore.RED}Error: {e}")
        traceback.print_exc()
        input(f"{Fore.YELLOW}Press Enter to exit...{Style.RESET_ALL}")

if __name__ == "__main__":
    main()