"""
ComfyUI Workflow Unpacker - GUI Application
图形化解包工具主程序
"""
import sys
import json
import webbrowser
from pathlib import Path
from typing import Optional

# 版本号
VERSION = "1.0.0"

# 配置文件路径
CONFIG_FILE = Path.home() / ".comfy_pack_unpacker_config.json"

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QDialog,
    QListWidget,
    QDialogButtonBox,
)

try:
    # 尝试相对导入（开发环境）
    from .unpacker_core import (
        detect_python_environments,
        detect_git_executable,
        unpack_to_existing_comfyui,
        UnpackerError,
    )
except ImportError:
    # 绝对导入（打包后的 EXE）
    from comfy_pack.unpacker_core import (
        detect_python_environments,
        detect_git_executable,
        unpack_to_existing_comfyui,
        UnpackerError,
    )


def load_config() -> dict:
    """加载配置文件"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 验证路径是否仍然有效
                validated_config = {}
                
                if 'cpack_path' in config:
                    path = Path(config['cpack_path'])
                    if path.exists():
                        validated_config['cpack_path'] = str(path)
                
                if 'comfyui_dir' in config:
                    path = Path(config['comfyui_dir'])
                    if path.exists() and path.is_dir():
                        validated_config['comfyui_dir'] = str(path)
                
                if 'python_exe' in config:
                    path = Path(config['python_exe'])
                    if path.exists() and path.is_file():
                        validated_config['python_exe'] = str(path)
                
                if 'git_exe' in config:
                    path = Path(config['git_exe'])
                    if path.exists() and path.is_file():
                        validated_config['git_exe'] = str(path)
                
                return validated_config
    except Exception:
        pass
    
    return {}


def save_config(config: dict):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


class UnpackWorker(QThread):
    """解包工作线程"""
    progress = Signal(str, int)  # (stage, percentage)
    log = Signal(str)  # log message
    finished = Signal(bool, str)  # (success, custom_message)
    error = Signal(str)  # error message
    
    def __init__(
        self,
        cpack_path: Path,
        comfyui_dir: Path,
        python_exe: Path,
        git_exe: Optional[Path] = None
    ):
        super().__init__()
        self.cpack_path = cpack_path
        self.comfyui_dir = comfyui_dir
        self.python_exe = python_exe
        self.git_exe = git_exe
        self.custom_message = ""
    
    def run(self):
        """执行解包"""
        try:
            def progress_callback(stage: str, pct: int):
                self.progress.emit(stage, pct)
            
            def log_callback(msg: str):
                self.log.emit(msg)
            
            success = unpack_to_existing_comfyui(
                self.cpack_path,
                self.comfyui_dir,
                self.python_exe,
                self.git_exe,
                progress_callback,
                log_callback
            )
            
            # 读取自定义完成消息
            if success:
                self.custom_message = self._read_completion_message()
            
            self.finished.emit(success, self.custom_message)
        
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False, "")
    
    def _read_completion_message(self) -> str:
        """读取压缩包中的完成消息"""
        import zipfile
        try:
            with zipfile.ZipFile(self.cpack_path, 'r') as zf:
                if 'completion_message.txt' in zf.namelist():
                    return zf.read('completion_message.txt').decode('utf-8').strip()
        except Exception:
            pass
        return ""


class PythonSelectorDialog(QDialog):
    """Python 环境选择对话框"""
    def __init__(self, python_paths: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择 Python 环境")
        self.setMinimumWidth(500)
        self.selected_python = None
        
        layout = QVBoxLayout()
        
        # 说明文字
        label = QLabel("检测到多个 Python 环境，请选择要使用的环境：")
        layout.addWidget(label)
        
        # 列表
        self.list_widget = QListWidget()
        for py_path in python_paths:
            self.list_widget.addItem(str(py_path))
        self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_selected_python(self) -> Optional[Path]:
        """获取选中的 Python 路径"""
        if self.result() == QDialog.Accepted:
            current_item = self.list_widget.currentItem()
            if current_item:
                return Path(current_item.text())
        return None


class CompletionDialog(QDialog):
    """完成对话框"""
    def __init__(self, custom_message: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("解包完成")
        self.setMinimumWidth(450)
        self.setMinimumHeight(250)
        
        # 设置对话框为白色主题
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                color: #2c3e50;
                background-color: transparent;
            }
            QLabel a {
                color: #0078d4;
                text-decoration: none;
            }
            QLabel a:hover {
                text-decoration: underline;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 成功图标和标题
        title = QLabel("✓ 解包成功！")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #28a745; padding: 15px 0;")
        layout.addWidget(title)
        
        if custom_message:
            # 显示自定义消息
            message_label = QLabel(custom_message)
            message_label.setWordWrap(True)
            message_label.setAlignment(Qt.AlignCenter)
            message_label.setOpenExternalLinks(True)  # 支持点击链接
            message_label.setTextFormat(Qt.RichText)  # 支持富文本
            message_label.setStyleSheet("""
                font-size: 11pt; 
                line-height: 1.6; 
                color: #2c3e50;
                padding: 10px;
            """)
            
            # 将纯文本转换为支持链接的 HTML
            html_message = self._convert_to_html(custom_message)
            message_label.setText(html_message)
            
            layout.addWidget(message_label)
        else:
            # 默认消息
            desc = QLabel("工作流已成功安装到您的 ComfyUI 环境中。")
            desc.setWordWrap(True)
            desc.setAlignment(Qt.AlignCenter)
            desc.setStyleSheet("font-size: 11pt; color: #555; padding: 10px;")
            layout.addWidget(desc)
        
        layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setMinimumHeight(45)
        close_btn.setMinimumWidth(120)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignCenter)
        
        self.setLayout(layout)
    
    def _convert_to_html(self, text: str) -> str:
        """将纯文本转换为 HTML，自动识别链接"""
        import re
        
        # 转义 HTML 特殊字符
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # 识别 URL 并转换为链接
        url_pattern = r'(https?://[^\s]+)'
        text = re.sub(url_pattern, r'<a href="\1">\1</a>', text)
        
        # 替换换行符为 <br>
        text = text.replace('\n', '<br>')
        
        return text


class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Aaalice的工作流解包工具 v{VERSION}")
        self.setMinimumSize(800, 600)
        
        # 设置窗口图标
        icon_path = self.get_icon_path()

        if icon_path and icon_path.exists():
            try:
                from PySide6.QtGui import QIcon
                icon = QIcon(str(icon_path))
                if not icon.isNull():
                    self.setWindowIcon(icon)
            except Exception as e:
                pass  # 静默处理图标设置失败
        
        self.cpack_path: Optional[Path] = None
        self.comfyui_dir: Optional[Path] = None
        self.python_exe: Optional[Path] = None
        self.git_exe: Optional[Path] = None
        self.worker: Optional[UnpackWorker] = None
        
        self.init_ui()
        self.load_previous_config()
    
    def get_icon_path(self) -> Optional[Path]:
        """获取图标文件路径"""
        # 尝试从多个位置查找图标
        possible_paths = [
            Path(__file__).parent.parent.parent / "icon.ico",  # 插件根目录
            Path(__file__).parent / "icon.ico",  # comfy_pack 目录
            Path("icon.ico"),  # 当前目录
            # 打包后的可能路径
            Path("_internal/icon.ico"),  # PyInstaller内部目录
            Path("../icon.ico"),  # 上级目录
        ]
        
        for path in possible_paths:
            if path.exists():
                return path

        return None
    
    def load_previous_config(self):
        """加载上次的配置"""
        config = load_config()
        
        if 'cpack_path' in config:
            self.cpack_path = Path(config['cpack_path'])
            self.cpack_input.setText(str(self.cpack_path))
        
        if 'comfyui_dir' in config:
            self.comfyui_dir = Path(config['comfyui_dir'])
            self.comfyui_input.setText(str(self.comfyui_dir))
        
        if 'python_exe' in config:
            self.python_exe = Path(config['python_exe'])
            self.python_input.setText(str(self.python_exe))
            self.python_btn.setEnabled(True)
        
        if 'git_exe' in config:
            self.git_exe = Path(config['git_exe'])
            self.git_input.setText(str(self.git_exe))
            self.git_btn.setEnabled(True)
        
        self.check_ready()
    
    def save_current_config(self):
        """保存当前配置"""
        config = {}
        
        if self.cpack_path and self.cpack_path.exists():
            config['cpack_path'] = str(self.cpack_path)
        
        if self.comfyui_dir and self.comfyui_dir.exists():
            config['comfyui_dir'] = str(self.comfyui_dir)
        
        if self.python_exe and self.python_exe.exists():
            config['python_exe'] = str(self.python_exe)
        
        if self.git_exe and self.git_exe.exists():
            config['git_exe'] = str(self.git_exe)
        
        save_config(config)
    
    def init_ui(self):
        """初始化UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 文件选择区域
        # 压缩包选择
        cpack_layout = QHBoxLayout()
        cpack_layout.addWidget(QLabel("压缩包:"))
        self.cpack_input = QLineEdit()
        self.cpack_input.setPlaceholderText("选择 .cpack.zip 文件...")
        self.cpack_input.setReadOnly(True)
        cpack_layout.addWidget(self.cpack_input, 1)
        cpack_btn = QPushButton("浏览")
        cpack_btn.clicked.connect(self.browse_cpack)
        cpack_layout.addWidget(cpack_btn)
        main_layout.addLayout(cpack_layout)
        
        # ComfyUI 目录选择
        comfyui_layout = QHBoxLayout()
        comfyui_layout.addWidget(QLabel("ComfyUI:"))
        self.comfyui_input = QLineEdit()
        self.comfyui_input.setPlaceholderText("选择 ComfyUI 根目录...")
        self.comfyui_input.setReadOnly(True)
        comfyui_layout.addWidget(self.comfyui_input, 1)
        comfyui_btn = QPushButton("浏览")
        comfyui_btn.clicked.connect(self.browse_comfyui)
        comfyui_layout.addWidget(comfyui_btn)
        main_layout.addLayout(comfyui_layout)
        
        # Python 环境选择
        python_layout = QHBoxLayout()
        python_layout.addWidget(QLabel("Python:"))
        self.python_input = QLineEdit()
        self.python_input.setPlaceholderText("自动检测...")
        self.python_input.setReadOnly(True)
        python_layout.addWidget(self.python_input, 1)
        self.python_btn = QPushButton("手动选择")
        self.python_btn.clicked.connect(self.select_python)
        self.python_btn.setEnabled(False)
        python_layout.addWidget(self.python_btn)
        main_layout.addLayout(python_layout)
        
        # Git 路径选择
        git_layout = QHBoxLayout()
        git_layout.addWidget(QLabel("Git:"))
        self.git_input = QLineEdit()
        self.git_input.setPlaceholderText("自动检测...")
        self.git_input.setReadOnly(True)
        git_layout.addWidget(self.git_input, 1)
        self.git_btn = QPushButton("手动选择")
        self.git_btn.clicked.connect(self.select_git)
        self.git_btn.setEnabled(False)
        git_layout.addWidget(self.git_btn)
        main_layout.addLayout(git_layout)
        
        # 状态指示器
        self.status_box = QWidget()
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(15, 15, 15, 15)
        status_layout.setSpacing(8)
        self.status_box.setLayout(status_layout)
        self.status_box.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
            }
        """)
        
        self.status_plugin = QLabel("● 检测插件: 等待中")
        self.status_plugin.setStyleSheet("color: #666; font-size: 10pt;")
        self.status_deps = QLabel("● 安装依赖: 等待中")
        self.status_deps.setStyleSheet("color: #666; font-size: 10pt;")
        self.status_files = QLabel("● 复制文件: 等待中")
        self.status_files.setStyleSheet("color: #666; font-size: 10pt;")
        
        status_layout.addWidget(self.status_plugin)
        status_layout.addWidget(self.status_deps)
        status_layout.addWidget(self.status_files)
        
        main_layout.addWidget(self.status_box)
        
        # 总进度条
        progress_layout = QVBoxLayout()
        progress_label = QLabel("总进度:")
        progress_layout.addWidget(progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(progress_layout)
        
        # 日志区域
        log_header_layout = QHBoxLayout()
        log_label = QLabel("日志:")
        log_header_layout.addWidget(log_label)
        log_header_layout.addStretch()
        
        # 复制日志按钮
        self.copy_log_btn = QPushButton("📋 复制日志")
        self.copy_log_btn.setMinimumWidth(120)
        self.copy_log_btn.setMinimumHeight(32)
        self.copy_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 15px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #4CAF50;
                color: white;
            }
        """)
        self.copy_log_btn.clicked.connect(self.copy_log)
        log_header_layout.addWidget(self.copy_log_btn)
        main_layout.addLayout(log_header_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
                border: 1px solid #333;
                border-radius: 3px;
            }
        """)
        main_layout.addWidget(self.log_text, 3)  # 增加伸展因子，让日志区域占更多空间
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.start_btn = QPushButton("开始解包")
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumWidth(120)
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #999;
            }
        """)
        self.start_btn.clicked.connect(self.start_unpack)
        button_layout.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #666;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #999;
            }
        """)
        self.cancel_btn.clicked.connect(self.close)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        central_widget.setLayout(main_layout)
    
    def log(self, message: str, color: str = "#d4d4d4"):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'
        self.log_text.append(formatted)
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
    
    def copy_log(self):
        """复制日志内容到剪贴板"""
        # 获取纯文本（去除HTML格式）
        plain_text = self.log_text.toPlainText()
        
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(plain_text)
        
        # 临时改变按钮文字提示已复制
        original_text = self.copy_log_btn.text()
        self.copy_log_btn.setText("✓ 已复制")
        self.copy_log_btn.setEnabled(False)
        
        # 1秒后恢复按钮文字
        QTimer.singleShot(1000, lambda: (
            self.copy_log_btn.setText(original_text),
            self.copy_log_btn.setEnabled(True)
        ))
    
    def browse_cpack(self):
        """浏览选择压缩包"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择工作流压缩包",
            "",
            "ComfyUI 工作流包 (*.cpack.zip *.zip);;所有文件 (*.*)"
        )
        
        if file_path:
            self.cpack_path = Path(file_path)
            self.cpack_input.setText(str(self.cpack_path))
            self.log(f"选择压缩包: {self.cpack_path.name}", "#4CAF50")
            self.save_current_config()
            self.check_ready()
    
    def browse_comfyui(self):
        """浏览选择 ComfyUI 目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择 ComfyUI 根目录"
        )
        
        if dir_path:
            self.comfyui_dir = Path(dir_path)
            self.comfyui_input.setText(str(self.comfyui_dir))
            self.log(f"选择目录: {self.comfyui_dir}", "#4CAF50")
            self.save_current_config()
            
            # 自动检测 Python 和 Git
            self.detect_python()
            self.detect_git()
            self.check_ready()
    
    def detect_python(self):
        """自动检测 Python 环境"""
        if not self.comfyui_dir:
            return
        
        self.log("正在检测 Python 环境...", "#2196F3")
        
        # 使用日志回调来输出详细的检测过程
        def log_callback(msg: str):
            self.log(msg, "#888888")
        
        python_paths = detect_python_environments(self.comfyui_dir, log_callback)
        
        if not python_paths:
            self.log("未检测到 Python 环境", "#FF9800")
            self.python_input.setText("未检测到")
            self.python_btn.setEnabled(True)
            self.python_exe = None
        elif len(python_paths) == 1:
            self.python_exe = python_paths[0]
            self.python_input.setText(str(self.python_exe))
            self.log(f"检测到 Python: {self.python_exe}", "#4CAF50")
            self.python_btn.setEnabled(True)
            self.save_current_config()
        else:
            # 多个环境，让用户选择
            self.log(f"检测到 {len(python_paths)} 个 Python 环境", "#FF9800")
            dialog = PythonSelectorDialog(python_paths, self)
            if dialog.exec():
                self.python_exe = dialog.get_selected_python()
                if self.python_exe:
                    self.python_input.setText(str(self.python_exe))
                    self.log(f"选择 Python: {self.python_exe}", "#4CAF50")
                    self.save_current_config()
            self.python_btn.setEnabled(True)
    
    def select_python(self):
        """手动选择 Python"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Python 可执行文件",
            str(self.comfyui_dir.parent) if self.comfyui_dir else "",
            "Python (python.exe python);;所有文件 (*.*)"
        )
        
        if file_path:
            self.python_exe = Path(file_path)
            self.python_input.setText(str(self.python_exe))
            self.log(f"手动选择 Python: {self.python_exe}", "#4CAF50")
            self.save_current_config()
            self.check_ready()
    
    def detect_git(self):
        """自动检测 Git"""
        if not self.comfyui_dir:
            return
        
        self.log("正在检测 Git...", "#2196F3")
        git_path = detect_git_executable(self.comfyui_dir)
        
        if git_path:
            self.git_exe = git_path
            self.git_input.setText(str(self.git_exe))
            self.log(f"检测到 Git: {self.git_exe}", "#4CAF50")
            self.save_current_config()
        else:
            self.log("未检测到 Git（可手动选择）", "#FF9800")
            self.git_input.setText("未检测到")
            self.git_exe = None
        
        self.git_btn.setEnabled(True)
    
    def select_git(self):
        """手动选择 Git"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Git 可执行文件",
            str(self.comfyui_dir.parent) if self.comfyui_dir else "",
            "Git (git.exe git);;所有文件 (*.*)"
        )
        
        if file_path:
            self.git_exe = Path(file_path)
            self.git_input.setText(str(self.git_exe))
            self.log(f"手动选择 Git: {self.git_exe}", "#4CAF50")
            self.save_current_config()
            self.check_ready()
    
    def check_ready(self):
        """检查是否可以开始解包"""
        ready = bool(
            self.cpack_path and
            self.comfyui_dir and
            self.python_exe and
            self.git_exe and
            self.cpack_path.exists() and
            self.comfyui_dir.exists() and
            self.python_exe.exists() and
            self.git_exe.exists()
        )
        self.start_btn.setEnabled(ready)
    
    def start_unpack(self):
        """开始解包"""
        if not all([self.cpack_path, self.comfyui_dir, self.python_exe, self.git_exe]):
            QMessageBox.warning(self, "提示", "请先选择所有必需的文件和目录")
            return
        
        # 禁用按钮
        self.start_btn.setEnabled(False)
        self.python_btn.setEnabled(False)
        self.git_btn.setEnabled(False)
        
        # 重置状态
        self.progress_bar.setValue(0)
        self.status_plugin.setText("● 检测插件: 准备中...")
        self.status_deps.setText("● 安装依赖: 等待中")
        self.status_files.setText("● 复制文件: 等待中")
        
        self.log("=" * 60, "#888")
        self.log("开始解包...", "#2196F3")
        
        # 创建工作线程
        self.worker = UnpackWorker(
            self.cpack_path,
            self.comfyui_dir,
            self.python_exe,
            self.git_exe
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.on_log)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def on_progress(self, stage: str, percentage: int):
        """进度更新"""
        self.progress_bar.setValue(percentage)
        
        # 更新状态指示器
        if "插件" in stage or "检查插件" in stage:
            self.status_plugin.setText(f"● {stage}")
        elif "依赖" in stage:
            self.status_deps.setText(f"● {stage}")
        elif "文件" in stage or "工作流" in stage:
            self.status_files.setText(f"● {stage}")
    
    def on_log(self, message: str):
        """日志更新"""
        # 根据内容设置颜色
        if message.startswith("✓") or "完成" in message or "成功" in message:
            color = "#4CAF50"  # 绿色
        elif message.startswith("✗") or "失败" in message or "错误" in message:
            color = "#F44336"  # 红色
        elif "警告" in message:
            color = "#FF9800"  # 橙色
        else:
            color = "#d4d4d4"  # 默认
        
        self.log(message, color)
    
    def on_error(self, error_msg: str):
        """错误处理"""
        self.log(f"✗ 错误: {error_msg}", "#F44336")
        QMessageBox.critical(self, "错误", f"解包失败:\n{error_msg}")
        self.reset_ui()
    
    def on_finished(self, success: bool, custom_message: str):
        """解包完成"""
        if success:
            self.log("=" * 60, "#888")
            self.log("✓ 解包完成！", "#4CAF50")
            self.status_plugin.setText("● 检测插件: 完成")
            self.status_deps.setText("● 安装依赖: 完成")
            self.status_files.setText("● 复制文件: 完成")
            
            # 显示完成对话框（传入自定义消息）
            self.log(f"准备显示完成对话框，自定义消息: {custom_message if custom_message else '(无)'}", "#888")
            dialog = CompletionDialog(custom_message, self)
            dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)  # 保持在最前面
            dialog.exec()
        else:
            self.log("✗ 解包失败", "#F44336")
        
        self.reset_ui()
    
    def reset_ui(self):
        """重置 UI 状态"""
        self.start_btn.setEnabled(True)
        self.python_btn.setEnabled(True)
        self.git_btn.setEnabled(True)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式为 Fusion
    app.setStyle("Fusion")
    
    # 设置全局样式表 - 现代浅色主题
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QWidget {
            font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
            font-size: 10pt;
        }
        QLabel {
            color: #2c3e50;
            font-size: 10pt;
        }
        QLineEdit {
            background-color: white;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 6px 10px;
            color: #2c3e50;
            selection-background-color: #0078d4;
        }
        QLineEdit:focus {
            border: 2px solid #0078d4;
        }
        QLineEdit:read-only {
            background-color: #f8f8f8;
            color: #555;
        }
        QPushButton {
            background-color: white;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 6px 15px;
            color: #2c3e50;
            min-height: 28px;
        }
        QPushButton:hover {
            background-color: #e8f4ff;
            border-color: #0078d4;
        }
        QPushButton:pressed {
            background-color: #cce4f7;
        }
        QPushButton:disabled {
            background-color: #f0f0f0;
            color: #999;
            border-color: #e0e0e0;
        }
        QTextEdit {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 8px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 9pt;
        }
        QProgressBar {
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            text-align: center;
            background-color: white;
            color: #2c3e50;
            font-weight: bold;
        }
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 3px;
        }
    """)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

