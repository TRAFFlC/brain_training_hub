"""
舒尔特方格自动通关 - RapidOCR版
使用 RapidOCR 进行数字识别（轻量级，无需下载模型）
"""

import pyautogui
import time
import tkinter as tk
from tkinter import ttk
from PIL import ImageGrab, ImageTk
import threading
import cv2
import numpy as np
import keyboard
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.005

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug')


class SchulteAutoOCR:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("舒尔特方格自动通关")
        self.root.geometry("420x580")
        self.root.attributes('-topmost', True)
        self.root.resizable(False, False)

        self.corners = [None, None]
        self.running = False
        self.ocr = None
        self.debug_mode = False
        self.ocr_preloaded = False

        self.setup_ui()
        self.setup_global_hotkey()

    def setup_global_hotkey(self):
        keyboard.add_hotkey('f9', lambda: self.capture_corner(0))
        keyboard.add_hotkey('f10', lambda: self.capture_corner(1))
        keyboard.add_hotkey('s', self.one_click_solve)

    def preload_ocr(self):
        if not self.ocr_preloaded:
            self.status_label.config(text="正在预加载OCR模型...", foreground="orange")
            self.root.update()
            self.get_ocr()
            self.ocr_preloaded = True
            self.status_label.config(text="OCR模型已就绪", foreground="green")

    def get_ocr(self):
        if self.ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR()
        return self.ocr

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main_frame, text="🎯 舒尔特方格助手",
                          font=('Arial', 18, 'bold'))
        title.pack(pady=5)

        size_frame = ttk.Frame(main_frame)
        size_frame.pack(fill=tk.X, pady=5)

        ttk.Label(size_frame, text="方格大小:").pack(side=tk.LEFT)
        self.size_var = tk.IntVar(value=5)
        ttk.Spinbox(size_frame, from_=3, to=10, width=5,
                    textvariable=self.size_var).pack(side=tk.LEFT, padx=5)

        ttk.Label(size_frame, text="点击间隔:").pack(side=tk.LEFT, padx=(15, 0))
        self.delay_var = tk.DoubleVar(value=0.01)
        ttk.Spinbox(size_frame, from_=0.0, to=1.0, increment=0.005, width=6,
                    textvariable=self.delay_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(size_frame, text="秒").pack(side=tk.LEFT)

        debug_frame = ttk.Frame(main_frame)
        debug_frame.pack(fill=tk.X, pady=5)
        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(debug_frame, text="保存调试图片",
                        variable=self.debug_var).pack(side=tk.LEFT)

        ttk.Button(debug_frame, text="预加载OCR", command=self.preload_ocr).pack(
            side=tk.RIGHT, padx=5)

        area_frame = ttk.LabelFrame(main_frame, text="设置区域", padding="8")
        area_frame.pack(fill=tk.X, pady=5)

        ttk.Label(area_frame, text="F9 = 设置左上角", font=(
            'Arial', 12, 'bold'), foreground='blue').pack(pady=2)
        ttk.Label(area_frame, text="F10 = 设置右下角", font=(
            'Arial', 12, 'bold'), foreground='blue').pack(pady=2)

        self.area_label = ttk.Label(
            area_frame, text="移动鼠标到位置，按 F9/F10 确认", foreground="gray")
        self.area_label.pack(pady=5)

        preview_frame = ttk.LabelFrame(main_frame, text="识别并通关", padding="8")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.preview_canvas = tk.Canvas(
            preview_frame, width=400, height=120, bg='#2d2d2d')
        self.preview_canvas.pack()

        btn_row2 = ttk.Frame(preview_frame)
        btn_row2.pack(fill=tk.X, pady=5)

        ttk.Button(btn_row2, text="📷 截图预览", command=self.capture_preview).pack(
            side=tk.LEFT, padx=5, expand=True)
        ttk.Button(btn_row2, text="🚀 一键通关 (S键)", command=self.one_click_solve).pack(
            side=tk.LEFT, padx=5, expand=True)

        self.result_label = ttk.Label(
            preview_frame, text="按 S 键快速开始！", foreground="gray")
        self.result_label.pack()

        action_frame = ttk.LabelFrame(main_frame, text="操作", padding="8")
        action_frame.pack(fill=tk.X, pady=5)

        self.start_btn = ttk.Button(
            action_frame, text="▶ 开始自动点击", command=self.start_auto)
        self.start_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.stop_btn = ttk.Button(
            action_frame, text="⏹ 停止", command=self.stop_auto, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.status_label = ttk.Label(
            main_frame, text="状态: 就绪 - 按 S 键快速通关", foreground="green", font=('Arial', 11))
        self.status_label.pack(pady=5)

        self.number_positions = {}

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
                text=f"区域: ({min(x1, x2)}, {min(y1, y2)}) → ({max(x1, x2)}, {max(y1, y2)})",
                foreground="blue"
            ))

    def capture_preview(self):
        if not self.corners[0] or not self.corners[1]:
            self.status_label.config(text="请先设置区域!", foreground="red")
            return

        x1, y1 = self.corners[0]
        x2, y2 = self.corners[1]

        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))

        self.tk_preview = ImageTk.PhotoImage(screenshot)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(200, 60, image=self.tk_preview)

        size = self.size_var.get()
        self.debug_mode = self.debug_var.get()
        self.number_positions = self.recognize_all_numbers(
            screenshot, x1, y1, x2, y2, size)

        if self.number_positions:
            found = sorted(self.number_positions.keys())
            self.result_label.config(
                text=f"识别到 {len(found)} 个数字: {found}",
                foreground="blue"
            )
            self.status_label.config(text=f"识别成功!", foreground="green")
        else:
            self.result_label.config(text="识别失败", foreground="red")

    def save_debug_image(self, img, row, col, recognized, actual=None):
        if not self.debug_mode:
            return

        if not os.path.exists(DEBUG_DIR):
            os.makedirs(DEBUG_DIR)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_r{row}_c{col}_rec{recognized}"
        if actual is not None:
            filename += f"_act{actual}"
        filename += ".png"

        cv2.imwrite(os.path.join(DEBUG_DIR, filename), img)

    def recognize_all_numbers(self, screenshot, x1, y1, x2, y2, size):
        grid_w = x2 - x1
        grid_h = y2 - y1
        cell_w = grid_w / size
        cell_h = grid_h / size

        img_array = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        if self.debug_mode:
            if not os.path.exists(DEBUG_DIR):
                os.makedirs(DEBUG_DIR)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cv2.imwrite(os.path.join(
                DEBUG_DIR, f"{timestamp}_full_grid.png"), img_bgr)

        cells = []
        for row in range(size):
            for col in range(size):
                cell_x1 = int(col * cell_w)
                cell_y1 = int(row * cell_h)
                cell_x2 = int((col + 1) * cell_w)
                cell_y2 = int((row + 1) * cell_h)

                cell_img = img_bgr[cell_y1:cell_y2, cell_x1:cell_x2]
                cells.append((row, col, cell_img))

        def recognize_cell(args):
            row, col, cell_img = args
            num, processed_img = self.recognize_digit(cell_img)
            if self.debug_mode and processed_img is not None:
                self.save_debug_image(processed_img, row,
                                      col, num if num else "None")
            return (row, col, num)

        number_positions = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(recognize_cell, cells))

        for row, col, num in results:
            if num is not None:
                center_x = x1 + col * cell_w + cell_w / 2
                center_y = y1 + row * cell_h + cell_h / 2
                number_positions[num] = (center_x, center_y)

        return number_positions

    def recognize_digit(self, cell_img):
        """
        使用 RapidOCR 识别数字
        返回: (识别的数字, 处理后的图像)
        """
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)

        def try_recognize(processed_img):
            try:
                ocr = self.get_ocr()
                result, _ = ocr(processed_img)

                if result:
                    for item in result:
                        text = item[1].strip()
                        if text.isdigit() and len(text) <= 3:
                            return int(text)
            except Exception as e:
                pass
            return None

        def preprocess_and_try(thresh_img):
            contours, _ = cv2.findContours(
                thresh_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                all_contours = [c for c in contours if cv2.contourArea(c) > 10]

                if all_contours:
                    xs, ys = [], []
                    for c in all_contours:
                        x, y, w, h = cv2.boundingRect(c)
                        xs.extend([x, x+w])
                        ys.extend([y, y+h])

                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)

                    padding = 15
                    min_x = max(0, min_x - padding)
                    min_y = max(0, min_y - padding)
                    max_x = min(thresh_img.shape[1], max_x + padding)
                    max_y = min(thresh_img.shape[0], max_y + padding)

                    digit_roi = thresh_img[min_y:max_y, min_x:max_x]
                else:
                    digit_roi = thresh_img
            else:
                digit_roi = thresh_img

            h, w = digit_roi.shape
            if h == 0 or w == 0:
                return None, None

            scale = max(4, 80 // max(h, w))
            new_w = w * scale
            new_h = h * scale
            digit_roi = cv2.resize(
                digit_roi, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

            border = 20
            digit_roi = cv2.copyMakeBorder(digit_roi, border, border, border, border,
                                           cv2.BORDER_CONSTANT, value=0)

            digit_rgb = cv2.cvtColor(digit_roi, cv2.COLOR_GRAY2RGB)
            result = try_recognize(digit_rgb)
            return result, digit_rgb

        result = try_recognize(cell_img)
        if result is not None:
            return result, cell_img

        h, w = cell_img.shape[:2]
        scale = max(2, 60 // max(h, w))
        cell_img_scaled = cv2.resize(
            cell_img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
        border = 15
        cell_img_padded = cv2.copyMakeBorder(cell_img_scaled, border, border, border, border,
                                             cv2.BORDER_CONSTANT, value=(255, 255, 255))
        result = try_recognize(cell_img_padded)
        if result is not None:
            return result, cell_img_padded

        _, thresh_otsu = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(gray) > 127:
            thresh_otsu = cv2.bitwise_not(thresh_otsu)

        result, digit_rgb = preprocess_and_try(thresh_otsu)
        if result is not None:
            return result, digit_rgb

        result, digit_rgb = preprocess_and_try(cv2.bitwise_not(thresh_otsu))
        if result is not None:
            return result, digit_rgb

        for thresh_val in [127, 100, 150, 80, 180]:
            _, thresh_fixed = cv2.threshold(
                gray, thresh_val, 255, cv2.THRESH_BINARY)
            result, digit_rgb = preprocess_and_try(thresh_fixed)
            if result is not None:
                return result, digit_rgb
            result, digit_rgb = preprocess_and_try(
                cv2.bitwise_not(thresh_fixed))
            if result is not None:
                return result, digit_rgb

        thresh_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                             cv2.THRESH_BINARY, 11, 2)
        result, digit_rgb = preprocess_and_try(thresh_adapt)
        if result is not None:
            return result, digit_rgb
        result, digit_rgb = preprocess_and_try(cv2.bitwise_not(thresh_adapt))
        if result is not None:
            return result, digit_rgb

        thresh_adapt2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                              cv2.THRESH_BINARY, 15, 5)
        result, digit_rgb = preprocess_and_try(thresh_adapt2)
        if result is not None:
            return result, digit_rgb

        return None, digit_rgb

    def one_click_solve(self):
        if not self.corners[0] or not self.corners[1]:
            self.root.after(0, lambda: self.status_label.config(
                text="请先设置区域!", foreground="red"))
            return

        if self.running:
            return

        self.running = True
        self.debug_mode = self.debug_var.get()
        self.root.after(0, lambda: self.start_btn.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.stop_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.status_label.config(
            text="识别中...", foreground="orange"))

        thread = threading.Thread(target=self.run_one_click, daemon=True)
        thread.start()

    def run_one_click(self):
        try:
            x1, y1 = self.corners[0]
            x2, y2 = self.corners[1]

            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1

            size = self.size_var.get()
            delay = self.delay_var.get()
            total = size * size

            start_time = time.time()
            screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            number_positions = self.recognize_all_numbers(
                screenshot, x1, y1, x2, y2, size)
            recognize_time = time.time() - start_time

            if not number_positions:
                self.root.after(0, lambda: self.status_label.config(
                    text="识别失败!", foreground="red"))
                return

            if len(number_positions) != total:
                missing = [i for i in range(
                    1, total+1) if i not in number_positions]
                print(f"识别结果: {sorted(number_positions.keys())}")
                print(f"缺少: {missing}")

            sorted_nums = sorted(
                [n for n in number_positions.keys() if 1 <= n <= total])

            click_start = time.time()
            for i, num in enumerate(sorted_nums):
                if not self.running:
                    break

                x, y = number_positions[num]
                pyautogui.click(x, y)
                if delay > 0:
                    time.sleep(delay)

                final_num = num
                final_idx = i + 1

            total_time = time.time() - start_time
            if self.running:
                self.root.after(0, lambda: self.status_label.config(
                    text=f"✓ 完成! 识别:{recognize_time:.2f}s 总计:{total_time:.2f}s", foreground="green"))

        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(
                text=f"错误: {str(e)}", foreground="red"))
        finally:
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self.running = False

    def start_auto(self):
        if not self.number_positions:
            self.status_label.config(text="请先点击'截图预览'!", foreground="red")
            return

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="状态: 运行中...", foreground="orange")

        thread = threading.Thread(target=self.run_auto_click, daemon=True)
        thread.start()

    def run_auto_click(self):
        try:
            delay = self.delay_var.get()
            size = self.size_var.get()
            total = size * size
            sorted_nums = sorted(
                [n for n in self.number_positions.keys() if 1 <= n <= total])

            for i, num in enumerate(sorted_nums):
                if not self.running:
                    break

                x, y = self.number_positions[num]
                pyautogui.click(x, y)
                time.sleep(delay)

                final_num = num
                final_idx = i + 1
                self.root.after(0, lambda n=final_num, idx=final_idx: self.status_label.config(
                    text=f"点击 {n} ({idx}/{len(sorted_nums)})", foreground="orange"))

            if self.running:
                self.root.after(0, lambda: self.status_label.config(
                    text="✓ 完成!", foreground="green"))

        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(
                text=f"错误: {str(e)}", foreground="red"))
        finally:
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self.running = False

    def stop_auto(self):
        self.running = False
        self.status_label.config(text="已停止", foreground="red")
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
    print("   舒尔特方格自动通关 - RapidOCR版")
    print("=" * 50)
    print("\n快捷键:")
    print("  F9  = 设置左上角")
    print("  F10 = 设置右下角")
    print("  S   = 一键通关")
    print("\n启动中...")

    app = SchulteAutoOCR()
    app.run()
