"""
找不同的字 - 暴力版
点击所有100个格子，循环往复
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

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.001

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'


class FindDifferentCharBrute:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("找不同的字 - 暴力版")
        self.root.geometry("450x500")
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)

        self.target_corner = (1545, 444)
        self.grid_corner = [(808, 484), (1558, 1234)]
        self.running = False
        self.auto_mode = False

        self.grid_size = 10
        self.cps = 50

        self.setup_ui()
        self.setup_hotkeys()

    def setup_hotkeys(self):
        keyboard.add_hotkey('f9', lambda: self.set_corner(0))
        keyboard.add_hotkey('f10', lambda: self.set_corner(1))
        keyboard.add_hotkey('f11', lambda: self.set_corner(2))
        keyboard.add_hotkey('w', self.start_auto_mode)
        keyboard.add_hotkey('esc', self.stop_all)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main_frame, text="🔨 找不同的字 - 暴力版", font=('Microsoft YaHei UI', 18, 'bold'))
        title.pack(pady=(0, 15))

        settings_frame = ttk.LabelFrame(main_frame, text="参数设置", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        cps_frame = ttk.Frame(settings_frame)
        cps_frame.pack(fill=tk.X)
        ttk.Label(cps_frame, text="点击速度 (CPS):").pack(side=tk.LEFT)
        self.cps_var = tk.IntVar(value=50)
        ttk.Spinbox(cps_frame, from_=1, to=200, width=8,
                    textvariable=self.cps_var).pack(side=tk.LEFT, padx=5)
        ttk.Button(cps_frame, text="应用", command=self.apply_cps).pack(side=tk.LEFT, padx=5)

        area_frame = ttk.LabelFrame(main_frame, text="区域设置 (游戏中操作)", padding="10")
        area_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(area_frame, text="F9  = 设置目标字区域 (右上角)", font=('Arial', 11, 'bold'), foreground='blue').pack(pady=2)
        ttk.Label(area_frame, text="F10 = 设置10*10区域左上角", font=('Arial', 11, 'bold'), foreground='green').pack(pady=2)
        ttk.Label(area_frame, text="F11 = 设置10*10区域右下角", font=('Arial', 11, 'bold'), foreground='purple').pack(pady=2)

        self.area_label = ttk.Label(area_frame, text="请依次设置目标字区域和10*10区域", foreground="gray", font=('Arial', 10))
        self.area_label.pack(pady=5)

        preview_frame = ttk.LabelFrame(main_frame, text="预览", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.grid_canvas = tk.Canvas(preview_frame, width=400, height=400, bg='#1a1a1a')
        self.grid_canvas.pack(pady=5, fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="📷 预览网格", command=self.show_preview).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        ttk.Button(btn_frame, text="🔄 开始暴力点击 (W)", command=self.start_auto_mode).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X)

        self.start_btn = ttk.Button(control_frame, text="▶ 开始", command=self.start_auto_mode)
        self.start_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        self.stop_btn = ttk.Button(control_frame, text="⏹ 停止", command=self.stop_all, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        self.status_label = ttk.Label(main_frame, text="状态: 就绪 - 按 W 开始", foreground="green", font=('Arial', 11))
        self.status_label.pack(pady=5)

        info_label = ttk.Label(main_frame, text="快捷键: F9=目标区 F10=网格左上 F11=网格右下 W=开始 ESC=停止",
                               font=('Arial', 8), foreground="gray")
        info_label.pack(pady=(5, 0))

        self.update_area_label()

    def apply_cps(self):
        self.cps = self.cps_var.get()
        self.status_label.config(text=f"CPS已设为 {self.cps}", foreground="blue")

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

    def get_all_cell_centers(self):
        grid_data = self.capture_grid()
        if not grid_data:
            return []

        img, x1, y1, x2, y2 = grid_data
        img_array = np.array(img)
        h, w = img_array.shape[:2]

        col_widths = [71 if i in [0, 4, 7] else 72 for i in range(10)]
        row_heights = [71 if i in [2, 5, 9] else 72 for i in range(10)]
        border_line_width = 3

        centers = []

        for row in range(self.grid_size):
            for col in range(self.grid_size):
                cell_center_x = border_line_width + col * border_line_width + sum(col_widths[:col]) + col_widths[col] / 2
                cell_center_y = border_line_width + row * border_line_width + sum(row_heights[:row]) + row_heights[row] / 2

                screen_x = x1 + cell_center_x
                screen_y = y1 + cell_center_y
                centers.append((screen_x, screen_y))

        return centers

    def show_preview(self):
        grid_data = self.capture_grid()
        if grid_data:
            img, x1, y1, x2, y2 = grid_data
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

            centers = self.get_all_cell_centers()
            for cx, cy in centers:
                dx = (cx - x1) * display_scale
                dy = (cy - y1) * display_scale
                self.grid_canvas.create_oval(dx-3, dy-3, dx+3, dy+3, fill="red", outline="red")

            self.status_label.config(text=f"已显示 {len(centers)} 个中心点", foreground="green")

    def start_auto_mode(self):
        if not self.grid_corner or not self.grid_corner[0] or not self.grid_corner[1]:
            self.status_label.config(text="请先设置网格区域!", foreground="red")
            return

        if self.running:
            return

        self.running = True
        self.auto_mode = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="暴力点击运行中...", foreground="green")

        threading.Thread(target=self.run_auto_mode, daemon=True).start()

    def run_auto_mode(self):
        click_interval = 1.0 / self.cps

        while self.running and self.auto_mode:
            try:
                centers = self.get_all_cell_centers()

                if not centers:
                    self.root.after(0, lambda: self.status_label.config(text="无法获取中心点!", foreground="red"))
                    break

                for cx, cy in centers:
                    if not self.running or not self.auto_mode:
                        break
                    pyautogui.click(cx, cy)
                    time.sleep(click_interval)

                self.root.after(0, lambda: self.status_label.config(
                    text=f"已点击 {len(centers)} 个格子", foreground="green"))

            except Exception as e:
                print(f"错误: {e}")
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
    print("   找不同的字 - 暴力版")
    print("=" * 50)
    print("\n点击所有100个格子，循环往复")
    print("\n设置步骤:")
    print("  1. 将鼠标移动到右上角目标字区域，按 F9")
    print("  2. 将鼠标移动到10*10网格左上角，按 F10")
    print("  3. 将鼠标移动到10*10网格右下角，按 F11")
    print("\n操作:")
    print("  W = 开始暴力点击")
    print("  ESC = 停止")
    print("\n启动中...")
    print("=" * 50)

    app = FindDifferentCharBrute()
    app.run()
