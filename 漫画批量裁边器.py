# 漫画批量裁边器.py
# 正式版 v3.4 | 优化UI细节

import sys
import os
import zipfile
import tempfile
import shutil
import threading
from pathlib import Path
from PIL import Image, ImageChops
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ============================================
# 版本信息
# ============================================

APP_NAME = "漫画批量裁边器"
APP_VERSION = "3.4"
APP_ICON = "📐"

# ============================================
# 配色方案
# ============================================

COLORS = {
    "bg": "#f0f2f5",
    "card": "#ffffff",
    "primary": "#5B7DF5",
    "primary_dark": "#4A6CF7",
    "primary_active": "#3D5FD4",
    "primary_light": "#EEF1FE",
    "success": "#2ECC71",
    "danger": "#EF5350",
    "danger_dark": "#D32F2F",
    "warning": "#F39C12",
    "text": "#2C3E50",
    "text_light": "#95A5A6",
    "border": "#E8ECF1",
    "shadow": "#D5D8DC",
    "white": "#FFFFFF",
    "hover": "#F5F7FA",
}

# ============================================
# Kindle 设备分辨率预设
# ============================================

KINDLE_PRESETS = {
    "Kindle (入门版)": {"width": 600, "height": 800},
    "Kindle 青春版 (2022)": {"width": 1072, "height": 1448},
    "Kindle Paperwhite (第1代)": {"width": 768, "height": 1024},
    "Kindle Paperwhite 2/3/4/5": {"width": 1072, "height": 1448},
    "Kindle Paperwhite 5 (6.8英寸)": {"width": 1236, "height": 1648},
    "Kindle Oasis (第1代)": {"width": 1072, "height": 1448},
    "Kindle Oasis (第2/3代, 7英寸)": {"width": 1264, "height": 1680},
    "Kindle DX / DXG": {"width": 824, "height": 1200},
    "Kindle Scribe (第1代)": {"width": 1860, "height": 2480},
    "Kindle Scribe (第3代, 11英寸)": {"width": 1986, "height": 2648},
    "Kindle Colorsoft": {"width": 1072, "height": 1448},
    "自定义": {"width": 0, "height": 0},
}

# ============================================
# 核心算法
# ============================================

def find_black_border(img_path, black_threshold=80):
    try:
        img = Image.open(img_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        data = np.array(img)
        h, w, _ = data.shape
        gray = data.mean(axis=2)
        top = h
        for y in range(h):
            if np.any(gray[y, :] < black_threshold):
                top = y
                break
        bottom = 0
        for y in range(h-1, -1, -1):
            if np.any(gray[y, :] < black_threshold):
                bottom = y
                break
        left = w
        for x in range(w):
            if np.any(gray[:, x] < black_threshold):
                left = x
                break
        right = 0
        for x in range(w-1, -1, -1):
            if np.any(gray[:, x] < black_threshold):
                right = x
                break
        if top >= bottom or left >= right:
            return None
        return (left, top, right, bottom)
    except:
        return None

def find_white_border(img_path, white_threshold=235):
    try:
        img = Image.open(img_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        data = np.array(img)
        h, w, _ = data.shape
        gray = data.mean(axis=2)
        top = h
        for y in range(h):
            if np.any(gray[y, :] < white_threshold):
                top = y
                break
        bottom = 0
        for y in range(h-1, -1, -1):
            if np.any(gray[y, :] < white_threshold):
                bottom = y
                break
        left = w
        for x in range(w):
            if np.any(gray[:, x] < white_threshold):
                left = x
                break
        right = 0
        for x in range(w-1, -1, -1):
            if np.any(gray[:, x] < white_threshold):
                right = x
                break
        if top >= bottom or left >= right:
            return None
        return (left, top, right, bottom)
    except:
        return None

def crop_to_border(img_path, black_threshold=80, white_threshold=235, margins=None):
    if margins is None:
        margins = {'left': 2, 'right': 2, 'top': 2, 'bottom': 2}
    bbox = find_black_border(img_path, black_threshold)
    if bbox is None:
        bbox = find_white_border(img_path, white_threshold)
    if bbox is None:
        return False
    left, top, right, bottom = bbox
    img = Image.open(img_path)
    w, h = img.size
    left = max(0, left - margins['left'])
    top = max(0, top - margins['top'])
    right = min(w, right + margins['right'])
    bottom = min(h, bottom + margins['bottom'])
    cropped = img.crop((left, top, right, bottom))
    cropped.save(img_path, quality=92)
    return True

def resize_to_target(img_path, target_width, target_height):
    try:
        img = Image.open(img_path)
        orig_w, orig_h = img.size
        scale = min(target_width / orig_w, target_height / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        if new_w == target_width and new_h == target_height:
            return True
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (target_width, target_height), (255, 255, 255))
        x_offset = (target_width - new_w) // 2
        y_offset = (target_height - new_h) // 2
        canvas.paste(img_resized, (x_offset, y_offset))
        canvas.save(img_path, quality=92)
        return True
    except:
        return False

def scan_epub_files(folder_path):
    folder_path = Path(folder_path)
    epub_files = []
    for epub in folder_path.rglob('*.epub'):
        epub_files.append(str(epub))
    return epub_files

# ============================================
# 自定义按钮
# ============================================

class FlatButton(tk.Button):
    def __init__(self, master, **kwargs):
        self.bg_color = kwargs.pop('bg', COLORS["primary"])
        self.fg_color = kwargs.pop('fg', COLORS["white"])
        self.hover_color = kwargs.pop('hover', COLORS["primary_dark"])
        self.active_color = kwargs.pop('active', COLORS["primary_active"])
        
        super().__init__(master, **kwargs)
        self.configure(
            bg=self.bg_color, fg=self.fg_color,
            relief='flat', borderwidth=0, highlightthickness=0,
            padx=16, pady=8, cursor='hand2',
            font=('Microsoft YaHei', 10, 'bold'),
            activebackground=self.bg_color, activeforeground=self.fg_color,
            disabledforeground='#B0B0B0',
        )
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
        self.bind('<Button-1>', self.on_press)
        self.bind('<ButtonRelease-1>', self.on_release)
    
    def on_enter(self, e):
        if self['state'] != 'disabled':
            self.configure(bg=self.hover_color)
    def on_leave(self, e):
        if self['state'] != 'disabled':
            self.configure(bg=self.bg_color)
    def on_press(self, e):
        if self['state'] != 'disabled':
            self.configure(bg=self.active_color)
    def on_release(self, e):
        if self['state'] != 'disabled':
            self.configure(bg=self.hover_color)

class DangerButton(FlatButton):
    def __init__(self, master, **kwargs):
        kwargs['bg'] = COLORS["danger"]
        kwargs['hover'] = COLORS["danger_dark"]
        kwargs['active'] = COLORS["danger_dark"]
        super().__init__(master, **kwargs)

# ============================================
# 美化版控件
# ============================================

class ModernCombobox(ttk.Combobox):
    """图一风格下拉框"""
    def __init__(self, master, **kwargs):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Modern.TCombobox',
                       fieldbackground=COLORS["white"],
                       background=COLORS["white"],
                       foreground=COLORS["text"],
                       borderwidth=1,
                       relief='solid',
                       padding=(8, 6),
                       font=('Microsoft YaHei', 10),
                       arrowcolor=COLORS["primary"])
        style.map('Modern.TCombobox',
                 fieldbackground=[('readonly', COLORS["white"])],
                 background=[('readonly', COLORS["white"])],
                 bordercolor=[('focus', COLORS["primary"])])
        kwargs['style'] = 'Modern.TCombobox'
        super().__init__(master, **kwargs)

class ModernSpinbox(tk.Spinbox):
    """美化版Spinbox"""
    def __init__(self, master, **kwargs):
        kwargs.setdefault('font', ('Microsoft YaHei', 10))
        kwargs.setdefault('relief', 'solid')
        kwargs.setdefault('borderwidth', 1)
        kwargs.setdefault('bg', COLORS["white"])
        kwargs.setdefault('fg', COLORS["text"])
        kwargs.setdefault('buttonbackground', COLORS["white"])
        kwargs.setdefault('activebackground', COLORS["primary_light"])
        kwargs.setdefault('readonlybackground', COLORS["white"])
        kwargs.setdefault('highlightthickness', 1)
        kwargs.setdefault('highlightcolor', COLORS["primary"])
        kwargs.setdefault('highlightbackground', COLORS["border"])
        super().__init__(master, **kwargs)
        self.config(selectbackground=COLORS["primary_light"], selectforeground=COLORS["text"])

# ============================================
# 处理类
# ============================================

class CropWorker:
    def __init__(self, file_list, output_dir, black_threshold, white_threshold, margins, 
                 target_width, target_height, log_callback, progress_callback, done_callback):
        self.file_list = file_list
        self.output_dir = output_dir
        self.black_threshold = black_threshold
        self.white_threshold = white_threshold
        self.margins = margins
        self.target_width = target_width
        self.target_height = target_height
        self.log = log_callback
        self.progress = progress_callback
        self.done = done_callback
        self.is_running = True
        self.total_files = len(file_list)
        self.current_file = 0

    def stop(self):
        self.is_running = False

    def process_epub(self, epub_path, output_path):
        self.log(f"📖 处理: {epub_path.name}")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            try:
                with zipfile.ZipFile(epub_path, 'r') as z:
                    z.extractall(temp_path)
            except Exception as e:
                self.log(f"  ❌ 解压失败: {e}")
                return False
            img_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
            img_files = []
            for ext in img_exts:
                img_files.extend(temp_path.rglob(f'*{ext}'))
            if not img_files:
                self.log(f"  ⚠️ 没有找到图片")
                return False
            img_files = sorted(img_files)
            self.log(f"  找到 {len(img_files)} 张图片")
            success_crop = 0
            success_resize = 0
            total = len(img_files)
            for i, img in enumerate(img_files, 1):
                if not self.is_running:
                    return False
                if crop_to_border(img, self.black_threshold, self.white_threshold, self.margins):
                    success_crop += 1
                if resize_to_target(img, self.target_width, self.target_height):
                    success_resize += 1
                sub_progress = int((i / total) * 100)
                overall_progress = self.current_file / self.total_files * 100 + (sub_progress / self.total_files)
                self.progress(int(overall_progress), f"{self.current_file}/{self.total_files} - {img.name}")
            self.log(f"  ✅ 裁切 {success_crop}/{total} 张, 缩放 {success_resize}/{total} 张")
            try:
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
                    for f in temp_path.rglob('*'):
                        if f.is_file():
                            z.write(f, f.relative_to(temp_path))
            except Exception as e:
                self.log(f"  ❌ 打包失败: {e}")
                return False
        return True

    def process_folder(self, folder_path, output_dir):
        self.log(f"📁 处理文件夹: {folder_path.name}")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        img_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
        img_files = []
        for ext in img_exts:
            img_files.extend(Path(folder_path).rglob(f'*{ext}'))
        if not img_files:
            self.log(f"  ⚠️ 没有找到图片")
            return False
        img_files = sorted(img_files)
        self.log(f"  找到 {len(img_files)} 张图片")
        success_crop = 0
        success_resize = 0
        total = len(img_files)
        for i, img in enumerate(img_files, 1):
            if not self.is_running:
                return False
            if crop_to_border(img, self.black_threshold, self.white_threshold, self.margins):
                success_crop += 1
            if resize_to_target(img, self.target_width, self.target_height):
                dest = output_dir / img.name
                shutil.copy2(img, dest)
                success_resize += 1
            sub_progress = int((i / total) * 100)
            overall_progress = self.current_file / self.total_files * 100 + (sub_progress / self.total_files)
            self.progress(int(overall_progress), f"{self.current_file}/{self.total_files} - {img.name}")
        self.log(f"  ✅ 裁切 {success_crop}/{total} 张, 缩放 {success_resize}/{total} 张")
        return True

    def run(self):
        self.log(f"📋 共 {self.total_files} 个文件/文件夹待处理")
        self.log(f"📁 输出目录: {self.output_dir}")
        self.log(f"🖥️  目标分辨率: {self.target_width} x {self.target_height}")
        self.log("=" * 50)
        output_dir = Path(self.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        success_count = 0
        for idx, item in enumerate(self.file_list, 1):
            if not self.is_running:
                self.done(False, "已取消")
                return
            self.current_file = idx
            item_path = Path(item)
            if not item_path.exists():
                self.log(f"⚠️ 跳过: {item_path.name} (不存在)")
                continue
            if item_path.is_file() and item_path.suffix.lower() == '.epub':
                output_path = output_dir / f"{item_path.stem}_裁切版.epub"
                result = self.process_epub(item_path, output_path)
            elif item_path.is_dir():
                output_path = output_dir / f"{item_path.name}_裁切版"
                result = self.process_folder(item_path, output_path)
            else:
                self.log(f"⚠️ 跳过: {item_path.name} (不支持的类型)")
                continue
            if result:
                success_count += 1
                self.log(f"✅ 完成: {output_path.name}")
            else:
                self.log(f"❌ 失败: {item_path.name}")
            self.log("-" * 30)
        self.done(True, f"完成！成功处理 {success_count}/{self.total_files} 个")

# ============================================
# 主窗口
# ============================================

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_ICON} {APP_NAME} v{APP_VERSION}")
        
        WINDOW_WIDTH = 780
        WINDOW_HEIGHT = 880
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.root.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg"])
        
        self.worker = None
        self.file_list = []
        self.count_label = None
        
        self.setup_ui()
        
    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg=COLORS["bg"], padx=20, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ---- 头部 ----
        header_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        header_frame.pack(fill=tk.X, pady=(0, 12))
        
        title_label = tk.Label(header_frame,
                              text=f"{APP_ICON} {APP_NAME}",
                              font=('Microsoft YaHei', 22, 'bold'),
                              bg=COLORS["bg"], fg=COLORS["primary"])
        title_label.pack(side=tk.LEFT)
        
        version_label = tk.Label(header_frame,
                                text=f"v{APP_VERSION}",
                                font=('Microsoft YaHei', 10),
                                bg=COLORS["bg"], fg=COLORS["text_light"])
        version_label.pack(side=tk.LEFT, padx=(8, 0), pady=(4, 0))
        
        subtitle_label = tk.Label(header_frame,
                                 text="智能裁切 · 适配 Kindle 分辨率",
                                 font=('Microsoft YaHei', 10),
                                 bg=COLORS["bg"], fg=COLORS["text_light"])
        subtitle_label.pack(anchor='w', pady=(2, 0))
        
        sep = tk.Frame(main_frame, bg=COLORS["border"], height=1)
        sep.pack(fill=tk.X, pady=(0, 12))
        
        # ---- 内容区域 ----
        content_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        left_col = tk.Frame(content_frame, bg=COLORS["bg"])
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        right_col = tk.Frame(content_frame, bg=COLORS["bg"], width=360)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        right_col.pack_propagate(False)
        
        # ============================================================
        # 左列：文件列表
        # ============================================================
        list_card = tk.Frame(left_col, bg=COLORS["card"], relief='flat')
        list_card.pack(fill=tk.BOTH, expand=True)
        
        list_inner = tk.Frame(list_card, bg=COLORS["card"], padx=14, pady=14)
        list_inner.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(list_inner, text="📋 待处理文件",
                font=('Microsoft YaHei', 11, 'bold'),
                bg=COLORS["card"], fg=COLORS["text"]).pack(anchor='w', pady=(0, 8))
        
        list_bg = tk.Frame(list_inner, bg=COLORS["white"], highlightthickness=1, highlightcolor=COLORS["border"])
        list_bg.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_bg)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(list_bg, yscrollcommand=scrollbar.set,
                                  font=('Microsoft YaHei', 10),
                                  selectmode=tk.EXTENDED,
                                  bg=COLORS["white"],
                                  fg=COLORS["text"],
                                  selectbackground=COLORS["primary"],
                                  selectforeground=COLORS["white"],
                                  relief='flat',
                                  borderwidth=0,
                                  highlightthickness=0,
                                  height=9)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        btn_row = tk.Frame(list_inner, bg=COLORS["card"])
        btn_row.pack(fill=tk.X, pady=(8, 0))
        
        small_btn = {'font': ('Microsoft YaHei', 9), 'bg': COLORS["primary_light"],
                    'fg': COLORS["primary"], 'relief': 'flat', 'padx': 10, 'pady': 4,
                    'cursor': 'hand2', 'activebackground': COLORS["primary_light"],
                    'activeforeground': COLORS["primary_dark"], 'borderwidth': 0}
        
        tk.Button(btn_row, text="添加 EPUB", command=self.add_files, **small_btn).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="添加文件夹", command=self.add_folder_with_epub, **small_btn).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="添加图片", command=self.add_image_folder, **small_btn).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="移除选中", command=self.remove_selected, **small_btn).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="清空列表", command=self.clear_list, **small_btn).pack(side=tk.LEFT, padx=2)
        
        # ============================================================
        # 右列：参数卡片
        # ============================================================
        
        # ---- 裁切参数（带恢复默认按钮） ----
        param_card = tk.Frame(right_col, bg=COLORS["card"], relief='flat')
        param_card.pack(fill=tk.X, pady=(0, 6))
        
        param_inner = tk.Frame(param_card, bg=COLORS["card"], padx=14, pady=12)
        param_inner.pack(fill=tk.X)
        
        # 标题栏（含恢复默认按钮）
        title_row = tk.Frame(param_inner, bg=COLORS["card"])
        title_row.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(title_row, text="⚙️ 裁切参数",
                font=('Microsoft YaHei', 11, 'bold'),
                bg=COLORS["card"], fg=COLORS["text"]).pack(side=tk.LEFT)
        
        # 恢复默认按钮（右上角）
        reset_btn = tk.Button(title_row, text="恢复默认",
                             font=('Microsoft YaHei', 9),
                             bg=COLORS["primary_light"], fg=COLORS["primary"],
                             relief='flat', padx=10, pady=2,
                             cursor='hand2', activebackground=COLORS["border"],
                             command=self.reset_defaults)
        reset_btn.pack(side=tk.RIGHT)
        
        # 黑框阈值
        grid = tk.Frame(param_inner, bg=COLORS["card"])
        grid.pack(fill=tk.X, pady=(0, 6))
        
        tk.Label(grid, text="黑框阈值", font=('Microsoft YaHei', 9),
                bg=COLORS["card"], fg=COLORS["text"]).grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.black_threshold_var = tk.IntVar(value=80)
        ModernSpinbox(grid, from_=30, to=150, width=7,
                     textvariable=self.black_threshold_var).grid(row=0, column=1, sticky='w')
        tk.Label(grid, text="值越小越严格", font=('Microsoft YaHei', 8),
                bg=COLORS["card"], fg=COLORS["text_light"]).grid(row=1, column=0, columnspan=2, sticky='w', padx=(0, 8))
        
        # 白边阈值
        grid2 = tk.Frame(param_inner, bg=COLORS["card"])
        grid2.pack(fill=tk.X, pady=(0, 6))
        
        tk.Label(grid2, text="白边阈值", font=('Microsoft YaHei', 9),
                bg=COLORS["card"], fg=COLORS["text"]).grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.white_threshold_var = tk.IntVar(value=235)
        ModernSpinbox(grid2, from_=200, to=250, width=7,
                     textvariable=self.white_threshold_var).grid(row=0, column=1, sticky='w')
        tk.Label(grid2, text="值越大越宽松", font=('Microsoft YaHei', 8),
                bg=COLORS["card"], fg=COLORS["text_light"]).grid(row=1, column=0, columnspan=2, sticky='w', padx=(0, 8))
        
        # 保留留白（分两行：左右一行，上下一行）
        grid3 = tk.Frame(param_inner, bg=COLORS["card"])
        grid3.pack(fill=tk.X, pady=(0, 2))
        
        tk.Label(grid3, text="保留留白 (px)", font=('Microsoft YaHei', 9),
                bg=COLORS["card"], fg=COLORS["text"]).grid(row=0, column=0, sticky='w', padx=(0, 8))
        
        # 第一行：左、右
        row1 = tk.Frame(grid3, bg=COLORS["card"])
        row1.grid(row=0, column=1, sticky='w')
        
        for label, var in [("左", "margin_left"), ("右", "margin_right")]:
            setattr(self, var, tk.IntVar(value=2))
            tk.Label(row1, text=label, font=('Microsoft YaHei', 9),
                    bg=COLORS["card"], fg=COLORS["text"]).pack(side=tk.LEFT, padx=(0, 2))
            ModernSpinbox(row1, from_=0, to=50, width=4,
                         textvariable=getattr(self, var)).pack(side=tk.LEFT, padx=(0, 12))
        
        # 第二行：上、下
        row2 = tk.Frame(grid3, bg=COLORS["card"])
        row2.grid(row=1, column=1, sticky='w', pady=(4, 0))
        
        for label, var in [("上", "margin_top"), ("下", "margin_bottom")]:
            setattr(self, var, tk.IntVar(value=2))
            tk.Label(row2, text=label, font=('Microsoft YaHei', 9),
                    bg=COLORS["card"], fg=COLORS["text"]).pack(side=tk.LEFT, padx=(0, 2))
            ModernSpinbox(row2, from_=0, to=50, width=4,
                         textvariable=getattr(self, var)).pack(side=tk.LEFT, padx=(0, 12))
        
        # ---- 目标设备 ----
        device_card = tk.Frame(right_col, bg=COLORS["card"], relief='flat')
        device_card.pack(fill=tk.X, pady=(0, 6))

        device_inner = tk.Frame(device_card, bg=COLORS["card"], padx=14, pady=12)
        device_inner.pack(fill=tk.X)

        tk.Label(device_inner, text="🖥️ 目标设备",
                font=('Microsoft YaHei', 11, 'bold'),
                bg=COLORS["card"], fg=COLORS["text"]).pack(anchor='w', pady=(0, 10))

        dev_grid = tk.Frame(device_inner, bg=COLORS["card"])
        dev_grid.pack(fill=tk.X, expand=True)  # 允许扩展

        # 设置列权重，让下拉框所在的列可以伸缩
        dev_grid.columnconfigure(1, weight=1)

        tk.Label(dev_grid, text="设备型号", font=('Microsoft YaHei', 9),
                bg=COLORS["card"], fg=COLORS["text"]).grid(row=0, column=0, sticky='w', padx=(0, 8))

        self.device_var = tk.StringVar(value="Kindle Paperwhite 2/3/4/5")
        self.device_combo = ModernCombobox(dev_grid, textvariable=self.device_var,
                                        values=list(KINDLE_PRESETS.keys()))
        self.device_combo.grid(row=0, column=1, columnspan=2, sticky='ew', padx=(0, 0))
        self.device_combo.bind('<<ComboboxSelected>>', self.on_device_selected)

        # 分辨率输入
        res_frame = tk.Frame(dev_grid, bg=COLORS["card"])
        res_frame.grid(row=1, column=0, columnspan=3, sticky='w', pady=(6, 0))

        tk.Label(res_frame, text="宽", font=('Microsoft YaHei', 9),
                bg=COLORS["card"], fg=COLORS["text"]).pack(side=tk.LEFT, padx=(0, 4))
        self.target_width_var = tk.IntVar(value=1072)
        ModernSpinbox(res_frame, from_=100, to=5000, width=7,
                    textvariable=self.target_width_var).pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(res_frame, text="高", font=('Microsoft YaHei', 9),
                bg=COLORS["card"], fg=COLORS["text"]).pack(side=tk.LEFT, padx=(0, 4))
        self.target_height_var = tk.IntVar(value=1448)
        ModernSpinbox(res_frame, from_=100, to=5000, width=7,
                    textvariable=self.target_height_var).pack(side=tk.LEFT)

        tip = "等比例缩放 · 完整显示 · 居中留白"
        tk.Label(device_inner, text=tip, font=('Microsoft YaHei', 8),
                bg=COLORS["card"], fg=COLORS["text_light"]).pack(anchor='w', pady=(6, 0))
                
        # ---- 输出目录 ----
        output_card = tk.Frame(right_col, bg=COLORS["card"], relief='flat')
        output_card.pack(fill=tk.X, pady=(0, 6))
        
        output_inner = tk.Frame(output_card, bg=COLORS["card"], padx=14, pady=12)
        output_inner.pack(fill=tk.X)
        
        tk.Label(output_inner, text="💾 输出目录",
                font=('Microsoft YaHei', 11, 'bold'),
                bg=COLORS["card"], fg=COLORS["text"]).pack(anchor='w', pady=(0, 8))
        
        out_row = tk.Frame(output_inner, bg=COLORS["card"])
        out_row.pack(fill=tk.X)
        
        self.output_var = tk.StringVar()
        self.output_var.set(os.path.expanduser("~/Desktop/裁切输出"))
        
        self.output_entry = tk.Entry(out_row, textvariable=self.output_var,
                                   font=('Microsoft YaHei', 10),
                                   relief='solid', borderwidth=1,
                                   bg=COLORS["white"], fg=COLORS["text"])
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        
        browse_btn = FlatButton(out_row, text="浏览", bg=COLORS["primary_light"],
                               fg=COLORS["primary"], hover=COLORS["border"],
                               active=COLORS["border"], padx=10, pady=4,
                               font=('Microsoft YaHei', 9), command=self.browse_output)
        browse_btn.pack(side=tk.RIGHT)
        
        # ---- 操作按钮 ----
        btn_frame = tk.Frame(right_col, bg=COLORS["bg"])
        btn_frame.pack(fill=tk.X, pady=(6, 0))
        
        self.btn_start = FlatButton(btn_frame, text="🚀 开始批量裁切",
                                   bg=COLORS["primary"], fg=COLORS["white"],
                                   hover=COLORS["primary_dark"], active=COLORS["primary_active"],
                                   command=self.start_crop)
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        
        self.btn_cancel = DangerButton(btn_frame, text="⏹ 取消",
                                      command=self.cancel_crop, state='disabled')
        self.btn_cancel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        
        # ---- 进度卡片 ----
        progress_card = tk.Frame(right_col, bg=COLORS["card"], relief='flat')
        progress_card.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        
        progress_inner = tk.Frame(progress_card, bg=COLORS["card"], padx=14, pady=12)
        progress_inner.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(progress_inner, text="📊 进度",
                font=('Microsoft YaHei', 11, 'bold'),
                bg=COLORS["card"], fg=COLORS["text"]).pack(anchor='w', pady=(0, 6))
        
        self.progress_bar = ttk.Progressbar(progress_inner, orient=tk.HORIZONTAL,
                                            length=100, mode='determinate',
                                            style='TProgressbar')
        self.progress_bar.pack(fill=tk.X, pady=(0, 4))
        
        self.status_label = tk.Label(progress_inner, text="就绪",
                                    font=('Microsoft YaHei', 10),
                                    bg=COLORS["card"], fg=COLORS["text_light"])
        self.status_label.pack(anchor='w', pady=(0, 4))
        
        self.log_text = scrolledtext.ScrolledText(progress_inner, height=4,
                                                  font=('Consolas', 9),
                                                  bg=COLORS["white"],
                                                  fg=COLORS["text"],
                                                  relief='flat',
                                                  borderwidth=1,
                                                  highlightthickness=0)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state='disabled')
        
        # ---- 底部状态栏 ----
        status_bar = tk.Frame(main_frame, bg=COLORS["bg"])
        status_bar.pack(fill=tk.X, pady=(8, 0))
        
        tk.Label(status_bar, text="💡 添加文件夹自动扫描子目录",
                font=('Microsoft YaHei', 9), bg=COLORS["bg"], fg=COLORS["text_light"]).pack(side=tk.LEFT)
        
        self.count_label = tk.Label(status_bar, text="共 0 个待处理",
                                   font=('Microsoft YaHei', 9, 'bold'),
                                   bg=COLORS["bg"], fg=COLORS["primary"])
        self.count_label.pack(side=tk.RIGHT)
        
        # 进度条样式
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TProgressbar', background=COLORS["primary"],
                       troughcolor=COLORS["border"], borderwidth=0, thickness=16)
    
    # ===== 恢复默认参数 =====
    def reset_defaults(self):
        self.black_threshold_var.set(80)
        self.white_threshold_var.set(235)
        self.margin_left.set(2)
        self.margin_right.set(2)
        self.margin_top.set(2)
        self.margin_bottom.set(2)
    
    # ===== 卡片辅助 =====
    def _make_card(self, parent, expand=False):
        card = tk.Frame(parent, bg=COLORS["card"], relief='flat')
        if expand:
            card.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        else:
            card.pack(fill=tk.X, pady=(0, 6))
        return card
    
    def _card_content(self, card, expand=False):
        inner = tk.Frame(card, bg=COLORS["card"], padx=14, pady=12)
        if expand:
            inner.pack(fill=tk.BOTH, expand=True)
        else:
            inner.pack(fill=tk.X)
        return inner
    
    # ===== 事件处理 =====
    def on_device_selected(self, event):
        device = self.device_var.get()
        preset = KINDLE_PRESETS.get(device)
        if preset and preset['width'] > 0 and preset['height'] > 0:
            self.target_width_var.set(preset['width'])
            self.target_height_var.set(preset['height'])
    
    def add_item(self, path):
        if not path:
            return
        if os.path.isdir(path):
            epub_files = scan_epub_files(path)
            if epub_files:
                for epub in epub_files:
                    if epub not in self.file_list:
                        self.file_list.append(epub)
                        self.listbox.insert(tk.END, os.path.basename(epub))
                self.update_count()
                self.log(f"📁 从文件夹添加了 {len(epub_files)} 个 EPUB")
            else:
                if path not in self.file_list:
                    self.file_list.append(path)
                    self.listbox.insert(tk.END, os.path.basename(path) + " (图片)")
                    self.update_count()
        else:
            if path not in self.file_list:
                self.file_list.append(path)
                self.listbox.insert(tk.END, os.path.basename(path))
                self.update_count()
    
    def add_files(self):
        files = filedialog.askopenfilenames(
            title="选择 EPUB 文件",
            filetypes=[("EPUB 文件", "*.epub")]
        )
        for f in files:
            self.add_item(f)
    
    def add_folder_with_epub(self):
        folder = filedialog.askdirectory(title="选择包含 EPUB 的文件夹")
        if folder:
            self.add_item(folder)
    
    def add_image_folder(self):
        folder = filedialog.askdirectory(title="选择图片文件夹")
        if folder:
            if folder not in self.file_list:
                self.file_list.append(folder)
                self.listbox.insert(tk.END, os.path.basename(folder) + " (图片)")
                self.update_count()
    
    def remove_selected(self):
        selected = self.listbox.curselection()
        for idx in reversed(selected):
            del self.file_list[idx]
            self.listbox.delete(idx)
        self.update_count()
    
    def clear_list(self):
        self.file_list = []
        self.listbox.delete(0, tk.END)
        self.update_count()
    
    def update_count(self):
        self.count_label.config(text=f"共 {len(self.file_list)} 个待处理")
    
    def browse_output(self):
        folder = filedialog.askdirectory(title="选择输出目录")
        if folder:
            self.output_var.set(folder)
    
    def log(self, text):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, text + '\n')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.root.update_idletasks()
    
    def start_crop(self):
        if not self.file_list:
            messagebox.showwarning("提示", "请先添加要处理的文件或文件夹")
            return
        output_dir = self.output_var.get()
        if not output_dir:
            messagebox.showwarning("提示", "请选择输出目录")
            return
        target_width = self.target_width_var.get()
        target_height = self.target_height_var.get()
        if target_width <= 0 or target_height <= 0:
            messagebox.showwarning("提示", "请输入有效的目标分辨率")
            return
        margins = {
            'left': self.margin_left.get(),
            'right': self.margin_right.get(),
            'top': self.margin_top.get(),
            'bottom': self.margin_bottom.get()
        }
        black_threshold = self.black_threshold_var.get()
        white_threshold = self.white_threshold_var.get()
        
        self.btn_start.config(state='disabled')
        self.btn_cancel.config(state='normal')
        self.progress_bar['value'] = 0
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        self.status_label.config(text="⏳ 处理中...", fg=COLORS["warning"])
        
        self.worker = CropWorker(
            self.file_list.copy(),
            output_dir,
            black_threshold,
            white_threshold,
            margins,
            target_width,
            target_height,
            self.log,
            self.on_progress,
            self.on_done
        )
        self.thread = threading.Thread(target=self.worker.run)
        self.thread.daemon = True
        self.thread.start()
    
    def on_progress(self, value, text):
        self.progress_bar['value'] = value
        self.status_label.config(text=text)
        self.root.update_idletasks()
    
    def on_done(self, success, message):
        self.btn_start.config(state='normal')
        self.btn_cancel.config(state='disabled')
        if success:
            self.status_label.config(text="✅ " + message, fg=COLORS["success"])
            self.progress_bar['value'] = 100
            messagebox.showinfo("完成", message)
        else:
            self.status_label.config(text="❌ " + message, fg=COLORS["danger"])
            messagebox.showerror("错误", message)
        self.worker = None
    
    def cancel_crop(self):
        if self.worker:
            self.worker.stop()
            self.status_label.config(text="⏹ 正在取消...", fg=COLORS["warning"])
    
    def run(self):
        self.root.mainloop()

# ============================================
# 入口
# ============================================

if __name__ == "__main__":
    try:
        import PIL
        import numpy
    except ImportError:
        print("❌ 缺少依赖，请运行:")
        print("pip install pillow numpy")
        input("按 Enter 退出")
        sys.exit(1)
    
    app = MainWindow()
    app.run()