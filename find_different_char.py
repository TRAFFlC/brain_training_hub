"""
找不同的字 - 自动通关外挂
使用pHash图像相似度匹配，右上角目标字与10*10网格中的字进行比对
"""

import tkinter as tk
from tkinter import ttk
import pyautogui
import time
import threading
import cv2
import numpy as np
from PIL import ImageGrab, ImageTk, Image
import keyboard
import os
import imagehash
from datetime import datetime

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'


class FindDifferentChar:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("找不同的字 - 自动通关")
        self.root.geometry("450x680")
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)

        self.target_char_hash = None
        self.target_corner = (1545, 444)
        self.grid_corner = [(808, 484), (1558, 1234)]
        self.running = False
        self.auto_mode = False

        self.grid_size = 10
        self.click_delay = 0.05
        self.similarity_threshold = 5
        self.char_size = 25

        self.preview_scale = 1.0

        self.debug_mode = True
        DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_find_char')
        if not os.path.exists(DEBUG_DIR):
            os.makedirs(DEBUG_DIR)

        self.setup_ui()
        self.setup_hotkeys()
        self.update_area_label()

    def setup_hotkeys(self):
        keyboard.add_hotkey('f9', lambda: self.set_corner(0))
        keyboard.add_hotkey('f10', lambda: self.set_corner(1))
        keyboard.add_hotkey('f11', lambda: self.set_corner(2))
        keyboard.add_hotkey('s', self.one_click_start)
        keyboard.add_hotkey('w', self.start_auto_mode)
        keyboard.add_hotkey('esc', self.stop_all)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main_frame, text="🔍 找不同的字", font=('Microsoft YaHei UI', 18, 'bold'))
        title.pack(pady=(0, 15))

        settings_frame = ttk.LabelFrame(main_frame, text="参数设置", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        delay_frame = ttk.Frame(settings_frame)
        delay_frame.pack(fill=tk.X)
        ttk.Label(delay_frame, text="点击延迟:").pack(side=tk.LEFT)
        self.delay_var = tk.DoubleVar(value=0.05)
        ttk.Spinbox(delay_frame, from_=0.0, to=1.0, increment=0.01, width=8,
                    textvariable=self.delay_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(delay_frame, text="秒").pack(side=tk.LEFT)

        scale_frame = ttk.Frame(settings_frame)
        scale_frame.pack(fill=tk.X, pady=5)
        ttk.Label(scale_frame, text="预览缩放:").pack(side=tk.LEFT)
        self.scale_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(scale_frame, from_=0.3, to=2.0, increment=0.1, width=6,
                    textvariable=self.scale_var).pack(side=tk.LEFT, padx=5)
        ttk.Button(scale_frame, text="应用缩放", command=self.apply_scale).pack(side=tk.LEFT, padx=5)

        threshold_frame = ttk.Frame(settings_frame)
        threshold_frame.pack(fill=tk.X, pady=5)
        ttk.Label(threshold_frame, text="相似度阈值:").pack(side=tk.LEFT)
        self.threshold_var = tk.IntVar(value=5)
        ttk.Spinbox(threshold_frame, from_=1, to=20, width=6,
                    textvariable=self.threshold_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(threshold_frame, text="(越小越严格)").pack(side=tk.LEFT)

        size_frame = ttk.Frame(settings_frame)
        size_frame.pack(fill=tk.X, pady=5)
        ttk.Label(size_frame, text="字符尺寸:").pack(side=tk.LEFT)
        self.size_var = tk.IntVar(value=25)
        ttk.Spinbox(size_frame, from_=20, to=60, width=6,
                    textvariable=self.size_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(size_frame, text="像素").pack(side=tk.LEFT)

        area_frame = ttk.LabelFrame(main_frame, text="区域设置 (游戏中操作)", padding="10")
        area_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(area_frame, text="F9  = 设置目标字区域 (右上角)", font=('Arial', 11, 'bold'), foreground='blue').pack(pady=2)
        ttk.Label(area_frame, text="F10 = 设置10*10区域左上角", font=('Arial', 11, 'bold'), foreground='green').pack(pady=2)
        ttk.Label(area_frame, text="F11 = 设置10*10区域右下角", font=('Arial', 11, 'bold'), foreground='purple').pack(pady=2)

        self.area_label = ttk.Label(area_frame, text="请依次设置目标字区域和10*10区域", foreground="gray", font=('Arial', 10))
        self.area_label.pack(pady=5)

        preview_frame = ttk.LabelFrame(main_frame, text="预览 (可拖拽调整大小)", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.target_canvas = tk.Canvas(preview_frame, width=80, height=80, bg='#1a1a1a')
        self.target_canvas.pack(pady=2)
        self.target_label = ttk.Label(preview_frame, text="目标字: 未设置", font=('Arial', 14, 'bold'))
        self.target_label.pack()

        self.grid_canvas = tk.Canvas(preview_frame, width=400, height=400, bg='#1a1a1a')
        self.grid_canvas.pack(pady=5, fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="📷 截图预览 (S)", command=self.one_click_start).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        ttk.Button(btn_frame, text="🔄 自动模式 (W)", command=self.start_auto_mode).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X)

        self.start_btn = ttk.Button(control_frame, text="▶ 开始", command=self.start_auto_mode)
        self.start_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        self.stop_btn = ttk.Button(control_frame, text="⏹ 停止", command=self.stop_all, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        self.status_label = ttk.Label(main_frame, text="状态: 就绪 - 按 S 预览, W 自动模式", foreground="green", font=('Arial', 11))
        self.status_label.pack(pady=5)

        info_label = ttk.Label(main_frame, text="快捷键: F9=目标区 F10=网格左上 F11=网格右下 S=预览 W=自动 ESC=停止",
                               font=('Arial', 8), foreground="gray")
        info_label.pack(pady=(5, 0))

    def apply_scale(self):
        self.preview_scale = self.scale_var.get()
        self.similarity_threshold = self.threshold_var.get()
        self.char_size = self.size_var.get()
        self.status_label.config(text=f"缩放:{self.preview_scale}x, 阈值:{self.similarity_threshold}, 尺寸:{self.char_size}px", foreground="blue")

    def set_corner(self, corner_idx):
        x, y = pyautogui.position()

        if corner_idx == 0:
            self.target_corner = (x, y)
            self.root.after(0, lambda: self.status_label.config(
                text=f"目标字区域: ({x}, {y})", foreground="blue"))
        elif corner_idx == 1:
            if self.grid_corner is None:
                self.grid_corner = [(x, y), None]
            else:
                self.grid_corner[0] = (x, y)
            self.root.after(0, lambda: self.status_label.config(
                text=f"网格左上角: ({x}, {y})", foreground="green"))
        elif corner_idx == 2:
            if self.grid_corner is None:
                self.grid_corner = [None, (x, y)]
            else:
                self.grid_corner[1] = (x, y)
            self.root.after(0, lambda: self.status_label.config(
                text=f"网格右下角: ({x}, {y})", foreground="purple"))

        self.update_area_label()

    def update_area_label(self):
        parts = []
        if self.target_corner:
            parts.append(f"目标区: {self.target_corner}")
        if self.grid_corner and self.grid_corner[0]:
            parts.append(f"网格左上: {self.grid_corner[0]}")
        if self.grid_corner and self.grid_corner[1]:
            parts.append(f"网格右下: {self.grid_corner[1]}")

        if parts:
            self.area_label.config(text=" | ".join(parts), foreground="black")
        else:
            self.area_label.config(text="请依次设置目标字区域和10*10区域", foreground="gray")

    def capture_target_char(self):
        if not self.target_corner:
            return None

        x, y = self.target_corner
        size = self.char_size
        bbox = (x - size//2, y - size//2, x + size//2, y + size//2)

        try:
            img = ImageGrab.grab(bbox=bbox)
            return img
        except:
            return None

    def capture_grid(self):
        if not self.grid_corner or not self.grid_corner[0] or not self.grid_corner[1]:
            return None

        x1, y1 = self.grid_corner[0]
        x2, y2 = self.grid_corner[1]

        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        try:
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            return img, x1, y1, x2, y2
        except:
            return None

    def crop_char_from_cell(self, img_array, use_bg=False):
        target_size = 36

        h, w = img_array.shape[:2]
        if h == 0 or w == 0:
            return np.zeros((target_size, target_size, 3), dtype=np.uint8)

        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        if use_bg:
            bg_size = 72
            bg = np.ones((bg_size, bg_size), dtype=np.uint8) * 255

            if w > 0 and h > 0:
                if w > bg_size or h > bg_size:
                    scale = min(bg_size / w, bg_size / h)
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    resized = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
                else:
                    resized = gray

                rh, rw = resized.shape[:2]
                y_offset = (bg_size - rh) // 2
                x_offset = (bg_size - rw) // 2
                bg[y_offset:y_offset+rh, x_offset:x_offset+rw] = resized

            gray = bg

        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        binary_resized = cv2.resize(binary, (target_size, target_size), interpolation=cv2.INTER_CUBIC)
        result = cv2.cvtColor(binary_resized, cv2.COLOR_GRAY2RGB)

        return result

    def get_phash(self, img):
        if isinstance(img, np.ndarray):
            img = Image.fromarray(img)

        try:
            hash_val = imagehash.phash(img, hash_size=8)
            return hash_val
        except:
            return None

    def compare_hashes(self, hash1, hash2):
        if hash1 is None or hash2 is None:
            return 999
        return hash1 - hash2

    def recognize_grid_with_p_hash(self):
        grid_data = self.capture_grid()
        if not grid_data:
            return None, None, None, None, None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_find_char')

        img, x1, y1, x2, y2 = grid_data
        img_array = np.array(img)
        h, w = img_array.shape[:2]

        col_widths = [71 if i in [0, 4, 7] else 72 for i in range(10)]
        row_heights = [71 if i in [2, 5, 9] else 72 for i in range(10)]
        border_line_width = 3

        threshold = self.threshold_var.get()
        found_positions = []

        if self.debug_mode:
            target_img = self.capture_target_char()
            if target_img:
                target_array = np.array(target_img)
                cropped_target = self.crop_char_from_cell(target_array)
                cv2.imwrite(os.path.join(debug_dir, f"{timestamp}_target.png"), cropped_target)
            with open(os.path.join(debug_dir, f"{timestamp}_grid_info.txt"), 'w', encoding='utf-8') as f:
                f.write(f"网格尺寸: {w}x{h}\n")
                f.write(f"列宽度: {col_widths}\n")
                f.write(f"行高度: {row_heights}\n")

        for row in range(self.grid_size):
            for col in range(self.grid_size):
                cell_center_x = border_line_width + col * border_line_width + sum(col_widths[:col]) + col_widths[col] / 2
                cell_center_y = border_line_width + row * border_line_width + sum(row_heights[:row]) + row_heights[row] / 2

                cell_w = col_widths[col]
                cell_h = row_heights[row]
                cx1 = int(cell_center_x - cell_w / 2)
                cy1 = int(cell_center_y - cell_h / 2)
                cx2 = int(cell_center_x + cell_w / 2)
                cy2 = int(cell_center_y + cell_h / 2)

                cx1 = max(0, cx1)
                cy1 = max(0, cy1)
                cx2 = min(w, cx2)
                cy2 = min(h, cy2)

                cell_img = img_array[cy1:cy2, cx1:cx2]

                if cell_img.size == 0:
                    continue

                if self.debug_mode:
                    cv2.imwrite(os.path.join(debug_dir, f"{timestamp}_cell_{row}_{col}_raw.png"), cell_img)

                cropped = self.crop_char_from_cell(cell_img)
                cell_hash = self.get_phash(cropped)

                if self.debug_mode:
                    cv2.imwrite(os.path.join(debug_dir, f"{timestamp}_cell_{row}_{col}.png"), cropped)

                if cell_hash and self.target_char_hash is not None:
                    diff = self.compare_hashes(cell_hash, self.target_char_hash)

                    if self.debug_mode:
                        with open(os.path.join(debug_dir, f"{timestamp}_log.txt"), 'a', encoding='utf-8') as f:
                            f.write(f"Cell[{row},{col}]: center=({cell_center_x:.1f},{cell_center_y:.1f}) size={cell_w}x{cell_h} hash={cell_hash}, target={self.target_char_hash}, diff={diff}, match={diff <= threshold}\n")

                    if diff <= threshold:
                        screen_x = x1 + cell_center_x
                        screen_y = y1 + cell_center_y
                        found_positions.append((screen_x, screen_y, diff))

        if found_positions:
            min_diff = min(pos[2] for pos in found_positions)
            found_positions = [pos for pos in found_positions if pos[2] == min_diff]

        return found_positions, img, x1, y1, x2, y2

    def show_preview(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_find_char')

        target_img = self.capture_target_char()

        if target_img:
            scale = self.preview_scale
            display_size = int(80 * scale)
            self.target_photo = ImageTk.PhotoImage(target_img.resize((display_size, display_size)))
            self.target_canvas.delete("all")
            self.target_canvas.config(width=display_size, height=display_size)
            self.target_canvas.create_image(display_size//2, display_size//2, image=self.target_photo)

            cropped = self.crop_char_from_cell(np.array(target_img), use_bg=True)
            self.target_char_hash = self.get_phash(cropped)

            if self.debug_mode:
                cv2.imwrite(os.path.join(debug_dir, f"{timestamp}_target_original.png"), np.array(target_img))
                cv2.imwrite(os.path.join(debug_dir, f"{timestamp}_target_cropped.png"), cropped)
                with open(os.path.join(debug_dir, f"{timestamp}_params.txt"), 'w', encoding='utf-8') as f:
                    f.write(f"时间: {timestamp}\n")
                    f.write(f"字符尺寸: {self.char_size}\n")
                    f.write(f"相似度阈值: {self.threshold_var.get()}\n")
                    f.write(f"目标Hash: {self.target_char_hash}\n")
                    f.write(f"网格坐标: {self.grid_corner}\n")

            if self.target_char_hash:
                self.target_label.config(text=f"目标字: 已锁定 (pHash)", foreground="blue")
            else:
                self.target_label.config(text="目标字: 获取失败", foreground="red")

        grid_data = self.capture_grid()
        if grid_data:
            img, x1, y1, x2, y2 = grid_data

            if self.debug_mode:
                cv2.imwrite(os.path.join(debug_dir, f"{timestamp}_grid_full.png"), np.array(img))

            canvas_w = self.grid_canvas.winfo_width()
            canvas_h = self.grid_canvas.winfo_height()
            if canvas_w < 100:
                canvas_w = 400
                canvas_h = 400

            img_w, img_h = img.size
            scale_x = canvas_w / img_w
            scale_y = canvas_h / img_h
            display_scale = min(scale_x, scale_y)

            display_w = int(img_w * display_scale)
            display_h = int(img_h * display_scale)

            img_display = img.resize((display_w, display_h))
            self.grid_photo = ImageTk.PhotoImage(img_display)
            self.grid_canvas.delete("all")
            self.grid_canvas.config(width=display_w, height=display_h)
            self.grid_canvas.create_image(display_w//2, display_h//2, image=self.grid_photo)

            self.root.after(100, self.recognize_and_highlight)

    def recognize_and_highlight(self):
        if not self.target_char_hash:
            return

        found_positions, img, x1, y1, x2, y2 = self.recognize_grid_with_p_hash()

        canvas_w = self.grid_canvas.winfo_width()
        canvas_h = self.grid_canvas.winfo_height()
        if canvas_w < 100:
            canvas_w = 400
            canvas_h = 400

        border_w = int((x2 - x1) * 0.03)
        border_h = int((y2 - y1) * 0.03)

        if found_positions:
            self.status_label.config(text=f"找到 {len(found_positions)} 个匹配, 阈值:{self.threshold_var.get()}", foreground="green")

            display_scale_x = canvas_w / (x2 - x1)
            display_scale_y = canvas_h / (y2 - y1)

            for fx, fy, diff in found_positions:
                dx = (fx - x1) * display_scale_x
                dy = (fy - y1) * display_scale_y
                self.grid_canvas.create_oval(dx-5, dy-5, dx+5, dy+5, outline="red", width=3)
        else:
            self.status_label.config(text=f"未找到匹配 (阈值:{self.threshold_var.get()})", foreground="orange")

    def one_click_start(self):
        if not self.target_corner or not self.grid_corner or not self.grid_corner[0] or not self.grid_corner[1]:
            self.status_label.config(text="请先设置所有区域!", foreground="red")
            return

        self.status_label.config(text="正在识别...", foreground="orange")
        self.root.update()

        self.show_preview()

    def start_auto_mode(self):
        if not self.target_corner or not self.grid_corner or not self.grid_corner[0] or not self.grid_corner[1]:
            self.status_label.config(text="请先设置所有区域!", foreground="red")
            return

        if self.running:
            return

        self.running = True
        self.auto_mode = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="自动模式运行中...", foreground="green")

        threading.Thread(target=self.run_auto_mode, daemon=True).start()

    def run_auto_mode(self):
        consecutive_fails = 0
        max_fails = 5

        while self.running and self.auto_mode:
            try:
                target_img = self.capture_target_char()
                if not target_img:
                    consecutive_fails += 1
                    if consecutive_fails >= max_fails:
                        self.root.after(0, lambda: self.status_label.config(text="无法捕获目标区域!", foreground="red"))
                        break
                    time.sleep(0.5)
                    continue

                cropped = self.crop_char_from_cell(np.array(target_img), use_bg=True)
                self.target_char_hash = self.get_phash(cropped)

                if not self.target_char_hash:
                    consecutive_fails += 1
                    if consecutive_fails >= max_fails:
                        self.root.after(0, lambda: self.status_label.config(text="无法识别目标字!", foreground="red"))
                        break
                    time.sleep(0.5)
                    continue

                consecutive_fails = 0

                self.root.after(0, lambda: self.target_label.config(text="目标字: 已锁定 (pHash)", foreground="blue"))

                found_positions, img, x1, y1, x2, y2 = self.recognize_grid_with_p_hash()

                if not found_positions:
                    self.root.after(0, lambda: self.status_label.config(
                        text="未找到匹配, 等待重试...", foreground="orange"))
                    time.sleep(0.3)
                    continue

                delay = self.delay_var.get()

                for fx, fy, diff in found_positions:
                    if not self.running or not self.auto_mode:
                        break
                    pyautogui.click(fx, fy)
                    time.sleep(delay)

                self.root.after(0, lambda: self.status_label.config(
                    text=f"✓ 点击了 {len(found_positions)} 个匹配", foreground="green"))

                time.sleep(0.5)

            except Exception as e:
                print(f"自动模式错误: {e}")
                self.root.after(0, lambda: self.status_label.config(text=f"错误: {str(e)}", foreground="red"))
                break

        self.running = False
        self.auto_mode = False
        self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.status_label.config(text="已停止", foreground="gray"))

    def stop_all(self):
        self.running = False
        self.auto_mode = False
        self.status_label.config(text="已停止", foreground="gray")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def on_closing(self):
        keyboard.unhook_all()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 50)
    print("   找不同的字 - pHash版")
    print("=" * 50)
    print("\n使用pHash图像哈希进行相似度匹配")
    print("\n设置步骤:")
    print("  1. 将鼠标移动到右上角目标字区域，按 F9")
    print("  2. 将鼠标移动到10*10网格左上角，按 F10")
    print("  3. 将鼠标移动到10*10网格右下角，按 F11")
    print("\n操作:")
    print("  S = 截图预览")
    print("  W = 开始自动模式")
    print("  ESC = 停止")
    print("\n相似度阈值:")
    print("  数值越小越严格，建议5-10")
    print("\n启动中...")
    print("=" * 50)

    app = FindDifferentChar()
    app.run()
