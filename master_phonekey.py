import subprocess
import socket
import threading
import random
import string
import sys
import os
import json
import time
import urllib.parse
import http.server
import socketserver
import tkinter as tk
import shutil
import re
from difflib import get_close_matches

try:
    import bluetooth
    BLUETOOTH_AVAILABLE = True
except ImportError:
    BLUETOOTH_AVAILABLE = False

try:
    import cv2
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False

try:
    from PIL import ImageGrab, Image
    SCREENSHOT_AVAILABLE = True
except ImportError:
    SCREENSHOT_AVAILABLE = False


try:
    from fuzzywuzzy import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except:
    SPACY_AVAILABLE = False

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except:
    TEXTBLOB_AVAILABLE = False

import win32gui
import win32con
import keyboard


ADB_PATH = r"C:\Users\Prince\AppData\Local\Android\Sdk\platform-tools\adb.exe"
CORRECT_PIN = "1234"
CORRECT_PASSWORD = "PRINCE"
CORRECT_PATTERN = "0-1-2-5-8"
BACKUP_PASSWORD = "PRINCE"
VAULT_DIR = r"D:\\"
SECURITY_WRONG_THRESHOLD = 3


LOCK_COMMAND = "LOCK"
PORT = 5000
HTTP_PORT = 5001
HOST = "0.0.0.0"
CHARS = string.ascii_letters + string.digits + "!@#$%^&*<>/\\|"
CREATE_NO_WINDOW = 0x08000000

QUOTES = [
    "> access denied is just a suggestion_",
    "> trust nothing, verify everything_",
    "> the pin is mightier than the sword_",
]

os.makedirs(VAULT_DIR, exist_ok=True)
os.makedirs(os.path.join(VAULT_DIR, "security_captures"), exist_ok=True)
os.makedirs(os.path.join(VAULT_DIR, "screenshots"), exist_ok=True)
os.makedirs(os.path.join(VAULT_DIR, "camera_snaps"), exist_ok=True)

intrusion_log = []
security_mode = False
wrong_attempt_count = 0
_camera_lock = threading.Lock()
_cam_state = {
    "capture": None,
    "latest_frame": None,
    "running": False,
    "thread": None,
    "lock": threading.Lock(),
    "frame_lock": threading.Lock(),
    "read_fail_count": 0,
    "total_frames": 0,
}

def _cam_start():
    with _cam_state["lock"]:
        if _cam_state["running"] and _cam_state["capture"] is not None:
            print("[CAM-SHARED] already running, skip start")
            return True
        cam = _safe_open_camera(label="CAM-START")
        if cam is None:
            print("[CAM-START] FAILED to open camera")
            return False
        _cam_state["capture"] = cam
        _cam_state["running"] = True
        _cam_state["latest_frame"] = None
        _cam_state["read_fail_count"] = 0
        _cam_state["total_frames"] = 0
        _cam_state["thread_stop_event"] = threading.Event()
        stop_evt = _cam_state["thread_stop_event"]

        def _capture_loop():
            tid = threading.current_thread().name
            print(f"[CAM-CAPTURE] thread {tid} started")
            consecutive_fails = 0
            while not stop_evt.is_set():
                cam_ref = _cam_state["capture"]
                if cam_ref is None:
                    print(f"[CAM-CAPTURE] thread {tid} EXIT: capture object is None")
                    break
                try:
                    if not cam_ref.isOpened():
                        print(f"[CAM-CAPTURE] thread {tid} EXIT: camera isOpened=False")
                        break
                    ok, frame = cam_ref.read()
                    if ok and frame is not None:
                        h, w = frame.shape[:2]
                        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        with _cam_state["frame_lock"]:
                            _cam_state["latest_frame"] = jpeg.tobytes()
                        _cam_state["total_frames"] += 1
                        consecutive_fails = 0
                        if _cam_state["total_frames"] % 100 == 0:
                            print(f"[CAM-CAPTURE] thread {tid} OK: {_cam_state['total_frames']} frames sent ({w}x{h})")
                    else:
                        consecutive_fails += 1
                        _cam_state["read_fail_count"] = consecutive_fails
                        print(f"[CAM-CAPTURE] thread {tid} read() returned False (fail #{consecutive_fails}) ok={ok} frame={'None' if frame is None else 'exists'}")
                        if consecutive_fails >= 30:
                            print(f"[CAM-CAPTURE] thread {tid} EXIT: {consecutive_fails} consecutive read failures, camera likely disconnected")
                            break
                        time.sleep(0.1)
                except Exception as e:
                    consecutive_fails += 1
                    _cam_state["read_fail_count"] = consecutive_fails
                    print(f"[CAM-CAPTURE] thread {tid} EXCEPTION (fail #{consecutive_fails}): {type(e).__name__}: {e}")
                    if consecutive_fails >= 30:
                        print(f"[CAM-CAPTURE] thread {tid} EXIT: {consecutive_fails} consecutive exceptions")
                        break
                    time.sleep(0.2)
            reason = "stop_event set" if stop_evt.is_set() else "error/exit"
            print(f"[CAM-CAPTURE] thread {tid} EXITING: reason={reason} total_frames={_cam_state['total_frames']} consecutive_fails={consecutive_fails}")

        t = threading.Thread(target=_capture_loop, name="cam-capture", daemon=True)
        t.start()
        _cam_state["thread"] = t
        print(f"[CAM-START] camera opened, capture thread launched")
        return True

def _cam_stop():
    print("[CAM-STOP] stopping camera...")
    with _cam_state["lock"]:
        if not _cam_state["running"]:
            print("[CAM-STOP] not running, nothing to stop")
            return
        _cam_state["running"] = False
        if "thread_stop_event" in _cam_state and _cam_state["thread_stop_event"] is not None:
            _cam_state["thread_stop_event"].set()

    t = _cam_state.get("thread")
    if t is not None:
        print(f"[CAM-STOP] waiting for thread {t.name} to exit...")
        t.join(timeout=5)
        if t.is_alive():
            print(f"[CAM-STOP] WARNING: thread {t.name} did NOT exit within 5s")
        else:
            print(f"[CAM-STOP] thread {t.name} exited cleanly")
        _cam_state["thread"] = None

    with _cam_state["lock"]:
        cam = _cam_state["capture"]
        _cam_state["capture"] = None
        _cam_state["latest_frame"] = None
    if cam is not None:
        try:
            cam.release()
            print("[CAM-STOP] camera released")
        except Exception as e:
            print(f"[CAM-STOP] error releasing camera: {e}")
    print(f"[CAM-STOP] done. total_frames={_cam_state.get('total_frames', 0)}")


def run_hidden(args):
    return subprocess.run(args, creationflags=CREATE_NO_WINDOW, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def log_debug(msg):
    try:
        with open(os.path.join(VAULT_DIR, "phonekey_debug.log"), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def _safe_open_camera(label="cam"):
    if not CAMERA_AVAILABLE:
        print(f"[{label}] cv2 not available")
        return None
    backends = [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW), ("ANY", cv2.CAP_ANY)]
    for idx in range(2):
        for name, backend in backends:
            try:
                print(f"[{label}] trying index={idx} backend={name}")
                c = cv2.VideoCapture(idx, backend)
                if c.isOpened():
                    print(f"[{label}] SUCCESS index={idx} backend={name}")
                    return c
                else:
                    print(f"[{label}] isOpened=false index={idx} backend={name}")
                    try:
                        c.release()
                    except Exception:
                        pass
            except Exception as e:
                print(f"[{label}] exception index={idx} backend={name}: {e}")
                try:
                    c.release()
                except Exception:
                    pass
    print(f"[{label}] no camera found")
    return None

def set_taskbar_visible(visible: bool):
    taskbar = win32gui.FindWindow("Shell_TrayWnd", None)
    start_button = win32gui.FindWindow("Button", None)
    flag = win32con.SW_SHOW if visible else win32con.SW_HIDE
    if taskbar:
        win32gui.ShowWindow(taskbar, flag)
    if start_button:
        win32gui.ShowWindow(start_button, flag)

def capture_security_photo():
    if not CAMERA_AVAILABLE:
        print("[SEC-PHOTO] cv2 not available")
        return
    if _cam_state["running"] and _cam_state["latest_frame"] is not None:
        print("[SEC-PHOTO] using shared camera frame")
        fname = f"intruder_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        fpath = os.path.join(VAULT_DIR, "security_captures", fname)
        import numpy as np
        with _cam_state["frame_lock"]:
            raw = _cam_state["latest_frame"]
        if raw is None:
            print("[SEC-PHOTO] frame became None before read")
            return
        arr = np.frombuffer(raw, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            cv2.imwrite(fpath, frame)
            print(f"[SEC-PHOTO] saved from shared: {fpath}")
        return
    print("[SEC-PHOTO] no shared stream, opening camera directly")
    if not _camera_lock.acquire(blocking=False):
        print("[SEC-PHOTO] camera lock busy")
        return
    try:
        cam = _safe_open_camera()
        if cam is None:
            print("[SEC-PHOTO] no camera found")
            return
        try:
            ok, frame = cam.read()
            if ok:
                fname = f"intruder_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                path = os.path.join(VAULT_DIR, "security_captures", fname)
                cv2.imwrite(path, frame)
                print(f"[SEC-PHOTO] saved: {path}")
        finally:
            cam.release()
    except Exception as e:
        print(f"[SEC-PHOTO] error: {e}")
    finally:
        _camera_lock.release()

def take_screenshot():
    if not SCREENSHOT_AVAILABLE:
        return
    try:
        screenshots_dir = os.path.join(VAULT_DIR, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        img = ImageGrab.grab()
        fname = f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path = os.path.join(screenshots_dir, fname)
        img.save(path)
        log_debug(f"Screenshot saved: {fname}")
    except Exception as e:
        log_debug(f"Screenshot error: {e}")

def capture_webcam_snap():
    if not CAMERA_AVAILABLE:
        print("[SNAP] cv2 not available")
        return
    camera_dir = os.path.join(VAULT_DIR, "camera_snaps")
    os.makedirs(camera_dir, exist_ok=True)
    if _cam_state["running"] and _cam_state["latest_frame"] is not None:
        print("[SNAP] using shared camera frame")
        fname = f"webcam_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        fpath = os.path.join(camera_dir, fname)
        import numpy as np
        with _cam_state["frame_lock"]:
            raw = _cam_state["latest_frame"]
        if raw is None:
            print("[SNAP] frame became None before read")
            return
        arr = np.frombuffer(raw, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            cv2.imwrite(fpath, frame)
            print(f"[SNAP] saved from shared: {fpath}")
        return
    print("[SNAP] no shared stream, opening camera directly")
    if not _camera_lock.acquire(blocking=False):
        print("[SNAP] camera lock busy")
        return
    try:
        cam = _safe_open_camera()
        if cam is None:
            print("[SNAP] no camera found")
            return
        try:
            ok, frame = cam.read()
            if ok:
                fname = f"webcam_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                path = os.path.join(camera_dir, fname)
                cv2.imwrite(path, frame)
                print(f"[SNAP] saved: {path}")
        finally:
            cam.release()
    except Exception as e:
        print(f"[SNAP] error: {e}")
    finally:
        _camera_lock.release()

def setup_adb():
    print("[ADB] Starting ADB server...")
    run_hidden([ADB_PATH, "start-server"])
    run_hidden([ADB_PATH, "wait-for-device"])
    for _ in range(30):
        r1 = run_hidden([ADB_PATH, "reverse", "tcp:5000", "tcp:5000"])
        r2 = run_hidden([ADB_PATH, "reverse", "tcp:5001", "tcp:5001"])
        if r1.returncode == 0 and r2.returncode == 0:
            print("[ADB] Reverse setup successful!")
            break
        time.sleep(0.5)
    while True:
        time.sleep(15)
        run_hidden([ADB_PATH, "reverse", "tcp:5000", "tcp:5000"])
        run_hidden([ADB_PATH, "reverse", "tcp:5001", "tcp:5001"])

def resolve_vault_path(rel_path, endpoint="unknown"):
    if not rel_path:
        print(f"[VAULT-PATH] {endpoint}: empty path -> VAULT_DIR={VAULT_DIR}")
        return VAULT_DIR
    rel_path = urllib.parse.unquote(rel_path)
    rel_path = rel_path.replace("/", "\\")
    if rel_path.startswith("D:") or rel_path.startswith("d:"):
        result = os.path.normpath(rel_path)
        print(f"[VAULT-PATH] {endpoint}: absolute path -> {result}")
        return result
    target = os.path.normpath(os.path.join(VAULT_DIR, rel_path))
    if not target.startswith("D:\\") and not target.startswith("d:\\"):
        print(f"[VAULT-PATH] {endpoint}: PATH ESCAPE BLOCKED! rel={rel_path} -> {target}")
        return None
    print(f"[VAULT-PATH] {endpoint}: rel={rel_path} -> {target} exists={os.path.exists(target)} isfile={os.path.isfile(target) if os.path.exists(target) else 'N/A'}")
    return target

class VoiceCommandProcessor:
    def __init__(self, vault_dir=VAULT_DIR, lock_screen=None):
        self.vault_dir = vault_dir
        self.current_dir = vault_dir
        self.lock_screen = lock_screen
        self.command_history = []
        self.last_result = None
        self.last_folder_contents = []

        
        self.urdu_map = {
            "pichay": "back", "peeche": "back",
            "kholo": "open", "khol": "open",
            "chalao": "play", "play": "play",
            "dekhao": "view", "dikhao": "view",
            "image": "image", "video": "video",
            "folder": "folder", "file": "file",
            "pehli": "first", "doosri": "second", "tisri": "third", "chauthi": "fourth",
            "number": "number", "wali": "", "wala": "",
            "le chalo": "go to", "jao": "go",
            "andar": "in", "bahir": "out",
            "band karo": "close",
            "delete": "delete", "copy": "copy", "move": "move", "rename": "rename",
            "hide": "hide", "unhide": "unhide",
            "help": "help", "madad": "help",
            "kahan": "where", "location": "where",
            "list": "list", "show": "list", "files": "list", "contents": "list",
            "mujhe": "", "le chalo": "go to", "le ja": "go to",
            "mein": "in", "se": "from", "ko": "to", "ka": "of", "ki": "of", "ke": "of"
        }

        
        self.system_synonyms = {
            "shutdown": ["shutdown", "band karo", "off", "power off"],
            "restart": ["restart", "reboot", "phir se chalu"],
            "sleep": ["sleep", "sula do", "suspend"],
            "lock": ["lock", "band", "screen lock"],
            "volume up": ["volume up", "awaz badhao", "tez karo"],
            "volume down": ["volume down", "awaz kam karo", "dheere karo"],
            "mute": ["mute", "awaz band karo", "silent"],
            "browser": ["browser", "chrome", "internet", "web"],
            "notepad": ["notepad", "notes"],
            "cmd": ["cmd", "command prompt"],
            "explorer": ["explorer", "file explorer"],
            "settings": ["settings", "system settings"],
            "calculator": ["calculator", "calc"],
            "paint": ["paint", "draw"],
            "wordpad": ["wordpad", "word"]
        }

    
    def translate_urdu(self, text):
        words = text.split()
        translated = []
        for word in words:
            word_lower = word.lower()
            if word_lower in self.urdu_map:
                translated.append(self.urdu_map[word_lower])
            else:
                translated.append(word_lower)
        return " ".join(translated)

    def get_current_dir(self):
        return self.current_dir

    def set_current_dir(self, new_dir):
        if os.path.exists(new_dir) and os.path.isdir(new_dir):
            norm_new = os.path.normpath(new_dir)
            norm_vault = os.path.normpath(self.vault_dir)
            if norm_new.startswith(norm_vault) or norm_new == norm_vault:
                self.current_dir = norm_new
                self.last_folder_contents = self.list_current_folder()
                log_debug(f"Directory changed to: {self.current_dir}")
                return True
        return False

    def go_back(self):
        parent = os.path.dirname(self.current_dir)
        if parent and os.path.exists(parent):
            norm_parent = os.path.normpath(parent)
            norm_vault = os.path.normpath(self.vault_dir)
            if norm_parent.startswith(norm_vault) or norm_parent == norm_vault:
                self.current_dir = norm_parent
                self.last_folder_contents = self.list_current_folder()
                log_debug(f"Went back to: {self.current_dir}")
                return True
        return False

    def list_current_folder(self):
        try:
            items = []
            for entry in os.scandir(self.current_dir):
                if not entry.name.startswith("."):
                    items.append(entry.name)
            return items
        except:
            return []

    def find_item(self, name, search_root=None, search_depth=2, prefer_files=False):
        """Find item using fuzzy match if available, else difflib"""
        if search_root is None:
            search_root = self.current_dir
        name_lower = name.lower().strip()

        
        candidates = []  
        try:
            for entry in os.scandir(search_root):
                candidates.append((entry.path, entry.is_dir(), entry.name))
            if search_depth > 0:
                for root, dirs, files in os.walk(search_root):
                    for d in dirs:
                        candidates.append((os.path.join(root, d), True, d))
                    for f in files:
                        candidates.append((os.path.join(root, f), False, f))
                    depth = root.replace(search_root, "").count(os.sep)
                    if depth >= search_depth - 1:
                        break
        except:
            pass

        if candidates:
            
            if FUZZY_AVAILABLE:
                scores = []
                for path, is_dir, cand_name in candidates:
                    ratio = fuzz.token_set_ratio(name_lower, cand_name.lower())
                    partial = fuzz.partial_ratio(name_lower, cand_name.lower())
                    score = max(ratio, partial)
                    if prefer_files and is_dir:
                        score = score * 0.9
                    elif not prefer_files and not is_dir:
                        score = score * 0.9
                    scores.append((score, path, is_dir))
                best = max(scores, key=lambda x: x[0])
                if best[0] >= 55:
                    return best[1], best[2]
            else:
                
                names = [c[2] for c in candidates]
                matches = get_close_matches(name_lower, names, n=1, cutoff=0.6)
                if matches:
                    for path, is_dir, cand_name in candidates:
                        if cand_name == matches[0]:
                            return path, is_dir
        return None, None

    def handle_numbered_file(self, cmd):
        numbers = re.findall(r'\d+', cmd)
        if numbers:
            idx = int(numbers[0]) - 1
        elif "first" in cmd or "pehli" in cmd:
            idx = 0
        elif "second" in cmd or "doosri" in cmd:
            idx = 1
        elif "third" in cmd or "tisri" in cmd:
            idx = 2
        elif "fourth" in cmd or "chauthi" in cmd:
            idx = 3
        else:
            return None, None
        files = [entry for entry in os.scandir(self.current_dir) if entry.is_file()]
        if files and 0 <= idx < len(files):
            return files[idx].path, False
        return None, None

    
    def cmd_go_back(self):
        if self.go_back():
            contents = self.last_folder_contents[:10]
            if contents:
                return f"CMD_OK:✅ Pichay gaya - {os.path.basename(self.current_dir)} | Files: {', '.join(contents)}"
            else:
                return f"CMD_OK:✅ Pichay gaya - {os.path.basename(self.current_dir)} (khali)"
        return "CMD_ERROR:❌ Root pe hain, pichay nahi ja sakte"

    def cmd_go_to_folder(self, target):
        if not target:
            return "CMD_ERROR:❌ Folder ka naam batao"
        path, is_dir = self.find_item(target, self.current_dir, search_depth=0, prefer_files=False)
        if path and is_dir:
            self.set_current_dir(path)
            contents = self.last_folder_contents[:10]
            if contents:
                return f"CMD_OK:✅ {os.path.basename(path)} mein chale gaye | Files: {', '.join(contents)}"
            else:
                return f"CMD_OK:✅ {os.path.basename(path)} mein chale gaye (khali)"
        path, is_dir = self.find_item(target, self.vault_dir, search_depth=2, prefer_files=False)
        if path and is_dir:
            self.set_current_dir(path)
            contents = self.last_folder_contents[:10]
            if contents:
                return f"CMD_OK:✅ {os.path.basename(path)} mein chale gaye | Files: {', '.join(contents)}"
            else:
                return f"CMD_OK:✅ {os.path.basename(path)} mein chale gaye (khali)"
        return f"CMD_ERROR:❌ '{target}' naam ka folder nahi mila"

    def cmd_open_item(self, target):
        if not target:
            return "CMD_ERROR:❌ Kya kholna hai batao"
        res = self.handle_numbered_file(target)
        if res:
            path, is_dir = res
            if not is_dir:
                try:
                    os.startfile(path)
                    return f"CMD_OK:✅ {os.path.basename(path)} khol diya"
                except Exception as e:
                    return f"CMD_ERROR:❌ Kholne mein masla: {e}"
        path, is_dir = self.find_item(target, self.current_dir, search_depth=1, prefer_files=False)
        if not path:
            return f"CMD_ERROR:❌ '{target}' nahi mila"
        if is_dir:
            try:
                subprocess.run(["explorer", path], creationflags=CREATE_NO_WINDOW)
                return f"CMD_OK:✅ Folder {os.path.basename(path)} khol diya"
            except Exception as e:
                return f"CMD_ERROR:❌ Folder kholne mein masla: {e}"
        else:
            try:
                os.startfile(path)
                return f"CMD_OK:✅ {os.path.basename(path)} khol diya"
            except Exception as e:
                return f"CMD_ERROR:❌ Kholne mein masla: {e}"

    def cmd_play_media(self, target):
        if not target:
            return "CMD_ERROR:❌ Kya chalana hai batao"
        res = self.handle_numbered_file(target)
        if res:
            path, is_dir = res
            if not is_dir and path.lower().endswith((".mp4", ".mkv", ".mp3", ".wav")):
                try:
                    os.startfile(path)
                    return f"CMD_OK:✅ {os.path.basename(path)} chala raha hoon"
                except Exception as e:
                    return f"CMD_ERROR:❌ Chalane mein masla: {e}"
        path, is_dir = self.find_item(target, self.vault_dir, search_depth=2, prefer_files=True)
        if not path:
            return f"CMD_ERROR:❌ '{target}' nahi mila"
        if is_dir:
            media_extensions = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".mp3", ".wav")
            try:
                for entry in os.scandir(path):
                    if entry.is_file() and entry.name.lower().endswith(media_extensions):
                        os.startfile(entry.path)
                        return f"CMD_OK:✅ {entry.name} chala raha hoon"
                return f"CMD_ERROR:❌ Folder mein koi media nahi"
            except:
                return f"CMD_ERROR:❌ Folder nahi khul paaya"
        if not path.lower().endswith((".mp4", ".mkv", ".mp3", ".wav", ".avi", ".mov", ".webm")):
            return f"CMD_ERROR:❌ '{target}' media file nahi hai"
        try:
            os.startfile(path)
            return f"CMD_OK:✅ {os.path.basename(path)} chala raha hoon"
        except Exception as e:
            return f"CMD_ERROR:❌ Chalane mein masla: {e}"

    def cmd_view_image(self, target):
        if not target:
            return "CMD_ERROR:❌ Kaunsi image dekhni hai"
        res = self.handle_numbered_file(target)
        if res:
            path, is_dir = res
            if not is_dir and path.lower().endswith((".jpg", ".png", ".gif")):
                try:
                    os.startfile(path)
                    return f"CMD_OK:✅ {os.path.basename(path)} dikha raha hoon"
                except Exception as e:
                    return f"CMD_ERROR:❌ Dikhane mein masla: {e}"
        path, is_dir = self.find_item(target, self.vault_dir, search_depth=2, prefer_files=True)
        if not path:
            return f"CMD_ERROR:❌ '{target}' nahi mili"
        if is_dir:
            image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
            try:
                for entry in os.scandir(path):
                    if entry.is_file() and entry.name.lower().endswith(image_extensions):
                        os.startfile(entry.path)
                        return f"CMD_OK:✅ {entry.name} dikha raha hoon"
                return f"CMD_ERROR:❌ Folder mein koi image nahi"
            except:
                return f"CMD_ERROR:❌ Folder nahi khul paaya"
        if not path.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
            return f"CMD_ERROR:❌ '{target}' image nahi hai"
        try:
            os.startfile(path)
            return f"CMD_OK:✅ {os.path.basename(path)} dikha raha hoon"
        except Exception as e:
            return f"CMD_ERROR:❌ Dikhane mein masla: {e}"

    def cmd_delete_item(self, target):
        if not target:
            return "CMD_ERROR:❌ Kya delete karna hai"
        path, is_dir = self.find_item(target, self.current_dir, search_depth=0, prefer_files=False)
        if not path:
            return f"CMD_ERROR:❌ '{target}' nahi mila"
        if os.path.normpath(path) == os.path.normpath(self.vault_dir):
            return "CMD_ERROR:❌ Root delete nahi kar sakte"
        try:
            if is_dir:
                shutil.rmtree(path)
                return f"CMD_OK:✅ {os.path.basename(path)} delete kar diya"
            else:
                os.remove(path)
                return f"CMD_OK:✅ {os.path.basename(path)} delete kar diya"
        except Exception as e:
            return f"CMD_ERROR:❌ Delete nahi ho paaya: {e}"

    def cmd_copy_item(self, target):
        if not target:
            return "CMD_ERROR:❌ Kya copy karna hai"
        path, is_dir = self.find_item(target, self.current_dir, search_depth=0, prefer_files=False)
        if not path:
            return f"CMD_ERROR:❌ '{target}' nahi mila"
        try:
            base, ext = os.path.splitext(path)
            new_path = f"{base}_copy{ext}"
            if is_dir:
                shutil.copytree(path, new_path)
            else:
                shutil.copy2(path, new_path)
            return f"CMD_OK:✅ {os.path.basename(path)} copy ho gaya"
        except Exception as e:
            return f"CMD_ERROR:❌ Copy nahi ho paaya: {e}"

    def cmd_move_item(self, target, dest=None):
        if not target:
            return "CMD_ERROR:❌ Kya move karna hai"
        path, is_dir = self.find_item(target, self.current_dir, search_depth=0, prefer_files=False)
        if not path:
            return f"CMD_ERROR:❌ '{target}' nahi mila"
        try:
            if dest:
                dest_path = os.path.join(self.current_dir, dest)
                shutil.move(path, dest_path)
                return f"CMD_OK:✅ {os.path.basename(path)} move ho gaya"
            else:
                base, ext = os.path.splitext(path)
                new_path = f"{base}_moved{ext}"
                shutil.move(path, new_path)
                return f"CMD_OK:✅ {os.path.basename(path)} move ho gaya"
        except Exception as e:
            return f"CMD_ERROR:❌ Move nahi ho paaya: {e}"

    def cmd_rename_item(self, old_name, new_name):
        if not old_name or not new_name:
            return "CMD_ERROR:❌ Old aur new naam dono chahiye"
        path, _ = self.find_item(old_name, self.current_dir, search_depth=0, prefer_files=False)
        if not path:
            return f"CMD_ERROR:❌ '{old_name}' nahi mila"
        try:
            dir_path = os.path.dirname(path)
            new_path = os.path.join(dir_path, new_name)
            os.rename(path, new_path)
            return f"CMD_OK:✅ {old_name} -> {new_name} rename ho gaya"
        except Exception as e:
            return f"CMD_ERROR:❌ Rename nahi ho paaya: {e}"

    def cmd_hide_item(self, target):
        if not target:
            return "CMD_ERROR:❌ Kya hide karna hai"
        path, _ = self.find_item(target, self.current_dir, search_depth=0, prefer_files=False)
        if not path:
            return f"CMD_ERROR:❌ '{target}' nahi mila"
        try:
            subprocess.run(["attrib", "+h", path], creationflags=CREATE_NO_WINDOW)
            return f"CMD_OK:✅ {os.path.basename(path)} hide kar diya"
        except Exception as e:
            return f"CMD_ERROR:❌ Hide nahi ho paaya: {e}"

    def cmd_unhide_item(self, target):
        if not target:
            return "CMD_ERROR:❌ Kya unhide karna hai"
        path, _ = self.find_item(target, self.current_dir, search_depth=0, prefer_files=False)
        if not path:
            return f"CMD_ERROR:❌ '{target}' nahi mila"
        try:
            subprocess.run(["attrib", "-h", path], creationflags=CREATE_NO_WINDOW)
            return f"CMD_OK:✅ {os.path.basename(path)} unhide kar diya"
        except Exception as e:
            return f"CMD_ERROR:❌ Unhide nahi ho paaya: {e}"

    def cmd_list_files(self):
        items = self.list_current_folder()
        if not items:
            return "CMD_OK:📂 Folder khali hai"
        items_str = ", ".join(items[:20])
        if len(items) > 20:
            items_str += f" aur {len(items)-20} aur"
        return f"CMD_OK:📂 Files: {items_str}"

    def cmd_where_am_i(self):
        return f"CMD_OK:📍 Current: {self.current_dir}"

    def cmd_funny_voice(self):
        if self.lock_screen:
            return self.lock_screen.play_funny_voice()
        return "CMD_ERROR:❌ Funny voice available nahi"

    def cmd_clear_screen(self):
        try:
            keyboard.press_and_release('win+d')
            return "CMD_OK:✅ Screen clear kar diya"
        except Exception as e:
            return f"CMD_ERROR:❌ Clear nahi ho paaya: {e}"

    def cmd_help(self):
        help_text = (
            "📋 Available Commands:\n"
            "  • Navigation: back, go to [folder], open folder [name]\n"
            "  • Play: play [name], play video, play music\n"
            "  • View: view [name], show image, see picture\n"
            "  • File ops: delete, copy, move, rename, hide, unhide\n"
            "  • System: shutdown, restart, sleep, lock\n"
            "  • Volume: volume up/down, mute\n"
            "  • Apps: open browser, notepad, cmd, calculator, paint\n"
            "  • Utility: list files, where, clear screen, funny\n"
            "You can use Urdu/Hindi as well."
        )
        return f"CMD_OK:{help_text}"

    def cmd_system_action(self, action):
        actions = {
            "shutdown": ["shutdown", "/s", "/t", "0"],
            "restart": ["shutdown", "/r", "/t", "0"],
            "reboot": ["shutdown", "/r", "/t", "0"],
            "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
            "lock": None,
            "volume up": ["powershell", "-c", "$o=New-Object -ComObject WScript.Shell;1..5|%{$o.SendKeys([char]175)}"],
            "volume down": ["powershell", "-c", "$o=New-Object -ComObject WScript.Shell;1..5|%{$o.SendKeys([char]174)}"],
            "mute": ["powershell", "-c", "$o=New-Object -ComObject WScript.Shell;$o.SendKeys([char]173)"],
            "chrome": ["cmd", "/c", "start", "chrome"],
            "browser": ["cmd", "/c", "start", "chrome"],
            "notepad": ["notepad.exe"],
            "cmd": ["cmd.exe"],
            "explorer": ["explorer.exe"],
            "settings": ["start", "ms-settings:"],
            "calculator": ["calc.exe"],
            "paint": ["mspaint.exe"],
            "wordpad": ["write.exe"]
        }
        if action in actions:
            if action == "lock":
                if self.lock_screen:
                    self.lock_screen.root.after(0, self.lock_screen.do_lock)
                    return "CMD_OK:✅ Lock kar diya"
                return "CMD_ERROR:❌ Lock available nahi"
            try:
                subprocess.run(actions[action], creationflags=CREATE_NO_WINDOW)
                return f"CMD_OK:✅ {action} execute ho gaya"
            except Exception as e:
                return f"CMD_ERROR:❌ {action} execute nahi ho paaya: {e}"
        return "CMD_UNKNOWN"

    
    def process_command(self, command_text):
        
        translated = self.translate_urdu(command_text)
        cmd = translated.lower().strip()
        self.command_history.append(cmd)
        log_debug(f"Translated: {translated} | Original: {command_text}")

        
        if SPACY_AVAILABLE:
            try:
                doc = nlp(cmd)
                verbs = [token.lemma_ for token in doc if token.pos_ == "VERB"]
                nouns = [token.text for token in doc if token.pos_ == "NOUN"]
               
                if "back" in verbs or ("go" in verbs and "back" in cmd):
                    return self.cmd_go_back()
                if "open" in verbs:
                    object_phrase = " ".join([token.text for token in doc if token.dep_ == "dobj" or token.dep_ == "pobj"])
                    if not object_phrase:
                        parts = cmd.split("open", 1)
                        if len(parts) > 1:
                            object_phrase = parts[1].strip()
                    if object_phrase:
                        if "folder" in object_phrase:
                            return self.cmd_go_to_folder(object_phrase.replace("folder", "").strip())
                        else:
                            return self.cmd_open_item(object_phrase)
                    else:
                        return "CMD_ERROR:❌ Kya kholna hai?"
                if "play" in verbs:
                    object_phrase = " ".join([token.text for token in doc if token.dep_ == "dobj"])
                    if not object_phrase:
                        parts = cmd.split("play", 1)
                        if len(parts) > 1:
                            object_phrase = parts[1].strip()
                    if object_phrase:
                        return self.cmd_play_media(object_phrase)
                    else:
                        return "CMD_ERROR:❌ Kya chalana hai?"
                if "view" in verbs or "show" in verbs or "see" in verbs:
                    object_phrase = " ".join([token.text for token in doc if token.dep_ == "dobj"])
                    if not object_phrase:
                        parts = cmd.split("view", 1) or cmd.split("show", 1) or cmd.split("see", 1)
                        if len(parts) > 1:
                            object_phrase = parts[1].strip()
                    if object_phrase:
                        return self.cmd_view_image(object_phrase)
                    else:
                        return "CMD_ERROR:❌ Kaunsi image?"
                if "delete" in verbs or "remove" in verbs:
                    object_phrase = " ".join([token.text for token in doc if token.dep_ == "dobj"])
                    if not object_phrase:
                        parts = cmd.split("delete", 1) or cmd.split("remove", 1)
                        if len(parts) > 1:
                            object_phrase = parts[1].strip()
                    if object_phrase:
                        return self.cmd_delete_item(object_phrase)
                    else:
                        return "CMD_ERROR:❌ Kya delete karna hai?"
                if "copy" in verbs:
                    object_phrase = " ".join([token.text for token in doc if token.dep_ == "dobj"])
                    if not object_phrase:
                        parts = cmd.split("copy", 1)
                        if len(parts) > 1:
                            object_phrase = parts[1].strip()
                    if object_phrase:
                        return self.cmd_copy_item(object_phrase)
                    else:
                        return "CMD_ERROR:❌ Kya copy karna hai?"
                if "move" in verbs:
                    object_phrase = " ".join([token.text for token in doc if token.dep_ == "dobj"])
                    if not object_phrase:
                        parts = cmd.split("move", 1)
                        if len(parts) > 1:
                            object_phrase = parts[1].strip()
                    if object_phrase:
                        return self.cmd_move_item(object_phrase)
                    else:
                        return "CMD_ERROR:❌ Kya move karna hai?"
                if "rename" in verbs:
                    if " to " in cmd:
                        parts = cmd.split(" to ")
                        if len(parts) == 2:
                            old = parts[0].replace("rename", "").strip()
                            new = parts[1].strip()
                            return self.cmd_rename_item(old, new)
                    return "CMD_ERROR:❌ Usage: rename old to new"
                if "hide" in verbs:
                    object_phrase = " ".join([token.text for token in doc if token.dep_ == "dobj"])
                    if object_phrase:
                        return self.cmd_hide_item(object_phrase)
                    else:
                        return "CMD_ERROR:❌ Kya hide karna hai?"
                if "unhide" in verbs:
                    object_phrase = " ".join([token.text for token in doc if token.dep_ == "dobj"])
                    if object_phrase:
                        return self.cmd_unhide_item(object_phrase)
                    else:
                        return "CMD_ERROR:❌ Kya unhide karna hai?"
                if "list" in verbs or ("show" in verbs and "files" in nouns):
                    return self.cmd_list_files()
                if "where" in doc.text or "location" in doc.text:
                    return self.cmd_where_am_i()
                if "funny" in doc.text or "joke" in doc.text:
                    return self.cmd_funny_voice()
                if "clear" in verbs and "screen" in nouns:
                    return self.cmd_clear_screen()
                if "help" in doc.text:
                    return self.cmd_help()
                
                if "go" in verbs and "to" in [token.text for token in doc]:
                    for token in doc:
                        if token.dep_ == "prep" and token.text == "to":
                            target_phrase = " ".join([t.text for t in doc[token.i+1:]])
                            if target_phrase:
                                return self.cmd_go_to_folder(target_phrase)
                            break
                
                for action, synonyms in self.system_synonyms.items():
                    if any(syn in cmd for syn in synonyms):
                        return self.cmd_system_action(action)
                
                return f"CMD_UNKNOWN: Maaf karo, main samjha nahi. 'help' try karo."
            except Exception as e:
                log_debug(f"Spacy processing error: {e}, falling back to keyword")
                return self._keyword_process(cmd)
        else:
            
            return self._keyword_process(cmd)

    def _keyword_process(self, cmd):
        """Fallback keyword-based processor (guaranteed to work)"""
        
        if cmd in ["back", "go back", "pichay", "peeche"]:
            return self.cmd_go_back()
        if any(cmd.startswith(x) for x in ["go to ", "navigate to ", "take me to ", "open folder ", "le chalo "]):
            target = cmd.replace("go to ", "").replace("navigate to ", "").replace("take me to ", "").replace("open folder ", "").replace("le chalo ", "").strip()
            return self.cmd_go_to_folder(target)
        
        if cmd.startswith("play ") or "chalao" in cmd:
            target = cmd.replace("play ", "").replace("chalao", "").strip()
            return self.cmd_play_media(target)
        if "play" in cmd and any(x in cmd for x in ["video", "music", "audio", "song", "movie"]):
            words = cmd.split()
            target = " ".join([w for w in words if w not in ["play", "my", "the", "video", "music", "audio", "song", "movie"]]).strip()
            if target:
                return self.cmd_play_media(target)
            
            try:
                for entry in os.scandir(self.current_dir):
                    if entry.is_file() and entry.name.lower().endswith((".mp4", ".mkv", ".mp3")):
                        os.startfile(entry.path)
                        return f"CMD_OK:✅ {entry.name} chala raha hoon"
                return "CMD_ERROR:❌ Koi media nahi mila"
            except:
                return "CMD_ERROR:❌ Media dhundhne mein masla"
        
        if cmd.startswith("view ") or cmd.startswith("show image ") or cmd.startswith("show picture ") or cmd.startswith("see ") or "dekhao" in cmd or "dikhao" in cmd:
            target = cmd.replace("view ", "").replace("show image ", "").replace("show picture ", "").replace("see ", "").replace("dekhao", "").replace("dikhao", "").strip()
            return self.cmd_view_image(target)
        
        if cmd.startswith("open ") or "kholo" in cmd or "khol" in cmd:
            target = cmd.replace("open ", "").replace("kholo", "").replace("khol", "").strip()
            if "." not in target:
                path, is_dir = self.find_item(target, self.current_dir, search_depth=0, prefer_files=False)
                if path and is_dir:
                    return self.cmd_go_to_folder(target)
            return self.cmd_open_item(target)
        
        if cmd.startswith("delete ") or cmd.startswith("remove ") or "delete" in cmd:
            target = cmd.replace("delete ", "").replace("remove ", "").strip()
            return self.cmd_delete_item(target)
        if cmd.startswith("copy "):
            target = cmd.replace("copy ", "").strip()
            return self.cmd_copy_item(target)
        if cmd.startswith("move "):
            if " to " in cmd:
                parts = cmd.split(" to ")
                if len(parts) == 2:
                    src = parts[0].replace("move ", "").strip()
                    dst = parts[1].strip()
                    return self.cmd_move_item(src, dst)
            target = cmd.replace("move ", "").strip()
            return self.cmd_move_item(target)
        if cmd.startswith("rename "):
            if " to " in cmd:
                parts = cmd.split(" to ")
                if len(parts) == 2:
                    old = parts[0].replace("rename ", "").strip()
                    new = parts[1].strip()
                    return self.cmd_rename_item(old, new)
            return "CMD_ERROR:❌ Usage: rename old_name to new_name"
        if cmd.startswith("hide "):
            target = cmd.replace("hide ", "").strip()
            return self.cmd_hide_item(target)
        if cmd.startswith("unhide ") or cmd.startswith("show hidden "):
            target = cmd.replace("unhide ", "").replace("show hidden ", "").strip()
            return self.cmd_unhide_item(target)
        
        if any(x in cmd for x in ["list", "show files", "what is here", "dir", "ls"]):
            return self.cmd_list_files()
        if any(x in cmd for x in ["where", "current folder", "pwd", "location", "which folder", "kahan"]):
            return self.cmd_where_am_i()
        
        if any(x in cmd for x in ["funny", "joke", "sexy", "make me laugh", "tell me a joke"]):
            return self.cmd_funny_voice()
        if any(x in cmd for x in ["clear screen", "minimize", "hide windows", "show desktop"]):
            return self.cmd_clear_screen()
        
        if "help" in cmd or "madad" in cmd:
            return self.cmd_help()
        
        if any(x in cmd for x in ["number", "first", "second", "third", "fourth", "pehli", "doosri", "tisri", "chauthi"]):
            res = self.handle_numbered_file(cmd)
            if res:
                path, is_dir = res
                if not is_dir:
                    try:
                        os.startfile(path)
                        return f"CMD_OK:✅ {os.path.basename(path)} khol diya"
                    except Exception as e:
                        return f"CMD_ERROR:❌ Kholne mein masla: {e}"
                else:
                    return "CMD_ERROR:❌ Yeh folder hai, file nahi"
        
        for action, synonyms in self.system_synonyms.items():
            if any(syn in cmd for syn in synonyms):
                return self.cmd_system_action(action)
        return "CMD_UNKNOWN: Firgive Me, I Didn't Understand. try. 'help' "


class VaultHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[VAULT] {format % args}")

    def _authed(self, query):
        auth = query.get("auth", [""])[0]
        return auth == CORRECT_PIN or auth == CORRECT_PASSWORD

    def _json_reply(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if not self._authed(query):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return
        if parsed.path == "/list":
            self._handle_list(query)
            return
        if parsed.path == "/file":
            rel = query.get("path", [""])[0]
            print(f"[VAULT-FILE] raw query path: '{rel}'")
            target = resolve_vault_path(rel, "file")
            if target is None or not os.path.isfile(target):
                print(f"[VAULT-FILE] FILE NOT FOUND: {target}")
                self.send_response(404)
                self.end_headers()
                return
            print(f"[VAULT-FILE] serving: {target}")
            ext = target.lower().rsplit(".", 1)[-1] if "." in target else ""
            mime_map = {
                "mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg",
                "flac": "audio/flac", "aac": "audio/aac", "m4a": "audio/mp4", "wma": "audio/x-ms-wma",
                "pdf": "application/pdf",
                "txt": "text/plain", "csv": "text/csv", "log": "text/plain",
                "json": "application/json", "xml": "application/xml",
                "html": "text/html", "css": "text/css", "js": "application/javascript",
                "md": "text/markdown", "py": "text/plain", "java": "text/plain",
                "kt": "text/plain", "sh": "text/plain", "bat": "text/plain",
                "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp",
                "mp4": "video/mp4", "mkv": "video/x-matroska", "avi": "video/x-msvideo",
                "mov": "video/quicktime", "webm": "video/webm",
                "doc": "application/msword", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xls": "application/vnd.ms-excel", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "ppt": "application/vnd.ms-powerpoint", "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "zip": "application/zip", "rar": "application/vnd.rar",
            }
            content_type = mime_map.get(ext, "application/octet-stream")
            self._serve_file_with_range(target, content_type)
            return
        if parsed.path == "/image":
            rel = query.get("path", [""])[0]
            print(f"[VAULT-IMG] raw query path: '{rel}'")
            target = resolve_vault_path(rel, "image")
            if target is None or not os.path.isfile(target):
                print(f"[VAULT-IMG] FILE NOT FOUND: {target}")
                self.send_response(404)
                self.end_headers()
                return
            print(f"[VAULT-IMG] serving: {target}")
            self._serve_image_preview(target)
            return
        if parsed.path == "/video":
            rel = query.get("path", [""])[0]
            print(f"[VAULT-VID] raw query path: '{rel}'")
            target = resolve_vault_path(rel, "video")
            if target is None or not os.path.isfile(target):
                print(f"[VAULT-VID] FILE NOT FOUND: {target}")
                self.send_response(404)
                self.end_headers()
                return
            print(f"[VAULT-VID] serving: {target}")
            self._serve_video(target)
            return
        if parsed.path == "/webcam_frame":
            self._handle_webcam_frame()
            return
        if parsed.path == "/webcam_stream":
            self._handle_webcam_stream()
            return
        if parsed.path == "/webcam_start":
            ok = _cam_start()
            self._json_reply({"ok": ok})
            return
        if parsed.path == "/webcam_stop":
            _cam_stop()
            self._json_reply({"ok": True})
            return
        self.send_response(404)
        self.end_headers()

    def _handle_list(self, query):
        raw_rel = query.get("path", [""])[0]
        print(f"[VAULT-LIST] raw query path: '{raw_rel}'")
        target = resolve_vault_path(raw_rel, "list")
        if target is None or not os.path.exists(target):
            print(f"[VAULT-LIST] target not found: {target}")
            self.send_response(404)
            self.end_headers()
            return
        print(f"[VAULT-LIST] scanning: {target}")
        items = []
        try:
            for entry in os.scandir(target):
                if entry.name in ["System Volume Information", "$Recycle.Bin", "RECYCLER"]:
                    continue
                try:
                    is_dir = entry.is_dir()
                    size = entry.stat().st_size if entry.is_file() else 0
                except:
                    is_dir = True
                    size = 0
                is_hidden = entry.name.startswith(".")
                try:
                    attrs = os.stat(entry.path).st_file_attributes
                    is_hidden = bool(attrs & 2)
                except:
                    pass
                name = entry.name
                try:
                    name.encode('utf-8')
                except:
                    name = str(entry.name)
                items.append({"name": name, "is_dir": is_dir, "size": size, "is_hidden": is_hidden})
        except Exception as e:
            print(f"[VAULT] List error: {e}")
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        self._json_reply(items)

    def _serve_video(self, path):
        try:
            file_size = os.path.getsize(path)
            ext = path.lower().split(".")[-1]
            mime_types = {"mp4": "video/mp4", "mkv": "video/x-matroska", "avi": "video/x-msvideo", "mov": "video/quicktime", "webm": "video/webm"}
            mime_type = mime_types.get(ext, "video/mp4")
            range_header = self.headers.get("Range")
            if range_header:
                start, end = 0, file_size - 1
                try:
                    unit, rng = range_header.split("=")
                    s, e = rng.split("-")
                    if s: start = int(s)
                    if e: end = int(e)
                except:
                    pass
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Type", mime_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(8192, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            else:
                self.send_response(200)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Type", mime_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
        except Exception as e:
            print(f"[VAULT] Video error: {e}")
            self.send_response(500)
            self.end_headers()

    def _serve_image_preview(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
            ext = path.lower().split(".")[-1]
            mime = {"jpg": "image/jpeg", "png": "image/png", "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp"}.get(ext, "image/jpeg")
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            print(f"[VAULT] Image error: {e}")
            self.send_response(500)

    def _serve_file_with_range(self, path, content_type="application/octet-stream"):
        file_size = os.path.getsize(path)
        range_header = self.headers.get("Range")
        if range_header:
            start, end = 0, file_size - 1
            try:
                unit, rng = range_header.split("=")
                s, e = rng.split("-")
                if s: start = int(s)
                if e: end = int(e)
            except:
                pass
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

    def _handle_webcam_frame(self):
        if not CAMERA_AVAILABLE:
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Camera not available")
            return
        if not _cam_state["running"] or _cam_state["latest_frame"] is None:
            print("[CAM-FRAME] no stream active, returning 503")
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Camera stream not started")
            return
        with _cam_state["frame_lock"]:
            data = _cam_state["latest_frame"]
        if data is None:
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Waiting for first frame...")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _handle_webcam_stream(self):
        if not CAMERA_AVAILABLE:
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Camera not available")
            return
        if not _cam_state["running"]:
            print("[CAM-STREAM] no stream active, returning 503")
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Camera stream not started")
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while _cam_state["running"]:
                with _cam_state["frame_lock"]:
                    data = _cam_state["latest_frame"]
                if data is None:
                    time.sleep(0.05)
                    continue
                self.wfile.write(b'--frame\r\n')
                self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                self.wfile.write(data)
                self.wfile.write(b'\r\n')
                self.wfile.flush()
                time.sleep(0.033)
        except Exception:
            print("[CAM-STREAM] client disconnected")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if not self._authed(query):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return
        if parsed.path == "/delete":
            self._handle_delete(query)
        elif parsed.path == "/hide":
            self._handle_hide(query, hide=True)
        elif parsed.path == "/unhide":
            self._handle_hide(query, hide=False)
        elif parsed.path == "/rename":
            self._handle_rename(query)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_delete(self, query):
        rel = query.get("path", [""])[0]
        target = resolve_vault_path(rel)
        if target is None or not os.path.exists(target):
            self.send_response(404)
            self.end_headers()
            return
        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
            self._json_reply({"deleted": True})
        except Exception as e:
            self._json_reply({"deleted": False, "error": str(e)}, status=500)

    def _handle_hide(self, query, hide=True):
        rel = query.get("path", [""])[0]
        target = resolve_vault_path(rel)
        if target is None or not os.path.exists(target):
            self.send_response(404)
            self.end_headers()
            return
        flag = "+h" if hide else "-h"
        try:
            run_hidden(["attrib", flag, target])
            self._json_reply({"hidden": hide})
        except Exception as e:
            self._json_reply({"error": str(e)}, status=500)

    def _handle_rename(self, query):
        rel = query.get("path", [""])[0]
        new_name = query.get("new_name", [""])[0]
        target = resolve_vault_path(rel)
        if target is None or not os.path.exists(target):
            self._json_reply({"error": "file not found"}, status=404)
            return
        try:
            parent_dir = os.path.dirname(target)
            new_path = os.path.join(parent_dir, new_name)
            if os.path.exists(new_path):
                self._json_reply({"error": "name already exists"}, status=400)
                return
            os.rename(target, new_path)
            self._json_reply({"renamed": True})
        except Exception as e:
            self._json_reply({"error": str(e)}, status=500)


def run_vault_server():
    try:
        server = socketserver.ThreadingTCPServer((HOST, HTTP_PORT), VaultHandler)
        print(f"[VAULT] HTTP Server running on port {HTTP_PORT}")
        server.serve_forever()
    except Exception as e:
        print(f"[VAULT] Server error: {e}")



class LockScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Locked")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        self.width = self.root.winfo_screenwidth()
        self.height = self.root.winfo_screenheight()

        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg="black", highlightthickness=0)
        self.canvas.place(x=0, y=0)

        self.font_size = 16
        self.cols = self.width // self.font_size
        self.drops = [random.randint(-30, 0) for _ in range(self.cols)]

        self.label = tk.Label(self.root, text="🔒 SYSTEM LOCKED\n\nWaiting for authentication from device...", fg="#00ff41", bg="black", font=("Consolas", 26, "bold"))
        self.label.place(relx=0.5, rely=0.42, anchor="center")

        self.quote_label = tk.Label(self.root, text=QUOTES[0], fg="#0d3b14", bg="black", font=("Consolas", 13, "italic"))
        self.quote_label.place(relx=0.5, rely=0.55, anchor="center")
        self.quote_index = 0

        self.log_label = tk.Label(self.root, text="", fg="#0d3b14", bg="black", font=("Consolas", 11), justify="left")
        self.log_label.place(relx=0.02, rely=0.98, anchor="sw")

        self.backup_frame = None
        self.is_locked = True

        
        self.voice_processor = VoiceCommandProcessor(VAULT_DIR, self)

        self.animate_matrix()
        self.rotate_quotes()
        self.update_log_display()
        self.apply_lockdown()

        keyboard.add_hotkey("ctrl+alt+shift+q", self.show_backup_prompt, suppress=True)

        threading.Thread(target=self.run_server, daemon=True).start()
        threading.Thread(target=run_vault_server, daemon=True).start()
        if BLUETOOTH_AVAILABLE:
            threading.Thread(target=self.run_bluetooth_server, daemon=True).start()

    def apply_lockdown(self):
        set_taskbar_visible(False)
        keyboard.block_key("windows")
        keyboard.add_hotkey("ctrl+esc", lambda: None, suppress=True)
        keyboard.add_hotkey("alt+tab", lambda: None, suppress=True)

    def remove_lockdown(self):
        set_taskbar_visible(True)
        try: keyboard.unblock_key("windows")
        except: pass
        try:
            keyboard.remove_hotkey("ctrl+esc")
            keyboard.remove_hotkey("alt+tab")
        except: pass

    def do_unlock(self):
        self.is_locked = False
        self.hide_backup_prompt()
        self.remove_lockdown()
        self.root.attributes("-topmost", False)
        self.root.withdraw()

    def do_lock(self):
        self.is_locked = True
        self.root.deiconify()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()
        self.apply_lockdown()

    def show_backup_prompt(self):
        if not self.is_locked or self.backup_frame is not None:
            return
        self.backup_frame = tk.Frame(self.root, bg="black", highlightbackground="#00ff41", highlightthickness=2)
        self.backup_frame.place(relx=0.5, rely=0.7, anchor="center")
        tk.Label(self.backup_frame, text="Backup Password:", fg="#00ff41", bg="black", font=("Consolas", 14)).pack(padx=15, pady=(10, 5))
        self.pw_var = tk.StringVar()
        entry = tk.Entry(self.backup_frame, textvariable=self.pw_var, show="*", font=("Consolas", 14), bg="#111111", fg="#00ff41", insertbackground="#00ff41")
        entry.pack(padx=15, pady=(0, 10))
        entry.focus_set()
        entry.bind("<Return>", self.check_backup_password)
        entry.bind("<Escape>", lambda e: self.hide_backup_prompt())

    def hide_backup_prompt(self):
        if self.backup_frame is not None:
            self.backup_frame.destroy()
            self.backup_frame = None

    def check_backup_password(self, event=None):
        if self.pw_var.get() == BACKUP_PASSWORD:
            self.root.after(0, self.do_unlock)
        else:
            self.pw_var.set("")

    def log_attempt(self, success, kind):
        intrusion_log.append({"time": time.strftime("%H:%M:%S"), "result": "OK" if success else "FAIL", "kind": kind})
        if len(intrusion_log) > 6:
            del intrusion_log[:-6]
        self.root.after(0, self.update_log_display)

    def update_log_display(self):
        lines = ["intrusion log:"]
        for entry in intrusion_log[-6:]:
            lines.append(f"  [{entry['time']}] {entry['kind']} -> {entry['result']}")
        self.log_label.config(text="\n".join(lines))

    def rotate_quotes(self):
        self.quote_index = (self.quote_index + 1) % len(QUOTES)
        self.quote_label.config(text=QUOTES[self.quote_index])
        self.root.after(6000, self.rotate_quotes)

    def play_funny_voice(self):
        mp3_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Bhola Record.mp3")
        if os.path.exists(mp3_path):
            try:
                import ctypes
                winmm = ctypes.windll.winmm
                try:
                    winmm.mciSendStringW('close bhola', 0, 0, 0)
                except Exception:
                    pass
                try:
                    winmm.mciSendStringW(f'open "{mp3_path}" type mpegvideo alias bhola', 0, 0, 0)
                except Exception:
                    pass
                winmm.mciSendStringW('play bhola', 0, 0, 0)
                import threading
                def stop_after():
                    import time as _time
                    _time.sleep(15)
                    try:
                        winmm.mciSendStringW('stop bhola', 0, 0, 0)
                    except Exception:
                        pass
                    try:
                        winmm.mciSendStringW('close bhola', 0, 0, 0)
                    except Exception:
                        pass
                threading.Thread(target=stop_after, daemon=True).start()
                return "FUNNY_VOICE_OK: Playing Bhola Record"
            except Exception as e:
                return f"FUNNY_VOICE_ERROR: {e}"
        return "FUNNY_VOICE_ERROR: Bhola Record.mp3 not found"

    def handle_command(self, data):
        global security_mode, wrong_attempt_count

        log_debug(f"Command: {data}")
        print(f"[LOCK] Command: {data}")

        if data == LOCK_COMMAND:
            self.root.after(0, self.do_lock)
            return "LOCKED"

        if data == "SECURITY_ON":
            security_mode = True
            return "SECURITY_ON_OK"

        if data == "SECURITY_OFF":
            security_mode = False
            return "SECURITY_OFF_OK"

        if data == "PING":
            return "PONG"

        if data == "FUNNY_VOICE":
            return self.play_funny_voice()

        if data.startswith("CMD:"):
            _, voice_cmd = data.split(":", 1)
            result = self.voice_processor.process_command(voice_cmd)
            if not result.startswith("CMD_"):
                result = "CMD_ERROR:" + result
            return result

        if data == "VPN_CONNECT":
            return "VPN_OK"

        if data == "VPN_DISCONNECT":
            return "VPN_DISCONNECT_OK"

        if data.startswith("SCREENSHOT:"):
            _, cred = data.split(":", 1)
            if cred not in (CORRECT_PIN, CORRECT_PASSWORD):
                return "WRONG"
            threading.Thread(target=take_screenshot, daemon=True).start()
            return "SCREENSHOT_OK"

        if data.startswith("WEBCAM:"):
            _, cred = data.split(":", 1)
            if cred not in (CORRECT_PIN, CORRECT_PASSWORD):
                return "WRONG"
            threading.Thread(target=capture_webcam_snap, daemon=True).start()
            return "WEBCAM_OK"

        if ":" in data:
            kind, value = data.split(":", 1)
        else:
            kind, value = "PIN", data

        correct = {"PIN": CORRECT_PIN, "PWD": CORRECT_PASSWORD, "PATTERN": CORRECT_PATTERN}.get(kind)

        if correct is not None and value == correct:
            self.log_attempt(True, kind)
            wrong_attempt_count = 0
            self.root.after(0, self.do_unlock)
            return "OK"
        else:
            self.log_attempt(False, kind)
            if security_mode:
                wrong_attempt_count += 1
                if wrong_attempt_count >= SECURITY_WRONG_THRESHOLD:
                    threading.Thread(target=capture_security_photo, daemon=True).start()
                    wrong_attempt_count = 0
            return "WRONG"

    def run_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((HOST, PORT))
            print(f"[LOCK] TCP Server running on port {PORT}")
        except OSError as e:
            print(f"[LOCK] Error binding: {e}")
            server.close()
            return
        server.listen(5)
        while True:
            conn, addr = server.accept()
            with conn:
                try:
                    data = conn.recv(1024).decode("utf-8").strip()
                    response = self.handle_command(data)
                    conn.sendall(response.encode("utf-8"))
                except Exception as e:
                    print(f"[LOCK] Error: {e}")

    def run_bluetooth_server(self):
        try:
            server = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            server.bind(("", bluetooth.PORT_ANY))
            server.listen(5)
            SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"
            bluetooth.advertise_service(server, "PhoneKeyLock", service_id=SPP_UUID, service_classes=[SPP_UUID, bluetooth.SERIAL_PORT_CLASS], profiles=[bluetooth.SERIAL_PORT_PROFILE])
            while True:
                client, addr = server.accept()
                data = client.recv(1024).decode("utf-8").strip()
                response = self.handle_command(data)
                client.send(response)
                client.close()
        except:
            pass

    def animate_matrix(self):
        if self.is_locked:
            self.canvas.delete("all")
            for i in range(self.cols):
                x = i * self.font_size
                y = self.drops[i] * self.font_size
                char = random.choice(CHARS)
                self.canvas.create_text(x, y, text=char, fill="#00ff41", font=("Consolas", self.font_size), anchor="nw")
                if y > self.height and random.random() > 0.975:
                    self.drops[i] = 0
                self.drops[i] += 1
        self.root.after(50, self.animate_matrix)

    def start(self):
        print("[LOCK] Starting Lock Screen...")
        self.root.mainloop()




def do_install():
    print("=" * 50)
    print("  PhoneKey - v11 ")
    print("=" * 50)
    print("\n[1/4] Installing Python packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pywin32", "keyboard", "opencv-python", "Pillow"])
    print("\n[2/4] Disabling USB power-saving...")
    subprocess.run('powercfg /setacvalueindex scheme_current 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0', shell=True)
    subprocess.run('powercfg /setdcvalueindex scheme_current 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0', shell=True)
    subprocess.run('powercfg /setactive scheme_current', shell=True)
    print("\n[3/4] Adding firewall rules...")
    subprocess.run('netsh advfirewall firewall add rule name="PhoneKey" dir=in action=allow protocol=TCP localport=5000', shell=True)
    subprocess.run('netsh advfirewall firewall add rule name="PhoneKeyVault" dir=in action=allow protocol=TCP localport=5001', shell=True)
    print("\n[4/4] Creating startup task...")
    pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable
    script_path = os.path.abspath(__file__)
    subprocess.run(f'schtasks /create /tn "PhoneKey" /tr "\\"{pythonw_path}\\" \\"{script_path}\\"" /sc onlogon /rl highest /f', shell=True)
    print("\n✅ Setup complete!")
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    if "--install" in sys.argv:
        do_install()
        sys.exit(0)

    print("[MAIN] Starting PhoneKey...")
    print(f"[MAIN] VAULT_DIR: {VAULT_DIR}")
    
    threading.Thread(target=setup_adb, daemon=True).start()
    LockScreen().start()
