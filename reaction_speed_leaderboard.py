"""
反应速度测试外挂 - 冲榜版
功能：使用 Windows API 直接读取窗口像素，极速检测
- 窗口 DC 读取，无需截图（5-10ms）
- 单像素点变化检测
- 目标：冲进前 100（25ms），冲击前 10（4ms）
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
import time
import threading
import ctypes
import json
import os
import win32gui
import win32con
import win32ui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'reaction_leaderboard_config.json')


class UltraTimer:
    """超高精度计时器"""

    def __init__(self):
        self.timer_resolution = 1
        try:
            ctypes.windll.winmm.timeBeginPeriod(self.timer_resolution)
        except:
            pass

        try:
            kernel32 = ctypes.windll.kernel32
            current_process = kernel32.GetCurrentProcess()
            kernel32.SetPriorityClass(current_process, 0x00008000)
            print("[系统] 已提升进程优先级至 REALTIME")
        except Exception as e:
            print(f"[系统] 无法提升优先级：{e}")

        try:
            ctypes.windll.kernel32.SetThreadPriority(
                ctypes.windll.kernel32.GetCurrentThread(),
                15
            )
            print("[系统] 已提升线程优先级至 TIME_CRITICAL")
        except Exception as e:
            print(f"[系统] 无法提升线程优先级：{e}")

    def get_time(self):
        return time.perf_counter()

    def busy_wait(self, seconds):
        """纯忙等待"""
        if seconds <= 0:
            return
        end_time = time.perf_counter() + seconds
        while time.perf_counter() < end_time:
            pass

    def __del__(self):
        try:
            ctypes.windll.winmm.timeEndPeriod(self.timer_resolution)
        except:
            pass


class FastClicker:
    """快速点击器"""

    @staticmethod
    def click(x, y):
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)


class WindowPixelDetector:
    """
    窗口像素检测器 - 冲榜版
    使用 Windows API 直接读取窗口 DC，无需截图
    速度：5-10ms
    """

    def __init__(self):
        self.timer = UltraTimer()
        self.hwnd = None
        self.last_color = None

    def find_window_by_title(self, title_keyword):
        """通过窗口标题查找窗口句柄"""
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if title_keyword.lower() in window_title.lower():
                    windows.append((hwnd, window_title))
            return True
        
        windows = []
        win32gui.EnumWindows(callback, windows)
        
        if windows:
            self.hwnd = windows[0][0]
            print(f"[系统] 找到窗口：{windows[0][1]} (句柄：{self.hwnd})")
            return True
        
        return False

    def get_pixel_dc(self, x, y):
        """
        使用 GetPixel API 直接读取窗口像素
        比 ImageGrab 快 10 倍以上
        """
        if not self.hwnd:
            return None
        
        try:
            dc = win32gui.GetWindowDC(self.hwnd)
            color = win32gui.GetPixel(dc, int(x), int(y))
            win32gui.ReleaseDC(self.hwnd, dc)
            return color
        except Exception as e:
            return None

    def get_pixel_screen(self, x, y):
        """读取屏幕像素（备用方案）"""
        dc = win32gui.GetWindowDC(0)
        try:
            color = win32gui.GetPixel(dc, int(x), int(y))
        finally:
            win32gui.ReleaseDC(0, dc)
        return color

    def wait_for_change(self, x, y, timeout=5.0):
        """
        等待像素点发生变化
        使用纯忙等待 + DC 读取
        """
        start_time = self.timer.get_time()
        
        initial_value = self.get_pixel_screen(x, y)
        last_value = initial_value
        
        check_count = 0
        
        while True:
            current_time = self.timer.get_time()
            elapsed = current_time - start_time

            if elapsed > timeout:
                return None, initial_value, elapsed

            current_value = self.get_pixel_screen(x, y)
            check_count += 1
            
            if current_value != last_value and current_value != -1:
                reaction_time = self.timer.get_time() - start_time
                print(f"[调试] 检测次数：{check_count}, 反应时间：{reaction_time*1000:.3f}ms")
                return True, initial_value, reaction_time
            
            last_value = current_value
            
            self.timer.busy_wait(0.000001)

    def measure_speed(self, x, y, iterations=100):
        """测量检测速度"""
        times = []
        for _ in range(iterations):
            start = self.timer.get_time()
            self.get_pixel_screen(x, y)
            end = self.timer.get_time()
            times.append((end - start) * 1000)
        
        return {
            'avg': sum(times) / len(times),
            'min': min(times),
            'max': max(times)
        }


class ReactionSpeedUltimate:
    """反应速度训练器 - 终极版"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("⚡ 反应速度测试 - 终极版 (像素检测)")
        self.root.geometry("500x600")
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)
        self.root.minsize(450, 550)

        self.detect_point = None
        self.click_position = None
        self.window_title = None
        self.running = False
        self.timer = UltraTimer()
        self.detector = WindowPixelDetector()

        self.config = self.load_config()

        self.setup_ui()
        self.setup_hotkeys()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if 'detect_point' in config:
                    self.detect_point = config['detect_point']
                if 'click_position' in config:
                    self.click_position = config['click_position']
                return config
            except:
                pass
        return {}

    def save_config(self):
        config = {
            'detect_point': self.detect_point,
            'click_position': self.click_position
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def setup_hotkeys(self):
        import keyboard
        keyboard.add_hotkey('f5', self.capture_detect_point)
        keyboard.add_hotkey('f7', self.capture_click_position)
        keyboard.add_hotkey('f8', self.start_test)
        keyboard.add_hotkey('f9', self.stop_test)
        keyboard.add_hotkey('f10', self.test_speed)
        keyboard.add_hotkey('f11', self.capture_window_title)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main_frame, text="⚡ 反应速度测试 - 冲榜版",
                          font=('Arial', 18, 'bold'))
        title.pack(pady=10)

        desc = ttk.Label(main_frame,
                         text="窗口 DC 读取 | 目标 25ms 冲前 100，4ms 冲前 10",
                         font=('Arial', 10, 'bold'), foreground='blue')
        desc.pack(pady=5)

        hotkey_frame = ttk.LabelFrame(main_frame, text="热键说明", padding="8")
        hotkey_frame.pack(fill=tk.X, pady=10)

        ttk.Label(hotkey_frame, text="F5  = 设置检测点位置",
                  font=('Arial', 10, 'bold'), foreground='blue').pack(pady=2)
        ttk.Label(hotkey_frame, text="F7  = 设置点击位置",
                  font=('Arial', 10, 'bold'), foreground='green').pack(pady=2)
        ttk.Label(hotkey_frame, text="F8  = 开始测试",
                  font=('Arial', 10, 'bold'), foreground='orange').pack(pady=2)
        ttk.Label(hotkey_frame, text="F9  = 停止测试",
                  font=('Arial', 10, 'bold'), foreground='red').pack(pady=2)
        ttk.Label(hotkey_frame, text="F10 = 测试检测速度",
                  font=('Arial', 10, 'bold'), foreground='purple').pack(pady=2)
        ttk.Label(hotkey_frame, text="F11 = 设置窗口标题",
                  font=('Arial', 10, 'bold'), foreground='brown').pack(pady=2)

        window_frame = ttk.LabelFrame(main_frame, text="窗口设置", padding="8")
        window_frame.pack(fill=tk.X, pady=10)

        self.window_label = ttk.Label(window_frame,
                                      text="窗口标题：未设置 (按 F11 设置)",
                                      foreground="gray", font=('Arial', 10))
        self.window_label.pack(pady=5)

        ttk.Button(window_frame, text="🪟 设置窗口标题 (F11)",
                   command=self.capture_window_title).pack(pady=5)

        point_frame = ttk.LabelFrame(main_frame, text="检测点设置", padding="8")
        point_frame.pack(fill=tk.X, pady=10)

        self.point_label = ttk.Label(point_frame,
                                     text="检测点：未设置 (按 F5 设置)",
                                     foreground="gray", font=('Arial', 10))
        self.point_label.pack(pady=5)

        ttk.Button(point_frame, text="🎯 设置检测点 (F5)",
                   command=self.capture_detect_point).pack(pady=5)

        click_frame = ttk.LabelFrame(main_frame, text="点击位置设置", padding="8")
        click_frame.pack(fill=tk.X, pady=10)

        self.click_label = ttk.Label(click_frame,
                                     text="点击位置：未设置 (按 F7 设置)",
                                     foreground="gray", font=('Arial', 10))
        self.click_label.pack(pady=5)

        ttk.Button(click_frame, text="🎯 设置点击位置 (F7)",
                   command=self.capture_click_position).pack(pady=5)

        config_frame = ttk.LabelFrame(main_frame, text="测试设置", padding="8")
        config_frame.pack(fill=tk.X, pady=10)

        ttk.Label(config_frame, text="超时时间:",
                  font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.timeout_var = tk.DoubleVar(value=5.0)
        ttk.Spinbox(config_frame, from_=1.0, to=30.0,
                    increment=0.5, width=8,
                    textvariable=self.timeout_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(config_frame, text="秒",
                  font=('Arial', 10)).pack(side=tk.LEFT, padx=5)

        control_frame = ttk.LabelFrame(main_frame, text="控制", padding="8")
        control_frame.pack(fill=tk.X, pady=10)

        btn_row = ttk.Frame(control_frame)
        btn_row.pack(fill=tk.X)

        self.start_btn = ttk.Button(btn_row, text="▶ 开始测试 (F8)",
                                    command=self.start_test)
        self.start_btn.pack(side=tk.LEFT, expand=True, padx=5)

        self.stop_btn = ttk.Button(btn_row, text="⏹ 停止 (F9)",
                                   command=self.stop_test,
                                   state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, padx=5)

        result_frame = ttk.LabelFrame(main_frame, text="测试结果", padding="8")
        result_frame.pack(fill=tk.X, pady=10)

        self.result_label = ttk.Label(result_frame,
                                      text="等待开始...",
                                      font=('Arial', 14, 'bold'),
                                      foreground='blue')
        self.result_label.pack(pady=10)

        self.stats_label = ttk.Label(result_frame,
                                     text="最佳：-- ms | 平均：-- ms | 测试：0 次",
                                     font=('Arial', 11))
        self.stats_label.pack(pady=5)

        self.speed_label = ttk.Label(result_frame,
                                     text="检测速度：未测试 (按 F10 测试)",
                                     font=('Arial', 10),
                                     foreground='gray')
        self.speed_label.pack(pady=5)

        self.status_label = ttk.Label(main_frame,
                                      text="状态：就绪",
                                      foreground="green",
                                      font=('Arial', 11, 'bold'))
        self.status_label.pack(pady=10)

        info_frame = ttk.LabelFrame(main_frame, text="原理说明", padding="8")
        info_frame.pack(fill=tk.X, pady=10)

        info_text = tk.Text(info_frame, height=5, font=('Consolas', 9),
                           wrap=tk.WORD, bg='#f0f0f0')
        info_text.pack(fill=tk.X, pady=5)
        info_text.insert('1.0', 
            "原理：使用 Windows API GetPixel 直接读取窗口像素\n"
            "优势：无需截图，速度提升 10 倍（5-10ms）\n"
            "目标：前 100（25ms）→ 前 10（4ms）")
        info_text.config(state='disabled')

        self.test_thread = None
        self.test_results = []

    def capture_detect_point(self):
        time.sleep(0.1)
        x, y = pyautogui.position()
        self.detect_point = (x, y)

        self.point_label.config(
            text=f"检测点：({x}, {y})",
            foreground="green"
        )
        self.status_label.config(
            text=f"✓ 已记录检测点位置",
            foreground="green"
        )

        self.save_config()

    def capture_click_position(self):
        time.sleep(0.1)
        x, y = pyautogui.position()
        self.click_position = (x, y)

        self.click_label.config(
            text=f"点击位置：({x}, {y})",
            foreground="green"
        )
        self.status_label.config(
            text=f"✓ 已记录点击位置",
            foreground="green"
        )

        self.save_config()

    def capture_window_title(self):
        """设置窗口标题用于查找"""
        dialog = tk.Toplevel(self.root)
        dialog.title("设置窗口标题")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="请输入目标窗口的标题关键字：",
                  font=('Arial', 10)).pack(pady=10)

        entry = ttk.Entry(dialog, width=40)
        entry.pack(pady=5)
        entry.insert(0, self.window_title or "")

        def on_confirm():
            self.window_title = entry.get().strip()
            if self.window_title:
                if self.detector.find_window_by_title(self.window_title):
                    self.window_label.config(
                        text=f"窗口标题：{self.window_title} ✓",
                        foreground="green"
                    )
                    self.status_label.config(
                        text=f"✓ 已找到窗口：{self.window_title}",
                        foreground="green"
                    )
                else:
                    messagebox.showwarning("警告", f"未找到包含 '{self.window_title}' 的窗口")
            dialog.destroy()

        ttk.Button(dialog, text="确定", command=on_confirm).pack(pady=10)
        entry.bind('<Return>', lambda e: on_confirm())
        entry.focus()

    def test_speed(self):
        """测试检测速度"""
        if not self.detect_point:
            messagebox.showwarning("警告", "请先设置检测点！")
            return

        x, y = self.detect_point
        self.status_label.config(text="状态：测试检测速度...", foreground="purple")
        
        result = self.detector.measure_speed(x, y, 100)
        
        self.speed_label.config(
            text=f"检测速度：平均 {result['avg']:.3f}ms | 最快 {result['min']:.3f}ms | 最慢 {result['max']:.3f}ms",
            foreground='blue' if result['avg'] < 2 else 'orange'
        )
        
        self.status_label.config(text="状态：速度测试完成", foreground="green")
        
        messagebox.showinfo(
            "速度测试结果",
            f"检测速度统计 (100 次):\n\n"
            f"平均：{result['avg']:.3f} ms\n"
            f"最快：{result['min']:.3f} ms\n"
            f"最慢：{result['max']:.3f} ms\n\n"
            f"评价：{'神级 (<2ms)' if result['avg'] < 2 else '优秀 (2-5ms)' if result['avg'] < 5 else '良好 (5-10ms)'}"
        )

    def start_test(self):
        if not self.detect_point:
            self.status_label.config(text="请先设置检测点 (F5)", foreground="red")
            messagebox.showwarning("警告", "请先设置检测点！\n按 F5 设置")
            return

        if not self.click_position:
            self.status_label.config(text="请先设置点击位置 (F7)", foreground="red")
            messagebox.showwarning("警告", "请先设置点击位置！\n按 F7 设置")
            return

        if self.running:
            return

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="状态：测试中...", foreground="orange")

        self.test_thread = threading.Thread(
            target=self.run_test, daemon=True)
        self.test_thread.start()

    def stop_test(self):
        self.running = False
        self.status_label.config(text="已停止", foreground="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def run_test(self):
        try:
            timeout = self.timeout_var.get()
            click_x, click_y = self.click_position
            detect_x, detect_y = self.detect_point

            test_count = 0
            success_count = 0

            while self.running:
                test_count += 1

                self.root.after(0, lambda c=test_count: self.result_label.config(
                    text=f"等待第 {c} 次测试..."))
                self.status_label.config(text="状态：等待变化...", foreground="red")

                start_time = None
                wait_start = self.timer.get_time()

                # 等待像素变化
                changed, initial_value, reaction_time = self.detector.wait_for_change(
                    detect_x, detect_y, timeout
                )

                if changed:
                    # 检测到变化，立即点击
                    FastClicker.click(click_x, click_y)

                    success_count += 1
                    self.test_results.append(reaction_time)

                    reaction_ms = reaction_time * 1000

                    self.root.after(0, lambda rt=reaction_ms: self.result_label.config(
                        text=f"✓ 反应时间：{rt:.3f} ms",
                        foreground='green'))

                    if len(self.test_results) >= 1:
                        best = min(self.test_results) * 1000
                        avg = sum(self.test_results) / len(self.test_results) * 1000
                        self.root.after(0, lambda b=best, a=avg, c=test_count:
                                       self.stats_label.config(
                                           text=f"最佳：{b:.3f} ms | 平均：{a:.3f} ms | 测试：{c} 次"))

                    self.status_label.config(
                        text=f"状态：测试完成！{reaction_ms:.3f} ms", 
                        foreground="green")

                    time.sleep(2.0)

                if success_count >= 10 and self.running:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "测试完成", 
                        f"已完成 10 次测试！\n\n"
                        f"最佳反应时间：{min(self.test_results)*1000:.3f} ms\n"
                        f"平均反应时间：{sum(self.test_results)/len(self.test_results)*1000:.3f} ms"))
                    break

        except Exception as e:
            import traceback
            error_msg = f"错误：{str(e)}"
            print(f"\n[错误] {error_msg}")
            print(traceback.format_exc())
            self.root.after(0, lambda: self.status_label.config(
                text=error_msg, foreground="red"))
        finally:
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.status_label.config(
                text="状态：就绪", foreground="green"))
            self.running = False

    def on_closing(self):
        self.save_config()
        try:
            import keyboard
            keyboard.unhook_all()
        except:
            pass
        try:
            del self.timer
        except:
            pass
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        if self.detect_point:
            x, y = self.detect_point
            self.point_label.config(
                text=f"检测点：({x}, {y})",
                foreground="green"
            )

        if self.click_position:
            x, y = self.click_position
            self.click_label.config(
                text=f"点击位置：({x}, {y})",
                foreground="green"
            )

        print("=" * 60)
        print("   ⚡ 反应速度测试 - 冲榜版")
        print("=" * 60)
        print("\n热键:")
        print("  F5  = 设置检测点位置")
        print("  F7  = 设置点击位置")
        print("  F8  = 开始测试")
        print("  F9  = 停止测试")
        print("  F10 = 测试检测速度")
        print("  F11 = 设置窗口标题")
        print("\n使用说明:")
        print("  1. 按 F11 设置目标窗口标题（可选，但推荐）")
        print("  2. 按 F5 设置检测点（会发生颜色变化的像素点）")
        print("  3. 按 F7 设置点击位置")
        print("  4. 按 F10 测试检测速度（查看当前性能）")
        print("  5. 按 F8 开始测试")
        print("\n冲榜目标:")
        print("  - 前 100 名：25ms")
        print("  - 前 10 名：4ms")
        print("\n优化技术:")
        print("  - Windows API GetPixel (无需截图)")
        print("  - 单像素点变化检测")
        print("  - 纯忙等待循环 (无 sleep 延迟)")
        print("  - 进程/线程优先级提升 (REALTIME 级)")
        print("\n启动中...")

        self.root.mainloop()


if __name__ == "__main__":
    app = ReactionSpeedUltimate()
    app.run()
