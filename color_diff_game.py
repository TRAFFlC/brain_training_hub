import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import numpy as np
from PIL import ImageGrab, ImageTk
import pyautogui
import keyboard

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


class ColorDifferenceGame:
    def __init__(self):
        self.corners = [None, None]
        self.running = False
        self.total_rounds = 40
        self.current_round = 0
        self.start_time = 0
        self.total_time = 0
        self.avg_time = 0
        self.click_delay = 0.0

    def set_corners(self, corner_idx):
        x, y = pyautogui.position()
        self.corners[corner_idx] = (x, y)
        return x, y

    def capture_game_area(self):
        if not self.corners[0] or not self.corners[1]:
            return None

        x1, y1 = self.corners[0]
        x2, y2 = self.corners[1]

        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        return screenshot, x1, y1, x2, y2

    def analyze_colors(self, screenshot):
        img_array = np.array(screenshot)

        h, w = img_array.shape[:2]

        cell_h = h // 3
        cell_w = w // 3

        colors = []
        for row in range(3):
            for col in range(3):
                center_y = row * cell_h + cell_h // 2
                center_x = col * cell_w + cell_w // 2
                
                sample_y1 = max(0, center_y - 2)
                sample_y2 = min(h, center_y + 3)
                sample_x1 = max(0, center_x - 2)
                sample_x2 = min(w, center_x + 3)
                
                cell_sample = img_array[sample_y1:sample_y2, sample_x1:sample_x2]
                pixel_color = np.mean(cell_sample, axis=(0, 1))
                colors.append(pixel_color)

        return colors

    def find_different_cell(self, colors):
        colors_array = np.array(colors)
        
        color_counts = {}
        for color in colors_array:
            key = tuple(color)
            color_counts[key] = color_counts.get(key, 0) + 1
        
        most_common_color = max(color_counts.keys(), key=lambda x: color_counts[x])
        
        different_idx = 0
        max_diff_to_common = 0
        
        for i, color in enumerate(colors_array):
            diff = np.sum(np.abs(color - np.array(most_common_color)))
            if diff > max_diff_to_common:
                max_diff_to_common = diff
                different_idx = i
        
        if max_diff_to_common < 0:
            import random
            different_idx = random.randint(0, 8)

        return different_idx, [max_diff_to_common]

    def get_cell_center(self, screenshot, cell_idx):
        img_array = np.array(screenshot)
        h, w = img_array.shape[:2]

        cell_h = h // 3
        cell_w = w // 3

        row = cell_idx // 3
        col = cell_idx % 3

        center_x = col * cell_w + cell_w // 2
        center_y = row * cell_h + cell_h // 2

        return center_x, center_y

    def click_cell(self, screenshot, x1, y1, cell_idx):
        center_x, center_y = self.get_cell_center(screenshot, cell_idx)
        click_x = x1 + center_x
        click_y = y1 + center_y
        pyautogui.click(click_x, click_y)
        return click_x, click_y


class ColorDiffGUI:
    def __init__(self):
        self.game = ColorDifferenceGame()
        self.root = tk.Tk()
        self.root.title("色差感知游戏外挂")
        self.root.geometry("500x700")
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)

        self.setup_ui()
        self.setup_hotkeys()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            main_frame,
            text="🎯 色差感知游戏外挂",
            font=('Microsoft YaHei UI', 18, 'bold')
        )
        title.pack(pady=(0, 15))

        info_frame = ttk.LabelFrame(main_frame, text="游戏说明", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(
            info_frame,
            text="3x3方格中8个颜色相同，1个颜色不同\n点击颜色不同的格子，共40轮，越快越好",
            font=('Microsoft YaHei UI', 10)
        ).pack()

        self.area_frame = ttk.LabelFrame(main_frame, text="区域设置", padding="10")
        self.area_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            self.area_frame,
            text="F9 = 设置左上角  |  F10 = 设置右下角",
            font=('Microsoft YaHei UI', 10, 'bold'),
            foreground='blue'
        ).pack(pady=5)

        self.area_label = ttk.Label(
            self.area_frame,
            text="未设置区域",
            foreground='gray'
        )
        self.area_label.pack(pady=5)

        settings_frame = ttk.LabelFrame(main_frame, text="游戏设置", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        delay_row = ttk.Frame(settings_frame)
        delay_row.pack(fill=tk.X)
        ttk.Label(delay_row, text="总轮数:").pack(side=tk.LEFT)
        self.rounds_var = tk.StringVar(value="40")
        ttk.Entry(delay_row, textvariable=self.rounds_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(delay_row, text="轮").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(delay_row, text="点击后等待:").pack(side=tk.LEFT, padx=(20, 0))
        self.delay_var = tk.StringVar(value="0.0")
        ttk.Entry(delay_row, textvariable=self.delay_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(delay_row, text="秒").pack(side=tk.LEFT)

        preview_frame = ttk.LabelFrame(main_frame, text="预览", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.preview_canvas = tk.Canvas(
            preview_frame, width=400, height=200, bg='#1a1a1a')
        self.preview_canvas.pack()

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        self.start_btn = ttk.Button(
            control_frame,
            text="🚀 开始 (S键)",
            command=self.start_game,
            width=15
        )
        self.start_btn.pack(side=tk.LEFT, padx=5, expand=True)

        self.stop_btn = ttk.Button(
            control_frame,
            text="⏹ 停止",
            command=self.stop_game,
            state=tk.DISABLED,
            width=15
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5, expand=True)

        self.stats_frame = ttk.LabelFrame(main_frame, text="统计", padding="10")
        self.stats_frame.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(
            self.stats_frame,
            text="状态: 就绪",
            font=('Microsoft YaHei UI', 12, 'bold'),
            foreground='green'
        )
        self.status_label.pack(pady=5)

        self.round_label = ttk.Label(
            self.stats_frame,
            text="当前轮次: 0",
            font=('Microsoft YaHei UI', 11)
        )
        self.round_label.pack(pady=2)

        self.time_label = ttk.Label(
            self.stats_frame,
            text="本轮用时: 0.000s",
            font=('Microsoft YaHei UI', 11)
        )
        self.time_label.pack(pady=2)

        self.total_label = ttk.Label(
            self.stats_frame,
            text="总用时: 0.000s",
            font=('Microsoft YaHei UI', 11)
        )
        self.total_label.pack(pady=2)

        self.avg_label = ttk.Label(
            self.stats_frame,
            text="平均用时: 0.000s",
            font=('Microsoft YaHei UI', 11)
        )
        self.avg_label.pack(pady=2)

        self.result_label = ttk.Label(
            main_frame,
            text="快捷键: S=开始  ESC=停止",
            font=('Microsoft YaHei UI', 9),
            foreground='gray'
        )
        self.result_label.pack(pady=(10, 0))

    def setup_hotkeys(self):
        keyboard.add_hotkey('f9', lambda: self.root.after(0, lambda: self.capture_corner(0)))
        keyboard.add_hotkey('f10', lambda: self.root.after(0, lambda: self.capture_corner(1)))
        keyboard.add_hotkey('s', lambda: self.root.after(0, self.start_game))
        keyboard.add_hotkey('esc', lambda: self.root.after(0, self.stop_game))

    def capture_corner(self, corner_idx):
        x, y = self.game.set_corners(corner_idx)
        corner_name = "左上角" if corner_idx == 0 else "右下角"
        self.root.after(0, lambda: self.status_label.config(
            text=f"已记录{corner_name}: ({x}, {y})",
            foreground="blue"
        ))

        if self.game.corners[0] and self.game.corners[1]:
            x1, y1 = self.game.corners[0]
            x2, y2 = self.game.corners[1]
            self.root.after(0, lambda: self.area_label.config(
                text=f"区域: ({min(x1, x2)}, {min(y1, y2)}) → ({max(x1, x2)}, {max(y1, y2)})",
                foreground="blue"
            ))

    def capture_preview(self):
        result = self.game.capture_game_area()
        if result is None:
            self.status_label.config(text="请先设置区域!", foreground="red")
            return

        screenshot, x1, y1, x2, y2 = result

        self.tk_preview = ImageTk.PhotoImage(screenshot)
        self.preview_canvas.delete("all")
        canvas_w = self.preview_canvas.winfo_width()
        canvas_h = self.preview_canvas.winfo_height()
        self.preview_canvas.create_image(
            canvas_w // 2, canvas_h // 2, image=self.tk_preview)

    def start_game(self):
        if not self.game.corners[0] or not self.game.corners[1]:
            messagebox.showwarning("警告", "请先设置游戏区域!\n\n步骤:\n1. 按 F9 设置左上角\n2. 按 F10 设置右下角\n3. 再按 S 开始游戏")
            return

        if self.game.running:
            return

        try:
            rounds = int(self.rounds_var.get())
            if rounds <= 0:
                raise ValueError()
            self.game.total_rounds = rounds
        except ValueError:
            messagebox.showerror("错误", "请输入有效的轮数（正整数）")
            return

        try:
            delay = float(self.delay_var.get())
            if delay < 0:
                raise ValueError()
            self.game.click_delay = delay
        except ValueError:
            messagebox.showerror("错误", "请输入有效的等待时间（正数）")
            return

        self.game.running = True
        self.game.current_round = 0
        self.game.start_time = time.time()

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="游戏进行中... (启动线程)", foreground="orange")
        self.root.update()

        thread = threading.Thread(target=self.run_game, daemon=True)
        thread.start()
        
        self.root.after(500, self.check_game_status)

    def check_game_status(self):
        if self.game.running and self.game.current_round == 0:
            self.status_label.config(text="警告: 线程可能未运行", foreground="red")
        elif not self.game.running and self.game.current_round == 0:
            self.status_label.config(text="游戏已结束", foreground="gray")

    def run_game(self):
        try:
            for round_num in range(1, self.game.total_rounds + 1):
                if not self.game.running:
                    break

                round_start = time.time()

                try:
                    result = self.game.capture_game_area()
                    if result is None:
                        self.root.after(0, lambda: self.status_label.config(
                            text="请先设置区域!", foreground="red"))
                        break

                    screenshot, x1, y1, x2, y2 = result
                except Exception as e:
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"截图错误：{str(e)}", foreground="red"))
                    break

                colors = self.game.analyze_colors(screenshot)
                different_idx, distances = self.game.find_different_cell(colors)

                max_dist = max(distances)
                if max_dist < 5.0:
                    time.sleep(0.015)
                    result2 = self.game.capture_game_area()
                    if result2:
                        screenshot2, x1_2, y1_2, _, _ = result2
                        colors2 = self.game.analyze_colors(screenshot2)
                        different_idx2, _ = self.game.find_different_cell(colors2)
                        if different_idx2 != different_idx:
                            different_idx = different_idx2

                try:
                    self.game.click_cell(screenshot, x1, y1, different_idx)
                except Exception as e:
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"点击错误: {str(e)}", foreground="red"))
                    break

                if self.game.click_delay > 0:
                    time.sleep(self.game.click_delay)

                round_time = time.time() - round_start

                self.game.current_round = round_num
                total_time = time.time() - self.game.start_time
                avg_time = total_time / round_num

                self.root.after(0, lambda r=round_num, t=self.game.total_rounds: self.round_label.config(
                    text=f"当前轮次: {r}/{t}"))
                self.root.after(0, lambda: self.time_label.config(
                    text=f"本轮用时: {round_time:.3f}s"))
                self.root.after(0, lambda: self.total_label.config(
                    text=f"总用时: {total_time:.3f}s"))
                self.root.after(0, lambda: self.avg_label.config(
                    text=f"平均用时: {avg_time:.3f}s"))

            if self.game.running:
                self.game.running = False
                total_time = time.time() - self.game.start_time
                rounds_played = self.game.current_round
                avg_time = total_time / rounds_played if rounds_played > 0 else 0

                self.root.after(0, lambda: self.status_label.config(
                    text=f"✅ 完成! 总用时: {total_time:.3f}s 平均: {avg_time:.3f}s",
                    foreground="green"
                ))
                self.root.after(0, lambda: messagebox.showinfo(
                    "完成",
                    f"恭喜完成{rounds_played}轮!\n总用时: {total_time:.3f}s\n平均用时: {avg_time:.3f}s"
                ))

        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(
                text=f"错误: {str(e)}", foreground="red"))
        finally:
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))

    def stop_game(self):
        self.game.running = False
        self.status_label.config(text="已停止", foreground="red")

    def on_closing(self):
        keyboard.unhook_all()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 50)
    print("   色差感知游戏外挂")
    print("=" * 50)
    print("\n快捷键:")
    print("  F9  = 设置左上角")
    print("  F10 = 设置右下角")
    print("  S   = 开始游戏")
    print("\n启动中...")

    app = ColorDiffGUI()
    app.run()
