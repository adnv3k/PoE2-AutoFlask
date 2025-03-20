# PoE2-AutoFlask

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An automatic potion/flask manager for Path of Exile 2 that monitors your health and mana bars and triggers flasks when levels drop below configurable thresholds.

## Features

- **Intelligent Potion Management**: Automatically uses health and mana potions when levels drop below customizable thresholds
- **Robust Visual Detection**: Enhanced computer vision algorithms optimized for POE2's UI to monitor health and mana levels
- **Interactive Calibration**: Easy setup process with automated detection to precisely locate your UI elements
- **Configurable Hotkeys**: Customize which keys are used for potions and controls
- **Adaptive Monitoring**: Checks more frequently when health/mana levels are critical
- **Real-time UI**: Visual display of health and mana levels with color-coded status indicators
- **Comprehensive Logging**: Detailed logs for troubleshooting and tracking system behavior
- **Debug Mode**: Optional debug mode with detailed diagnostics and screenshot capturing
- **Error Recovery**: Robust error handling to maintain stability during extended play sessions
- **Toggle System**: Easily enable/disable with a hotkey
- **Cooldown Management**: Respects potion cooldown times

## Installation

### Prerequisites
- Python 3.6+
- Path of Exile 2

### Required Packages
```bash
pip install keyboard pillow numpy opencv-python colorama
```

### Setup
1. Clone this repository:
```bash
git clone https://github.com/yourusername/poe2-autoflask.git
cd poe2-autoflask
```

2. Run the script:
```bash
python autopot.py
```

3. Perform initial calibration by pressing 'C' and following the on-screen instructions

## Usage

- Press `F12` (default) to toggle the auto-flask system on/off
- Press `C` to enter calibration mode
- Press `D` to toggle debug mode
- Press `Ctrl+C` to exit the program

## Configuration

The script creates a configuration file (`poe2_autopot_config.ini`) with the following sections:

### Thresholds
- `health`: Percentage threshold for health flasks (default: 65%)
- `mana`: Percentage threshold for mana flasks (default: 25%)

### Hotkeys
- `health_potion`: Key to press for health flask (default: 1)
- `mana_potion`: Key to press for mana flask (default: 2)
- `toggle`: Key to toggle the system (default: F12)

### Screen Positions
- `health_bar`: Normalized coordinates of health bar (set during calibration)
- `mana_bar`: Normalized coordinates of mana bar (set during calibration)

### Cooldowns
- `health_potion`: Cooldown time for health flasks in seconds (default: 2.0)
- `mana_potion`: Cooldown time for mana flasks in seconds (default: 4.0)

### Debug
- `enabled`: Whether debug mode is enabled (default: false)

## How It Works

1. The script captures small regions of your screen where the health and mana bars are located
2. It uses enhanced color detection algorithms to determine the fill percentage of each bar
3. A verification system double-checks critical readings to prevent false triggers
4. When levels fall below the configured thresholds, it simulates keystrokes to use the appropriate flask
5. The system respects cooldown times to prevent wasteful flask usage
6. All actions are logged for troubleshooting and analysis

## Calibration

The calibration process has been enhanced:

1. Press 'C' to start calibration
2. Follow the on-screen instructions to identify your health and mana bars
3. The system will automatically refine the positions for optimal detection
4. Test readings are displayed immediately to verify calibration accuracy
5. The configuration is saved automatically

## Logging

The utility now includes comprehensive logging:

- All events are logged to timestamped files in the `logs` directory
- Critical errors are prominently displayed in the console
- In debug mode, screenshots of health/mana bar readings are saved to the `debug` directory
- Log files can be used to analyze and troubleshoot detection issues

## Legal Notice

This tool does not interact with the game client directly. It only:
1. Takes screenshots of specific regions
2. Analyzes those screenshots
3. Simulates regular keystrokes

This is designed to be compliant with Path of Exile's Terms of Service as it does not:
- Read or write to game memory
- Automate multiple actions with a single keystroke
- Perform actions without user supervision

However, use at your own risk. The developers are not responsible for any account actions that may result from using this tool.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This project is not affiliated with, endorsed by, or connected to Grinding Gear Games in any way.
