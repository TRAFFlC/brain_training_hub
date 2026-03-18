"""
顺序记忆训练外挂
游戏规则：3x3网格中，方块按顺序亮起，玩家需要按相同顺序点击
策略：检测方块颜色变化，记录亮起顺序，然后自动点击
"""

import pyautogui
import time
import tkinter as tk
from tkinter import ttk
from PIL import ImageGrab, ImageTk
import threading
import keyboard
import numpy as np

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.005


class SequenceMemoryAuto:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("顺序记忆训练助手")
        self.root.attributes('-topmost', True)

        self.corners = [None, None]
        self.running = False
        self.current_level = 1
        self.sequence = []
        self.cell_centers = []
        self.baseline_brightness = []
        self.grid_w = 0
        self.grid_h = 0

        self.setup_ui()
        self.setup_global_hotkey()

    def setup_global_hotkey(self):
        keyboard.add_hotkey('f9', lambda: self.capture_corner(0))
        keyboard.add_hotkey('f10', lambda: self.capture_corner(1))
        keyboard.add_hotkey('s', self.start_game)
        keyboard.add_hotkey('r', self.reset_level)
        keyboard.add_hotkey('d', self.debug_brightness)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main_frame, text="顺序记忆训练助手",
                          font=('Arial', 18, 'bold'))
        title.pack(pady=10)

        desc_frame = ttk.LabelFrame(main_frame, text="游戏说明", padding="10")
        desc_frame.pack(fill=tk.X, pady=5)
        ttk.Label(desc_frame, text="方块按顺序亮起，需要按相同顺序点击。成功后难度+1",
                  foreground="gray", font=('Arial', 10)).pack()

        config_frame = ttk.LabelFrame(main_frame, text="参数设置", padding="10")
        config_frame.pack(fill=tk.X, pady=5)

        row1 = ttk.Frame(config_frame)
        row1.pack(fill=tk.X, pady=5)

        ttk.Label(row1, text="亮度阈值:", font=('Arial', 10)).pack(side=tk.LEFT)
        self.threshold_var = tk.IntVar(value=30)
        ttk.Spinbox(row1, from_=10, to=100, width=6,
                    textvariable=self.threshold_var).pack(side=tk.LEFT, padx=5)

        ttk.Label(row1, text="    ", font=('Arial', 10)).pack(side=tk.LEFT)

        ttk.Label(row1, text="点击间隔:", font=('Arial', 10)).pack(side=tk.LEFT)
        self.click_delay_var = tk.DoubleVar(value=0.1)
        ttk.Spinbox(row1, from_=0.05, to=1.0, increment=0.05, width=6,
                    textvariable=self.click_delay_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="秒", font=('Arial', 10)).pack(side=tk.LEFT)

        row2 = ttk.Frame(config_frame)
        row2.pack(fill=tk.X, pady=5)

        ttk.Label(row2, text="检测间隔:", font=('Arial', 10)).pack(side=tk.LEFT)
        self.flash_interval_var = tk.DoubleVar(value=0.1)
        ttk.Spinbox(row2, from_=0.05, to=0.5, increment=0.05, width=6,
                    textvariable=self.flash_interval_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="秒", font=('Arial', 10)).pack(side=tk.LEFT)

        ttk.Label(row2, text="    ", font=('Arial', 10)).pack(side=tk.LEFT)

        ttk.Label(row2, text="结束等待:", font=('Arial', 10)).pack(side=tk.LEFT)
        self.end_wait_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(row2, from_=0.5, to=3.0, increment=0.1, width=6,
                    textvariable=self.end_wait_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="秒", font=('Arial', 10)).pack(side=tk.LEFT)

        area_frame = ttk.LabelFrame(main_frame, text="设置游戏区域", padding="10")
        area_frame.pack(fill=tk.X, pady=5)

        hotkey_row = ttk.Frame(area_frame)
        hotkey_row.pack(pady=5)
        ttk.Label(hotkey_row, text="F9 = 左上角", font=(
            'Arial', 12, 'bold'), foreground='blue').pack(side=tk.LEFT, padx=30)
        ttk.Label(hotkey_row, text="F10 = 右下角", font=(
            'Arial', 12, 'bold'), foreground='blue').pack(side=tk.LEFT, padx=30)

        self.area_label = ttk.Label(
            area_frame, text="移动鼠标到位置，按 F9/F10 确认", foreground="gray", font=('Arial', 10))
        self.area_label.pack(pady=5)

        level_frame = ttk.LabelFrame(main_frame, text="当前状态", padding="10")
        level_frame.pack(fill=tk.X, pady=5)

        self.level_label = ttk.Label(
            level_frame, text="当前难度: 1", font=('Arial', 14, 'bold'), foreground="blue")
        self.level_label.pack(pady=5)

        self.sequence_label = ttk.Label(
            level_frame, text="记录序列: []", font=('Arial', 11), foreground="gray")
        self.sequence_label.pack(pady=3)

        self.brightness_label = ttk.Label(
            level_frame, text="", font=('Arial', 9), foreground="gray")
        self.brightness_label.pack(pady=3)

        preview_frame = ttk.LabelFrame(main_frame, text="网格预览", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.preview_canvas = tk.Canvas(
            preview_frame, width=300, height=200, bg='#1a1a2e')
        self.preview_canvas.pack(pady=5)

        action_frame = ttk.LabelFrame(main_frame, text="操作", padding="10")
        action_frame.pack(fill=tk.X, pady=5)

        btn_row1 = ttk.Frame(action_frame)
        btn_row1.pack(fill=tk.X, pady=5)

        ttk.Button(btn_row1, text="重置难度 (R键)", command=self.reset_level,
                   width=15).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(btn_row1, text="调试亮度 (D键)", command=self.debug_brightness,
                   width=15).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(btn_row1, text="开始 (S键)", command=self.start_game,
                   width=15).pack(side=tk.LEFT, padx=5, expand=True)

        btn_row2 = ttk.Frame(action_frame)
        btn_row2.pack(fill=tk.X, pady=5)

        self.start_btn = ttk.Button(
            btn_row2, text="开始游戏", command=self.start_game, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=10, expand=True)

        self.stop_btn = ttk.Button(
            btn_row2, text="停止", command=self.stop_auto, state=tk.DISABLED, width=15)
        self.stop_btn.pack(side=tk.LEFT, padx=10, expand=True)

        self.status_label = ttk.Label(
            main_frame, text="状态: 就绪 - 请设置游戏区域", foreground="green", font=('Arial', 12))
        self.status_label.pack(pady=8)

    def capture_corner(self, corner_idx):
        x, y = pyautogui.position()
        self.corners[corner_idx] = (x, y)

        corner_name = "左上角" if corner_idx == 0 else "右下角"

        self.root.after(0, lambda: self.status_label.config(
            text=f"已记录{corner_name}: ({x}, {y})", foreground="blue"))

        if self.corners[0] and self.corners[1]:
            x1, y1 = self.corners[0]
            x2, y2 = self.corners[1]
            self.root.after(0, lambda: self.area_label.config(
                text=f"区域: ({min(x1, x2)}, {min(y1, y2)}) -> ({max(x1, x2)}, {max(y1, y2)})",
                foreground="blue"
            ))
            self.calculate_cell_centers()

    def calculate_cell_centers(self):
        if not self.corners[0] or not self.corners[1]:
            return

        x1, y1 = self.corners[0]
        x2, y2 = self.corners[1]

        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        self.grid_w = x2 - x1
        self.grid_h = y2 - y1
        cell_w = self.grid_w / 3
        cell_h = self.grid_h / 3

        self.cell_centers = []
        for row in range(3):
            for col in range(3):
                center_x = x1 + col * cell_w + cell_w / 2
                center_y = y1 + row * cell_h + cell_h / 2
                self.cell_centers.append((center_x, center_y))

        self.draw_grid_preview()

    def draw_grid_preview(self, highlight_idx=-1):
        self.preview_canvas.delete("all")

        canvas_w = 300
        canvas_h = 200
        margin = 20
        grid_size = min(canvas_w - 2 * margin, canvas_h - 2 * margin)
        cell_size = grid_size / 3

        start_x = (canvas_w - grid_size) / 2
        start_y = (canvas_h - grid_size) / 2

        for i in range(3):
            for j in range(3):
                idx = i * 3 + j
                x1 = start_x + j * cell_size
                y1 = start_y + i * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size

                if idx == highlight_idx:
                    color = '#00ff00'
                else:
                    color = '#3a3a5a'

                self.preview_canvas.create_rectangle(
                    x1, y1, x2, y2, fill=color, outline='#666', width=2)
                self.preview_canvas.create_text(
                    (x1 + x2) / 2, (y1 + y2) / 2,
                    text=str(idx + 1), fill='white', font=('Arial', 14, 'bold')
                )

    def get_cell_brightness(self, img_array, cell_idx):
        if self.grid_w == 0 or self.grid_h == 0:
            return 0

        cell_w = self.grid_w / 3
        cell_h = self.grid_h / 3

        row = cell_idx // 3
        col = cell_idx % 3

        cell_x1 = int(col * cell_w + cell_w * 0.1)
        cell_y1 = int(row * cell_h + cell_h * 0.1)
        cell_x2 = int((col + 1) * cell_w - cell_w * 0.1)
        cell_y2 = int((row + 1) * cell_h - cell_h * 0.1)

        if cell_y2 > img_array.shape[0]:
            cell_y2 = img_array.shape[0]
        if cell_x2 > img_array.shape[1]:
            cell_x2 = img_array.shape[1]

        cell_region = img_array[cell_y1:cell_y2, cell_x1:cell_x2]

        if cell_region.size == 0:
            return 0

        gray = np.mean(cell_region, axis=2)
        return np.mean(gray)

    def calibrate_baseline(self):
        if not self.corners[0] or not self.corners[1]:
            return False

        x1, y1 = self.corners[0]
        x2, y2 = self.corners[1]

        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        img_array = np.array(screenshot)

        self.baseline_brightness = []
        for i in range(9):
            brightness = self.get_cell_brightness(img_array, i)
            self.baseline_brightness.append(brightness)

        return True

    def detect_lit_cell(self):
        if not self.corners[0] or not self.corners[1]:
            return -1, []

        x1, y1 = self.corners[0]
        x2, y2 = self.corners[1]

        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        img_array = np.array(screenshot)

        threshold = self.threshold_var.get()
        max_diff = 0
        lit_cell = -1
        diffs = []

        for i in range(9):
            if i >= len(self.baseline_brightness):
                continue

            current_brightness = self.get_cell_brightness(img_array, i)
            diff = current_brightness - self.baseline_brightness[i]
            diffs.append(diff)

            if diff > threshold and diff > max_diff:
                max_diff = diff
                lit_cell = i

        return lit_cell, diffs

    def debug_brightness(self):
        if not self.corners[0] or not self.corners[1]:
            self.status_label.config(text="请先设置区域!", foreground="red")
            return

        self.calibrate_baseline()

        x1, y1 = self.corners[0]
        x2, y2 = self.corners[1]
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        img_array = np.array(screenshot)

        current_brightness = []
        for i in range(9):
            b = self.get_cell_brightness(img_array, i)
            current_brightness.append(b)

        diffs = [current_brightness[i] - self.baseline_brightness[i] for i in range(9)]

        info = f"基准: {[int(b) for b in self.baseline_brightness]}\n"
        info += f"当前: {[int(b) for b in current_brightness]}\n"
        info += f"差值: {[int(d) for d in diffs]}"
        self.brightness_label.config(text=info)

        self.status_label.config(text=f"调试: 最大差值={max(diffs):.1f}, 阈值={self.threshold_var.get()}", foreground="blue")

    def reset_level(self):
        self.current_level = 1
        self.sequence = []
        self.root.after(0, lambda: self.level_label.config(
            text="当前难度: 1", foreground="blue"))
        self.root.after(0, lambda: self.sequence_label.config(
            text="记录序列: []", foreground="gray"))
        self.root.after(0, lambda: self.status_label.config(
            text="难度已重置为1", foreground="green"))

    def start_game(self):
        if not self.corners[0] or not self.corners[1]:
            self.root.after(0, lambda: self.status_label.config(
                text="请先设置区域!", foreground="red"))
            return

        if self.running:
            return

        self.running = True
        self.sequence = []

        self.root.after(0, lambda: self.start_btn.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.stop_btn.config(state=tk.NORMAL))

        thread = threading.Thread(target=self.run_game, daemon=True)
        thread.start()

    def run_game(self):
        try:
            self.root.after(0, lambda: self.status_label.config(
                text="校准基准亮度...", foreground="orange"))

            if not self.calibrate_baseline():
                self.root.after(0, lambda: self.status_label.config(
                    text="校准失败!", foreground="red"))
                return

            time.sleep(0.2)

            self.root.after(0, lambda: self.status_label.config(
                text=f"等待方块亮起... (当前难度: {self.current_level})", foreground="blue"))

            check_interval = self.flash_interval_var.get()
            end_wait = self.end_wait_var.get()

            last_lit_cell = -1
            last_lit_time = 0
            no_lit_count = 0

            while self.running:
                lit_cell, diffs = self.detect_lit_cell()

                if lit_cell >= 0:
                    if lit_cell != last_lit_cell:
                        self.sequence.append(lit_cell)
                        last_lit_cell = lit_cell
                        last_lit_time = time.time()
                        no_lit_count = 0

                        self.root.after(0, lambda idx=lit_cell: self.draw_grid_preview(idx))
                        self.root.after(0, lambda seq=self.sequence.copy(): self.sequence_label.config(
                            text=f"记录序列: {[x+1 for x in seq]}", foreground="blue"))

                        self.root.after(0, lambda: self.status_label.config(
                            text=f"检测到方块 {lit_cell + 1} 亮起 (差值: {max(diffs):.1f})", foreground="orange"))
                    else:
                        no_lit_count = 0
                else:
                    if last_lit_cell >= 0:
                        no_lit_count += 1

                        time_since_last = time.time() - last_lit_time
                        if time_since_last > end_wait and no_lit_count > 3:
                            break

                        if len(self.sequence) >= self.current_level + 5:
                            break

                time.sleep(check_interval)

            if not self.running:
                return

            self.root.after(0, lambda: self.status_label.config(
                text=f"序列记录完成: {[x+1 for x in self.sequence]}", foreground="green"))

            self.root.after(0, lambda: self.draw_grid_preview(-1))

            time.sleep(0.3)

            self.root.after(0, lambda: self.status_label.config(
                text="开始按顺序点击...", foreground="orange"))

            click_delay = self.click_delay_var.get()

            for i, cell_idx in enumerate(self.sequence):
                if not self.running:
                    break

                if cell_idx < len(self.cell_centers):
                    x, y = self.cell_centers[cell_idx]
                    pyautogui.click(x, y)

                    self.root.after(0, lambda idx=cell_idx: self.draw_grid_preview(idx))
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"点击方块 {cell_idx + 1} ({i+1}/{len(self.sequence)})", foreground="orange"))

                    if click_delay > 0:
                        time.sleep(click_delay)

            if self.running:
                self.current_level += 1
                self.root.after(0, lambda: self.level_label.config(
                    text=f"当前难度: {self.current_level}", foreground="green"))
                self.root.after(0, lambda: self.status_label.config(
                    text=f"成功! 难度提升至 {self.current_level}", foreground="green"))

                time.sleep(1.0)

                if self.running:
                    self.sequence = []
                    self.run_game()
                    return

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self.status_label.config(
                text=f"错误: {str(e)}", foreground="red"))
        finally:
            if not self.running:
                self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
                self.root.after(0, lambda: self.draw_grid_preview(-1))
            self.running = False

    def stop_auto(self):
        self.running = False
        self.status_label.config(text="已停止", foreground="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.draw_grid_preview(-1)

    def on_closing(self):
        keyboard.unhook_all()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 50)
    print("   顺序记忆训练助手")
    print("=" * 50)
    print("\n游戏规则:")
    print("  方块按顺序亮起，需要按相同顺序点击")
    print("  成功后难度+1，序列会变长")
    print("\n快捷键:")
    print("  F9  = 设置左上角")
    print("  F10 = 设置右下角")
    print("  S   = 开始游戏")
    print("  R   = 重置难度为1")
    print("  D   = 调试亮度")
    print("\n启动中...")

    app = SequenceMemoryAuto()
    app.run()
