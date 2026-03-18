import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import numpy as np
from PIL import ImageGrab, ImageTk
import pyautogui
import keyboard
import cv2

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


class DynamicColorDiffGame:
    def __init__(self):
        self.corners = [None, None]
        self.running = False
        self.total_rounds = 40
        self.current_round = 0
        self.start_time = 0
        self.total_time = 0
        self.avg_time = 0
        self.click_delay = 0.0
        
        self.position_history = []
        self.max_history = 2

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

    def find_color_block_center(self, screenshot):
        img_array = np.array(screenshot)
        h, w = img_array.shape[:2]
        
        grid_size = 9
        grid_h = h // grid_size
        grid_w = w // grid_size
        
        grid_colors = []
        for row in range(grid_size):
            for col in range(grid_size):
                y_start = row * grid_h
                y_end = min((row + 1) * grid_h, h)
                x_start = col * grid_w
                x_end = min((col + 1) * grid_w, w)
                
                cell = img_array[y_start:y_end, x_start:x_end]
                avg_color = np.mean(cell, axis=(0, 1))
                grid_colors.append({
                    'row': row, 'col': col,
                    'color': avg_color,
                    'center_y': (y_start + y_end) // 2,
                    'center_x': (x_start + x_end) // 2,
                    'y1': y_start, 'y2': y_end,
                    'x1': x_start, 'x2': x_end
                })
        
        color_array = np.array([c['color'] for c in grid_colors])
        
        color_counts = {}
        for color in color_array:
            key = tuple(np.round(color, 1))
            color_counts[key] = color_counts.get(key, 0) + 1
        
        most_common_color = max(color_counts.keys(), key=lambda x: color_counts[x])
        most_common_color = np.array(most_common_color)
        
        for i, c in enumerate(grid_colors):
            diff = np.sum(np.abs(c['color'] - most_common_color))
            grid_colors[i]['diff'] = diff
        
        grid_colors.sort(key=lambda x: x['diff'], reverse=True)
        
        top_candidates = [c for c in grid_colors if c['diff'] > grid_colors[0]['diff'] * 0.8]
        
        if len(top_candidates) == 1:
            c = top_candidates[0]
            refined_x, refined_y = self.refine_position(screenshot, c)
            return refined_x, refined_y
        
        cluster_groups = self.group_nearby_cells(top_candidates)
        
        if cluster_groups:
            best_cluster = max(cluster_groups, key=lambda g: sum(c['diff'] for c in g))
            cluster_center_x = int(np.mean([c['center_x'] for c in best_cluster]))
            cluster_center_y = int(np.mean([c['center_y'] for c in best_cluster]))
            refined_x, refined_y = self.refine_position(screenshot, 
                {'center_x': cluster_center_x, 'center_y': cluster_center_y, 
                 'x1': cluster_center_x - grid_w, 'x2': cluster_center_x + grid_w,
                 'y1': cluster_center_y - grid_h, 'y2': cluster_center_y + grid_h})
            return refined_x, refined_y
        
        return None, None

    def group_nearby_cells(self, candidates):
        if not candidates:
            return []
        
        threshold = 2
        groups = []
        used = set()
        
        for i, c in enumerate(candidates):
            if i in used:
                continue
            
            group = [c]
            used.add(i)
            
            for j, c2 in enumerate(candidates):
                if j in used:
                    continue
                
                if abs(c['row'] - c2['row']) <= threshold and abs(c['col'] - c2['col']) <= threshold:
                    group.append(c2)
                    used.add(j)
            
            groups.append(group)
        
        return groups

    def refine_position(self, screenshot, region_info):
        img_array = np.array(screenshot)
        h, w = img_array.shape[:2]
        
        padding = 25
        x1 = max(0, region_info.get('x1', 0) - padding)
        x2 = min(w, region_info.get('x2', w) + padding)
        y1 = max(0, region_info.get('y1', 0) - padding)
        y2 = min(h, region_info.get('y2', h) + padding)
        
        region = img_array[y1:y2, x1:x2]
        
        region_h, region_w = region.shape[:2]
        
        ref_mean_color = np.mean(region, axis=(0, 1))
        
        region_float = region.astype(np.float32)
        ref_float = ref_mean_color.astype(np.float32)
        
        diff_map = np.sum(np.abs(region_float - ref_float), axis=2)
        
        threshold = np.percentile(diff_map, 65)
        
        binary_map = (diff_map > threshold).astype(np.uint8) * 255
        
        kernel = np.ones((5, 5), np.uint8)
        binary_map = cv2.morphologyEx(binary_map, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(binary_map, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)
            
            if area > 30:
                M = cv2.moments(largest)
                if M['m00'] > 0:
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])
                    
                    final_x = x1 + cx
                    final_y = y1 + cy
                    
                    if 0 <= final_x < w and 0 <= final_y < h:
                        return final_x, final_y
        
        return region_info['center_x'], region_info['center_y']

    def smooth_position(self, new_x, new_y):
        if new_x is None or new_y is None:
            return None, None
        
        self.position_history.append((new_x, new_y))
        if len(self.position_history) > self.max_history:
            self.position_history.pop(0)
        
        if len(self.position_history) >= 2:
            weights = np.linspace(0.3, 1.0, len(self.position_history))
            weights = weights / weights.sum()
            
            avg_x = sum(p[0] * w for p, w in zip(self.position_history, weights))
            avg_y = sum(p[1] * w for p, w in zip(self.position_history, weights))
            
            return int(avg_x), int(avg_y)
        
        return new_x, new_y

    def click_position(self, x1, y1, click_x, click_y):
        final_x = x1 + click_x
        final_y = y1 + click_y
        pyautogui.click(final_x, final_y)
        return final_x, final_y


class DynamicColorDiffGUI:
    def __init__(self):
        self.game = DynamicColorDiffGame()
        self.root = tk.Tk()
        self.root.title("动态色差感知游戏外挂 V2")
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
            text="🎯 动态色差感知游戏外挂 V2",
            font=('Microsoft YaHei UI', 18, 'bold')
        )
        title.pack(pady=(0, 15))

        info_frame = ttk.LabelFrame(main_frame, text="游戏说明", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(
            info_frame,
            text="大正方形内有一个颜色不同的小方块在平滑移动\n点击这个移动的色块，共40轮",
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
        self.game.position_history = []

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="游戏进行中...", foreground="orange")
        self.root.update()

        thread = threading.Thread(target=self.run_game, daemon=True)
        thread.start()

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

                target_x, target_y = self.game.find_color_block_center(screenshot)
                
                smooth_x, smooth_y = self.game.smooth_position(target_x, target_y)

                if smooth_x is None or smooth_y is None:
                    time.sleep(0.008)
                    result2 = self.game.capture_game_area()
                    if result2:
                        screenshot2, x1_2, y1_2, _, _ = result2
                        target_x2, target_y2 = self.game.find_color_block_center(screenshot2)
                        smooth_x, smooth_y = self.game.smooth_position(target_x2, target_y2)

                if smooth_x is not None and smooth_y is not None:
                    try:
                        self.game.click_position(x1, y1, smooth_x, smooth_y)
                    except Exception as e:
                        self.root.after(0, lambda: self.status_label.config(
                            text=f"点击错误: {str(e)}", foreground="red"))
                        break
                else:
                    self.root.after(0, lambda: self.status_label.config(
                        text="未能识别目标位置", foreground="orange"))

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
        self.game.position_history = []
        self.status_label.config(text="已停止", foreground="red")

    def on_closing(self):
        keyboard.unhook_all()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 50)
    print("   动态色差感知游戏外挂 V2")
    print("=" * 50)
    print("\n快捷键:")
    print("  F9  = 设置左上角")
    print("  F10 = 设置右下角")
    print("  S   = 开始游戏")
    print("\n启动中...")

    app = DynamicColorDiffGUI()
    app.run()
