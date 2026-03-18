import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from pynput.mouse import Controller as MouseController, Button as MouseButton
from pynput.keyboard import Controller as KeyboardController, Key, Listener as KeyboardListener
import sys


class ClickSpeedAutomation:
    def __init__(self):
        self.mouse = MouseController()
        self.keyboard = KeyboardController()

        self.running = False
        self.click_thread = None
        self.click_count = 0
        self.start_time = 0
        self.actual_cps = 0.0

        self.left_click_enabled = True
        self.right_click_enabled = False
        self.space_click_enabled = False

        self.target_cps = 100
        self.click_interval = 1.0 / self.target_cps

        self.click_limit_enabled = False
        self.click_limit = 100

        self.keyboard_listener = None
        self.gui = None

    def set_gui(self, gui):
        self.gui = gui

    def perform_click(self, click_type):
        if click_type == 'left':
            self.mouse.press(MouseButton.left)
            self.mouse.release(MouseButton.left)
        elif click_type == 'right':
            self.mouse.press(MouseButton.right)
            self.mouse.release(MouseButton.right)
        elif click_type == 'space':
            self.keyboard.press(Key.space)
            self.keyboard.release(Key.space)

    def click_loop(self):
        while self.running:
            click_performed = False

            if self.left_click_enabled:
                self.perform_click('left')
                click_performed = True

            if self.right_click_enabled:
                self.perform_click('right')
                click_performed = True

            if self.space_click_enabled:
                self.perform_click('space')
                click_performed = True

            if click_performed:
                self.click_count += 1

                if self.click_limit_enabled and self.click_count >= self.click_limit:
                    self.running = False
                    break

            elapsed = time.time() - self.start_time
            if elapsed > 0:
                self.actual_cps = self.click_count / elapsed

            time.sleep(self.click_interval)

    def start(self):
        if not self.running:
            self.running = True
            self.click_count = 0
            self.start_time = time.time()
            self.click_thread = threading.Thread(
                target=self.click_loop, daemon=True)
            self.click_thread.start()
            return True
        return False

    def stop(self):
        self.running = False
        if self.click_thread:
            self.click_thread.join(timeout=1.0)
            self.click_thread = None
        return self.actual_cps

    def set_click_limit(self, limit, enabled=True):
        self.click_limit = limit
        self.click_limit_enabled = enabled

    def get_stats(self):
        elapsed = time.time() - self.start_time if self.running else 0
        return {
            'running': self.running,
            'click_count': self.click_count,
            'elapsed_time': elapsed,
            'actual_cps': self.actual_cps
        }

    def start_keyboard_listener(self):
        if self.keyboard_listener is None or not self.keyboard_listener.is_alive():
            self.keyboard_listener = KeyboardListener(
                on_press=self.on_key_press)
            self.keyboard_listener.start()

    def stop_keyboard_listener(self):
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except:
                pass
            self.keyboard_listener = None

    def on_key_press(self, key):
        try:
            if key == Key.f9:
                if self.gui:
                    self.gui.toggle_clicking()
            elif key == Key.esc:
                if self.running:
                    self.stop()
                    if self.gui:
                        self.gui.on_stopped()
        except Exception as e:
            print(f"Key press error: {e}")
        return True


class ClickSpeedGUI:
    def __init__(self):
        self.automation = ClickSpeedAutomation()
        self.automation.set_gui(self)

        self.root = tk.Tk()
        self.root.title("点击速度测试外挂 - CPS Automation")
        self.root.geometry("400x380")
        self.root.resizable(False, False)

        self.setup_ui()

        self.automation.start_keyboard_listener()

        self.update_stats()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text="点击速度测试",
            font=("Microsoft YaHei UI", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        settings_frame = ttk.LabelFrame(
            main_frame, text="点击类型选择", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 15))

        self.left_click_var = tk.BooleanVar(value=True)
        self.right_click_var = tk.BooleanVar(value=False)
        self.space_click_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(
            settings_frame,
            text="左键点击",
            variable=self.left_click_var,
            command=self.update_settings
        ).pack(anchor=tk.W, pady=2)

        ttk.Checkbutton(
            settings_frame,
            text="右键点击",
            variable=self.right_click_var,
            command=self.update_settings
        ).pack(anchor=tk.W, pady=2)

        ttk.Checkbutton(
            settings_frame,
            text="空格键点击",
            variable=self.space_click_var,
            command=self.update_settings
        ).pack(anchor=tk.W, pady=2)

        target_frame = ttk.Frame(main_frame)
        target_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(target_frame, text="目标频率 (CPS): ").pack(side=tk.LEFT)
        self.cps_var = tk.StringVar(value="100")
        cps_entry = ttk.Entry(
            target_frame, textvariable=self.cps_var, width=10)
        cps_entry.pack(side=tk.LEFT)
        ttk.Button(
            target_frame,
            text="应用",
            command=self.update_cps
        ).pack(side=tk.LEFT, padx=(5, 0))

        limit_frame = ttk.Frame(main_frame)
        limit_frame.pack(fill=tk.X, pady=(0, 10))

        self.click_limit_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            limit_frame,
            text="启用点击次数限制",
            variable=self.click_limit_var,
            command=self.update_limit_setting
        ).pack(side=tk.LEFT)

        ttk.Label(limit_frame, text="  次数: ").pack(side=tk.LEFT)
        self.limit_count_var = tk.StringVar(value="100")
        limit_entry = ttk.Entry(
            limit_frame, textvariable=self.limit_count_var, width=8)
        limit_entry.pack(side=tk.LEFT)
        ttk.Button(
            limit_frame,
            text="设置",
            command=self.update_limit
        ).pack(side=tk.LEFT, padx=(5, 0))

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        self.start_button = ttk.Button(
            control_frame,
            text="开始点击 (F9)",
            command=self.toggle_clicking,
            width=15
        )
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_button = ttk.Button(
            control_frame,
            text="停止 (ESC)",
            command=self.stop_clicking,
            state=tk.DISABLED,
            width=15
        )
        self.stop_button.pack(side=tk.LEFT)

        stats_frame = ttk.LabelFrame(main_frame, text="实时统计", padding="10")
        stats_frame.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(
            stats_frame,
            text="状态：已停止",
            font=("Microsoft YaHei UI", 10)
        )
        self.status_label.pack(anchor=tk.W, pady=2)

        self.cps_label = ttk.Label(
            stats_frame,
            text="当前 CPS: 0.00",
            font=("Microsoft YaHei UI", 10)
        )
        self.cps_label.pack(anchor=tk.W, pady=2)

        self.count_label = ttk.Label(
            stats_frame,
            text="总点击数：0",
            font=("Microsoft YaHei UI", 10)
        )
        self.count_label.pack(anchor=tk.W, pady=2)

        self.time_label = ttk.Label(
            stats_frame,
            text="运行时间：0.00s",
            font=("Microsoft YaHei UI", 10)
        )
        self.time_label.pack(anchor=tk.W, pady=2)

        info_label = ttk.Label(
            main_frame,
            text="热键: F9=开始/停止  ESC=紧急停止",
            font=("Microsoft YaHei UI", 8),
            foreground="gray"
        )
        info_label.pack(pady=(10, 0))

    def update_settings(self):
        self.automation.left_click_enabled = self.left_click_var.get()
        self.automation.right_click_enabled = self.right_click_var.get()
        self.automation.space_click_enabled = self.space_click_var.get()

    def update_cps(self):
        try:
            cps = float(self.cps_var.get())
            if cps <= 0:
                raise ValueError()
            self.automation.target_cps = cps
            self.automation.click_interval = 1.0 / cps
            messagebox.showinfo("成功", f"目标频率已更新为 {cps} CPS")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正数")

    def update_limit_setting(self):
        enabled = self.click_limit_var.get()
        self.automation.set_click_limit(self.automation.click_limit, enabled)

    def update_limit(self):
        try:
            limit = int(self.limit_count_var.get())
            if limit <= 0:
                raise ValueError()
            self.automation.set_click_limit(limit, self.click_limit_var.get())
            messagebox.showinfo("成功", f"点击次数限制已设置为 {limit} 次")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正整数")

    def toggle_clicking(self):
        if not self.automation.running:
            if not any([self.left_click_var.get(),
                       self.right_click_var.get(),
                       self.space_click_var.get()]):
                messagebox.showwarning("警告", "请至少选择一种点击类型")
                return

            self.automation.start()
            self.start_button.config(text="运行中... (F9)", state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_label.config(text="状态：运行中", foreground="green")
            self.update_stats()
        else:
            self.stop_clicking()

    def stop_clicking(self):
        self.automation.stop()
        self.on_stopped()

    def on_stopped(self):
        self.start_button.config(text="开始点击 (F9)", state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

        stats = self.automation.get_stats()

        if self.automation.click_limit_enabled and stats['click_count'] >= self.automation.click_limit:
            self.status_label.config(text="状态：已达上限自动停止", foreground="blue")
            messagebox.showinfo(
                "完成",
                f"已达到设定的点击次数限制 ({self.automation.click_limit} 次)\n实际 CPS: {stats['actual_cps']:.2f}"
            )
        else:
            self.status_label.config(text="状态：已停止", foreground="black")

        self.count_label.config(text=f"总点击数：{stats['click_count']}")
        self.cps_label.config(text=f"最终 CPS: {stats['actual_cps']:.2f}")

    def update_stats(self):
        if self.automation.running:
            stats = self.automation.get_stats()
            self.status_label.config(
                text=f"状态：运行中 (CPS: {stats['actual_cps']:.2f})", foreground="green")
            self.cps_label.config(text=f"当前 CPS: {stats['actual_cps']:.2f}")
            self.count_label.config(text=f"总点击数：{stats['click_count']}")
            self.time_label.config(text=f"运行时间：{stats['elapsed_time']:.2f}s")
            self.root.after(100, self.update_stats)
        else:
            if self.automation.click_limit_enabled and self.automation.click_count >= self.automation.click_limit and self.automation.click_count > 0:
                if self.status_label.cget("foreground") != "blue":
                    self.on_stopped()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        self.automation.stop()
        self.automation.stop_keyboard_listener()
        self.root.destroy()


if __name__ == "__main__":
    app = ClickSpeedGUI()
    app.run()
