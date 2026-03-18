"""
时间感知训练外挂
功能：点击按钮进行时间感知训练
- 通过热键确定按钮位置
- 可指定时间间隔
- 通过按钮触发开始，自动第一次点击，经过设定时间后自动第二次点击
- 时间精度小于 0.01s
"""

import tkinter as tk
from tkinter import ttk
import pyautogui
import time
import threading
import ctypes
import json
import os

pyautogui.FAILSAFE = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'time_trainer_config.json')


class HighPrecisionTimer:
    """高精度计时器，针对极致精度优化"""

    # 系统延迟校准值（秒）- 可通过测试调整
    # 调整方法：
    # 1. 运行 calibrate_timer.py 校准工具
    # 2. 查看校准工具给出的建议值
    # 3. 修改下面的 CLICK_LATENCY 为建议值
    # 4. 重新运行本程序
    #
    # 调整原则：
    # - 如果实际时间 > 设定时间：增大 CLICK_LATENCY（如 0.0015 -> 0.0020）
    # - 如果实际时间 < 设定时间：减小 CLICK_LATENCY（如 0.0015 -> 0.0010）
    # - 一般范围：0.0005 ~ 0.0030 之间
    CLICK_LATENCY = 0.0030  # 约 3.0ms 的点击延迟（根据校准工具测量结果设置）

    OVERSHOOT_COMPENSATION = 0.0003  # 约 0.3ms 的过冲补偿
    # 过冲补偿一般不需要调整，保持 0.0003 即可

    # 异常检测阈值（秒）- 超过此值说明系统卡顿
    STUTTER_THRESHOLD = 0.100  # 100ms

    def __init__(self):
        # 设置 Windows 计时器精度为 1ms
        self.timer_resolution = 1
        try:
            ctypes.windll.winmm.timeBeginPeriod(self.timer_resolution)
        except:
            pass

        # 提升进程优先级，减少被系统抢占的可能
        try:
            # 获取当前进程
            kernel32 = ctypes.windll.kernel32
            current_process = kernel32.GetCurrentProcess()
            # 设置优先级为 REALTIME_PRIORITY_CLASS (最高优先级)
            # 使用 BELOW_NORMAL_PRIORITY_CLASS 更安全
            # ABOVE_NORMAL_PRIORITY_CLASS
            kernel32.SetPriorityClass(current_process, 0x00008000)
            print("[系统] 已提升进程优先级")
        except Exception as e:
            print(f"[系统] 无法提升优先级：{e}")

    def sleep(self, seconds, compensate_click=True):
        """
        高精度睡眠，使用 time.perf_counter()

        Args:
            seconds: 睡眠时间（秒）
            compensate_click: 是否补偿点击延迟（True 会稍微提前结束）
        """
        if seconds <= 0:
            return

        # 补偿点击延迟：实际等待时间 = 设定时间 - 点击延迟 - 过冲补偿
        if compensate_click:
            actual_sleep = seconds - self.CLICK_LATENCY - self.OVERSHOOT_COMPENSATION
            if actual_sleep < 0:
                actual_sleep = 0
        else:
            actual_sleep = seconds

        # time.perf_counter() 使用系统高精度计时器
        start = time.perf_counter()
        end_time = start + actual_sleep

        # 第一阶段：长时间休眠（当剩余时间>5ms 时）
        while True:
            current = time.perf_counter()
            remaining = end_time - current
            if remaining <= 0.005:  # 剩余 5ms 时进入精细等待
                break
            # 休眠剩余时间的 70%，避免过冲
            if remaining > 0.010:
                time.sleep(remaining * 0.7)
            else:
                time.sleep(0.001)

        # 第二阶段：精细忙等待（最后 5ms）
        # 这是关键：最后阶段不使用 sleep，避免系统调度延迟
        while time.perf_counter() < end_time:
            pass  # 纯忙等待，确保精度

        # 检测是否发生系统卡顿
        actual_elapsed = time.perf_counter() - start
        if actual_elapsed > actual_sleep + self.STUTTER_THRESHOLD:
            print(f"\n[警告] 检测到系统卡顿！实际等待：{actual_elapsed*1000:.1f}ms, "
                  f"目标：{actual_sleep*1000:.1f}ms, "
                  f"延迟：{(actual_elapsed - actual_sleep)*1000:.1f}ms")

    def get_time(self):
        """获取高精度时间（秒）"""
        return time.perf_counter()

    def measure_click_latency(self):
        """测量点击延迟（用于校准）"""
        times = []
        for _ in range(10):
            start = self.get_time()
            FastClicker.click(0, 0)  # 点击屏幕外
            end = self.get_time()
            times.append(end - start)
        return sum(times) / len(times)

    def __del__(self):
        try:
            ctypes.windll.winmm.timeEndPeriod(self.timer_resolution)
        except:
            pass


class FastClicker:
    """使用 Windows API 进行快速点击"""

    @staticmethod
    def click(x, y):
        """快速点击指定坐标"""
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        ctypes.windll.user32.mouse_event(
            0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
        ctypes.windll.user32.mouse_event(
            0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP


class TimePerceptionTrainer:
    """时间感知训练器"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("⏱️ 时间感知训练器")
        self.root.geometry("450x400")
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)
        self.root.minsize(400, 350)

        self.button_position = None
        self.running = False
        self.timer = HighPrecisionTimer()

        self.config = self.load_config()

        self.setup_ui()
        self.setup_hotkeys()

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if 'button_position' in config:
                    self.button_position = config['button_position']
                return config
            except:
                pass
        return {}

    def save_config(self):
        """保存配置文件"""
        config = {
            'button_position': self.button_position
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def setup_hotkeys(self):
        """设置热键"""
        import keyboard
        keyboard.add_hotkey('f7', self.capture_button_position)
        keyboard.add_hotkey('f8', self.trigger_training)

    def setup_ui(self):
        """设置界面"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main_frame, text="⏱️ 时间感知训练器",
                          font=('Arial', 18, 'bold'))
        title.pack(pady=10)

        desc = ttk.Label(main_frame,
                         text="训练内容：点击按钮后，精确感知指定时间间隔",
                         font=('Arial', 10))
        desc.pack(pady=5)

        hotkey_frame = ttk.LabelFrame(main_frame, text="热键说明", padding="8")
        hotkey_frame.pack(fill=tk.X, pady=10)

        ttk.Label(hotkey_frame, text="F7  = 设置按钮位置",
                  font=('Arial', 10, 'bold'), foreground='blue').pack(pady=2)
        ttk.Label(hotkey_frame, text="F8  = 触发训练开始",
                  font=('Arial', 10, 'bold'), foreground='green').pack(pady=2)

        pos_frame = ttk.LabelFrame(main_frame, text="按钮位置", padding="8")
        pos_frame.pack(fill=tk.X, pady=10)

        self.pos_label = ttk.Label(pos_frame, text="按钮位置：未设置 (按 F7 设置)",
                                   foreground="gray", font=('Arial', 10))
        self.pos_label.pack(pady=5)

        ttk.Button(pos_frame, text="📍 手动设置位置",
                   command=self.capture_button_position).pack(pady=5)

        time_frame = ttk.LabelFrame(main_frame, text="时间设置", padding="8")
        time_frame.pack(fill=tk.X, pady=10)

        ttk.Label(time_frame, text="时间间隔 (秒):",
                  font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.time_var = tk.DoubleVar(value=1.0)
        self.time_spinbox = ttk.Spinbox(time_frame, from_=0.01, to=10.0,
                                        increment=0.01, width=10,
                                        textvariable=self.time_var)
        self.time_spinbox.pack(side=tk.LEFT, padx=5)

        ttk.Label(time_frame, text="(精度：< 0.01s)",
                  font=('Arial', 9), foreground='green').pack(side=tk.LEFT, padx=5)

        control_frame = ttk.LabelFrame(main_frame, text="控制", padding="8")
        control_frame.pack(fill=tk.X, pady=10)

        btn_row = ttk.Frame(control_frame)
        btn_row.pack(fill=tk.X)

        self.start_btn = ttk.Button(btn_row, text="▶ 开始训练 (F8)",
                                    command=self.trigger_training)
        self.start_btn.pack(side=tk.LEFT, expand=True, padx=5)

        self.stop_btn = ttk.Button(btn_row, text="⏹ 停止",
                                   command=self.stop_training,
                                   state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, padx=5)

        result_frame = ttk.LabelFrame(main_frame, text="训练结果", padding="8")
        result_frame.pack(fill=tk.X, pady=10)

        self.result_label = ttk.Label(result_frame,
                                      text="等待开始...",
                                      font=('Arial', 11))
        self.result_label.pack(pady=5)

        self.status_label = ttk.Label(main_frame,
                                      text="状态：就绪",
                                      foreground="green",
                                      font=('Arial', 10, 'bold'))
        self.status_label.pack(pady=10)

        self.training_thread = None

    def capture_button_position(self):
        """捕获按钮位置"""
        time.sleep(0.1)
        x, y = pyautogui.position()
        self.button_position = (x, y)

        self.pos_label.config(
            text=f"按钮位置：({x}, {y})",
            foreground="green"
        )
        self.status_label.config(
            text=f"✓ 已记录按钮位置",
            foreground="green"
        )

        self.save_config()

    def trigger_training(self):
        """触发训练开始"""
        if not self.button_position:
            self.status_label.config(text="请先设置按钮位置 (F7)", foreground="red")
            return

        if self.running:
            return

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="状态：训练中...", foreground="orange")

        self.training_thread = threading.Thread(
            target=self.run_training, daemon=True)
        self.training_thread.start()

    def run_training(self):
        """执行训练"""
        try:
            target_time = self.time_var.get()
            x, y = self.button_position

            self.result_label.config(text="准备开始...")
            time.sleep(0.5)

            # 记录开始时间并立即点击
            start_time = self.timer.get_time()
            self.result_label.config(text="第 1 次点击！")
            FastClicker.click(x, y)

            # 精确等待指定时间（自动补偿点击延迟）
            print(f"\n[调试] 开始计时，目标时间：{target_time:.3f}s")
            self.timer.sleep(target_time, compensate_click=True)
            print(f"[调试] 计时结束")

            # 记录第二次点击的精确时间
            click_time = self.timer.get_time()
            self.result_label.config(text="第 2 次点击！")
            FastClicker.click(x, y)

            # 计算实际时间（从第一次点击到第二次点击的时间）
            actual_elapsed = click_time - start_time

            # 检测异常偏差
            time_diff = actual_elapsed - target_time
            if abs(time_diff) > 0.5:  # 偏差超过 0.5 秒
                warning_msg = (
                    f"\n⚠️ 警告：检测到重大偏差！\n"
                    f"可能原因：\n"
                    f"1. 系统卡顿（后台程序占用资源）\n"
                    f"2. CPU 频率调整\n"
                    f"3. 磁盘/内存占用过高\n\n"
                    f"建议：\n"
                    f"1. 关闭不必要的后台程序\n"
                    f"2. 设置电源模式为'高性能'\n"
                    f"3. 确保电脑散热良好\n"
                )
                print(warning_msg)
            accuracy = (1 - abs(time_diff) / target_time) * \
                100 if target_time > 0 else 0

            result_text = (
                f"✓ 完成！\n"
                f"设定时间：{target_time:.3f}s\n"
                f"实际时间：{actual_elapsed:.3f}s\n"
                f"误差：{time_diff:+.3f}s ({accuracy:.1f}% 精度)"
            )

            self.root.after(
                0, lambda: self.result_label.config(text=result_text))

            if abs(time_diff) < 0.01:
                self.status_label.config(
                    text="✓ 精度优秀！(< 0.01s)", foreground="green")
            elif abs(time_diff) < 0.05:
                self.status_label.config(
                    text="✓ 精度良好！(< 0.05s)", foreground="blue")
            else:
                self.status_label.config(text="⚠ 精度待提高", foreground="orange")

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

    def stop_training(self):
        """停止训练"""
        self.running = False
        self.status_label.config(text="已停止", foreground="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def on_closing(self):
        """关闭窗口处理"""
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
        """运行程序"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        if self.button_position:
            self.pos_label.config(
                text=f"按钮位置：({self.button_position[0]}, {self.button_position[1]})",
                foreground="green"
            )

        print("=" * 50)
        print("   ⏱️ 时间感知训练器")
        print("=" * 50)
        print("\n热键:")
        print("  F7 = 设置按钮位置")
        print("  F8 = 触发训练开始")
        print("\n使用说明:")
        print("  1. 移动鼠标到目标按钮位置")
        print("  2. 按 F7 记录按钮位置")
        print("  3. 设置时间间隔（默认 1.0 秒）")
        print("  4. 按 F8 开始训练")
        print("  5. 程序会自动点击两次按钮，间隔为设定时间")
        print("\n启动中...")

        self.root.mainloop()


if __name__ == "__main__":
    app = TimePerceptionTrainer()
    app.run()
