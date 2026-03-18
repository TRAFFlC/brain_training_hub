"""
舒尔特方格自动通关 V2 - 高性能版
使用模板匹配进行超高速数字识别
支持 3x3 到 9x9 舒尔特表（数字 1-81）
"""

import pyautogui
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageGrab
import threading
import cv2
import numpy as np
import keyboard
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import mss
import ctypes
from ctypes import windll

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.001

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
DEBUG_DIR = os.path.join(BASE_DIR, 'debug')


class FastClicker:
    """使用 Windows API 进行快速点击"""
    
    @staticmethod
    def click(x, y):
        """快速点击指定坐标"""
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)


class TemplateMatcher:
    """模板匹配识别器"""
    
    def __init__(self):
        self.templates = {}
        self.template_loaded = False
        
    def load_templates(self):
        """加载所有数字模板"""
        if not os.path.exists(TEMPLATE_DIR):
            return False
            
        for i in range(1, 82):
            template_path = os.path.join(TEMPLATE_DIR, f'{i}.png')
            if os.path.exists(template_path):
                template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                if template is not None:
                    self.templates[i] = template
                    
        self.template_loaded = len(self.templates) > 0
        return self.template_loaded
        
    def match_in_cell(self, cell_img, scales=[0.8, 0.9, 1.0, 1.1, 1.2], debug_mode=False, remove_border=False):
        """在单元格图像中匹配数字
        
        Args:
            cell_img: 单元格图像
            scales: 多尺度匹配参数
            debug_mode: 是否输出调试信息
            remove_border: 是否去除边框（裁剪掉边缘 10%）- 默认关闭
        """
        # 预处理：去除边框干扰（可选）
        if remove_border:
            h, w = cell_img.shape[:2]
            # 裁剪掉边缘 10%，去除灰色边框
            crop_h, crop_w = int(h * 0.1), int(w * 0.1)
            cell_img = cell_img[crop_h:h-crop_h, crop_w:w-crop_w]
        
        cell_gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
        
        # 记录所有匹配结果用于调试
        match_scores = {}
        
        best_match = None
        best_score = 0.7
        best_num = None
        
        for num, template in self.templates.items():
            num_best_score = 0  # 该数字在所有尺度中的最高分
            
            for scale in scales:
                if scale == 1.0:
                    resized_template = template
                else:
                    new_size = (int(template.shape[1] * scale), 
                               int(template.shape[0] * scale))
                    resized_template = cv2.resize(template, new_size)
                
                if resized_template.shape[0] > cell_gray.shape[0] or \
                   resized_template.shape[1] > cell_gray.shape[1]:
                    continue
                    
                result = cv2.matchTemplate(cell_gray, resized_template, 
                                          cv2.TM_CCOEFF_NORMED)
                score = result.max()
                
                # 记录该数字的最高分
                if score > num_best_score:
                    num_best_score = score
                
                if score > best_score:
                    best_score = score
                    best_match = (num, score)
            
            # 保存该数字的最高分
            match_scores[num] = num_best_score
        
        # 调试输出：显示所有数字的匹配分数
        if debug_mode and best_match:
            print(f"  匹配到数字 {best_match[0]}, 分数：{best_match[1]:.3f}")
            # 显示分数前 5 高的数字
            sorted_scores = sorted(match_scores.items(), key=lambda x: x[1], reverse=True)[:5]
            top5_str = ", ".join([f"{num}:{score:.3f}" for num, score in sorted_scores])
            print(f"  TOP5: {top5_str}")
                    
        return best_match


class TemplateCollector:
    """模板采集器 - 自动从截屏中提取数字模板"""
    
    def __init__(self, ocr_func):
        self.ocr = ocr_func
        self.debug_dir = os.path.join(BASE_DIR, 'debug')
        
    def collect_templates(self, screenshot, grid_size, x1, y1, x2, y2):
        """从截图中提取所有数字模板"""
        img_array = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        grid_w = x2 - x1
        grid_h = y2 - y1
        cell_w = grid_w / grid_size
        cell_h = grid_h / grid_size
        
        templates_found = {}
        cell_images = {}
        
        # 保存调试图像
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cv2.imwrite(os.path.join(self.debug_dir, f"{timestamp}_full_grid.png"), img_bgr)
        
        # 先提取所有单元格
        for row in range(grid_size):
            for col in range(grid_size):
                cell_x1 = int(col * cell_w)
                cell_y1 = int(row * cell_h)
                cell_x2 = int((col + 1) * cell_w)
                cell_y2 = int((row + 1) * cell_h)
                
                cell_img = img_bgr[cell_y1:cell_y2, cell_x1:cell_x2]
                
                # 保存原始单元格图像用于调试
                if row < 3 and col < 3:  # 只保存前几个单元格
                    debug_path = os.path.join(self.debug_dir, 
                                             f"{timestamp}_cell_r{row}_c{col}.png")
                    cv2.imwrite(debug_path, cell_img)
                
                cell_images[(row, col)] = cell_img
        
        # 识别所有单元格
        print(f"开始识别 {grid_size}x{grid_size} = {grid_size*grid_size} 个单元格...")
        for row in range(grid_size):
            for col in range(grid_size):
                cell_img = cell_images[(row, col)]
                num = self.ocr(cell_img)
                
                if num is not None and 1 <= num <= 81:
                    if num not in templates_found:
                        templates_found[num] = cell_img
                        print(f"  识别到数字 {num} (位置：行{row+1}, 列{col+1})")
                        
                        # 保存识别到的模板
                        template_path = os.path.join(self.debug_dir,
                                                    f"{timestamp}_recognized_{num}_r{row}_c{col}.png")
                        cv2.imwrite(template_path, cell_img)
                    else:
                        print(f"  数字 {num} 已存在，跳过 (位置：行{row+1}, 列{col+1})")
                else:
                    print(f"  未能识别位置 (行{row+1}, 列{col+1}) 的数字")
        
        # 保存所有模板
        self.save_templates(templates_found)
        
        print(f"\n模板采集完成！")
        print(f"  成功识别：{len(templates_found)} 个数字")
        print(f"  缺少：{[i for i in range(1, grid_size*grid_size+1) if i not in templates_found]}")
        
        return len(templates_found)
        
    def save_templates(self, templates):
        """保存模板到文件（保存原始图像，不裁剪）"""
        if not os.path.exists(TEMPLATE_DIR):
            os.makedirs(TEMPLATE_DIR)
            
        saved_count = 0
        for num, img in templates.items():
            # 保存原始图像（带边框），匹配时再裁剪
            template_path = os.path.join(TEMPLATE_DIR, f'{num}.png')
            cv2.imwrite(template_path, img)
            saved_count += 1
            
        print(f"已保存 {saved_count} 个模板到 {TEMPLATE_DIR}")


class SchulteAutoV2:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("舒尔特方格助手 V2 - 高性能版")
        self.root.geometry("500x650")
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)
        self.root.minsize(400, 500)
        
        self.corners = [None, None]
        self.start_button_pos = None
        self.running = False
        self.debug_mode = False
        self.template_loaded = False
        
        self.template_matcher = TemplateMatcher()
        self.ocr = None
        self.ocr_preloaded = False
        
        self.config = self.load_config()
        
        self.setup_ui()
        self.setup_global_hotkey()
        
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if 'corners' in config and len(config['corners']) == 2:
                    self.corners = config['corners']
                if 'start_button' in config:
                    self.start_button_pos = config['start_button']
                return config
            except:
                pass
        return {}
        
    def save_config(self):
        """保存配置文件"""
        config = {
            'corners': self.corners,
            'start_button': self.start_button_pos
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
    def setup_global_hotkey(self):
        keyboard.add_hotkey('f9', lambda: self.capture_corner(0))
        keyboard.add_hotkey('f10', lambda: self.capture_corner(1))
        keyboard.add_hotkey('f12', lambda: self.capture_start_button())
        keyboard.add_hotkey('s', self.one_click_solve)
        
    def get_ocr(self):
        """懒加载 OCR（仅用于首次模板采集）"""
        if self.ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR()
        return self.ocr
        
    def ocr_recognize_digit(self, cell_img):
        """
        使用 OCR 识别单个数字（仅用于模板采集）
        完整参考第一版的识别流程，提高识别准确率
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
                            num = int(text)
                            if 1 <= num <= 81:
                                return num
            except:
                pass
            return None
        
        def preprocess_and_try(thresh_img):
            """关键：先提取轮廓，裁剪 ROI，再缩放，最后转 BGR 给 OCR"""
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
                return None
            
            # 缩放
            scale = max(4, 80 // max(h, w))
            new_w = w * scale
            new_h = h * scale
            digit_roi = cv2.resize(
                digit_roi, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            
            # 加边框
            border = 20
            digit_roi = cv2.copyMakeBorder(digit_roi, border, border, border, border,
                                          cv2.BORDER_CONSTANT, value=0)
            
            # 关键：灰度图转 BGR（三通道）给 OCR
            digit_bgr = cv2.cvtColor(digit_roi, cv2.COLOR_GRAY2BGR)
            return try_recognize(digit_bgr)
        
        # 策略 1: 直接识别原图
        result = try_recognize(cell_img)
        if result is not None:
            return result
        
        # 策略 2: 缩放加边框（白底）
        h, w = cell_img.shape[:2]
        scale = max(2, 60 // max(h, w))
        cell_img_scaled = cv2.resize(
            cell_img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
        border = 15
        cell_img_padded = cv2.copyMakeBorder(cell_img_scaled, border, border, border, border,
                                            cv2.BORDER_CONSTANT, value=(255, 255, 255))
        result = try_recognize(cell_img_padded)
        if result is not None:
            return result
        
        # 策略 3: Otsu 二值化 + 轮廓提取
        _, thresh_otsu = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(gray) > 127:
            thresh_otsu = cv2.bitwise_not(thresh_otsu)
        
        result = preprocess_and_try(thresh_otsu)
        if result is not None:
            return result
        
        result = preprocess_and_try(cv2.bitwise_not(thresh_otsu))
        if result is not None:
            return result
        
        # 策略 4: 固定阈值 + 轮廓提取
        for thresh_val in [127, 100, 150, 80, 180]:
            _, thresh_fixed = cv2.threshold(
                gray, thresh_val, 255, cv2.THRESH_BINARY)
            result = preprocess_and_try(thresh_fixed)
            if result is not None:
                return result
            result = preprocess_and_try(cv2.bitwise_not(thresh_fixed))
            if result is not None:
                return result
        
        # 策略 5: 自适应阈值（高斯）+ 轮廓提取
        thresh_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 11, 2)
        result = preprocess_and_try(thresh_adapt)
        if result is not None:
            return result
        result = preprocess_and_try(cv2.bitwise_not(thresh_adapt))
        if result is not None:
            return result
        
        # 策略 6: 自适应阈值（均值）+ 轮廓提取
        thresh_adapt2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                             cv2.THRESH_BINARY, 15, 5)
        result = preprocess_and_try(thresh_adapt2)
        if result is not None:
            return result
        
        return None
        
    def preload_templates(self):
        """预加载模板"""
        if not self.template_loaded:
            self.status_label.config(text="正在加载模板...", foreground="orange")
            self.root.update()
            
            if self.template_matcher.load_templates():
                self.template_loaded = True
                count = len(self.template_matcher.templates)
                self.status_label.config(
                    text=f"模板已加载 ({count}个)", 
                    foreground="green"
                )
                print(f"✓ 模板加载成功：{count} 个模板")
            else:
                self.status_label.config(
                    text="模板不存在，首次使用需采集", 
                    foreground="red"
                )
                print("✗ 模板加载失败：templates 文件夹不存在或为空")
                
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title = ttk.Label(main_frame, text="🎯 舒尔特方格助手 V2",
                          font=('Arial', 18, 'bold'))
        title.pack(pady=5)
        
        size_frame = ttk.Frame(main_frame)
        size_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(size_frame, text="方格大小:").pack(side=tk.LEFT)
        self.size_var = tk.IntVar(value=8)
        ttk.Spinbox(size_frame, from_=3, to=9, width=5,
                    textvariable=self.size_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(size_frame, text="点击间隔:").pack(side=tk.LEFT, padx=(15, 0))
        self.delay_var = tk.DoubleVar(value=0.005)
        ttk.Spinbox(size_frame, from_=0.0, to=1.0, increment=0.001, width=6,
                    textvariable=self.delay_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(size_frame, text="秒").pack(side=tk.LEFT)
        
        ttk.Label(size_frame, text="    启动延迟:").pack(side=tk.LEFT, padx=(15, 0))
        self.start_delay_var = tk.DoubleVar(value=0.1)
        ttk.Spinbox(size_frame, from_=0.0, to=2.0, increment=0.01, width=6,
                    textvariable=self.start_delay_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(size_frame, text="秒").pack(side=tk.LEFT)
        
        debug_frame = ttk.Frame(main_frame)
        debug_frame.pack(fill=tk.X, pady=5)
        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(debug_frame, text="保存调试图片",
                        variable=self.debug_var).pack(side=tk.LEFT)
        
        ttk.Button(debug_frame, text="加载模板", 
                   command=self.preload_templates).pack(side=tk.RIGHT, padx=5)
        ttk.Button(debug_frame, text="重新采集模板", 
                   command=self.collect_templates).pack(side=tk.RIGHT, padx=5)
        
        area_frame = ttk.LabelFrame(main_frame, text="区域设置", padding="8")
        area_frame.pack(fill=tk.X, pady=5)
        
        btn_row = ttk.Frame(area_frame)
        btn_row.pack(fill=tk.X, pady=2)
        
        ttk.Label(btn_row, text="F9 = 设置左上角", font=(
            'Arial', 10, 'bold'), foreground='blue').pack(side=tk.LEFT, padx=5)
        ttk.Label(btn_row, text="F10 = 设置右下角", font=(
            'Arial', 10, 'bold'), foreground='blue').pack(side=tk.LEFT, padx=5)
        ttk.Label(btn_row, text="F12 = 设置开始按钮", font=(
            'Arial', 10, 'bold'), foreground='green').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(area_frame, text="📍 手动设置开始按钮", 
                   command=self.capture_start_button).pack(side=tk.RIGHT, padx=5, pady=2)
        
        self.area_label = ttk.Label(
            area_frame, text="移动鼠标到位置，按 F9/F10 确认", foreground="gray")
        self.area_label.pack(pady=5)
        
        self.start_btn_label = ttk.Label(
            area_frame, text="开始按钮：未设置", foreground="gray")
        self.start_btn_label.pack(pady=2)
        
        preview_frame = ttk.LabelFrame(main_frame, text="识别并通关", padding="8")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.preview_canvas = tk.Canvas(
            preview_frame, width=400, height=120, bg='#2d2d2d')
        self.preview_canvas.pack()
        
        btn_row2 = ttk.Frame(preview_frame)
        btn_row2.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_row2, text="📷 截图预览", 
                   command=self.capture_preview).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(btn_row2, text="🚀 一键通关 (S 键)", 
                   command=self.one_click_solve).pack(side=tk.LEFT, padx=5, expand=True)
        
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
            main_frame, text="状态：就绪 - 按 S 键快速通关", 
            foreground="green", font=('Arial', 11))
        self.status_label.pack(pady=5)
        
        perf_frame = ttk.LabelFrame(main_frame, text="性能统计", padding="8")
        perf_frame.pack(fill=tk.X, pady=5)
        
        self.perf_label = ttk.Label(
            perf_frame, 
            text="截图：-ms | 识别：-ms | 点击：-ms | 总计：-ms",
            foreground="blue"
        )
        self.perf_label.pack()
        
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
                text=f"区域：({min(x1, x2)}, {min(y1, y2)}) → ({max(x1, x2)}, {max(y1, y2)})",
                foreground="blue"
            ))
            
        self.save_config()
        
    def capture_start_button(self):
        """捕获开始按钮位置"""
        x, y = pyautogui.position()
        self.start_button_pos = (x, y)
        
        self.root.after(0, lambda: self.start_btn_label.config(
            text=f"开始按钮：({x}, {y})", 
            foreground="green"
        ))
        self.root.after(0, lambda: self.status_label.config(
            text=f"已记录开始按钮位置", 
            foreground="green"
        ))
        
        self.save_config()
        
    def collect_templates(self):
        """采集模板"""
        if not self.corners[0] or not self.corners[1]:
            messagebox.showwarning("警告", "请先设置区域（F9/F10）")
            return
            
        self.root.after(0, lambda: self.status_label.config(
            text="正在采集模板...", foreground="orange"))
        self.root.update()
        
        try:
            x1, y1 = self.corners[0]
            x2, y2 = self.corners[1]
            
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
                
            size = self.size_var.get()
            
            with mss.mss() as sct:
                monitor = {"left": x1, "top": y1, "width": x2-x1, "height": y2-y1}
                screenshot = sct.grab(monitor)
                screenshot = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
            
            collector = TemplateCollector(self.ocr_recognize_digit)
            count = collector.collect_templates(screenshot, size, 0, 0, x2-x1, y2-y1)
            
            if count > 0:
                self.template_matcher.load_templates()
                self.template_loaded = True
                missing = [i for i in range(1, size*size+1) if i not in self.template_matcher.templates]
                
                self.root.after(0, lambda: self.status_label.config(
                    text=f"模板采集成功！({count}个数字)", foreground="green"))
                
                if missing:
                    msg = (f"模板采集完成！共采集到 {count} 个数字模板。\n"
                          f"缺少：{missing}\n\n"
                          f"建议：\n"
                          f"1. 检查游戏界面是否完整\n"
                          f"2. 重新调整区域（F9/F10）\n"
                          f"3. 再次点击'重新采集模板'\n"
                          f"4. 调试图片已保存到 debug 文件夹")
                    self.root.after(0, lambda: messagebox.showwarning("部分成功", msg))
                else:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "成功", f"模板采集完成！共采集到 {count} 个数字模板。\n现在可以开始使用了。"))
            else:
                self.root.after(0, lambda: self.status_label.config(
                    text="模板采集失败", foreground="red"))
                self.root.after(0, lambda: messagebox.showerror(
                    "失败", "未能识别到任何数字，请检查区域设置是否正确"))
                    
        except Exception as e:
            import traceback
            error_msg = f"采集模板时出错：{str(e)}\n\n{traceback.format_exc()}"
            self.root.after(0, lambda: self.status_label.config(
                text=f"采集失败：{str(e)}", foreground="red"))
            self.root.after(0, lambda: messagebox.showerror(
                "错误", error_msg))
                
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
            
        with mss.mss() as sct:
            monitor = {"left": x1, "top": y1, "width": x2-x1, "height": y2-y1}
            screenshot = sct.grab(monitor)
            screenshot = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
        
        self.tk_preview = ImageTk.PhotoImage(screenshot)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(200, 60, image=self.tk_preview)
        
        size = self.size_var.get()
        self.debug_mode = self.debug_var.get()
        
        start_time = time.time()
        self.number_positions = self.recognize_all_numbers(
            screenshot, x1, y1, x2, y2, size)
        recognize_time = (time.time() - start_time) * 1000
        
        if self.number_positions:
            found = sorted(self.number_positions.keys())
            self.result_label.config(
                text=f"识别到 {len(found)} 个数字：{found}",
                foreground="blue"
            )
            self.status_label.config(
                text=f"识别成功！耗时：{recognize_time:.1f}ms", 
                foreground="green"
            )
        else:
            self.result_label.config(text="识别失败", foreground="red")
            
    def recognize_all_numbers(self, screenshot, x1, y1, x2, y2, size):
        """使用模板匹配识别所有数字"""
        if not self.template_loaded:
            if not self.template_matcher.load_templates():
                return {}
            self.template_loaded = True
                
        img_array = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        grid_w = x2 - x1
        grid_h = y2 - y1
        cell_w = grid_w / size
        cell_h = grid_h / size
        
        if self.debug_mode:
            print(f"\n开始识别 {size}x{size} 网格...")
            print(f"  区域：({x1}, {y1}) -> ({x2}, {y2})")
            print(f"  单元格大小：{cell_w:.1f} x {cell_h:.1f}")
            print(f"  模板数量：{len(self.template_matcher.templates)}")
        
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
            match_result = self.template_matcher.match_in_cell(cell_img, debug_mode=self.debug_mode)
            return (row, col, match_result, cell_img)
        
        number_positions = {}
        match_count = 0
        fail_count = 0
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(recognize_cell, cells))
        
        for row, col, match_result, cell_img in results:
            if match_result is not None:
                num, score = match_result
                center_x = x1 + col * cell_w + cell_w / 2
                center_y = y1 + row * cell_h + cell_h / 2
                number_positions[num] = (center_x, center_y)
                match_count += 1
                
                if self.debug_mode:
                    print(f"  单元格 [{row+1},{col+1}] -> 数字 {num} (分数：{score:.2f})")
                    # 保存调试图片
                    self.save_debug_image(cell_img, row, col, num, score)
            else:
                fail_count += 1
                if self.debug_mode:
                    print(f"  单元格 [{row+1},{col+1}] -> 未识别")
                    # 保存未识别的单元格
                    self.save_debug_image(cell_img, row, col, None, 0)
        
        if self.debug_mode:
            print(f"识别完成：成功 {match_count}/{size*size}, 失败 {fail_count}\n")
        
        return number_positions
        
    def save_debug_image(self, img, row, col, num, score):
        if not self.debug_mode:
            return
            
        if not os.path.exists(DEBUG_DIR):
            os.makedirs(DEBUG_DIR)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_r{row}_c{col}_num{num}_score{score:.2f}.png"
        cv2.imwrite(os.path.join(DEBUG_DIR, filename), img)
        
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
            start_delay = self.start_delay_var.get()
            total = size * size
            
            perf_start = time.time()
            
            # 步骤 1: 点击开始按钮（如果设置了）
            if self.start_button_pos:
                FastClicker.click(self.start_button_pos[0], self.start_button_pos[1])
                # 等待游戏显示数字
                if start_delay > 0:
                    time.sleep(start_delay)
            
            # 步骤 2: 截图
            screenshot_start = time.time()
            with mss.mss() as sct:
                monitor = {"left": x1, "top": y1, "width": x2-x1, "height": y2-y1}
                screenshot = sct.grab(monitor)
                screenshot = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
            screenshot_time = (time.time() - screenshot_start) * 1000
            
            # 步骤 3: 识别数字
            recognize_start = time.time()
            number_positions = self.recognize_all_numbers(
                screenshot, x1, y1, x2, y2, size)
            recognize_time = (time.time() - recognize_start) * 1000
            
            print(f"\n[性能] 截图：{screenshot_time:.1f}ms | 识别：{recognize_time:.1f}ms")
            print(f"[识别结果] 识别到 {len(number_positions)}/{total} 个数字\n")
            
            if not number_positions:
                self.root.after(0, lambda: self.status_label.config(
                    text="识别失败!", foreground="red"))
                self.root.after(0, lambda: self.perf_label.config(
                    text=f"截图：{screenshot_time:.1f}ms | 识别：{recognize_time:.1f}ms | 识别失败",
                    foreground="red"
                ))
                return
                
            sorted_nums = sorted(
                [n for n in number_positions.keys() if 1 <= n <= total])
            
            # 步骤 4: 点击数字
            click_start = time.time()
            for i, num in enumerate(sorted_nums):
                if not self.running:
                    break
                    
                x, y = number_positions[num]
                FastClicker.click(x, y)
                if delay > 0:
                    time.sleep(delay)
                    
            click_time = (time.time() - click_start) * 1000
            total_time = (time.time() - perf_start) * 1000
            
            if self.running:
                self.root.after(0, lambda: self.perf_label.config(
                    text=f"截图：{screenshot_time:.1f}ms | 识别：{recognize_time:.1f}ms | 点击：{click_time:.1f}ms | 总计：{total_time:.1f}ms",
                    foreground="green"
                ))
                self.root.after(0, lambda: self.status_label.config(
                    text=f"✓ 完成！总计:{total_time:.1f}ms", 
                    foreground="green"
                ))
                
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
            self.running = False
            
    def start_auto(self):
        if not self.number_positions:
            self.status_label.config(text="请先点击'截图预览'!", foreground="red")
            return
            
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="状态：运行中...", foreground="orange")
        
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
                FastClicker.click(x, y)
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
                text=f"错误：{str(e)}", foreground="red"))
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
        self.save_config()
        keyboard.unhook_all()
        self.root.destroy()
        
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.preload_templates()
        if self.start_button_pos:
            self.start_btn_label.config(
                text=f"开始按钮：({self.start_button_pos[0]}, {self.start_button_pos[1]})",
                foreground="green"
            )
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 50)
    print("   舒尔特方格自动通关 V2 - 高性能版")
    print("=" * 50)
    print("\n快捷键:")
    print("  F9  = 设置左上角")
    print("  F10 = 设置右下角")
    print("  F12 = 设置开始按钮")
    print("  S   = 一键通关")
    print("\n首次使用:")
    print("  1. 按 F9/F10 设置舒尔特表区域")
    print("  2. 点击'重新采集模板'自动采集数字模板")
    print("  3. 按 F12 设置开始按钮位置（可选）")
    print("  4. 按 S 键开始自动通关")
    print("\n启动中...")
    
    app = SchulteAutoV2()
    app.run()
