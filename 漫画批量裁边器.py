# 漫画批量裁边器.py
# 支持 EPUB + 图片文件夹 | 自动识别子目录 EPUB | 按钮操作

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
# 核心裁切算法
# ============================================

def find_black_border(img_path, black_threshold=80):
    """找到黑框的位置"""
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
    """检测白边位置（备用）"""
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
    """裁切到黑框或白边位置"""
    if margins is None:
        margins = {'left': 2, 'right': 2, 'top': 2, 'bottom': 2}
    
    # 先尝试黑框
    bbox = find_black_border(img_path, black_threshold)
    
    # 如果没找到黑框，尝试白边
    if bbox is None:
        bbox = find_white_border(img_path, white_threshold)
    
    if bbox is None:
        return False
    
    left, top, right, bottom = bbox
    
    img = Image.open(img_path)
    w, h = img.size
    
    # 应用用户自定义留白
    left = max(0, left - margins['left'])
    top = max(0, top - margins['top'])
    right = min(w, right + margins['right'])
    bottom = min(h, bottom + margins['bottom'])
    
    cropped = img.crop((left, top, right, bottom))
    cropped.save(img_path, quality=92)
    return True


# ============================================
# 辅助函数：扫描文件夹中的 EPUB
# ============================================

def scan_epub_files(folder_path):
    """扫描文件夹中所有 EPUB 文件"""
    folder_path = Path(folder_path)
    epub_files = []
    
    # 递归扫描所有子目录
    for epub in folder_path.rglob('*.epub'):
        epub_files.append(str(epub))
    
    return epub_files


# ============================================
# 处理类
# ============================================

class CropWorker:
    def __init__(self, file_list, output_dir, black_threshold, white_threshold, margins, log_callback, progress_callback, done_callback):
        self.file_list = file_list
        self.output_dir = output_dir
        self.black_threshold = black_threshold
        self.white_threshold = white_threshold
        self.margins = margins
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
            
            success = 0
            total = len(img_files)
            for i, img in enumerate(img_files, 1):
                if not self.is_running:
                    return False
                if crop_to_border(img, self.black_threshold, self.white_threshold, self.margins):
                    success += 1
                sub_progress = int((i / total) * 100)
                overall_progress = self.current_file / self.total_files * 100 + (sub_progress / self.total_files)
                self.progress(int(overall_progress), f"{self.current_file}/{self.total_files} - {img.name}")
            
            self.log(f"  ✅ 裁切 {success}/{total} 张")
            
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
        
        success = 0
        total = len(img_files)
        for i, img in enumerate(img_files, 1):
            if not self.is_running:
                return False
            if crop_to_border(img, self.black_threshold, self.white_threshold, self.margins):
                dest = output_dir / img.name
                shutil.copy2(img, dest)
                success += 1
            sub_progress = int((i / total) * 100)
            overall_progress = self.current_file / self.total_files * 100 + (sub_progress / self.total_files)
            self.progress(int(overall_progress), f"{self.current_file}/{self.total_files} - {img.name}")
        
        self.log(f"  ✅ 裁切 {success}/{total} 张")
        return True

    def run(self):
        self.log(f"📋 共 {self.total_files} 个文件/文件夹待处理")
        self.log(f"📁 输出目录: {self.output_dir}")
        self.log(f"⚙️ 黑框阈值: {self.black_threshold}, 白边阈值: {self.white_threshold}")
        self.log(f"📐 留白: L{self.margins['left']} R{self.margins['right']} T{self.margins['top']} B{self.margins['bottom']}")
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
# GUI 主窗口
# ============================================

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("漫画批量裁边器 v2.5")
        self.root.geometry("750x800")
        self.root.minsize(720, 780)
        self.root.configure(bg='#f0f0f0')
        
        self.worker = None
        self.file_list = []
        self.count_label = None
        
        self.setup_ui()
        
    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg='#f0f0f0', padx=20, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== 标题 =====
        title = tk.Label(main_frame, text="📐 漫画批量裁边器 v2.5", 
                        font=('Microsoft YaHei', 20, 'bold'), bg='#f0f0f0')
        title.pack(anchor='w')
        
        subtitle = tk.Label(main_frame, text="先检测黑框 → 再检测白边 | 支持 EPUB / 图片文件夹", 
                           font=('Microsoft YaHei', 10), bg='#f0f0f0', fg='#888')
        subtitle.pack(anchor='w', pady=(0, 15))
        
        # ===== 文件列表 =====
        list_frame = tk.LabelFrame(main_frame, text="📋 待处理列表", 
                                   font=('Microsoft YaHei', 10, 'bold'), bg='#f0f0f0')
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        list_inner = tk.Frame(list_frame, bg='#f0f0f0')
        list_inner.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = tk.Scrollbar(list_inner)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(list_inner, yscrollcommand=scrollbar.set,
                                  font=('Microsoft YaHei', 10), selectmode=tk.EXTENDED,
                                  bg='#fafafa', height=8)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # 按钮行
        btn_row1 = tk.Frame(list_frame, bg='#f0f0f0')
        btn_row1.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        tk.Button(btn_row1, text="➕ 添加 EPUB 文件", command=self.add_files,
                 font=('Microsoft YaHei', 10), bg='#e3f2fd').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row1, text="📁 添加文件夹(扫描EPUB)", command=self.add_folder_with_epub,
                 font=('Microsoft YaHei', 10), bg='#c8e6c9').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row1, text="📂 添加图片文件夹", command=self.add_image_folder,
                 font=('Microsoft YaHei', 10), bg='#e3f2fd').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row1, text="❌ 移除选中", command=self.remove_selected,
                 font=('Microsoft YaHei', 10), bg='#ffcdd2').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row1, text="🗑️ 清空", command=self.clear_list,
                 font=('Microsoft YaHei', 10), bg='#ffcdd2').pack(side=tk.LEFT, padx=2)
        
        # ===== 裁切参数 =====
        param_frame = tk.LabelFrame(main_frame, text="⚙️ 裁切参数", 
                                   font=('Microsoft YaHei', 10, 'bold'), bg='#f0f0f0')
        param_frame.pack(fill=tk.X, pady=5)
        
        param_inner = tk.Frame(param_frame, bg='#f0f0f0')
        param_inner.pack(fill=tk.X, padx=10, pady=8)
        
        # 黑框阈值
        tk.Label(param_inner, text="黑框阈值:", font=('Microsoft YaHei', 10), 
                bg='#f0f0f0').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.black_threshold_var = tk.IntVar(value=80)
        tk.Spinbox(param_inner, from_=30, to=150, width=8, 
                  textvariable=self.black_threshold_var, font=('Microsoft YaHei', 10)).grid(row=0, column=1, padx=(0, 20))
        tk.Label(param_inner, text="(值越小越严格)", font=('Microsoft YaHei', 9), 
                bg='#f0f0f0', fg='#888').grid(row=0, column=2, sticky='w')
        
        # 白边阈值
        tk.Label(param_inner, text="白边阈值:", font=('Microsoft YaHei', 10), 
                bg='#f0f0f0').grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(8, 0))
        self.white_threshold_var = tk.IntVar(value=235)
        tk.Spinbox(param_inner, from_=200, to=250, width=8, 
                  textvariable=self.white_threshold_var, font=('Microsoft YaHei', 10)).grid(row=1, column=1, padx=(0, 20), pady=(8, 0))
        tk.Label(param_inner, text="(值越大越宽松)", font=('Microsoft YaHei', 9), 
                bg='#f0f0f0', fg='#888').grid(row=1, column=2, sticky='w', pady=(8, 0))
        
        # 保留留白
        tk.Label(param_inner, text="保留留白 (像素):", font=('Microsoft YaHei', 10), 
                bg='#f0f0f0').grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(8, 0))
        
        margin_frame = tk.Frame(param_inner, bg='#f0f0f0')
        margin_frame.grid(row=2, column=1, columnspan=2, sticky='w', pady=(8, 0))
        
        tk.Label(margin_frame, text="左:", font=('Microsoft YaHei', 10), bg='#f0f0f0').pack(side=tk.LEFT)
        self.margin_left = tk.IntVar(value=2)
        tk.Spinbox(margin_frame, from_=0, to=50, width=5, textvariable=self.margin_left,
                  font=('Microsoft YaHei', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(margin_frame, text="右:", font=('Microsoft YaHei', 10), bg='#f0f0f0').pack(side=tk.LEFT)
        self.margin_right = tk.IntVar(value=2)
        tk.Spinbox(margin_frame, from_=0, to=50, width=5, textvariable=self.margin_right,
                  font=('Microsoft YaHei', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(margin_frame, text="上:", font=('Microsoft YaHei', 10), bg='#f0f0f0').pack(side=tk.LEFT)
        self.margin_top = tk.IntVar(value=2)
        tk.Spinbox(margin_frame, from_=0, to=50, width=5, textvariable=self.margin_top,
                  font=('Microsoft YaHei', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(margin_frame, text="下:", font=('Microsoft YaHei', 10), bg='#f0f0f0').pack(side=tk.LEFT)
        self.margin_bottom = tk.IntVar(value=2)
        tk.Spinbox(margin_frame, from_=0, to=50, width=5, textvariable=self.margin_bottom,
                  font=('Microsoft YaHei', 10)).pack(side=tk.LEFT)
        
        # ===== 输出目录 =====
        output_frame = tk.LabelFrame(main_frame, text="💾 输出目录", 
                                    font=('Microsoft YaHei', 10, 'bold'), bg='#f0f0f0')
        output_frame.pack(fill=tk.X, pady=5)
        
        output_inner = tk.Frame(output_frame, bg='#f0f0f0')
        output_inner.pack(fill=tk.X, padx=10, pady=8)
        
        self.output_var = tk.StringVar()
        self.output_var.set(os.path.expanduser("~/Desktop/裁切输出"))
        
        self.output_entry = tk.Entry(output_inner, textvariable=self.output_var,
                                   font=('Microsoft YaHei', 10))
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        tk.Button(output_inner, text="📁 浏览", command=self.browse_output,
                 font=('Microsoft YaHei', 10), bg='#e3f2fd').pack(side=tk.RIGHT)
        
        # ===== 按钮 =====
        btn_frame = tk.Frame(main_frame, bg='#f0f0f0', pady=5)
        btn_frame.pack(fill=tk.X)
        
        self.btn_start = tk.Button(btn_frame, text="🚀 开始批量裁切", 
                                  font=('Microsoft YaHei', 14, 'bold'),
                                  bg='#4CAF50', fg='white', height=1,
                                  command=self.start_crop)
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.btn_cancel = tk.Button(btn_frame, text="⏹ 取消", 
                                   font=('Microsoft YaHei', 12),
                                   bg='#f44336', fg='white', height=1,
                                   command=self.cancel_crop, state='disabled')
        self.btn_cancel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # ===== 进度 =====
        progress_frame = tk.LabelFrame(main_frame, text="📊 进度", 
                                      font=('Microsoft YaHei', 10, 'bold'), bg='#f0f0f0')
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, 
                                            length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(8, 5))
        
        self.status_label = tk.Label(progress_frame, text="就绪", 
                                    font=('Microsoft YaHei', 10), bg='#f0f0f0', fg='#666')
        self.status_label.pack(anchor='w', padx=10)
        
        self.log_text = scrolledtext.ScrolledText(progress_frame, height=5, 
                                                  font=('Consolas', 9), bg='#fafafa')
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text.config(state='disabled')
        
        # ===== 底部 =====
        tip_frame = tk.Frame(main_frame, bg='#f0f0f0')
        tip_frame.pack(fill=tk.X)
        
        tk.Label(tip_frame, text="💡 添加文件夹会自动扫描所有子目录的 EPUB 文件", 
                font=('Microsoft YaHei', 9), bg='#f0f0f0', fg='#999').pack(side=tk.LEFT)
        
        self.count_label = tk.Label(tip_frame, text="共 0 个待处理", 
                                   font=('Microsoft YaHei', 9), bg='#f0f0f0', fg='#999')
        self.count_label.pack(side=tk.RIGHT)
    
    def add_item(self, path):
        """添加单个项目到列表"""
        if not path:
            return
        
        # 如果是文件夹，扫描其中的所有 EPUB
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
                # 如果没有 EPUB，直接添加文件夹本身（作为图片文件夹处理）
                if path not in self.file_list:
                    self.file_list.append(path)
                    self.listbox.insert(tk.END, os.path.basename(path) + " (图片)")
                    self.update_count()
        else:
            # 单个文件
            if path not in self.file_list:
                self.file_list.append(path)
                self.listbox.insert(tk.END, os.path.basename(path))
                self.update_count()
    
    def add_files(self):
        """添加 EPUB 文件"""
        files = filedialog.askopenfilenames(
            title="选择 EPUB 文件",
            filetypes=[("EPUB 文件", "*.epub")]
        )
        for f in files:
            self.add_item(f)
    
    def add_folder_with_epub(self):
        """添加文件夹，自动扫描所有 EPUB"""
        folder = filedialog.askdirectory(title="选择包含 EPUB 的文件夹")
        if folder:
            self.add_item(folder)
    
    def add_image_folder(self):
        """添加图片文件夹（直接处理图片）"""
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
        self.status_label.config(text="处理中...")
        
        self.worker = CropWorker(
            self.file_list.copy(),
            output_dir,
            black_threshold,
            white_threshold,
            margins,
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
            self.status_label.config(text="✅ " + message)
            self.progress_bar['value'] = 100
            messagebox.showinfo("完成", message)
        else:
            self.status_label.config(text="❌ " + message)
            messagebox.showerror("错误", message)
        
        self.worker = None
    
    def cancel_crop(self):
        if self.worker:
            self.worker.stop()
            self.status_label.config(text="正在取消...")
    
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