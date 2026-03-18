"""
脑力训练外挂 - 统一工具面板
整合所有脑力训练小工具的统一界面
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TOOLS_CONFIG = [
    # 视觉训练
    {
        'id': 'schulte',
        'name': '🔢 舒尔特方格',
        'description': '舒尔特表自动通关\n支持 3x3 到 9x9\n模板匹配识别',
        'script': 'schulte_v2.py',
        'icon': '🎯',
        'category': '视觉训练'
    },
    {
        'id': 'schulte_ocr',
        'name': '📸 舒尔特方格-OCR',
        'description': 'RapidOCR 识别\n无需模板\n适应性强',
        'script': 'schulte_ocr.py',
        'icon': '📷',
        'category': '视觉训练'
    },
    {
        'id': 'find_char',
        'name': '🔤 找不同的字',
        'description': '10x10 网格找字\npHash 图像匹配\n右上角找目标字',
        'script': 'find_different_char.py',
        'icon': '🔍',
        'category': '视觉训练'
    },
    {
        'id': 'find_char_brute',
        'name': '🔨 找不同的字 - 暴力',
        'description': '暴力点击所有格子\n无需识别目标字\n循环点击 100 格',
        'script': 'find_different_char_brute.py',
        'icon': '⚒️',
        'category': '视觉训练'
    },
    # 记忆训练
    {
        'id': 'memory',
        'name': '🧠 数字记忆',
        'description': '数字顺序记忆训练\n点击 1 后隐藏\n按顺序点击剩余数字',
        'script': 'memory_training.py',
        'icon': '🔢',
        'category': '记忆训练'
    },
    {
        'id': 'sequence',
        'name': '🔲 顺序记忆',
        'description': '3x3 方块顺序记忆\n方块按顺序亮起\n按相同顺序点击',
        'script': 'sequence_memory.py',
        'icon': '🔳',
        'category': '记忆训练'
    },
    {
        'id': 'nback',
        'name': '🎴 N-Back 记忆',
        'description': 'N-Back 记忆力训练\n1-Back 到 8-Back 难度\n图片匹配训练',
        'script': 'nback_training.py',
        'icon': '🧩',
        'category': '记忆训练'
    },
    # 感知训练
    {
        'id': 'color_diff',
        'name': '🎨 色差感知',
        'description': '3x3 方格找不同\n8 个颜色相同\n1 个颜色不同',
        'script': 'color_diff_game.py',
        'icon': '🎯',
        'category': '感知训练'
    },
    {
        'id': 'dynamic_color',
        'name': '🌈 动态色差感知',
        'description': '动态颜色块找不同\n智能识别颜色差异\n自动定位点击',
        'script': 'dynamic_color_diff.py',
        'icon': '🌟',
        'category': '感知训练'
    },
    {
        'id': 'time',
        'name': '⏱️ 时间感知',
        'description': '时间感知训练\n精确时间间隔点击\n精度<0.01 秒',
        'script': 'time_perception_trainer.py',
        'icon': '⏱️',
        'category': '感知训练'
    },
    # 反应训练
    {
        'id': 'reaction',
        'name': '⚡ 反应速度',
        'description': '反应速度测试\n像素级检测\n目标冲进前 100',
        'script': 'reaction_speed_leaderboard.py',
        'icon': '⚡',
        'category': '反应训练'
    },
    {
        'id': 'reaction_afk',
        'name': '🤖 反应速度-挂机',
        'description': '自动循环点击\n挂机刷极限成绩\n简单粗暴有效',
        'script': 'reaction_afk_farm.py',
        'icon': '🤖',
        'category': '反应训练'
    },
    {
        'id': 'click_speed',
        'name': '🖱 点击速度测试',
        'description': '点击速度测试\n支持左键/右键/空格键\n可调节 CPS 速度',
        'script': 'click_speed_automation.py',
        'icon': '🖱',
        'category': '反应训练'
    },
    # 认知训练
    {
        'id': 'stroop',
        'name': '🎭 斯特鲁普效应',
        'description': '文字颜色与含义判断\n认知灵活性训练',
        'script': 'stroop_training.py',
        'icon': '🎭',
        'category': '认知训练'
    },
    # 辅助工具
    {
        'id': 'mouse',
        'name': '🔍 鼠标放大镜',
        'description': '16 倍放大预览\n实时坐标显示\n精细定位辅助',
        'script': 'mouse_magnifier.py',
        'icon': '🔍',
        'category': '辅助工具'
    }
]


class ToolLauncher:
    """工具启动器"""

    def __init__(self, script_name):
        self.script_name = script_name
        self.process = None
        self.running = False

    def start(self):
        """启动工具"""
        if self.running:
            return False

        try:
            script_path = os.path.join(BASE_DIR, self.script_name)
            if not os.path.exists(script_path):
                messagebox.showerror(
                    "错误",
                    f"找不到脚本文件:\n{script_path}"
                )
                return False

            self.process = subprocess.Popen(
                ['python', script_path],
                cwd=BASE_DIR,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            self.running = True
            return True
        except Exception as e:
            messagebox.showerror("启动错误", f"无法启动工具:\n{str(e)}")
            return False

    def stop(self):
        """停止工具"""
        if self.process and self.running:
            try:
                self.process.terminate()
                self.running = False
            except:
                pass


class BrainTrainingHub:
    """脑力训练中心"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🧠 脑力训练外挂 - 统一工具面板")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        self.running_tools = {}

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        """设置界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        title = ttk.Label(
            title_frame,
            text="🧠 脑力训练外挂",
            font=('Microsoft YaHei UI', 24, 'bold')
        )
        title.pack(side=tk.LEFT)

        subtitle = ttk.Label(
            title_frame,
            text="统一工具面板 - 点击工具图标启动",
            font=('Microsoft YaHei UI', 10)
        )
        subtitle.pack(side=tk.LEFT, padx=(20, 0), pady=(8, 0))

        self.status_label = ttk.Label(
            title_frame,
            text="就绪",
            font=('Microsoft YaHei UI', 10),
            foreground='green'
        )
        self.status_label.pack(side=tk.RIGHT, padx=(0, 10), pady=(8, 0))

        # 分类标签页
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # 按分类创建标签页
        categories = {}
        for tool in TOOLS_CONFIG:
            cat = tool['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(tool)

        self.tool_frames = {}

        for cat_name, tools in categories.items():
            tab_frame = ttk.Frame(notebook, padding="10")
            notebook.add(tab_frame, text=cat_name)

            # 工具网格布局
            row = 0
            col = 0
            max_cols = 2

            for tool in tools:
                tool_frame = self.create_tool_card(tab_frame, tool)
                tool_frame.grid(row=row, column=col, padx=10,
                                pady=10, sticky='nw')

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            # 配置网格权重
            for i in range(max_cols):
                tab_frame.columnconfigure(i, weight=1)
            tab_frame.rowconfigure(row, weight=1)

        # 底部状态栏
        status_frame = ttk.LabelFrame(main_frame, text="运行状态", padding="10")
        status_frame.pack(fill=tk.X, pady=(10, 0))

        self.running_label = ttk.Label(
            status_frame,
            text="当前运行工具：无",
            font=('Microsoft YaHei UI', 10)
        )
        self.running_label.pack(side=tk.LEFT)

        ttk.Button(
            status_frame,
            text="停止所有工具",
            command=self.stop_all_tools
        ).pack(side=tk.RIGHT)

        # 说明信息
        info_frame = ttk.LabelFrame(main_frame, text="使用说明", padding="10")
        info_frame.pack(fill=tk.X, pady=(10, 0))

        info_text = tk.Text(
            info_frame,
            height=4,
            font=('Microsoft YaHei UI', 9),
            wrap=tk.WORD,
            bg='#f5f5f5'
        )
        info_text.pack(fill=tk.X)
        info_text.insert('1.0',
                         '1. 点击工具卡片上的"启动"按钮即可打开对应工具\n'
                         '2. 每个工具都是独立窗口，可以同时运行多个工具\n'
                         '3. 工具窗口会显示在最上层，方便使用\n'
                         '4. 点击"停止所有工具"可以关闭所有已启动的工具\n'
                         '5. 部分工具需要设置屏幕区域（快捷键 F9/F10 等）')
        info_text.config(state='disabled')

    def create_tool_card(self, parent, tool_info):
        """创建工具卡片"""
        card = ttk.LabelFrame(
            parent,
            text=tool_info['name'],
            padding="15"
        )

        # 图标和名称
        icon_label = ttk.Label(
            card,
            text=tool_info['icon'],
            font=('Segoe UI Emoji', 32)
        )
        icon_label.pack(pady=(5, 10))

        # 描述
        desc_label = ttk.Label(
            card,
            text=tool_info['description'],
            font=('Microsoft YaHei UI', 9),
            foreground='gray',
            justify='center'
        )
        desc_label.pack(pady=(0, 10))

        # 启动按钮
        btn = ttk.Button(
            card,
            text="🚀 启动工具",
            command=lambda t=tool_info: self.launch_tool(t)
        )
        btn.pack(fill=tk.X, pady=5)

        # 状态标签
        status = ttk.Label(
            card,
            text="未运行",
            font=('Microsoft YaHei UI', 8),
            foreground='gray'
        )
        status.pack(pady=(5, 0))

        # 存储引用
        tool_id = tool_info['id']
        self.tool_frames[tool_id] = {
            'card': card,
            'button': btn,
            'status': status,
            'info': tool_info
        }

        return card

    def launch_tool(self, tool_info):
        """启动工具"""
        tool_id = tool_info['id']
        script_name = tool_info['script']

        if tool_id in self.running_tools and self.running_tools[tool_id].running:
            messagebox.showinfo(
                "提示",
                f"{tool_info['name']} 已经在运行中！"
            )
            return

        self.status_label.config(
            text=f"正在启动 {tool_info['name']}...",
            foreground='blue'
        )
        self.root.update()

        launcher = ToolLauncher(script_name)
        if launcher.start():
            self.running_tools[tool_id] = launcher
            self.update_tool_status(tool_id, True)
            self.status_label.config(
                text=f"✓ {tool_info['name']} 已启动",
                foreground='green'
            )
            self.update_running_label()
        else:
            self.status_label.config(
                text="启动失败",
                foreground='red'
            )

    def stop_tool(self, tool_id):
        """停止工具"""
        if tool_id in self.running_tools:
            self.running_tools[tool_id].stop()
            self.update_tool_status(tool_id, False)
            del self.running_tools[tool_id]
            self.update_running_label()

    def stop_all_tools(self):
        """停止所有工具"""
        if not self.running_tools:
            messagebox.showinfo("提示", "当前没有运行任何工具")
            return

        for tool_id in list(self.running_tools.keys()):
            self.stop_tool(tool_id)

        self.status_label.config(
            text="已停止所有工具",
            foreground='green'
        )
        messagebox.showinfo("完成", "所有工具已停止")

    def update_tool_status(self, tool_id, is_running):
        """更新工具状态显示"""
        if tool_id not in self.tool_frames:
            return

        frame = self.tool_frames[tool_id]
        if is_running:
            frame['status'].config(
                text="● 运行中",
                foreground='green'
            )
            frame['button'].config(
                text="● 运行中",
                state='disabled'
            )
        else:
            frame['status'].config(
                text="○ 未运行",
                foreground='gray'
            )
            frame['button'].config(
                text="🚀 启动工具",
                state='normal'
            )

    def update_running_label(self):
        """更新运行状态标签"""
        if not self.running_tools:
            self.running_label.config(
                text="当前运行工具：无",
                foreground='gray'
            )
        else:
            tool_names = [
                self.tool_frames[tid]['info']['name']
                for tid in self.running_tools.keys()
            ]
            self.running_label.config(
                text=f"当前运行工具：{', '.join(tool_names)}",
                foreground='green'
            )

    def load_settings(self):
        """加载设置"""
        # 可以在这里加载用户偏好设置
        pass

    def save_settings(self):
        """保存设置"""
        # 可以在这里保存用户偏好设置
        pass

    def on_closing(self):
        """关闭窗口处理"""
        if self.running_tools:
            if messagebox.askyesno("确认", "有工具正在运行，确定要退出吗？"):
                self.stop_all_tools()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        """运行主程序"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


def main():
    """主函数"""
    print("=" * 60)
    print("   🧠 脑力训练外挂 - 统一工具面板")
    print("=" * 60)
    print("\n启动中...")
    print("\n功能说明:")
    print("  - 集成 15 个脑力训练工具")
    print("  - 一键启动任意工具")
    print("  - 统一管理所有工具状态")
    print("  - 5 大分类：视觉/记忆/感知/反应/认知")
    print("\n工具列表:")
    for tool in TOOLS_CONFIG:
        print(
            f"  {tool['icon']} {tool['name']}: {tool['description'].split(chr(10))[0]}")
    print("\n" + "=" * 60)

    app = BrainTrainingHub()
    app.run()


if __name__ == "__main__":
    main()
