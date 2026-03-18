"""
反应速度测试 - 挂机刷分脚本
功能：自动循环点击，挂机刷成绩
- 每隔 1 秒点击一次（最小等待时间）
- 长时间挂机，总会碰到好成绩
- 简单粗暴但有效
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
import time
import threading
import ctypes
import json
import os

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'reaction_afk_config.json')


class AFKFarmBot:
    """挂机刷分机器人"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🤖 反应速度 - 挂机刷分脚本")
        self.root.geometry("450x500")
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)
        self.root.minsize(400, 450)

        self.click_position = None
        self.running = False
        self.config = self.load_config()

        self.setup_ui()
        self.setup_hotkeys()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if 'click_position' in config:
                    self.click_position = config['click_position']
                return config
            except:
                pass
        return {}

    def save_config(self):
        config = {
            'click_position': self.click_position
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def setup_hotkeys(self):
        import keyboard
        keyboard.add_hotkey('f7', self.capture_click_position)
        keyboard.add_hotkey('f8', self.start_farm)
        keyboard.add_hotkey('f9', self.stop_farm)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main_frame, text="🤖 反应速度 - 挂机刷分",
                          font=('Arial', 18, 'bold'))
        title.pack(pady=10)

        desc = ttk.Label(main_frame,
                         text="简单粗暴：每隔 1 秒点一次，挂机刷成绩",
                         font=('Arial', 10, 'bold'), foreground='blue')
        desc.pack(pady=5)

        hotkey_frame = ttk.LabelFrame(main_frame, text="热键说明", padding="8")
        hotkey_frame.pack(fill=tk.X, pady=10)

        ttk.Label(hotkey_frame, text="F7  = 设置点击位置",
                  font=('Arial', 10, 'bold'), foreground='green').pack(pady=2)
        ttk.Label(hotkey_frame, text="F8  = 开始挂机",
                  font=('Arial', 10, 'bold'), foreground='orange').pack(pady=2)
        ttk.Label(hotkey_frame, text="F9  = 停止挂机",
                  font=('Arial', 10, 'bold'), foreground='red').pack(pady=2)

        click_frame = ttk.LabelFrame(main_frame, text="点击位置设置", padding="8")
        click_frame.pack(fill=tk.X, pady=10)

        self.click_label = ttk.Label(click_frame,
                                     text="点击位置：未设置 (按 F7 设置)",
                                     foreground="gray", font=('Arial', 10))
        self.click_label.pack(pady=5)

        ttk.Button(click_frame, text="🎯 设置点击位置 (F7)",
                   command=self.capture_click_position).pack(pady=5)

        config_frame = ttk.LabelFrame(main_frame, text="挂机设置", padding="8")
        config_frame.pack(fill=tk.X, pady=10)

        ttk.Label(config_frame, text="点击间隔:",
                  font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.interval_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(config_frame, from_=0.5, to=5.0,
                    increment=0.1, width=8,
                    textvariable=self.interval_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(config_frame, text="秒",
                  font=('Arial', 10)).pack(side=tk.LEFT, padx=5)

        ttk.Label(config_frame, text="    ",
                  font=('Arial', 10)).pack(side=tk.LEFT)

        ttk.Label(config_frame, text="最小间隔 1 秒（游戏限制）",
                  font=('Arial', 9), foreground='gray').pack(side=tk.LEFT, padx=5)

        control_frame = ttk.LabelFrame(main_frame, text="控制", padding="8")
        control_frame.pack(fill=tk.X, pady=10)

        btn_row = ttk.Frame(control_frame)
        btn_row.pack(fill=tk.X)

        self.start_btn = ttk.Button(btn_row, text="▶ 开始挂机 (F8)",
                                    command=self.start_farm)
        self.start_btn.pack(side=tk.LEFT, expand=True, padx=5)

        self.stop_btn = ttk.Button(btn_row, text="⏹ 停止挂机 (F9)",
                                   command=self.stop_farm,
                                   state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, padx=5)

        stats_frame = ttk.LabelFrame(main_frame, text="挂机统计", padding="8")
        stats_frame.pack(fill=tk.X, pady=10)

        self.count_label = ttk.Label(stats_frame,
                                     text="点击次数：0",
                                     font=('Arial', 12, 'bold'))
        self.count_label.pack(pady=5)

        self.time_label = ttk.Label(stats_frame,
                                    text="挂机时间：0 分钟",
                                    font=('Arial', 11))
        self.time_label.pack(pady=5)

        self.status_label = ttk.Label(main_frame,
                                      text="状态：就绪",
                                      foreground="green",
                                      font=('Arial', 11, 'bold'))
        self.status_label.pack(pady=10)

        info_frame = ttk.LabelFrame(main_frame, text="刷分原理", padding="8")
        info_frame.pack(fill=tk.X, pady=10)

        info_text = tk.Text(info_frame, height=4, font=('Consolas', 9),
                           wrap=tk.WORD, bg='#f0f0f0')
        info_text.pack(fill=tk.X, pady=5)
        info_text.insert('1.0', 
            "原理：游戏随机等待 1 秒后红变绿\n"
            "策略：每隔 1 秒点一次，总会碰到正好变色的时候\n"
            "建议：挂机时间长一点，成绩会越来越好")
        info_text.config(state='disabled')

        self.farm_thread = None
        self.click_count = 0
        self.start_farm_time = None

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

    def start_farm(self):
        if not self.click_position:
            self.status_label.config(text="请先设置点击位置 (F7)", foreground="red")
            messagebox.showwarning("警告", "请先设置点击位置！\n按 F7 设置")
            return

        if self.running:
            return

        self.running = True
        self.click_count = 0
        self.start_farm_time = time.time()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="状态：挂机中...", foreground="orange")

        self.farm_thread = threading.Thread(
            target=self.run_farm, daemon=True)
        self.farm_thread.start()

    def stop_farm(self):
        self.running = False
        self.status_label.config(text="已停止", foreground="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def run_farm(self):
        try:
            interval = self.interval_var.get()
            click_x, click_y = self.click_position

            while self.running:
                # 点击
                pyautogui.click(click_x, click_y)
                self.click_count += 1

                # 更新统计
                elapsed_minutes = (time.time() - self.start_farm_time) / 60
                self.root.after(0, lambda c=self.click_count, m=elapsed_minutes:
                               self.count_label.config(text=f"点击次数：{c}"))
                self.root.after(0, lambda m=elapsed_minutes:
                               self.time_label.config(
                                   text=f"挂机时间：{m:.1f} 分钟"))

                # 等待
                for _ in range(int(interval * 10)):
                    if not self.running:
                        break
                    time.sleep(0.1)

            # 停止时显示统计
            if self.click_count > 0:
                total_minutes = (time.time() - self.start_farm_time) / 60
                self.root.after(0, lambda: messagebox.showinfo(
                    "挂机统计",
                    f"本次挂机统计:\n\n"
                    f"点击次数：{self.click_count} 次\n"
                    f"挂机时间：{total_minutes:.1f} 分钟\n"
                    f"平均每分钟：{self.click_count/total_minutes:.1f} 次\n\n"
                    f"继续挂机，成绩会越来越好！"))

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
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        if self.click_position:
            x, y = self.click_position
            self.click_label.config(
                text=f"点击位置：({x}, {y})",
                foreground="green"
            )

        print("=" * 60)
        print("   🤖 反应速度 - 挂机刷分脚本")
        print("=" * 60)
        print("\n热键:")
        print("  F7 = 设置点击位置")
        print("  F8 = 开始挂机")
        print("  F9 = 停止挂机")
        print("\n使用说明:")
        print("  1. 打开反应速度测试游戏")
        print("  2. 按 F7 设置点击位置（点击按钮的位置）")
        print("  3. 按 F8 开始挂机")
        print("  4. 脚本会自动每隔 1 秒点击一次")
        print("  5. 挂机时间越长，成绩越好")
        print("\n刷分原理:")
        print("  - 游戏随机等待≥1 秒后红变绿")
        print("  - 脚本每隔 1 秒点一次")
        print("  - 总会碰到正好变色的时候")
        print("  - 挂机一晚上，绝对有好成绩")
        print("\n启动中...")

        self.root.mainloop()


if __name__ == "__main__":
    app = AFKFarmBot()
    app.run()
