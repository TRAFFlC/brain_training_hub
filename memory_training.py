"""
数字顺序记忆训练外挂
游戏规则：点击1后所有数字隐藏，需要按顺序点击剩余数字
策略：先识别记录所有数字位置，然后按记忆点击
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


class MemoryTrainingAuto:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("数字顺序记忆训练助手")
        self.root.attributes('-topmost', True)

        self.corners = [None, None]
        self.running = False
        self.ocr = None
        self.debug_mode = False
        self.ocr_preloaded = False

        self.number_positions = {}
        self.current_level = 1
        self.phase = 'ready'
        self.auto_continue = False

        self.setup_ui()
        self.setup_global_hotkey()

        self.root.after(100, self.preload_ocr)

    def setup_global_hotkey(self):
        keyboard.add_hotkey('f9', lambda: self.capture_corner(0))
        keyboard.add_hotkey('f10', lambda: self.capture_corner(1))
        keyboard.add_hotkey('s', self.start_level)
        keyboard.add_hotkey('r', self.recognize_only)

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
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main_frame, text="🧠 数字顺序记忆训练助手",
                          font=('Arial', 18, 'bold'))
        title.pack(pady=10)

        desc_frame = ttk.LabelFrame(main_frame, text="游戏说明", padding="10")
        desc_frame.pack(fill=tk.X, pady=5)
        ttk.Label(desc_frame, text="点击数字1后，所有数字会隐藏，需要按顺序点击 1→2→3→...→N",
                  foreground="gray", font=('Arial', 10)).pack()

        config_frame = ttk.LabelFrame(main_frame, text="参数设置", padding="10")
        config_frame.pack(fill=tk.X, pady=5)

        row1 = ttk.Frame(config_frame)
        row1.pack(fill=tk.X, pady=5)

        ttk.Label(row1, text="网格大小:", font=('Arial', 10)).pack(side=tk.LEFT)
        self.rows_var = tk.IntVar(value=5)
        ttk.Spinbox(row1, from_=2, to=10, width=6,
                    textvariable=self.rows_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="行", font=('Arial', 10)).pack(side=tk.LEFT)

        ttk.Label(row1, text="    ", font=('Arial', 10)).pack(side=tk.LEFT)

        self.cols_var = tk.IntVar(value=8)
        ttk.Spinbox(row1, from_=2, to=10, width=6,
                    textvariable=self.cols_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="列", font=('Arial', 10)).pack(side=tk.LEFT)

        row2 = ttk.Frame(config_frame)
        row2.pack(fill=tk.X, pady=5)

        ttk.Label(row2, text="点击间隔:", font=('Arial', 10)).pack(side=tk.LEFT)
        self.delay_var = tk.DoubleVar(value=0.15)
        ttk.Spinbox(row2, from_=0.05, to=2.0, increment=0.05, width=8,
                    textvariable=self.delay_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="秒", font=('Arial', 10)).pack(side=tk.LEFT)

        ttk.Label(row2, text="    ", font=('Arial', 10)).pack(side=tk.LEFT)

        ttk.Label(row2, text="隐藏后等待:", font=('Arial', 10)).pack(side=tk.LEFT)
        self.hide_delay_var = tk.DoubleVar(value=0.3)
        ttk.Spinbox(row2, from_=0.1, to=2.0, increment=0.1, width=8,
                    textvariable=self.hide_delay_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="秒", font=('Arial', 10)).pack(side=tk.LEFT)

        row3 = ttk.Frame(config_frame)
        row3.pack(fill=tk.X, pady=5)

        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="调试", variable=self.debug_var).pack(
            side=tk.LEFT)

        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="自动继续下一关", variable=self.auto_var).pack(
            side=tk.LEFT, padx=20)

        ttk.Button(row3, text="预加载OCR",
                   command=self.preload_ocr).pack(side=tk.RIGHT)

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

        preview_frame = ttk.LabelFrame(main_frame, text="识别预览", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.preview_canvas = tk.Canvas(
            preview_frame, width=450, height=150, bg='#1a1a2e')
        self.preview_canvas.pack(pady=5)

        self.result_label = ttk.Label(
            preview_frame, text="", foreground="gray", font=('Arial', 11))
        self.result_label.pack(pady=5)

        action_frame = ttk.LabelFrame(main_frame, text="操作", padding="10")
        action_frame.pack(fill=tk.X, pady=5)

        btn_row1 = ttk.Frame(action_frame)
        btn_row1.pack(fill=tk.X, pady=5)

        ttk.Button(btn_row1, text="📷 仅识别 (R键)", command=self.recognize_only,
                   width=20).pack(side=tk.LEFT, padx=10, expand=True)
        ttk.Button(btn_row1, text="🚀 开始关卡 (S键)", command=self.start_level,
                   width=20).pack(side=tk.LEFT, padx=10, expand=True)

        btn_row2 = ttk.Frame(action_frame)
        btn_row2.pack(fill=tk.X, pady=5)

        self.start_btn = ttk.Button(
            btn_row2, text="▶ 开始关卡", command=self.start_level, width=20)
        self.start_btn.pack(side=tk.LEFT, padx=10, expand=True)

        self.stop_btn = ttk.Button(
            btn_row2, text="⏹ 停止", command=self.stop_auto, state=tk.DISABLED, width=20)
        self.stop_btn.pack(side=tk.LEFT, padx=10, expand=True)

        self.status_label = ttk.Label(
            main_frame, text="状态: 就绪 - 请设置游戏区域", foreground="green", font=('Arial', 12))
        self.status_label.pack(pady=8)

        self.info_label = ttk.Label(
            main_frame, text="", foreground="blue", font=('Arial', 11))
        self.info_label.pack(pady=3)

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

    def init_debug_dir(self):
        if not os.path.exists(DEBUG_DIR):
            os.makedirs(DEBUG_DIR)
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def save_debug_image(self, img, name, timestamp=None):
        if not self.debug_mode:
            return
        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{name}.png"
        cv2.imwrite(os.path.join(DEBUG_DIR, filename), img)

    def recognize_digit(self, cell_img, ocr):
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)

        def try_recognize(processed_img):
            try:
                result, _ = ocr(processed_img)
                if result:
                    for item in result:
                        text = item[1].strip()
                        if text.isdigit() and len(text) <= 3:
                            return int(text)
            except:
                pass
            return None

        result = try_recognize(cell_img)
        if result is not None:
            return result, "original"

        h, w = cell_img.shape[:2]
        scale = max(2, 60 // max(h, w))
        if scale > 1:
            cell_img_scaled = cv2.resize(
                cell_img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
            border = 15
            cell_img_padded = cv2.copyMakeBorder(cell_img_scaled, border, border, border, border,
                                                 cv2.BORDER_CONSTANT, value=(255, 255, 255))
            result = try_recognize(cell_img_padded)
            if result is not None:
                return result, "scaled"

        _, thresh_otsu = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(gray) > 127:
            thresh_otsu = cv2.bitwise_not(thresh_otsu)

        thresh_bgr = cv2.cvtColor(thresh_otsu, cv2.COLOR_GRAY2BGR)
        result = try_recognize(thresh_bgr)
        if result is not None:
            return result, "otsu"

        thresh_inv = cv2.bitwise_not(thresh_otsu)
        thresh_inv_bgr = cv2.cvtColor(thresh_inv, cv2.COLOR_GRAY2BGR)
        result = try_recognize(thresh_inv_bgr)
        if result is not None:
            return result, "otsu_inv"

        return None, "failed"

    def recognize_all_numbers(self, screenshot, x1, y1, x2, y2, rows, cols):
        grid_w = x2 - x1
        grid_h = y2 - y1
        cell_w = grid_w / cols
        cell_h = grid_h / rows

        img_array = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        timestamp = self.init_debug_dir() if self.debug_mode else ""

        if self.debug_mode:
            self.save_debug_image(img_bgr, "01_full_grid", timestamp)

        ocr = self.get_ocr()

        cells = []
        for row in range(rows):
            for col in range(cols):
                cell_x1 = int(col * cell_w)
                cell_y1 = int(row * cell_h)
                cell_x2 = int((col + 1) * cell_w)
                cell_y2 = int((row + 1) * cell_h)

                cell_img = img_bgr[cell_y1:cell_y2, cell_x1:cell_x2]
                cells.append((row, col, cell_img))

        def recognize_cell(args):
            row, col, cell_img = args
            num, method = self.recognize_digit(cell_img, ocr)
            return (row, col, num, method, cell_img)

        number_positions = {}

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(recognize_cell, cells))

        for row, col, num, method, cell_img in results:
            if num is not None:
                center_x = x1 + col * cell_w + cell_w / 2
                center_y = y1 + row * cell_h + cell_h / 2
                number_positions[num] = (center_x, center_y)

                if self.debug_mode:
                    self.save_debug_image(
                        cell_img, f"cell_r{row}_c{col}_num{num}_{method}", timestamp)

        if self.debug_mode:
            debug_img = img_bgr.copy()
            for row, col, num, method, cell_img in results:
                if num is not None:
                    cell_x1 = int(col * cell_w)
                    cell_y1 = int(row * cell_h)
                    cell_x2 = int((col + 1) * cell_w)
                    cell_y2 = int((row + 1) * cell_h)
                    cv2.rectangle(debug_img, (cell_x1, cell_y1),
                                  (cell_x2, cell_y2), (0, 255, 0), 2)
                    cv2.putText(debug_img, str(num), (cell_x1+5, cell_y1+25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            self.save_debug_image(
                debug_img, "02_recognition_result", timestamp)

        return number_positions

    def find_continue_button(self, x1, y1, x2, y2):
        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        img_array = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        ocr = self.get_ocr()
        result, _ = ocr(img_bgr)

        if result:
            for item in result:
                text = item[1].strip()
                if "继续" in text or "Continue" in text.lower() or "next" in text.lower():
                    box = item[0]
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    center_x = sum(xs) / 4 + x1
                    center_y = sum(ys) / 4 + y1
                    return (center_x, center_y)

        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        return (center_x, center_y)

    def recognize_only(self):
        if not self.corners[0] or not self.corners[1]:
            self.root.after(0, lambda: self.status_label.config(
                text="请先设置区域!", foreground="red"))
            return

        if self.running:
            return

        self.debug_mode = self.debug_var.get()
        self.root.after(0, lambda: self.status_label.config(
            text="识别中...", foreground="orange"))
        self.root.after(0, lambda: self.result_label.config(
            text="正在识别数字...", foreground="gray"))

        thread = threading.Thread(target=self.run_recognize_only, daemon=True)
        thread.start()

    def run_recognize_only(self):
        try:
            x1, y1 = self.corners[0]
            x2, y2 = self.corners[1]

            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1

            screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))

            self.tk_preview = ImageTk.PhotoImage(screenshot)
            self.root.after(0, lambda: self.preview_canvas.delete("all"))
            scale = min(450 / (x2-x1), 150 / (y2-y1))
            if scale < 1:
                from PIL import Image
                resized = screenshot.resize(
                    (int((x2-x1)*scale), int((y2-y1)*scale)), Image.LANCZOS)
                self.tk_preview = ImageTk.PhotoImage(resized)
            self.root.after(0, lambda: self.preview_canvas.create_image(
                225, 75, image=self.tk_preview))

            start_time = time.time()
            rows = self.rows_var.get()
            cols = self.cols_var.get()
            self.number_positions = self.recognize_all_numbers(
                screenshot, x1, y1, x2, y2, rows, cols)
            elapsed = time.time() - start_time

            if self.number_positions:
                found = sorted(self.number_positions.keys())

                self.root.after(0, lambda: self.result_label.config(
                    text=f"识别到 {len(found)} 个数字: {found} (耗时{elapsed:.2f}秒)",
                    foreground="blue"
                ))

                expected = max(found) if found else 0
                missing = [i for i in range(1, expected+1) if i not in found]

                if not missing:
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"✓ 识别成功! 共{len(found)}个数字，按S开始", foreground="green"))
                else:
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"⚠ 识别到{len(found)}个，缺少:{missing}", foreground="orange"))

                self.root.after(0, lambda: self.info_label.config(
                    text=f"数字位置已记录，点击S开始游戏"))
            else:
                self.root.after(0, lambda: self.result_label.config(
                    text="未识别到数字!", foreground="red"))
                self.root.after(0, lambda: self.status_label.config(
                    text="识别失败，请检查区域设置或开启调试", foreground="red"))

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self.status_label.config(
                text=f"错误: {str(e)}", foreground="red"))

    def start_level(self):
        if not self.corners[0] or not self.corners[1]:
            self.root.after(0, lambda: self.status_label.config(
                text="请先设置区域!", foreground="red"))
            return

        if self.running:
            return

        self.running = True
        self.auto_continue = self.auto_var.get()
        self.debug_mode = self.debug_var.get()
        self.phase = 'recognizing'

        self.root.after(0, lambda: self.start_btn.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.stop_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.status_label.config(
            text="阶段1: 识别数字...", foreground="orange"))

        thread = threading.Thread(target=self.run_level, daemon=True)
        thread.start()

    def run_level(self):
        try:
            x1, y1 = self.corners[0]
            x2, y2 = self.corners[1]

            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1

            rows = self.rows_var.get()
            cols = self.cols_var.get()
            screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))

            start_time = time.time()
            self.number_positions = self.recognize_all_numbers(
                screenshot, x1, y1, x2, y2, rows, cols)
            elapsed = time.time() - start_time

            found = sorted(self.number_positions.keys())

            if not found:
                self.root.after(0, lambda: self.status_label.config(
                    text=f"识别失败! 未找到任何数字", foreground="red"))
                return

            expected = max(found)
            missing = [i for i in range(1, expected+1) if i not in found]

            if missing:
                self.root.after(0, lambda: self.status_label.config(
                    text=f"⚠ 识别不完整! 缺少数字: {missing}", foreground="red"))
                self.root.after(0, lambda: self.info_label.config(
                    text="请检查识别结果或开启调试模式"))
                return

            self.root.after(0, lambda: self.result_label.config(
                text=f"识别到 {len(found)} 个数字: {found} (耗时{elapsed:.2f}秒)", foreground="blue"))

            self.phase = 'clicking_first'
            self.root.after(0, lambda: self.status_label.config(
                text="阶段2: 点击数字1触发隐藏...", foreground="orange"))

            x, y = self.number_positions[1]
            pyautogui.click(x, y)

            hide_delay = self.hide_delay_var.get()
            time.sleep(hide_delay)

            self.phase = 'clicking_sequence'
            self.root.after(0, lambda: self.status_label.config(
                text="阶段3: 按顺序点击剩余数字...", foreground="orange"))

            click_delay = self.delay_var.get()
            max_num = max(self.number_positions.keys())

            for num in range(2, max_num + 1):
                if not self.running:
                    break

                if num in self.number_positions:
                    x, y = self.number_positions[num]
                    pyautogui.click(x, y)

                    if click_delay > 0:
                        time.sleep(click_delay)

            if self.running and self.auto_continue:
                time.sleep(0.5)

                btn_pos = self.find_continue_button(x1, y1, x2, y2)
                if btn_pos:
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"点击继续按钮...", foreground="orange"))
                    pyautogui.click(btn_pos[0], btn_pos[1])
                    time.sleep(1.0)

                    if self.running:
                        self.root.after(0, lambda: self.status_label.config(
                            text=f"关卡完成! 开始下一关...", foreground="green"))
                        self.run_level()
                        return

            if self.running:
                self.root.after(0, lambda: self.status_label.config(
                    text=f"✓ 关卡完成! 共点击{max_num}个数字", foreground="green"))
                self.root.after(0, lambda: self.info_label.config(
                    text="等待下一关出现，按S继续"))

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self.status_label.config(
                text=f"错误: {str(e)}", foreground="red"))
        finally:
            if not self.auto_continue or not self.running:
                self.root.after(
                    0, lambda: self.start_btn.config(state=tk.NORMAL))
                self.root.after(
                    0, lambda: self.stop_btn.config(state=tk.DISABLED))
                self.running = False
                self.phase = 'ready'

    def stop_auto(self):
        self.running = False
        self.phase = 'ready'
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
    print("   数字顺序记忆训练助手")
    print("=" * 50)
    print("\n游戏规则:")
    print("  点击数字1后，所有数字会隐藏")
    print("  需要按顺序点击 1→2→3→...→N")
    print("\n快捷键:")
    print("  F9  = 设置左上角")
    print("  F10 = 设置右下角")
    print("  R   = 仅识别数字")
    print("  S   = 开始关卡 (识别→点击1→按序点击)")
    print("\n启动中...")

    app = MemoryTrainingAuto()
    app.run()
