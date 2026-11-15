#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PNG Alpha 通道提取与恢复工具的中文图形界面。"""

import io
import os
import queue
import subprocess
import sys
import threading
from contextlib import redirect_stdout
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from alpha_extractor import extract_alpha, restore_alpha


IMAGE_TYPES = [
    ("PNG 图片", "*.png"),
    ("常见图片", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"),
    ("所有文件", "*.*"),
]
PNG_TYPE = [("PNG 图片", "*.png"), ("所有文件", "*.*")]


class AlphaToolGUI:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.busy = False
        self.last_output = None

        self.input_var = tk.StringVar()
        self.rgb_output_var = tk.StringVar()
        self.alpha_output_var = tk.StringVar()
        self.restore_rgb_var = tk.StringVar()
        self.restore_alpha_var = tk.StringVar()
        self.final_output_var = tk.StringVar()

        root.title("PNG Alpha 通道提取与恢复工具")
        root.geometry("900x680")
        root.minsize(760, 590)

        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="提取：拆分为完全不透明的 RGB 图和灰度 Alpha 图。恢复：把 Alpha 合并回编辑后的 RGB 图。",
            foreground="#444",
            wraplength=840,
        ).pack(anchor="w", pady=(0, 10))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="x")
        extract_page = ttk.Frame(notebook, padding=12)
        restore_page = ttk.Frame(notebook, padding=12)
        notebook.add(extract_page, text="1．提取 Alpha")
        notebook.add(restore_page, text="2．恢复 Alpha")
        extract_page.columnconfigure(1, weight=1)
        restore_page.columnconfigure(1, weight=1)

        self.add_file_row(
            extract_page, 0, "原始 PNG：", self.input_var, self.pick_extract_input)
        self.add_file_row(
            extract_page, 1, "RGB 输出：", self.rgb_output_var,
            lambda: self.pick_save(self.rgb_output_var, "保存 RGB 图片"))
        self.add_file_row(
            extract_page, 2, "Alpha 输出：", self.alpha_output_var,
            lambda: self.pick_save(self.alpha_output_var, "保存 Alpha 灰度图"))
        ttk.Label(
            extract_page,
            text="默认在原图旁生成“原名_rgb.png”和“原名_alpha.png”。",
            foreground="#666",
        ).grid(row=3, column=1, sticky="w", padx=8, pady=(4, 10))
        self.extract_button = ttk.Button(
            extract_page, text="开始提取 RGB 和 Alpha", command=self.run_extract)
        self.extract_button.grid(row=4, column=1, sticky="w", padx=8)

        self.add_file_row(
            restore_page, 0, "编辑后的 RGB：", self.restore_rgb_var, self.pick_restore_rgb)
        self.add_file_row(
            restore_page, 1, "Alpha 灰度图：", self.restore_alpha_var,
            lambda: self.pick_open(self.restore_alpha_var, "选择 Alpha 灰度图"))
        self.add_file_row(
            restore_page, 2, "最终 PNG 输出：", self.final_output_var,
            lambda: self.pick_save(self.final_output_var, "保存恢复 Alpha 后的图片"))
        ttk.Label(
            restore_page,
            text="如果 RGB 与 Alpha 尺寸不同，会自动缩放 Alpha 以匹配 RGB（与原脚本一致）。",
            foreground="#666",
        ).grid(row=3, column=1, sticky="w", padx=8, pady=(4, 10))
        self.restore_button = ttk.Button(
            restore_page, text="恢复 Alpha 并保存 PNG", command=self.run_restore)
        self.restore_button.grid(row=4, column=1, sticky="w", padx=8)

        self.open_button = ttk.Button(
            outer, text="打开输出目录", command=self.open_folder, state="disabled")
        self.open_button.pack(anchor="w", pady=(12, 0))

        log_box = ttk.LabelFrame(outer, text="处理日志", padding=6)
        log_box.pack(fill="both", expand=True, pady=(8, 0))
        log_box.columnconfigure(0, weight=1)
        log_box.rowconfigure(0, weight=1)
        self.log = tk.Text(log_box, wrap="word", font=("Microsoft YaHei UI", 9))
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)
        self.set_log(
            "使用步骤：\n"
            "1．在“提取 Alpha”页选择原始 PNG，生成 RGB 和 Alpha 两张图片。\n"
            "2．使用绘图软件编辑 RGB 图片，不要覆盖或删除 Alpha 图片。\n"
            "3．在“恢复 Alpha”页选择编辑后的 RGB 和原 Alpha，生成最终 PNG。\n\n"
            "输出文件已存在时，程序会在覆盖前询问。"
        )
        self.root.after(100, self.poll_events)

    def add_file_row(self, parent, row, label, variable, command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(parent, text="浏览…", command=command).grid(
            row=row, column=2, pady=5)

    def pick_open(self, variable, title):
        path = filedialog.askopenfilename(title=title, filetypes=IMAGE_TYPES)
        if path:
            variable.set(path)

    def pick_save(self, variable, title):
        path = filedialog.asksaveasfilename(
            title=title, defaultextension=".png", filetypes=PNG_TYPE)
        if path:
            variable.set(path)

    def pick_extract_input(self):
        path = filedialog.askopenfilename(title="选择原始 PNG", filetypes=IMAGE_TYPES)
        if not path:
            return
        self.input_var.set(path)
        source = Path(path)
        self.rgb_output_var.set(str(source.with_name(source.stem + "_rgb.png")))
        self.alpha_output_var.set(str(source.with_name(source.stem + "_alpha.png")))

    def pick_restore_rgb(self):
        path = filedialog.askopenfilename(title="选择编辑后的 RGB 图片", filetypes=IMAGE_TYPES)
        if not path:
            return
        self.restore_rgb_var.set(path)
        source = Path(path)
        stem = source.stem
        base_stem = stem[:-4] if stem.lower().endswith("_rgb") else stem
        self.restore_alpha_var.set(str(source.with_name(base_stem + "_alpha.png")))
        self.final_output_var.set(str(source.with_name(base_stem + "_final.png")))

    def set_log(self, text):
        self.log.delete("1.0", "end")
        self.log.insert("1.0", text)

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.extract_button.configure(state=state)
        self.restore_button.configure(state=state)

    @staticmethod
    def normalized(path):
        return os.path.normcase(os.path.abspath(str(path)))

    def require_input(self, path, label):
        if not path or not Path(path).is_file():
            raise ValueError("请选择有效的%s文件。" % label)

    def require_png_output(self, path, label):
        if not path:
            raise ValueError("请选择%s的保存位置。" % label)
        if Path(path).suffix.lower() != ".png":
            raise ValueError("%s必须使用 .png 扩展名。" % label)

    def confirm_overwrite(self, paths):
        existing = [Path(path) for path in paths if Path(path).exists()]
        if not existing:
            return True
        names = "\n".join(str(path) for path in existing)
        return messagebox.askyesno(
            "输出文件已存在", "以下文件将被覆盖：\n\n%s\n\n是否继续？" % names,
            parent=self.root)

    def run_extract(self):
        if self.busy:
            return
        try:
            source = self.input_var.get().strip()
            rgb = self.rgb_output_var.get().strip()
            alpha = self.alpha_output_var.get().strip()
            self.require_input(source, "原始图片")
            self.require_png_output(rgb, "RGB 输出")
            self.require_png_output(alpha, "Alpha 输出")
            if self.normalized(rgb) == self.normalized(alpha):
                raise ValueError("RGB 和 Alpha 不能保存为同一个文件。")
            if self.normalized(source) in (self.normalized(rgb), self.normalized(alpha)):
                raise ValueError("为保护原图，输出文件不能覆盖输入图片。")
            if not self.confirm_overwrite((rgb, alpha)):
                return
            Path(rgb).parent.mkdir(parents=True, exist_ok=True)
            Path(alpha).parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法开始提取", str(exc), parent=self.root)
            return

        self.set_busy(True)
        self.set_log("正在提取 RGB 和 Alpha，请稍候……")
        threading.Thread(
            target=self.extract_worker, args=(source, rgb, alpha), daemon=True).start()

    def extract_worker(self, source, rgb, alpha):
        try:
            with redirect_stdout(io.StringIO()):
                extract_alpha(source, rgb, alpha)
        except Exception as exc:
            self.events.put(("error", "提取失败", str(exc)))
            return
        message = "提取完成。\n\nRGB 图片：\n%s\n\nAlpha 灰度图：\n%s" % (rgb, alpha)
        self.events.put(("success", "提取完成", message, rgb))

    def run_restore(self):
        if self.busy:
            return
        try:
            rgb = self.restore_rgb_var.get().strip()
            alpha = self.restore_alpha_var.get().strip()
            output = self.final_output_var.get().strip()
            self.require_input(rgb, "编辑后的 RGB 图片")
            self.require_input(alpha, "Alpha 灰度图")
            self.require_png_output(output, "最终 PNG 输出")
            if self.normalized(output) in (self.normalized(rgb), self.normalized(alpha)):
                raise ValueError("为保护输入图片，最终输出不能覆盖 RGB 或 Alpha 文件。")
            if not self.confirm_overwrite((output,)):
                return
            Path(output).parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法开始恢复", str(exc), parent=self.root)
            return

        self.set_busy(True)
        self.set_log("正在恢复 Alpha，请稍候……")
        threading.Thread(
            target=self.restore_worker, args=(rgb, alpha, output), daemon=True).start()

    def restore_worker(self, rgb, alpha, output):
        try:
            with redirect_stdout(io.StringIO()):
                restore_alpha(rgb, alpha, output)
        except Exception as exc:
            self.events.put(("error", "恢复失败", str(exc)))
            return
        message = "Alpha 已恢复，最终 PNG 已保存：\n%s" % output
        self.events.put(("success", "恢复完成", message, output))

    def poll_events(self):
        try:
            while True:
                kind, title, message, *extra = self.events.get_nowait()
                self.set_busy(False)
                if kind == "error":
                    self.set_log("%s：\n%s" % (title, message))
                    messagebox.showerror(title, message, parent=self.root)
                    continue

                output = extra[0]
                self.last_output = Path(output)
                self.open_button.configure(state="normal")
                self.set_log(message)
                messagebox.showinfo(title, message, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_events)

    def open_folder(self):
        if not self.last_output:
            return
        folder = str(self.last_output.parent)
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except OSError as exc:
            messagebox.showerror("无法打开目录", str(exc), parent=self.root)


def main():
    root = tk.Tk()
    AlphaToolGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
