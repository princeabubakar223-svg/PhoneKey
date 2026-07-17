# 🔐 PhoneKey — Remote PC Lock/Unlock System

**PhoneKey** lets you lock/unlock your Windows laptop from your Android phone over **USB cable** or **WiFi**, with a Matrix-style lock screen, J.A.R.V.I.S voice assistant, and advanced vault features.

[![Version](https://img.shields.io/badge/version-11.0-green.svg)](https://github.com/yourusername/phonekey)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![Android](https://img.shields.io/badge/android-6.0+-green.svg)](https://android.com)

---

## 📱 Features

### 🔐 Security
- PIN / Password / Pattern unlock
- Auto-Lock after 1 minute inactivity
- Wake-on-LAN support
- Intrusion log with failed attempts
- Security mode (photo capture after 3 failed attempts)
- Emergency backup password (Ctrl+Alt+Shift+Q)

### 🎤 J.A.R.V.I.S Voice Assistant
- Voice commands via phone microphone
- Text commands support
- Urdu/Hindi auto-translation
- System control (shutdown, restart, volume, mute)
- App launcher (browser, notepad, cmd, calculator, paint)
- File operations (open, play, view, delete, copy, move, rename, hide)

### 📁 Vault (Remote File Browser)
- Browse laptop files/folders
- View images, play videos
- Preview documents (PDF, text, code)
- Audio playback with controls
- File management (delete, hide, rename)
- Context menu (long press)

### 📷 Live Camera
- Real-time webcam streaming
- Start/Stop controls
- Frame counter

---

## 🚀 Quick Start

### What You Need
| Item | Where to get |
|------|-------------|
| PhoneKey.apk | [Releases](../../releases) |
| master_phonekey.py | This repository |
| Python 3.8+ | [python.org](https://python.org) |
| ADB Platform Tools | [Android Developers](https://developer.android.com/tools/releases/platform-tools) |

---

## 💻 Laptop Setup (Windows)

### Step 1: Install Python
1. Download from [python.org](https://python.org)
2. **IMPORTANT**: Tick **"Add python.exe to PATH"**
3. Verify: Open Command Prompt → `python --version`

### Step 2: Install ADB (Android Debug Bridge)
1. Download **SDK Platform-Tools** for Windows:
https://developer.android.com/tools/releases/platform-tools

text
2. Extract to `C:\platform-tools\`
3. Note the path: `C:\platform-tools\adb.exe`

### Step 3: Download PhoneKey Files
```bash
# Create folder
mkdir C:\PhoneKey
cd C:\PhoneKey

# Place these files here:
# - master_phonekey.py
# - requirements.txt
# - Bhola Record.mp3 (optional - for funny voice)(use your own mp3 Sound
Step 4: Install Python Packages
bash
# Open Command Prompt as Administrator
cd C:\PhoneKey
pip install -r requirements.txt

# Optional: Install spaCy language model
python -m spacy download en_core_web_sm
Step 5: Configure master_phonekey.py
Open with Notepad and edit these settings:

python
# Path to ADB (from Step 2)
ADB_PATH = r"C:\platform-tools\adb.exe"

# Authentication
CORRECT_PIN = "1234"                    # Change this!
CORRECT_PASSWORD = ""                   # Change this!
CORRECT_PATTERN = "0-1-2-5-8"          # Pattern (0-8 grid)
BACKUP_PASSWORD = "     "              # Emergency unlock (CHANGE!)

# File Vault
VAULT_DIR = r"D:\\"                     # Drive to share

# Security
SECURITY_WRONG_THRESHOLD = 3            # Failed attempts before photo
⚠️ IMPORTANT: Change all default passwords!

Step 6: Run Installer
bash
# As Administrator
python master_phonekey.py --install
This automatically:

Installs all required packages

Disables USB power-saving

Adds Windows Firewall rules (ports 5000, 5001)

Creates startup task (runs on every login)

Step 7: Restart Laptop
The Matrix lock screen will appear automatically.

📱 Phone Setup
Step 1: Enable Developer Options
Settings → About Phone

Tap "Build Number" 7 times

Go back → Settings → Developer Options

Enable USB Debugging

Step 2: Install PhoneKey.apk
Download APK from Releases

Transfer to phone

Install (tap "Install anyway" for unknown sources)

First run: Allow Bluetooth permission

🎯 How to Use
🔌 Cable Mode
Connect phone via USB cable

First time: Tap "Always allow from this computer" → Allow

Open app → Select CABLE

Enter PIN → Tap EXECUTE UNLOCK

📶 WiFi Mode (No Cable)
Connect phone and laptop to same WiFi (or phone hotspot)

On laptop: Open CMD → ipconfig → note IPv4 Address

App → Select WIFI → Enter IP

Enter PIN → Tap EXECUTE UNLOCK

🔒 Lock Now
Tap 🔒 LOCK NOW button → Laptop locks instantly

💻 Wake Laptop (Wake-on-LAN)
Enable Wake-on-LAN in app settings

Laptop must be in sleep/hibernate mode

Tap 💻 WAKE LAPTOP

⏰ Auto-Lock
Toggle in settings

Locks automatically after 1 minute of inactivity

🗣️ J.A.R.V.I.S Voice Commands
Navigation
text
back, go back                    # Parent folder
go to [folder]                   # Navigate
open folder [name]               # Open folder
le chalo [name]                  # Urdu: go to
Media
text
play [file]                      # Play media
play video, play music           # Auto-play
view [image]                     # View image
dekhao [name]                    # Urdu: show
File Operations
text
delete [file]                    # Delete
copy [file]                      # Copy
move [file] to [folder]          # Move
rename [old] to [new]            # Rename
hide [file]                      # Hide
unhide [file]                    # Unhide
System Control
text
lock, band karo                  # Lock screen
shutdown, band karo             # Shutdown
restart, reboot                 # Restart
sleep, sula do                  # Sleep mode
volume up, awaz badhao          # Volume up
volume down, awaz kam karo      # Volume down
mute, awaz band karo            # Mute
Launch Apps
text
browser, chrome, internet, web  # Browser
notepad, notes                  # Notepad
cmd, command prompt             # CMD
explorer, file explorer         # Explorer
settings, system settings       # Settings
calculator, calc                # Calculator
paint, draw                     # Paint
wordpad, word                   # Wordpad
Utility
text
list files, show files, dir, ls # List contents
where, location, kahan          # Current directory
clear screen, show desktop      # Minimize all
funny, joke, make me laugh      # Play Bhola Record.mp3
help, madad                     # Show help
🆘 Emergency Backup Unlock
If phone can't connect:

On laptop: Press Ctrl + Alt + Shift + Q

Enter BACKUP_PASSWORD

Press Enter → Laptop unlocks

📁 Vault Features
Browse Files
Navigate D: drive (or custom VAULT_DIR)

View folders and files

Long press for context menu

Media Playback
Images: Full-screen viewer

Videos: ExoPlayer with controls

Audio: Player with visualizer

Documents: Text/PDF viewer

File Operations
Delete: Remove file/folder

Hide/Unhide: Toggle hidden

Rename: Change file name

📷 Live Camera
Tap 📹 LIVE CAM from main screen

Tap START to begin webcam stream

Real-time video from laptop camera

Tap STOP to end stream

🔧 Troubleshooting
Problem	Fix
"Connection refused"	Auto-retries for ~15 seconds — wait
USB debugging popup missing	Disable Windows "Fast Startup" in Power Options
Lock stops working	Tunnel auto-refreshes every 15 seconds
WiFi mode not connecting	Check IP with ipconfig, same network
Camera not working	Check webcam drivers, try different camera
Locked out completely	Use backup password: Ctrl+Alt+Shift+Q
Voice commands not working	Check microphone permissions, install spaCy
🛠️ Development
Build APK (if modifying)
bash
# Requires Android Studio
Build → Build App Bundle(s) / APK(s) → Build APK(s)
# Output: app/build/outputs/apk/debug/app-debug.apk
Run Python Script Manually
bash
# Without startup task
python master_phonekey.py
Uninstall
bash
# Remove startup task
schtasks /delete /tn "PhoneKey" /f

# Remove firewall rules
netsh advfirewall firewall delete rule name="PhoneKey"
netsh advfirewall firewall delete rule name="PhoneKeyVault"
🔐 Security Notes
CHANGE ALL DEFAULT PASSWORDS before use

Backup password is ultimate fallback — keep it secure

Security mode captures photos after 3 failed attempts

Intrusion log shows all authentication attempts

📦 Dependencies
Python Packages (requirements.txt)
text
pywin32>=306          # Windows API
keyboard>=0.13.5      # Hotkeys
opencv-python>=4.8.0  # Webcam
Pillow>=10.0.0        # Screenshots
spacy>=3.7.0          # NLP (optional)
textblob>=0.17.1      # Text analysis (optional)
fuzzywuzzy>=0.18.0    # Fuzzy matching (optional)
Ports Used
5000: Command TCP server

5001: HTTP vault server

File Locations
VAULT_DIR: D:\\ (configurable)

screenshots: D:\screenshots\

security_captures: D:\security_captures\

camera_snaps: D:\camera_snaps\

📝 Default Credentials (CHANGE THESE!)
text
PIN: "Set Your Own Pin"
Password: "Set Your Own Password"
Pattern: "0-1-2-5-8"
Backup: "Set Your Own Backup password here"
