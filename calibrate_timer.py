"""
计时器校准工具
用于精确测量系统点击延迟，帮助优化时间感知训练器的精度
"""

import tkinter as tk
from tkinter import ttk
import time
import ctypes
import threading

pyautogui = __import__('pyautogui')


class HighPrecisionTimer:
    """高精度计时器"""
    
    def __init__(self):
        self.timer_resolution = 1
        try:
            ctypes.windll.winmm.timeBeginPeriod(self.timer_resolution)
        except:
            pass
    
    def sleep(self, seconds):
        """高精度睡眠"""
        if seconds <= 0:
            return
        
        start = time.perf_counter()
        end_time = start + seconds
        
        while True:
            current = time.perf_counter()
            remaining = end_time - current
            if remaining <= 0:
                break
            if remaining > 0.005:
                time.sleep(remaining * 0.7)
            else:
                # 最后 5ms 纯忙等待
                while time.perf_counter() < end_time:
                    pass
    
    def get_time(self):
        return time.perf_counter()
    
    def __del__(self):
        try:
            ctypes.windll.winmm.timeEndPeriod(self.timer_resolution)
        except:
            pass


class FastClicker:
    """快速点击器"""
    
    @staticmethod
    def click(x, y):
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)


class TimerCalibrator:
    """计时器校准器"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("⚙️ 计时器校准工具")
        self.root.geometry("500x450")
        self.root.attributes('-topmost', True)
        
        self.timer = HighPrecisionTimer()
        self.running = False
        self.calibration_results = []
        
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title = ttk.Label(main_frame, text="⚙️ 计时器校准工具",
                         font=('Arial', 16, 'bold'))
        title.pack(pady=10)
        
        desc = ttk.Label(main_frame, 
                        text="测量系统点击延迟，优化训练器精度",
                        font=('Arial', 10))
        desc.pack(pady=5)
        
        # 校准设置
        setting_frame = ttk.LabelFrame(main_frame, text="校准设置", padding="8")
        setting_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(setting_frame, text="测试次数:").pack(side=tk.LEFT, padx=5)
        self.iterations_var = tk.IntVar(value=20)
        ttk.Spinbox(setting_frame, from_=5, to=100, width=5,
                    textvariable=self.iterations_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(setting_frame, text="间隔时间 (秒):").pack(side=tk.LEFT, padx=(15, 0))
        self.interval_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(setting_frame, from_=0.1, to=10.0, increment=0.1, width=6,
                    textvariable=self.interval_var).pack(side=tk.LEFT, padx=5)
        
        # 控制按钮
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="▶ 开始校准",
                                   command=self.start_calibration)
        self.start_btn.pack(side=tk.LEFT, expand=True, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹ 停止",
                                  command=self.stop_calibration,
                                  state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, padx=5)
        
        # 实时结果
        result_frame = ttk.LabelFrame(main_frame, text="实时结果", padding="8")
        result_frame.pack(fill=tk.X, pady=10)
        
        self.current_label = ttk.Label(result_frame, text="等待开始...",
                                       font=('Arial', 11))
        self.current_label.pack(pady=5)
        
        # 统计结果
        stats_frame = ttk.LabelFrame(main_frame, text="统计结果", padding="8")
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.stats_text = tk.Text(stats_frame, height=8, width=60,
                                  font=('Consolas', 9))
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        # 建议
        advice_frame = ttk.LabelFrame(main_frame, text="优化建议", padding="8")
        advice_frame.pack(fill=tk.X, pady=10)
        
        self.advice_label = ttk.Label(advice_frame, text="请先运行校准...",
                                      font=('Arial', 10), foreground='orange')
        self.advice_label.pack(pady=5)
        
        self.status_label = ttk.Label(main_frame, text="状态：就绪",
                                      foreground="green", font=('Arial', 10))
        self.status_label.pack(pady=5)
    
    def start_calibration(self):
        if self.running:
            return
        
        self.running = True
        self.calibration_results = []
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="状态：校准中...", foreground="orange")
        
        thread = threading.Thread(target=self.run_calibration, daemon=True)
        thread.start()
    
    def run_calibration(self):
        try:
            iterations = self.iterations_var.get()
            interval = self.interval_var.get()
            
            self.root.after(0, lambda: self.stats_text.delete(1.0, tk.END))
            
            for i in range(iterations):
                if not self.running:
                    break
                
                # 第一次点击
                start = self.timer.get_time()
                FastClicker.click(100, 100)
                
                # 等待设定时间
                self.timer.sleep(interval)
                
                # 第二次点击
                end = self.timer.get_time()
                FastClicker.click(100, 100)
                
                # 计算误差
                actual = end - start
                error = actual - interval
                
                self.calibration_results.append(error)
                
                # 更新显示
                result_str = f"第{i+1}/{iterations}次：实际={actual*1000:.3f}ms, "
                result_str += f"误差={error*1000:+.3f}ms"
                self.root.after(0, lambda s=result_str: 
                               self.current_label.config(text=s))
                
                # 添加到文本框
                log_str = f"测试{i+1:2d}: 实际={actual*1000:8.3f}ms, "
                log_str += f"误差={error*1000:+8.3f}ms, "
                log_str += f"相对误差={error/interval*100:+7.4f}%\n"
                self.root.after(0, lambda s=log_str: 
                               self.stats_text.insert(tk.END, s))
                
                # 滚动到底部
                self.root.after(0, lambda: self.stats_text.see(tk.END))
                
                # 短暂休息
                time.sleep(0.1)
            
            if self.running:
                self.calculate_statistics()
                
        except Exception as e:
            import traceback
            self.root.after(0, lambda: self.status_label.config(
                text=f"错误：{str(e)}", foreground="red"))
            print(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            if self.running:
                self.root.after(0, lambda: self.status_label.config(
                    text="状态：校准完成", foreground="green"))
            self.running = False
    
    def stop_calibration(self):
        self.running = False
        self.status_label.config(text="已停止", foreground="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def calculate_statistics(self):
        if not self.calibration_results:
            return
        
        import statistics
        
        errors_ms = [e * 1000 for e in self.calibration_results]
        
        mean_error = statistics.mean(errors_ms)
        median_error = statistics.median(errors_ms)
        std_dev = statistics.stdev(errors_ms) if len(errors_ms) > 1 else 0
        min_error = min(errors_ms)
        max_error = max(errors_ms)
        
        stats_str = f"\n{'='*60}\n"
        stats_str += f"统计结果 (共{len(errors_ms)}次测试):\n"
        stats_str += f"{'='*60}\n"
        stats_str += f"平均误差：   {mean_error:+7.3f} ms\n"
        stats_str += f"中位数误差： {median_error:+7.3f} ms\n"
        stats_str += f"标准差：     {std_dev:7.3f} ms\n"
        stats_str += f"最小误差：   {min_error:+7.3f} ms\n"
        stats_str += f"最大误差：   {max_error:+7.3f} ms\n"
        stats_str += f"{'='*60}\n"
        
        self.root.after(0, lambda: self.stats_text.insert(tk.END, stats_str))
        self.root.after(0, lambda: self.stats_text.see(tk.END))
        
        # 给出建议
        interval = self.interval_var.get()
        relative_error = mean_error / (interval * 1000) * 100
        
        advice = ""
        if abs(mean_error) < 0.5:
            advice = f"✓ 精度优秀！系统延迟约 {abs(mean_error):.3f}ms\n"
            advice += f"建议：在 time_perception_trainer.py 中设置:\n"
            advice += f"  CLICK_LATENCY = {abs(mean_error)/1000:.4f}"
        elif abs(mean_error) < 2.0:
            advice = f"✓ 精度良好！系统延迟约 {abs(mean_error):.3f}ms\n"
            advice += f"建议：在 time_perception_trainer.py 中设置:\n"
            advice += f"  CLICK_LATENCY = {abs(mean_error)/1000:.4f}"
        else:
            advice = f"⚠ 延迟较大 ({abs(mean_error):.3f}ms)，建议:\n"
            advice += f"1. 关闭其他程序释放资源\n"
            advice += f"2. 确保电源模式为高性能\n"
            advice += f"3. 更新显卡和主板驱动"
        
        self.root.after(0, lambda: self.advice_label.config(text=advice))
    
    def on_closing(self):
        try:
            del self.timer
        except:
            pass
        self.root.destroy()
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        print("=" * 50)
        print("   ⚙️ 计时器校准工具")
        print("=" * 50)
        print("\n使用说明:")
        print("  1. 设置测试次数和间隔时间")
        print("  2. 点击'开始校准'")
        print("  3. 程序会自动点击并测量误差")
        print("  4. 根据统计结果优化配置")
        print("\n启动中...")
        
        self.root.mainloop()


if __name__ == "__main__":
    app = TimerCalibrator()
    app.run()
