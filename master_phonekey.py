import subprocess
import socket
import threading
import random
import string
import sys
import os
import tkinter as tk

def do_install():
    
    print("=" * 50)
    print("  PhoneKey - Setup")
    print("=" * 50)

    print("\n[1/4] Python packages install ho rahe hain...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pywin32", "keyboard"])

    print("\n[2/4] USB power-saving disable ho raha hai...")
    subprocess.run(
        'powercfg /setacvalueindex scheme_current 2a737441-1930-4402-8d77-b2bebba308a3 '
        '48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0', shell=True
    )
    subprocess.run(
        'powercfg /setdcvalueindex scheme_current 2a737441-1930-4402-8d77-b2bebba308a3 '
        '48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0', shell=True
    )
    subprocess.run('powercfg /setactive scheme_current', shell=True)

    print("\n[3/4] Firewall mein WiFi connection allow ho raha hai...")
    subprocess.run(
        'netsh advfirewall firewall add rule name="PhoneKey" dir=in '
        'action=allow protocol=TCP localport=5000', shell=True
    )

    print("\n[4/4] Startup task bana raha hoon...")
    
    pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable  

    script_path = os.path.abspath(__file__)
    subprocess.run(
        f'schtasks /create /tn "PhoneKey" /tr "\\"{pythonw_path}\\" \\"{script_path}\\"" '
        f'/sc onlogon /rl highest /f', shell=True
    )

    print("\n" + "=" * 50)
    print("  Setup complete!")
    print("=" * 50)
    print("\nZaroori: is file mein neeche ye 3 lines apne hisaab se badlo:")
    print('   CORRECT_PIN, BACKUP_PASSWORD, ADB_PATH')
    print("\nLaptop restart karo - system ab khud chalega.")
    input("\nEnter dabao band karne ke liye...")




import win32gui
import win32con
import keyboard

# ---------------- Config ----------------
ADB_PATH = r"C:\Users\Prince\AppData\Local\Android\Sdk\platform-tools\adb.exe"
CORRECT_PIN = "1234"
BACKUP_PASSWORD = "PRINCE"  
LOCK_COMMAND = "__LOCK_NOW__"  
HOST = "0.0.0.0"
PORT = 5000
CHARS = string.ascii_letters + string.digits + "!@#$%^&*<>/\\|"
CREATE_NO_WINDOW = 0x08000000


def run_hidden(args):
    return subprocess.run(
        args, creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def setup_adb():
    """Tunnel banata hai aur hamesha zinda rakhta hai - agar USB power-saving
    ya kisi wajah se tunnel drop ho jaye, ye har 15 second mein refresh
    karta rehta hai, taake Lock/Unlock kabhi bhi (ghanton baad bhi) kaam kare."""
    run_hidden([ADB_PATH, "start-server"])
    run_hidden([ADB_PATH, "wait-for-device"])

    
    for _ in range(20):
        result = run_hidden([ADB_PATH, "reverse", "tcp:5000", "tcp:5000"])
        if result.returncode == 0:
            break
        import time
        time.sleep(0.5)

    
    import time
    while True:
        time.sleep(15)
        run_hidden([ADB_PATH, "reverse", "tcp:5000", "tcp:5000"])


def set_taskbar_visible(visible: bool):
    taskbar = win32gui.FindWindow("Shell_TrayWnd", None)
    start_button = win32gui.FindWindow("Button", None)
    flag = win32con.SW_SHOW if visible else win32con.SW_HIDE
    if taskbar:
        win32gui.ShowWindow(taskbar, flag)
    if start_button:
        win32gui.ShowWindow(start_button, flag)


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

        self.canvas = tk.Canvas(
            self.root, width=self.width, height=self.height,
            bg="black", highlightthickness=0
        )
        self.canvas.place(x=0, y=0)

        self.font_size = 16
        self.cols = self.width // self.font_size
        self.drops = [random.randint(-30, 0) for _ in range(self.cols)]

        self.label = tk.Label(
            self.root,
            text="🔒 SYSTEM LOCKED\n\nWaiting for authentication from device...",
            fg="#00ff41", bg="black",
            font=("Consolas", 26, "bold"),
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")

        self.backup_frame = None
        self.is_locked = True
        self.animating = True

        self.animate_matrix()
        self.apply_lockdown()

        keyboard.add_hotkey("ctrl+alt+shift+q", self.show_backup_prompt, suppress=True)

        threading.Thread(target=self.run_server, daemon=True).start()
        
            

    
    def apply_lockdown(self):
        set_taskbar_visible(False)
        keyboard.block_key("windows")
        keyboard.add_hotkey("ctrl+esc", lambda: None, suppress=True)
        keyboard.add_hotkey("alt+tab", lambda: None, suppress=True)

    def remove_lockdown(self):
        set_taskbar_visible(True)
        try:
            keyboard.unblock_key("windows")
        except Exception:
            pass
        try:
            keyboard.remove_hotkey("ctrl+esc")
            keyboard.remove_hotkey("alt+tab")
        except Exception:
            pass

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

        self.backup_frame = tk.Frame(self.root, bg="black", highlightbackground="#00ff41",
                                      highlightthickness=2)
        self.backup_frame.place(relx=0.5, rely=0.65, anchor="center")

        tk.Label(self.backup_frame, text="Backup Password:", fg="#00ff41", bg="black",
                 font=("Consolas", 14)).pack(padx=15, pady=(10, 5))

        self.pw_var = tk.StringVar()
        entry = tk.Entry(self.backup_frame, textvariable=self.pw_var, show="*",
                          font=("Consolas", 14), bg="#111111", fg="#00ff41",
                          insertbackground="#00ff41")
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

    
    def run_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((HOST, PORT))
        except OSError:
            server.close()
            return
        server.listen(5)

        while True:
            conn, addr = server.accept()
            with conn:
                data = conn.recv(1024).decode("utf-8").strip()
                if data == LOCK_COMMAND:
                    conn.sendall(b"LOCKED")
                    self.root.after(0, self.do_lock)
                elif data == CORRECT_PIN:
                    conn.sendall(b"OK")
                    self.root.after(0, self.do_unlock)
                else:
                    conn.sendall(b"WRONG")
    def animate_matrix(self):
        if self.is_locked:
            self.canvas.delete("all")
            for i in range(self.cols):
                x = i * self.font_size
                y = self.drops[i] * self.font_size
                char = random.choice(CHARS)
                self.canvas.create_text(
                    x, y, text=char, fill="#00ff41",
                    font=("Consolas", self.font_size), anchor="nw"
                )
                if y > self.height and random.random() > 0.975:
                    self.drops[i] = 0
                self.drops[i] += 1
        self.root.after(50, self.animate_matrix)

    def start(self):
        self.root.mainloop()


if __name__ == "__main__":
    if "--install" in sys.argv:
        do_install()
        sys.exit(0)

    threading.Thread(target=setup_adb, daemon=True).start()
    LockScreen().start()
