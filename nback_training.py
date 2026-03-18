"""
N-Back 记忆力训练外挂
游戏规则：
  难度N-Back (1-Back到8-Back)
  
  正确流程：
  第1轮：展示图片1（无候选栏）
  第2轮：展示图片2 + 候选栏出现 → 选图片1
  第3轮：展示图片3 + 候选栏更新 → 选图片2
  ...
  
  核心逻辑：
  - 展示图片变化 → 记录到历史
  - 候选栏有效 + 历史足够 + 历史数量变化 → 答题
  
  注意：展示图片可能重复！重复时也要记录！
"""

import pyautogui
import time
import tkinter as tk
from tkinter import ttk
from PIL import ImageGrab, Image
import threading
import keyboard
import numpy as np
from collections import deque
import os
from datetime import datetime

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.001

DEBUG_DIR = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'debug_nback')


def compute_dhash(img, hash_size=8):
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img)
    img = img.convert('L').resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = list(img.getdata())
    diff = []
    for row in range(hash_size):
        for col in range(hash_size):
            idx = row * (hash_size + 1) + col
            diff.append(pixels[idx] > pixels[idx + 1])
    return sum([2**i for i, v in enumerate(diff) if v])


def hamming_distance(hash1, hash2):
    return bin(hash1 ^ hash2).count('1')


def compute_center_hash(img, hash_size=8, center_ratio=0.7):
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img)
    w, h = img.size
    margin_x = int(w * (1 - center_ratio) / 2)
    margin_y = int(h * (1 - center_ratio) / 2)
    center_img = img.crop((margin_x, margin_y, w - margin_x, h - margin_y))
    return compute_dhash(center_img, hash_size)


def save_debug_image(img, name, timestamp=None):
    if not os.path.exists(DEBUG_DIR):
        os.makedirs(DEBUG_DIR)
    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{name}.png"
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img)
    img.save(os.path.join(DEBUG_DIR, filename))


class NBackAuto:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("N-Back 记忆力训练助手")
        self.root.attributes('-topmost', True)
        self.corners = [None, None]
        self.running = False
        self.n_level = 2
        self.total_rounds = 20
        self.history_hashes = deque(maxlen=15)
        self.history_images = deque(maxlen=15)
        self.display_area = None
        self.candidate_area = None
        self.debug_mode = False
        self.setup_ui()
        self.setup_global_hotkey()

    def setup_global_hotkey(self):
        keyboard.add_hotkey('f9', lambda: self.capture_corner(0))
        keyboard.add_hotkey('f10', lambda: self.capture_corner(1))
        keyboard.add_hotkey('s', self.start_game)
        keyboard.add_hotkey('t', self.test_threshold)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="🧠 N-Back 记忆力训练助手",
                  font=('Arial', 16, 'bold')).pack(pady=5)
        ttk.Label(main_frame, text="展示图片变化→记录历史 | 候选栏有效→答题",
                  foreground="gray", font=('Arial', 9)).pack()

        config_frame = ttk.LabelFrame(main_frame, text="参数", padding="5")
        config_frame.pack(fill=tk.X, pady=5)

        row1 = ttk.Frame(config_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="N-Back:").pack(side=tk.LEFT)
        self.n_var = tk.IntVar(value=2)
        ttk.Spinbox(row1, from_=1, to=8, width=5,
                    textvariable=self.n_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="轮数:").pack(side=tk.LEFT)
        self.rounds_var = tk.IntVar(value=20)
        ttk.Spinbox(row1, from_=10, to=50, width=5,
                    textvariable=self.rounds_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="变化阈值:").pack(side=tk.LEFT)
        self.change_var = tk.IntVar(value=5)
        ttk.Spinbox(row1, from_=1, to=20, width=5,
                    textvariable=self.change_var).pack(side=tk.LEFT, padx=5)

        row2 = ttk.Frame(config_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="检测间隔:").pack(side=tk.LEFT)
        self.interval_var = tk.DoubleVar(value=0.02)
        ttk.Spinbox(row2, from_=0.01, to=0.5, increment=0.01, width=6,
                    textvariable=self.interval_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="秒").pack(side=tk.LEFT)
        ttk.Label(row2, text="点击等待:").pack(side=tk.LEFT)
        self.wait_var = tk.DoubleVar(value=0.15)
        ttk.Spinbox(row2, from_=0.05, to=1.0, increment=0.05, width=6,
                    textvariable=self.wait_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="秒").pack(side=tk.LEFT)

        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(config_frame, text="调试模式",
                        variable=self.debug_var).pack(anchor=tk.W)

        area_frame = ttk.LabelFrame(
            main_frame, text="区域设置 (F9/F10)", padding="5")
        area_frame.pack(fill=tk.X, pady=5)
        self.area_label = ttk.Label(
            area_frame, text="F9=左上角 F10=右下角", foreground="gray")
        self.area_label.pack()
        btn_row = ttk.Frame(area_frame)
        btn_row.pack(fill=tk.X, pady=2)
        ttk.Button(btn_row, text="设置展示区域", command=self.set_display_area,
                   width=12).pack(side=tk.LEFT, padx=2, expand=True)
        ttk.Button(btn_row, text="设置候选区域", command=self.set_candidate_area,
                   width=12).pack(side=tk.LEFT, padx=2, expand=True)
        ttk.Button(btn_row, text="测试(T)", command=self.test_threshold,
                   width=8).pack(side=tk.LEFT, padx=2, expand=True)

        status_frame = ttk.LabelFrame(main_frame, text="状态", padding="5")
        status_frame.pack(fill=tk.X, pady=5)
        status_row = ttk.Frame(status_frame)
        status_row.pack(fill=tk.X)
        self.round_label = ttk.Label(
            status_row, text="轮次: 0/20", foreground="blue", font=('Arial', 11))
        self.round_label.pack(side=tk.LEFT, padx=10)
        self.history_label = ttk.Label(
            status_row, text="历史: 0", foreground="gray", font=('Arial', 10))
        self.history_label.pack(side=tk.LEFT, padx=10)
        self.debug_label = ttk.Label(
            status_frame, text="", foreground="orange", font=('Arial', 9))
        self.debug_label.pack()

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=5)
        self.start_btn = ttk.Button(
            action_frame, text="▶ 开始 (S)", command=self.start_game, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.stop_btn = ttk.Button(
            action_frame, text="⏹ 停止", command=self.stop_game, state=tk.DISABLED, width=15)
        self.stop_btn.pack(side=tk.LEFT, padx=5, expand=True)

        self.status_label = ttk.Label(
            main_frame, text="就绪", foreground="green", font=('Arial', 11))
        self.status_label.pack(pady=5)

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

    def set_display_area(self):
        if not all(self.corners):
            self.status_label.config(text="请先F9/F10设置!", foreground="red")
            return
        x1, y1, x2, y2 = min(self.corners[0][0], self.corners[1][0]), min(self.corners[0][1], self.corners[1][1]), max(
            self.corners[0][0], self.corners[1][0]), max(self.corners[0][1], self.corners[1][1])
        self.display_area = (x1, y1, x2, y2)
        self.status_label.config(text="展示区域已设置", foreground="green")

    def set_candidate_area(self):
        if not all(self.corners):
            self.status_label.config(text="请先F9/F10设置!", foreground="red")
            return
        x1, y1, x2, y2 = min(self.corners[0][0], self.corners[1][0]), min(self.corners[0][1], self.corners[1][1]), max(
            self.corners[0][0], self.corners[1][0]), max(self.corners[0][1], self.corners[1][1])
        self.candidate_area = (x1, y1, x2, y2)
        self.status_label.config(text="候选区域已设置", foreground="green")

    def capture_display(self):
        if not self.display_area:
            return None, None, None
        x1, y1, x2, y2 = self.display_area
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        return compute_dhash(img), compute_center_hash(img), img

    def capture_candidates(self):
        if not self.candidate_area:
            return [], [], [], []
        x1, y1, x2, y2 = self.candidate_area
        w = (x2 - x1) // 4
        positions, hashes, center_hashes, images = [], [], [], []
        for i in range(4):
            img = ImageGrab.grab(bbox=(x1 + i*w, y1, x1 + (i+1)*w, y2))
            positions.append((x1 + i*w + w//2, (y1 + y2)//2))
            hashes.append(compute_dhash(img))
            center_hashes.append(compute_center_hash(img))
            images.append(img)
        return positions, hashes, center_hashes, images

    def find_best(self, th, tch, hashes, center_hashes):
        best_idx, best_score = 0, float('inf')
        for i, (h, ch) in enumerate(zip(hashes, center_hashes)):
            score = hamming_distance(tch, ch) * 2 + hamming_distance(th, h)
            if score < best_score:
                best_score, best_idx = score, i
        return best_idx

    def test_threshold(self):
        if not self.display_area or not self.candidate_area:
            self.status_label.config(text="请先设置区域!", foreground="red")
            return
        h, ch, _ = self.capture_display()
        _, hashes, center_hashes, _ = self.capture_candidates()
        info = " | ".join(
            [f"候选{i+1}:{hamming_distance(h, hh)}" for i, hh in enumerate(hashes)])
        self.debug_label.config(text=info)

    def start_game(self):
        if not self.display_area or not self.candidate_area:
            self.status_label.config(text="请先设置区域!", foreground="red")
            return
        if self.running:
            return
        self.running = True
        self.debug_mode = self.debug_var.get()
        self.n_level = self.n_var.get()
        self.total_rounds = self.rounds_var.get()
        self.history_hashes.clear()
        self.history_images.clear()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        threading.Thread(target=self.run_game, daemon=True).start()

    def run_game(self):
        try:
            interval = self.interval_var.get()
            wait = self.wait_var.get()
            change_threshold = self.change_var.get()
            answered = 0
            ts = datetime.now().strftime("%Y%m%d_%H%M%S") if self.debug_mode else None
            last_display_h = None
            last_candidate_hash = None

            while answered < self.total_rounds and self.running:
                h, ch, img = self.capture_display()
                if h is None:
                    time.sleep(interval)
                    continue

                # 展示图片变化时记录（独立于候选栏）
                display_changed = last_display_h is None or hamming_distance(
                    last_display_h, h) > change_threshold
                if display_changed:
                    self.history_hashes.append((h, ch))
                    self.history_images.append(img)
                    last_display_h = h
                    if self.debug_mode:
                        save_debug_image(
                            img, f"display_{len(self.history_hashes)}", ts)
                    self.root.after(0, lambda: self.history_label.config(
                        text=f"历史: {len(self.history_hashes)}"))

                # 检查候选栏
                positions, hashes, center_hashes, images = self.capture_candidates()
                if not positions:
                    time.sleep(interval)
                    continue

                # 候选栏有效性：4个格子互不相同
                valid = len(set(hashes)) == 4
                if not valid:
                    time.sleep(interval)
                    continue

                # 候选栏变化？
                current_candidate_hash = sum(hashes)
                if last_candidate_hash == current_candidate_hash:
                    time.sleep(interval)
                    continue

                # 更新候选栏哈希
                last_candidate_hash = current_candidate_hash

                # 历史足够？
                if len(self.history_hashes) < self.n_level + 1:
                    time.sleep(interval)
                    continue

                # 匹配并点击
                target_idx = len(self.history_hashes) - self.n_level - 1
                th, tch = self.history_hashes[target_idx]
                timg = self.history_images[target_idx]
                best_idx = self.find_best(th, tch, hashes, center_hashes)

                if self.debug_mode:
                    save_debug_image(
                        timg, f"target_{target_idx+1}_round{answered+1}", ts)
                    for i, im in enumerate(images):
                        save_debug_image(
                            im, f"candidate_{i+1}_round{answered+1}", ts)

                x, y = positions[best_idx]
                pyautogui.click(x, y)

                answered += 1

                self.root.after(0, lambda a=answered: self.round_label.config(
                    text=f"轮次: {a}/{self.total_rounds}"))
                self.root.after(0, lambda bi=best_idx, ti=target_idx: self.status_label.config(
                    text=f"点击候选{bi+1} (历史#{ti+1})", foreground="green"))

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
        self.root.protocol("WM_DELETE_WINDOW", lambda: (
            keyboard.unhook_all(), self.root.destroy()))
        self.root.mainloop()


if __name__ == "__main__":
    print("N-Back 训练助手 | F9/F10=设置区域 S=开始 T=测试")
    NBackAuto().run()
