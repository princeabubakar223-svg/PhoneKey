# PhoneKey — Setup Guide

PhoneKey lets you lock/unlock your laptop from your phone over **USB cable** or **WiFi**, with a Matrix-style lock screen and a secret backup password as a fallback.

This guide covers a **fresh install on a brand-new laptop** — no Android Studio required on that machine.

---
<img width="720" height="1600" alt="Screenshot_20260703-120851" src="https://github.com/user-attachments/assets/12c0ef62-74e0-4122-ba72-b34b1ad0e839" />
## What You Need

| Item | Where to get it | Required on |
|---|---|---|
| Python 3.x | [python.org](https://python.org) | New laptop |
| ADB Platform Tools | [developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools) | New laptop |
| `PhoneKey.apk` (already built) | You build this once in Android Studio, then share the file | Phone |
| `master_phonekey.py` | Provided | New laptop |

You do **not** need Android Studio on the new laptop — only the `.apk` file and platform-tools.

---

## Part 1 — Build the APK (only you need to do this, once)

1. Open the project in Android Studio.
2. Menu: **Build → Build App Bundle(s) / APK(s) → Build APK(s)**.
3. When it finishes, click **locate** — the file will be at:
   ```
   app/build/outputs/apk/debug/app-debug.apk
   ```
4. Rename it to `PhoneKey.apk` and send it (WhatsApp, cable, USB drive — any method) along with `master_phonekey.py`.

---

## Part 2 — New Laptop Setup

### Step 1: Install Python
- Download from [python.org](https://python.org)
- During install, **tick "Add python.exe to PATH"** — this is required.

### Step 2: Install ADB (platform-tools)
- Download the **SDK Platform-Tools** zip for Windows from:
  `https://developer.android.com/tools/releases/platform-tools`
- Extract it anywhere, e.g. `C:\platform-tools\`
- Inside that folder you'll find `adb.exe` — note down its full path, you'll need it in Step 4.

### Step 3: Place the files
- Put `master_phonekey.py` anywhere convenient, e.g. `C:\PhoneKey\master_phonekey.py`

### Step 4: Edit 3 settings in `master_phonekey.py`
Open it with Notepad and change these lines near the top:

```python
ADB_PATH = r"C:\platform-tools\adb.exe"        # path from Step 2
CORRECT_PIN = "1234"                            # your own PIN
BACKUP_PASSWORD = "your_own_secret_password"    # your own secret password
```

### Step 5: Run the installer command
Open **Command Prompt as Administrator**, navigate to the folder, and run:

```
cd C:\PhoneKey                                                                 ( Step 5 is optional dont use if you dont have full setup )
python master_phonekey.py --install
```

This single command automatically:
- Installs required Python packages (`pywin32`, `keyboard`)
- Disables USB power-saving (prevents the connection from dropping)
- Allows the app through Windows Firewall (for WiFi mode)
- Creates a Windows startup task so PhoneKey runs on every login

### Step 6: Restart the laptop
The lock screen should now appear automatically on every boot/login.

---

## Part 3 — Phone Setup

1. **Settings → About Phone → tap "Build Number" 7 times** (unlocks Developer Options)
2. **Settings → Developer Options → USB Debugging → ON**
3. Install `PhoneKey.apk`:
   - You'll see an "Unknown sources" warning — this is normal for any app installed outside the Play Store. Tap **Install anyway**.
4. First time you open the app, allow the Bluetooth permission prompt (safe to allow even if you don't plan to use Bluetooth).

---

## Part 4 — Using It

### Cable Mode
1. Connect phone to laptop via USB cable.
2. First time only: phone may show an "Allow USB debugging?" popup — tap **Always allow from this computer**, then Allow.
3. Open the app, select **CABLE**, enter your PIN, tap **EXECUTE UNLOCK**.

### WiFi Mode (no cable needed)
1. Connect both phone and laptop to the **same WiFi network** (or use your phone's own Hotspot — no internet required either way).
2. On the laptop, open Command Prompt and run `ipconfig` — note the **IPv4 Address**.
3. In the app, select **WIFI**, enter that IP address, enter your PIN, tap **EXECUTE UNLOCK**.

### Lock Now
Tap the red **🔒 LOCK NOW** button anytime to instantly lock the laptop, no PIN needed to trigger a lock.

### Cancel
If a connection is taking too long, tap **CANCEL** to stop it and try again immediately — no need to close the app.

### Emergency Backup Unlock
If the phone can't connect for any reason:
- On the laptop, press **Ctrl + Alt + Shift + Q**
- A password box appears — type your `BACKUP_PASSWORD`, press Enter

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Connection refused" first try | Normal — the app auto-retries for ~15 seconds while the tunnel sets up. Just wait. |
| USB debugging popup doesn't show after reboot | Windows "Fast Startup" is likely enabled — disable it in Control Panel → Power Options → "Choose what the power buttons do" |
| Lock stops working after some time | Fixed — the tunnel now auto-refreshes every 15 seconds. Make sure you're using the latest `master_phonekey.py`. |
| WiFi mode not connecting | Check the laptop's IP hasn't changed (`ipconfig` again), and make sure both devices are on the same network |
| Locked out completely | Use the backup password (Ctrl+Alt+Shift+Q on the laptop) |

---

## Security Note

Anyone with your `CORRECT_PIN` or `BACKUP_PASSWORD` can control this laptop remotely. Keep both private, and change the defaults in `master_phonekey.py` before use — never share the file with your real PIN/password still inside it.
