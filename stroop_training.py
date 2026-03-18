"""
斯特鲁普效应训练外挂
游戏规则：
  模式一：文字的意思和文字的颜色是否匹配
  游戏展示一个带颜色的字，判断颜色是否是该字表达的含义
  点击"是"或"否"按钮，共20轮

核心逻辑：
  1. 计算文字形状哈希（与颜色无关）
  2. 通过哈希匹配识别文字
  3. 检测文字颜色
  4. 比较文字含义与颜色是否匹配
"""

import pyautogui
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageGrab, Image
import threading
import keyboard
import cv2
import numpy as np
import os
from datetime import datetime

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.001

DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_stroop')

COLOR_NAMES = {
    '红': 'red',
    '蓝': 'blue',
    '绿': 'green',
    '橙': 'orange',
    '紫': 'purple',
    '灰': 'gray',
    '黑': 'black',
}

COLOR_RANGES = {
    'red': [
        ((0, 100, 100), (10, 255, 255)),
        ((160, 100, 100), (180, 255, 255)),
    ],
    'blue': [
        ((100, 100, 100), (130, 255, 255)),
    ],
    'green': [
        ((35, 100, 100), (85, 255, 255)),
    ],
    'orange': [
        ((10, 100, 100), (20, 255, 255)),
    ],
    'purple': [
        ((130, 100, 100), (160, 255, 255)),
    ],
    'black': None,
}


def compute_shape_hash(img, hash_size=16):
    if isinstance(img, Image.Image):
        img = np.array(img)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    binary_pil = Image.fromarray(binary)
    resized = binary_pil.resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = list(resized.getdata())

    diff = []
    for row in range(hash_size):
        for col in range(hash_size):
            idx = row * (hash_size + 1) + col
            diff.append(pixels[idx] > pixels[idx + 1])

    hash_val = sum([2**i for i, v in enumerate(diff) if v])
    return hash_val


def hamming_distance(hash1, hash2):
    return bin(int(hash1) ^ int(hash2)).count('1')


def save_debug_image(img, name, timestamp=None):
    if not os.path.exists(DEBUG_DIR):
        os.makedirs(DEBUG_DIR)
    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{name}.png"
    if isinstance(img, np.ndarray):
        img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    img.save(os.path.join(DEBUG_DIR, filename))


class StroopAuto:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("斯特鲁普效应训练助手")
        self.root.attributes('-topmost', True)
        self.corners = [None, None]
        self.running = False
        self.total_rounds = 20
        self.word_area = None
        self.yes_btn = None
        self.no_btn = None
        self.debug_mode = False
        self.char_hashes = {}
        self.hash_threshold = 30
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="🎨 斯特鲁普效应训练助手",
                  font=('Arial', 16, 'bold')).pack(pady=5)
        ttk.Label(main_frame, text="设置哈希值 → 测试 → 开始",
                  foreground="gray", font=('Arial', 9)).pack()

        config_frame = ttk.LabelFrame(main_frame, text="参数", padding="5")
        config_frame.pack(fill=tk.X, pady=5)

        row1 = ttk.Frame(config_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="轮数:").pack(side=tk.LEFT)
        self.rounds_var = tk.IntVar(value=20)
        ttk.Spinbox(row1, from_=5, to=50, width=5,
                    textvariable=self.rounds_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="哈希阈值:").pack(side=tk.LEFT)
        self.threshold_var = tk.IntVar(value=30)
        ttk.Spinbox(row1, from_=5, to=100, width=5,
                    textvariable=self.threshold_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="检测间隔:").pack(side=tk.LEFT)
        self.interval_var = tk.DoubleVar(value=0.1)
        ttk.Spinbox(row1, from_=0.05, to=1.0, increment=0.05, width=6,
                    textvariable=self.interval_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="秒").pack(side=tk.LEFT)

        row2 = ttk.Frame(config_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="点击等待:").pack(side=tk.LEFT)
        self.wait_var = tk.DoubleVar(value=0.2)
        ttk.Spinbox(row2, from_=0.1, to=1.0, increment=0.1, width=6,
                    textvariable=self.wait_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="秒").pack(side=tk.LEFT)

        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(config_frame, text="调试模式",
                        variable=self.debug_var).pack(anchor=tk.W)

        area_frame = ttk.LabelFrame(main_frame, text="区域设置 (F9/F10)", padding="5")
        area_frame.pack(fill=tk.X, pady=5)

        self.area_label = ttk.Label(area_frame, text="F9=左上角 F10=右下角", foreground="gray")
        self.area_label.pack()

        btn_row1 = ttk.Frame(area_frame)
        btn_row1.pack(fill=tk.X, pady=2)
        ttk.Button(btn_row1, text="设置文字区域", command=self.set_word_area,
                   width=12).pack(side=tk.LEFT, padx=2, expand=True)
        ttk.Button(btn_row1, text="设置\"是\"按钮", command=self.set_yes_btn,
                   width=12).pack(side=tk.LEFT, padx=2, expand=True)
        ttk.Button(btn_row1, text="设置\"否\"按钮", command=self.set_no_btn,
                   width=12).pack(side=tk.LEFT, padx=2, expand=True)

        btn_row2 = ttk.Frame(area_frame)
        btn_row2.pack(fill=tk.X, pady=2)
        ttk.Button(btn_row2, text="测试检测", command=self.test_detection,
                   width=15).pack(side=tk.LEFT, padx=2, expand=True)

        hash_frame = ttk.LabelFrame(main_frame, text="哈希值设置 (测试后复制填入)", padding="5")
        hash_frame.pack(fill=tk.X, pady=5)

        self.hash_vars = {}
        chars = ['红', '蓝', '绿', '橙', '紫', '灰', '黑']

        for i, char in enumerate(chars):
            row_frame = ttk.Frame(hash_frame)
            row_frame.pack(fill=tk.X, pady=1)
            ttk.Label(row_frame, text=f"{char}:", width=3).pack(side=tk.LEFT)
            var = tk.StringVar(value="")
            self.hash_vars[char] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=25)
            entry.pack(side=tk.LEFT, padx=5)
            ttk.Button(row_frame, text="清空", width=4,
                       command=lambda c=char: self.hash_vars[c].set("")).pack(side=tk.LEFT)

        btn_row3 = ttk.Frame(hash_frame)
        btn_row3.pack(fill=tk.X, pady=5)
        ttk.Button(btn_row3, text="应用哈希值", command=self.apply_hashes,
                   width=12).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(btn_row3, text="清空全部", command=self.clear_all_hashes,
                   width=12).pack(side=tk.LEFT, padx=5, expand=True)

        self.hash_status_label = ttk.Label(hash_frame, text="未应用哈希值", foreground="orange")
        self.hash_status_label.pack()

        result_frame = ttk.LabelFrame(main_frame, text="检测结果", padding="5")
        result_frame.pack(fill=tk.X, pady=5)

        self.hash_result_label = ttk.Label(result_frame, text="哈希: (未测试)", 
                                            font=('Arial', 12, 'bold'), foreground="blue")
        self.hash_result_label.pack(pady=2)

        self.color_result_label = ttk.Label(result_frame, text="颜色: (未测试)",
                                             font=('Arial', 11), foreground="purple")
        self.color_result_label.pack(pady=2)

        self.match_result_label = ttk.Label(result_frame, text="匹配: (未测试)",
                                             font=('Arial', 11), foreground="green")
        self.match_result_label.pack(pady=2)

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=5)
        self.start_btn = ttk.Button(
            action_frame, text="▶ 开始", command=self.start_game, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.stop_btn = ttk.Button(
            action_frame, text="⏹ 停止", command=self.stop_game, state=tk.DISABLED, width=15)
        self.stop_btn.pack(side=tk.LEFT, padx=5, expand=True)

        self.status_label = ttk.Label(
            main_frame, text="就绪", foreground="green", font=('Arial', 11))
        self.status_label.pack(pady=5)

        self.root.bind('<F9>', lambda e: self.capture_corner(0))
        self.root.bind('<F10>', lambda e: self.capture_corner(1))
        self.root.bind('<t>', lambda e: self.test_detection())
        self.root.bind('<T>', lambda e: self.test_detection())
        self.root.bind('<s>', lambda e: self.start_game())
        self.root.bind('<S>', lambda e: self.start_game())

        keyboard.add_hotkey('f9', lambda: self.capture_corner(0))
        keyboard.add_hotkey('f10', lambda: self.capture_corner(1))

    def apply_hashes(self):
        self.char_hashes = {}
        for char, var in self.hash_vars.items():
            val = var.get().strip()
            if val:
                try:
                    self.char_hashes[char] = int(val)
                except ValueError:
                    pass

        if self.char_hashes:
            self.hash_status_label.config(
                text=f"已应用 {len(self.char_hashes)} 个哈希值", foreground="green")
        else:
            self.hash_status_label.config(text="未设置任何哈希值", foreground="red")

    def clear_all_hashes(self):
        for var in self.hash_vars.values():
            var.set("")
        self.char_hashes = {}
        self.hash_status_label.config(text="已清空全部哈希值", foreground="orange")

    def capture_corner(self, idx):
        x, y = pyautogui.position()
        self.corners[idx] = (x, y)
        name = "左上" if idx == 0 else "右下"
        self.status_label.config(text=f"{name}: ({x},{y})", foreground="blue")
        if self.corners[0] and self.corners[1]:
            x1, y1 = self.corners[0]
            x2, y2 = self.corners[1]
            self.area_label.config(
                text=f"({min(x1, x2)},{min(y1, y2)})-({max(x1, x2)},{max(y1, y2)})", foreground="blue")

    def set_word_area(self):
        if not all(self.corners):
            self.status_label.config(text="请先F9/F10设置!", foreground="red")
            return
        x1, y1, x2, y2 = min(self.corners[0][0], self.corners[1][0]), min(self.corners[0][1], self.corners[1][1]), max(
            self.corners[0][0], self.corners[1][0]), max(self.corners[0][1], self.corners[1][1])
        self.word_area = (x1, y1, x2, y2)
        self.status_label.config(text="文字区域已设置", foreground="green")

    def set_yes_btn(self):
        if not all(self.corners):
            self.status_label.config(text="请先F9/F10设置!", foreground="red")
            return
        x1, y1, x2, y2 = min(self.corners[0][0], self.corners[1][0]), min(self.corners[0][1], self.corners[1][1]), max(
            self.corners[0][0], self.corners[1][0]), max(self.corners[0][1], self.corners[1][1])
        self.yes_btn = ((x1 + x2) // 2, (y1 + y2) // 2)
        self.status_label.config(text="\"是\"按钮已设置", foreground="green")

    def set_no_btn(self):
        if not all(self.corners):
            self.status_label.config(text="请先F9/F10设置!", foreground="red")
            return
        x1, y1, x2, y2 = min(self.corners[0][0], self.corners[1][0]), min(self.corners[0][1], self.corners[1][1]), max(
            self.corners[0][0], self.corners[1][0]), max(self.corners[0][1], self.corners[1][1])
        self.no_btn = ((x1 + x2) // 2, (y1 + y2) // 2)
        self.status_label.config(text="\"否\"按钮已设置", foreground="green")

    def capture_word(self):
        if not self.word_area:
            return None
        x1, y1, x2, y2 = self.word_area
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        return img

    def detect_color(self, img):
        if isinstance(img, Image.Image):
            img = np.array(img)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        text_mask = binary == 255
        if np.sum(text_mask) < 10:
            return None

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        h, s, v = cv2.split(hsv)
        text_h = h[text_mask]
        text_s = s[text_mask]
        text_v = v[text_mask]

        mean_v = np.mean(text_v)
        mean_s = np.mean(text_s)

        if mean_v < 50:
            return 'black'

        if mean_s < 50 and mean_v >= 50:
            return 'gray'

        color_scores = {}
        for color_name, ranges in COLOR_RANGES.items():
            if ranges is None:
                continue
            total_pixels = 0
            for lower, upper in ranges:
                lower = np.array(lower)
                upper = np.array(upper)
                mask = cv2.inRange(hsv, lower, upper)
                total_pixels += np.sum(mask & binary)
            if total_pixels > 0:
                color_scores[color_name] = total_pixels

        if color_scores:
            best_color = max(color_scores, key=color_scores.get)
            return best_color

        return None

    def recognize_text(self, img):
        if isinstance(img, Image.Image):
            img = np.array(img)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        current_hash = compute_shape_hash(img)

        if not self.char_hashes:
            return None, None, current_hash

        best_match = None
        best_distance = float('inf')

        for char, stored_hash in self.char_hashes.items():
            dist = hamming_distance(current_hash, stored_hash)
            if dist < best_distance:
                best_distance = dist
                best_match = char

        if best_match and best_distance <= self.hash_threshold:
            return best_match, COLOR_NAMES.get(best_match), current_hash

        return None, None, current_hash

    def test_detection(self):
        if not self.word_area:
            messagebox.showwarning("警告", "请先设置文字区域!")
            return

        img = self.capture_word()
        if img is None:
            messagebox.showerror("错误", "无法截图!")
            return

        if isinstance(img, Image.Image):
            img_np = np.array(img)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = img

        current_hash = compute_shape_hash(img_bgr)
        detected_color = self.detect_color(img_bgr)

        if self.debug_var.get():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_debug_image(img_bgr, "test", ts)

        text, text_color, _ = self.recognize_text(img_bgr)

        self.hash_result_label.config(text=f"哈希: {current_hash}")
        self.color_result_label.config(text=f"颜色: {detected_color}")

        if text:
            self.match_result_label.config(text=f"识别文字: {text} ({text_color})")
            if text_color and detected_color:
                match = text_color == detected_color
                self.status_label.config(text=f"匹配: {'是' if match else '否'}")
        else:
            self.match_result_label.config(text="识别文字: (未设置哈希或未匹配)")

        self.root.clipboard_clear()
        self.root.clipboard_append(str(current_hash))
        self.root.update()

        messagebox.showinfo("测试结果", 
            f"哈希值: {current_hash}\n\n"
            f"检测颜色: {detected_color}\n\n"
            f"识别文字: {text if text else '(未设置哈希或未匹配)'}\n\n"
            f"哈希值已复制到剪贴板!")

    def start_game(self):
        if not self.word_area or not self.yes_btn or not self.no_btn:
            messagebox.showwarning("警告", "请先设置所有区域!")
            return

        if not self.char_hashes:
            messagebox.showwarning("警告", "请先设置哈希值!")
            return

        if self.running:
            return

        self.running = True
        self.debug_mode = self.debug_var.get()
        self.hash_threshold = self.threshold_var.get()
        self.total_rounds = self.rounds_var.get()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        threading.Thread(target=self.run_game, daemon=True).start()

    def run_game(self):
        try:
            interval = self.interval_var.get()
            wait = self.wait_var.get()
            answered = 0
            ts = datetime.now().strftime("%Y%m%d_%H%M%S") if self.debug_mode else None
            last_hash = None
            same_count = 0

            while answered < self.total_rounds and self.running:
                img = self.capture_word()
                if img is None:
                    time.sleep(interval)
                    continue

                if isinstance(img, Image.Image):
                    img_np = np.array(img)
                    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                else:
                    img_bgr = img

                current_hash = compute_shape_hash(img_bgr)

                if last_hash is not None:
                    dist = hamming_distance(current_hash, last_hash)
                    if dist < 10:
                        same_count += 1
                        if same_count > 3:
                            time.sleep(interval)
                            continue
                    else:
                        same_count = 0

                last_hash = current_hash

                text, text_color, _ = self.recognize_text(img_bgr)

                if text is None:
                    time.sleep(interval)
                    continue

                detected_color = self.detect_color(img_bgr)

                if detected_color is None:
                    time.sleep(interval)
                    continue

                is_match = (text_color == detected_color)

                if self.debug_mode:
                    save_debug_image(img_bgr, f"round_{answered+1}_text_{text}", ts)

                if is_match:
                    pyautogui.click(self.yes_btn[0], self.yes_btn[1])
                    btn_text = "是"
                else:
                    pyautogui.click(self.no_btn[0], self.no_btn[1])
                    btn_text = "否"

                answered += 1

                self.root.after(0, lambda a=answered: self.hash_result_label.config(
                    text=f"轮次: {a}/{self.total_rounds}"))
                self.root.after(0, lambda t=text, tc=text_color, dc=detected_color, b=btn_text:
                                self.color_result_label.config(
                                    text=f"文字:{t}({tc}) 颜色:{dc} → 点击\"{b}\""))
                self.root.after(0, lambda t=text, tc=text_color, dc=detected_color:
                                self.match_result_label.config(
                                    text=f"文字含义:{tc} | 检测颜色:{dc} | 匹配:{tc == dc}"))

                time.sleep(wait)

            if self.running:
                self.root.after(0, lambda: self.status_label.config(
                    text=f"✓ 完成! {answered}/{self.total_rounds}", foreground="green"))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self.status_label.config(
                text=f"错误: {e}", foreground="red"))
        finally:
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self.running = False

    def stop_game(self):
        self.running = False
        self.status_label.config(text="已停止", foreground="red")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("斯特鲁普效应训练助手")
    app = StroopAuto()
    app.run()
