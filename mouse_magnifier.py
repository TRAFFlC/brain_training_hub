import tkinter as tk
import threading
import time
import pyautogui
from PIL import Image, ImageTk, ImageGrab
import os


class MouseMagnifier:
    def __init__(self):
        self.running = False
        self.update_interval = 0.05

        self.magnification = 16
        self.capture_size = 20
        self.canvas_size = self.capture_size * self.magnification

        self.root = tk.Tk()
        self.root.title("鼠标坐标放大镜")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.9)
        self.root.configure(bg="#1e1e1e")

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"380x400+{screen_width-400}+{screen_height-420}")

        self.coord_label = tk.Label(
            self.root,
            text="坐标: (0, 0)",
            font=("Consolas", 14, "bold"),
            bg="#1e1e1e",
            fg="#00ff00"
        )
        self.coord_label.pack(pady=10)

        self.screen_label = tk.Label(
            self.root,
            text="16倍放大预览",
            font=("Arial", 10),
            bg="#1e1e1e",
            fg="#cccccc"
        )
        self.screen_label.pack()

        self.preview_frame = tk.Frame(
            self.root, bg="#000000", bd=2, relief="solid")
        self.preview_frame.pack(pady=5)

        self.canvas = tk.Canvas(
            self.preview_frame,
            width=self.canvas_size,
            height=self.canvas_size,
            bg="#000000",
            highlightthickness=0
        )
        self.canvas.pack()

        self.info_label = tk.Label(
            self.root,
            text="移动鼠标查看坐标和放大区域\nESC 键退出",
            font=("Arial", 9),
            bg="#1e1e1e",
            fg="#888888"
        )
        self.info_label.pack(pady=10)

        self.root.bind("<Escape>", self.on_escape)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.photo = None

    def on_escape(self, event):
        self.stop()

    def on_close(self):
        self.stop()

    def start(self):
        self.running = True
        self.update_loop()
        self.root.mainloop()

    def stop(self):
        self.running = False
        self.root.quit()
        self.root.destroy()

    def update_loop(self):
        if not self.running:
            return

        try:
            x, y = pyautogui.position()

            self.coord_label.config(text=f"坐标: ({x}, {y})")

            screen_width = pyautogui.size().width
            screen_height = pyautogui.size().height

            half_size = self.capture_size // 2

            left = max(0, x - half_size)
            top = max(0, y - half_size)
            right = min(screen_width, x + half_size)
            bottom = min(screen_height, y + half_size)

            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))

            magnified = screenshot.resize(
                (self.canvas_size, self.canvas_size),
                Image.Resampling.NEAREST
            )

            center_x = self.canvas_size // 2
            center_y = self.canvas_size // 2

            cross_size = 20
            draw_image = magnified.copy()
            from PIL import ImageDraw
            draw = ImageDraw.Draw(draw_image)

            draw.line([(center_x - cross_size, center_y), (center_x + cross_size, center_y)],
                      fill="#ff0000", width=2)
            draw.line([(center_x, center_y - cross_size), (center_x, center_y + cross_size)],
                      fill="#ff0000", width=2)

            self.photo = ImageTk.PhotoImage(draw_image)
            self.canvas.delete("all")
            self.canvas.create_image(
                self.canvas_size // 2, self.canvas_size // 2,
                image=self.photo,
                anchor="center"
            )

        except Exception as e:
            print(f"更新错误: {e}")

        if self.running:
            self.root.after(int(self.update_interval * 1000), self.update_loop)


def main():
    app = MouseMagnifier()
    app.start()


if __name__ == "__main__":
    main()
