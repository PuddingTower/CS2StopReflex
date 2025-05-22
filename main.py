import sys
import os
import time
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QHBoxLayout, QListWidget, QMessageBox, QListWidgetItem, QPushButton,
    QSizePolicy, QSpacerItem, QGridLayout, QGroupBox, QDialog,
    QRadioButton, QButtonGroup, QShortcut, QLineEdit, QFormLayout, QTextBrowser
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QSize, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon, QDesktopServices, QPixmap, QPainter, QKeySequence
from pynput import keyboard
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import statistics
from matplotlib import rcParams
import matplotlib.colors as mcolors # Import colors module

# 设置 matplotlib 字体以支持中文
rcParams['font.sans-serif'] = ['Microsoft YaHei']
rcParams['axes.unicode_minus'] = False

def resource_path(relative_path):
    """ 获取资源的绝对路径，支持打包后的应用 """
    if getattr(sys, 'frozen', False):  # 如果是打包后的可执行文件
        current_dir = sys._MEIPASS  # 打包后的临时目录
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, relative_path)

class BackgroundLabel(QLabel):
    """ 带透明度和背景模糊效果的背景标签 """
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.pixmap_original = QPixmap(image_path)
        self.opacity = 0.8
        self.setAttribute(Qt.WA_TransparentForMouseEvents) # 允许鼠标事件穿透
        self.setScaledContents(False) # 不自动缩放内容
        self.update_pixmap()

    def set_opacity(self, opacity):
        """ 设置背景透明度 """
        self.opacity = opacity
        self.update_pixmap()

    def update_pixmap(self):
        """ 更新显示的 Pixmap，应用透明度和模糊效果 """
        if self.pixmap_original.isNull():
            return
        size = self.size()
        if size.isEmpty():
            return

        # 保持宽高比扩展缩放图像
        scaled_pixmap = self.pixmap_original.scaled(
            size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )

        # 创建带透明度的 Pixmap
        pixmap_with_opacity = QPixmap(size)
        pixmap_with_opacity.fill(Qt.transparent) # 填充透明背景

        painter = QPainter(pixmap_with_opacity)
        painter.setOpacity(self.opacity) # 设置图片本身透明度

        # 计算居中绘制的位置
        x = (size.width() - scaled_pixmap.width()) // 2
        y = (size.height() - scaled_pixmap.height()) // 2
        painter.drawPixmap(x, y, scaled_pixmap) # 绘制缩放后的图片

        # 添加一层半透明白色遮罩，模拟模糊效果
        painter.setOpacity(0.3)
        painter.fillRect(pixmap_with_opacity.rect(), QColor(255, 255, 255))
        painter.end()

        super().setPixmap(pixmap_with_opacity) # 设置最终的 Pixmap

    def resizeEvent(self, event):
        """ 窗口大小改变时重新计算并更新 Pixmap """
        if hasattr(self, 'pixmap_original') and not self.pixmap_original.isNull():
            self.update_pixmap()
        super().resizeEvent(event)

class OptionDialog(QDialog):
    """ 用于选择选项的通用对话框 """
    def __init__(self, title, options, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.selected_option = None

        layout = QVBoxLayout()

        self.button_group = QButtonGroup(self)
        self.radio_buttons = {}
        for option in options:
            radio_button = QRadioButton(option)
            self.button_group.addButton(radio_button)
            layout.addWidget(radio_button)
            self.radio_buttons[option] = radio_button
            if option == options[0]:
                radio_button.setChecked(True)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def set_selected_option(self, option_text):
        if option_text in self.radio_buttons:
            self.radio_buttons[option_text].setChecked(True)

    def get_selected_option(self):
        selected_button = self.button_group.checkedButton()
        if selected_button:
            return selected_button.text()
        return None

class KeyMappingDialog(QDialog):
    """ 用于设置按键映射的对话框 """
    def __init__(self, current_mappings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("按键映射设置")
        self.current_mappings = current_mappings 
        self.new_mappings = current_mappings.copy()

        layout = QFormLayout()
        self.setMinimumWidth(300)

        self.map_inputs = {}
        for target_key in ['W', 'A', 'S', 'D']:
            source_key = self.current_mappings.get(target_key, target_key)
            line_edit = QLineEdit(source_key)
            line_edit.setMaxLength(1) 
            line_edit.setFont(QFont("Arial", 12))
            self.map_inputs[target_key] = line_edit
            layout.addRow(f"映射到 {target_key}:", line_edit)

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: red;")
        layout.addWidget(self.validation_label)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.validate_and_accept)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        self.default_button = QPushButton("恢复默认")
        self.default_button.clicked.connect(self.restore_defaults)

        button_layout.addWidget(self.default_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        main_v_layout = QVBoxLayout()
        main_v_layout.addLayout(layout)
        main_v_layout.addLayout(button_layout)
        self.setLayout(main_v_layout)

    def validate_and_accept(self):
        temp_mappings = {}
        pressed_keys = set()
        valid = True
        for target_key, line_edit in self.map_inputs.items():
            val = line_edit.text().upper()
            if not val: 
                self.validation_label.setText(f"错误: {target_key} 的映射不能为空。")
                valid = False
                break
            if not val.isalnum(): 
                self.validation_label.setText(f"错误: {target_key} 的映射 '{val}' 无效 (仅限字母或数字)。")
                valid = False
                break
            if val in pressed_keys:
                self.validation_label.setText(f"错误: 按键 '{val}' 被多次映射。")
                valid = False
                break
            pressed_keys.add(val)
            temp_mappings[target_key] = val

        if valid:
            self.new_mappings = temp_mappings
            self.accept()
        else:
            pass

    def restore_defaults(self):
        defaults = {'W': 'W', 'A': 'A', 'S': 'S', 'D': 'D'}
        for target_key, line_edit in self.map_inputs.items():
            line_edit.setText(defaults[target_key])
        self.validation_label.setText("") 

    def get_mappings(self):
        return self.new_mappings

class NoSpaceActivateListWidget(QListWidget):
    """
    自定义QListWidget，阻止空格键激活项目。
    """
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            event.ignore()  # 忽略空格键事件，不传递给父类处理
            return          # 直接返回，不执行默认的空格键行为
        super().keyPressEvent(event) # 其他按键正常处理


class InstructionsDialog(QDialog):
    """
    显示使用说明的自定义对话框，包含外部链接按钮。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("使用说明")
        self.setMinimumSize(500, 450) # 稍微调大一点以容纳新文本

        layout = QVBoxLayout(self)

        self.instructions_browser = QTextBrowser(self)
        self.instructions_browser.setOpenExternalLinks(True)
        
        # 新增的说明文本
        new_intro_text = """
        <p><b>此工具主要用于CS2玩家找到自己合适的磁轴键程，请注意，本软件在设计上没有为其他游戏与机械键盘用户开发，请注意使用范围。请详细阅读说明或者去作者B站观看视频。</b></p>
        <hr>
        """
        
        existing_instructions_text = """
        欢迎使用 CS2 急停评估工具！

        <b>基本操作:</b>
        1. 在游戏中或桌面进行 W/A/S/D (或您映射的按键) 急停操作。
           - AD 急停: 按住 A 后松开并立即按 D (或反之)。
           - WS 急停: 按住 W 后松开并立即按 S (或反之)。
           - 反向急停: 按住 A 和 D，然后松开其中一个。
        2. 工具会记录您每次急停的时间差 (毫秒)。
           - 负数表示反向键按早了。
           - 正数表示反向键按晚了。
           - 接近 0 表示完美。
        3. 查看图表和历史记录来分析您的表现。

        <b>功能键:</b>
        - <b>F5 / 刷新按钮</b>: 清空所有记录和图表。
        - <b>F6 / 建议按钮</b>: 根据当前数据提供急停建议 (数据充足时显示)。
        - <b>F7 / 使用说明按钮</b>: 显示此帮助信息。
        - <b>F8 / 按键映射按钮</b>: 设置用其他按键 (如IJKL) 模拟WASD。

        <b>其他设置:</b>
        - 记录次数: 设置图表中显示的最近记录数量。
        - 过滤阈值: 忽略时间差绝对值大于此阈值的记录。

        <b>提示:</b>
        - 为了获得准确数据，请确保工具在后台运行时，游戏内没有绑定冲突的按键。
        - 建议在练习模式或本地服务器进行测试。
        - 如果键盘监听失败，尝试以管理员身份运行本程序。

        祝您练习愉快，枪法进步！
        """
        full_instructions_html = new_intro_text + existing_instructions_text.strip().replace("\n", "<br>")
        self.instructions_browser.setHtml(full_instructions_html)
        layout.addWidget(self.instructions_browser)

        button_layout = QHBoxLayout()
        
        self.github_button = QPushButton("作者GitHub主页")
        self.github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/PuddingTower")))
        button_layout.addWidget(self.github_button)

        self.bilibili_button = QPushButton("作者B站主页")
        self.bilibili_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://space.bilibili.com/13723713")))
        button_layout.addWidget(self.bilibili_button)

        button_layout.addStretch() 

        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept) 
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)


class MainWindow(QMainWindow):
    feedback_signal = pyqtSignal(str, QColor)
    history_signal = pyqtSignal(str, float, float, dict, QColor)
    key_state_signal = pyqtSignal(str, bool) 
    start_timer_signal = pyqtSignal(str, int)
    stop_timer_signal = pyqtSignal(str)
    key_press_signal = pyqtSignal(str, float) 
    key_release_signal = pyqtSignal(str, float) 
    log_signal = pyqtSignal(str)
    update_key_labels_signal = pyqtSignal()


    def __init__(self):
        super().__init__()
        self.setWindowTitle("CS2急停评估工具")
        self.setGeometry(100, 100, 1600, 900)

        icon_path = resource_path("CS2.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print("图标文件 CS2.ico 未找到。")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        background_path = resource_path("background.png")
        if os.path.exists(background_path):
            self.background_label = BackgroundLabel(background_path, central_widget)
            self.background_label.setGeometry(central_widget.rect())
            self.background_label.lower()
        else:
            print("背景图片 background.png 未找到。")
            self.background_label = None

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        left_layout = QVBoxLayout()

        font_large = QFont("Microsoft YaHei", 18)
        font_small = QFont("Microsoft YaHei", 12)
        font_key = QFont("Microsoft YaHei", 14, QFont.Bold)

        self.feedback_label = QLabel("请模拟自己PEEK时进行AD和WS急停")
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setFont(font_large)
        self.feedback_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF; background-color: #2E2E2E;
                border-radius: 10px; padding: 15px;
            }
        """)
        left_layout.addWidget(self.feedback_label)

        self.key_mappings = {'W': 'W', 'A': 'A', 'S': 'S', 'D': 'D'}
        self.reverse_key_mappings = {v: k for k, v in self.key_mappings.items()}


        key_status_layout = QGridLayout()
        self.w_key_label = self.create_key_label(f"{self.key_mappings['W']}键 (W): 未按下", font_key)
        key_status_layout.addWidget(self.w_key_label, 0, 1)
        self.a_key_label = self.create_key_label(f"{self.key_mappings['A']}键 (A): 未按下", font_key)
        key_status_layout.addWidget(self.a_key_label, 1, 0)
        self.s_key_label = self.create_key_label(f"{self.key_mappings['S']}键 (S): 未按下", font_key)
        key_status_layout.addWidget(self.s_key_label, 1, 1)
        self.d_key_label = self.create_key_label(f"{self.key_mappings['D']}键 (D): 未按下", font_key)
        key_status_layout.addWidget(self.d_key_label, 1, 2)
        left_layout.addLayout(key_status_layout)

        self.history_list = NoSpaceActivateListWidget() 
        self.history_list.setFont(font_small)
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 180); border: 1px solid #CCCCCC;
                border-radius: 5px;
            }
            QListWidget::item:selected { background-color: #ADD8E6; }
        """)
        self.history_list.itemClicked.connect(self.show_detail_info)
        left_layout.addWidget(self.history_list, stretch=2)

        self.output_list = QListWidget()
        self.output_list.setFont(font_small)
        self.output_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 180); border: 1px solid #CCCCCC;
                border-radius: 5px;
            }
            QListWidget::item:selected { background-color: #ADD8E6; }
        """)
        left_layout.addWidget(self.output_list, stretch=1)
        
        # --- Controls Button Layout (Record Count, Filter, Key Mapping) ---
        controls_button_layout = QHBoxLayout()
        controls_button_layout.addStretch(1) # ADDED: Stretch before the first button

        self.record_count_button = QPushButton("记录次数")
        self.setup_styled_button(self.record_count_button, "设置图表显示的记录次数", self.set_record_count, fixed_width=100)
        controls_button_layout.addWidget(self.record_count_button)
        
        controls_button_layout.addStretch(1) # Stretch between buttons
        
        self.filter_threshold_button = QPushButton("过滤阈值")
        self.setup_styled_button(self.filter_threshold_button, "设置记录有效急停的时间差阈值", self.set_filter_threshold, fixed_width=100)
        controls_button_layout.addWidget(self.filter_threshold_button)

        controls_button_layout.addStretch(1) # Stretch between buttons

        self.key_mapping_button = QPushButton("按键映射 (F8)")
        self.setup_styled_button(self.key_mapping_button, "设置自定义按键映射 (F8)", self.show_key_mapping_dialog, fixed_width=140)
        controls_button_layout.addWidget(self.key_mapping_button)
        
        controls_button_layout.addStretch(1) # ADDED: Stretch after the last button
        
        left_layout.addLayout(controls_button_layout)

        # --- Footer Button Layout (Instructions, Refresh, Recommendations) ---
        footer_button_layout = QHBoxLayout()
        self.instructions_button = QPushButton("使用说明 (F7)")
        self.setup_styled_button(self.instructions_button, "查看使用说明 (F7)", self.show_instructions_dialog, fixed_width=140)
        footer_button_layout.addWidget(self.instructions_button)
        
        footer_button_layout.addStretch() 

        self.refresh_button = QPushButton("刷新 (F5)")
        self.setup_styled_button(self.refresh_button, "刷新图表和记录 (F5)", self.refresh, fixed_width=100)
        footer_button_layout.addWidget(self.refresh_button)
        
        footer_button_layout.addSpacing(10) 

        self.recommendations_button = QPushButton("建议 (F6)")
        self.setup_styled_button(self.recommendations_button, "查看急停建议 (F6)", self.show_recommendations, fixed_width=100)
        self.recommendations_button.hide() 
        footer_button_layout.addWidget(self.recommendations_button)
        
        left_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        left_layout.addLayout(footer_button_layout)


        right_layout = QVBoxLayout()
        ad_group = QGroupBox("AD急停图表")
        ad_layout = QVBoxLayout()
        self.ad_figure_line = Figure(figsize=(5, 3), facecolor='none')
        self.ad_canvas_line = FigureCanvas(self.ad_figure_line)
        self.ad_canvas_line.setStyleSheet("background-color: transparent;")
        ad_layout.addWidget(self.ad_canvas_line)
        self.ad_figure_box = Figure(figsize=(5, 3), facecolor='none')
        self.ad_canvas_box = FigureCanvas(self.ad_figure_box)
        self.ad_canvas_box.setStyleSheet("background-color: transparent;")
        ad_layout.addWidget(self.ad_canvas_box)
        ad_group.setLayout(ad_layout)
        right_layout.addWidget(ad_group)

        ws_group = QGroupBox("WS急停图表")
        ws_layout = QVBoxLayout()
        self.ws_figure_line = Figure(figsize=(5, 3), facecolor='none')
        self.ws_canvas_line = FigureCanvas(self.ws_figure_line)
        self.ws_canvas_line.setStyleSheet("background-color: transparent;")
        ws_layout.addWidget(self.ws_canvas_line)
        self.ws_figure_box = Figure(figsize=(5, 3), facecolor='none')
        self.ws_canvas_box = FigureCanvas(self.ws_figure_box)
        self.ws_canvas_box.setStyleSheet("background-color: transparent;")
        ws_layout.addWidget(self.ws_canvas_box)
        ws_group.setLayout(ws_layout)
        right_layout.addWidget(ws_group)

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 2)

        self.setStyleSheet("""
            QMainWindow { background-color: transparent; }
            QWidget#MainWindow { background-color: transparent; }
            QGroupBox {
                color: #E0E0E0; font-size: 14px; font-weight: bold;
                border: 1px solid rgba(255, 255, 255, 100); border-radius: 5px;
                margin-top: 1ex; background-color: rgba(0, 0, 0, 80);
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top center;
                padding: 0 3px; background-color: rgba(0, 0, 0, 0); color: #E0E0E0;
            }
            QLabel { color: #2E2E2E; }
            QListWidget { background-color: rgba(255, 255, 255, 180); }
        """)

        self.key_state = {
            'A': {'pressed': False, 'time': None}, 'D': {'pressed': False, 'time': None},
            'W': {'pressed': False, 'time': None}, 'S': {'pressed': False, 'time': None}
        }
        self.waiting_for_opposite_key = {}
        self.ad_data = deque(maxlen=200)
        self.ws_data = deque(maxlen=200)
        self.last_record_time = 0
        self.min_time_between_records = 0.05
        self.in_quick_stop_cooldown = False

        self.feedback_signal.connect(self.update_feedback)
        self.history_signal.connect(self.update_history)
        self.key_state_signal.connect(self.update_key_state_display)
        self.start_timer_signal.connect(self.start_timer)
        self.stop_timer_signal.connect(self.stop_timer)
        self.key_press_signal.connect(self.on_key_press_main_thread)
        self.key_release_signal.connect(self.on_key_release_main_thread)
        self.log_signal.connect(self.append_log)
        self.update_key_labels_signal.connect(self.update_all_key_labels_text)


        self.record_count = 20
        self.filter_threshold = 120
        self.box_plot_multiplier = 2
        self.timer_buffer = 20

        self.timers = {'AD': QTimer(self), 'WS': QTimer(self)}
        self.timers['AD'].setSingleShot(True)
        self.timers['AD'].timeout.connect(lambda: self.reset_quick_stop('AD'))
        self.timers['WS'].setSingleShot(True)
        self.timers['WS'].timeout.connect(lambda: self.reset_quick_stop('WS'))

        self.f5_shortcut = QShortcut(QKeySequence("F5"), self)
        self.f5_shortcut.activated.connect(self.refresh)
        self.f6_shortcut = QShortcut(QKeySequence("F6"), self)
        self.f6_shortcut.activated.connect(self.show_recommendations)
        self.f7_shortcut = QShortcut(QKeySequence("F7"), self)
        self.f7_shortcut.activated.connect(self.show_instructions_dialog)
        self.f8_shortcut = QShortcut(QKeySequence("F8"), self)
        self.f8_shortcut.activated.connect(self.show_key_mapping_dialog)


        try:
            self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release, suppress=False)
            self.listener.start()
            self.log_message("键盘监听器已启动。")
        except Exception as e:
            self.log_message(f"启动键盘监听失败: {e}")
            QMessageBox.critical(self, "错误", f"无法启动键盘监听器。\n请检查程序权限或是否有其他程序占用了键盘钩子。\n以管理员身份运行可能解决此问题。\n错误信息: {e}")
            self.feedback_label.setText("键盘监听启动失败！")
            self.listener = None

        self.update_plot()

    def setup_styled_button(self, button, tooltip, on_click_action, fixed_width=100, fixed_height=40, font_size=12):
        button.setFont(QFont("Microsoft YaHei", font_size))
        button.setFixedSize(fixed_width, fixed_height)
        button.setStyleSheet("""
            QPushButton {
                background-color: #2E2E2E; color: #FFFFFF; border: none; 
                border-radius: 10px; padding: 5px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #1E1E1E; }
        """)
        button.setToolTip(tooltip)
        button.clicked.connect(on_click_action)


    def create_key_label(self, text, font_key):
        label = QLabel(text)
        label.setFont(font_key)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                background-color: #D3D3D3; border: 2px solid #000000;
                border-radius: 8px; min-width: 100px; 
                padding: 5px; color: #2E2E2E;
            }
        """)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return label

    @pyqtSlot()
    def update_all_key_labels_text(self):
        self.w_key_label.setText(f"{self.key_mappings['W']}键 (W): {'按下' if self.key_state['W']['pressed'] else '未按下'}")
        self.a_key_label.setText(f"{self.key_mappings['A']}键 (A): {'按下' if self.key_state['A']['pressed'] else '未按下'}")
        self.s_key_label.setText(f"{self.key_mappings['S']}键 (S): {'按下' if self.key_state['S']['pressed'] else '未按下'}")
        self.d_key_label.setText(f"{self.key_mappings['D']}键 (D): {'按下' if self.key_state['D']['pressed'] else '未按下'}")


    @pyqtSlot(str)
    def append_log(self, message):
        timestamp = time.strftime("%H:%M:%S", time.localtime()) + f".{int((time.time() % 1) * 1000):03d}"
        self.output_list.addItem(f"{timestamp} - {message}")
        self.output_list.scrollToBottom()
        if self.output_list.count() > 150:
            self.output_list.takeItem(0)

    def log_message(self, msg):
        print(msg)
        self.log_signal.emit(msg)

    def on_press(self, key):
        if not hasattr(self, 'listener') or not self.listener or not self.listener.is_alive():
            return
        try:
            original_key_char = key.char.upper()
            self.key_press_signal.emit(original_key_char, time.perf_counter())
        except AttributeError:
            pass 
        except Exception as e:
            print(f"Error in on_press: {e}")

    def on_release(self, key):
        if not hasattr(self, 'listener') or not self.listener or not self.listener.is_alive():
            return
        try:
            original_key_char = key.char.upper()
            self.key_release_signal.emit(original_key_char, time.perf_counter())
        except AttributeError:
            pass 
        except Exception as e:
            print(f"Error in on_release: {e}")

    @pyqtSlot(str, float)
    def on_key_press_main_thread(self, original_key_char, press_time):
        key_char = self.reverse_key_mappings.get(original_key_char)
        if not key_char: 
            return

        if not self.key_state[key_char]['pressed']:
            self.key_state[key_char]['pressed'] = True
            self.key_state[key_char]['time'] = press_time
            self.key_state_signal.emit(key_char, True) 
            self.log_message(f"按下: {original_key_char} (映射为 {key_char}) at {press_time:.4f}")

            key_type = self.get_key_type(key_char)

            if key_type in self.waiting_for_opposite_key and key_char == self.waiting_for_opposite_key[key_type]['key']:
                current_time = time.perf_counter()
                if current_time - self.last_record_time < self.min_time_between_records:
                    self.log_message(f"操作过于频繁，忽略此次 {key_type} 急停 (松开后按)。")
                    del self.waiting_for_opposite_key[key_type]
                    self.stop_timer_signal.emit(key_type)
                    return

                release_time = self.waiting_for_opposite_key[key_type]['release_time']
                key_released_before_orig = self.waiting_for_opposite_key[key_type]['key_released_orig'] 
                key_released_before_mapped = self.waiting_for_opposite_key[key_type]['key_released_mapped'] 

                original_events = self.waiting_for_opposite_key[key_type]['events']

                time_diff = press_time - release_time
                time_diff_ms = round(time_diff * 1000, 1)

                self.log_message(f"检测到 {key_type} 急停 (松开后按): {key_released_before_orig} ({key_released_before_mapped}) -> {original_key_char} ({key_char}), 时间差: {time_diff_ms:.1f}ms")

                if abs(time_diff_ms) > self.filter_threshold:
                    self.log_message(f"时间差 {time_diff_ms:.1f}ms 超过阈值 {self.filter_threshold}ms，忽略记录。")
                else:
                    color = self.get_color(time_diff_ms)
                    timing = '完美急停' if abs(time_diff_ms) <= 2 else ('按早了' if time_diff_ms < 0 else '按晚了')
                    
                    feedback = f"[{key_type}] {timing}：松开{key_released_before_orig}后 {time_diff_ms:.1f}ms 按下了{original_key_char}"

                    detail_info = {
                        'events': original_events + [
                            {'key': original_key_char, 'event': '按下', 'time': press_time, 'time_str': self.format_time(press_time)}
                        ]
                    }
                    self.feedback_signal.emit(feedback, color)
                    self.history_signal.emit(key_type, press_time, time_diff, detail_info, color)
                    if key_type == 'AD': self.ad_data.append({'time': press_time, 'time_diff': time_diff})
                    else: self.ws_data.append({'time': press_time, 'time_diff': time_diff})
                    self.log_message(f"记录 {key_type} 急停 (松开后按): 时间差 {time_diff_ms:.1f}ms")
                    self.last_record_time = current_time
                    self.in_quick_stop_cooldown = True

                if key_type in self.waiting_for_opposite_key:
                    del self.waiting_for_opposite_key[key_type]
                    self.stop_timer_signal.emit(key_type)

            other_key_type = 'WS' if key_type == 'AD' else 'AD'
            if other_key_type in self.waiting_for_opposite_key:
                key_released_in_wait_orig = self.waiting_for_opposite_key[other_key_type]['key_released_orig']
                expected_key_in_wait_orig = self.key_mappings[self.waiting_for_opposite_key[other_key_type]['key']]

                self.log_message(f"按下 {original_key_char} ({key_char}) 时取消了等待 {expected_key_in_wait_orig} (原松开 {key_released_in_wait_orig}) 的 {other_key_type} 状态。")
                del self.waiting_for_opposite_key[other_key_type]
                self.stop_timer_signal.emit(other_key_type)

    @pyqtSlot(str, float)
    def on_key_release_main_thread(self, original_key_char, release_time):
        key_char = self.reverse_key_mappings.get(original_key_char)
        if not key_char: 
            return

        if self.key_state[key_char]['pressed']:
            self.key_state[key_char]['pressed'] = False
            self.key_state_signal.emit(key_char, False) 
            self.log_message(f"松开: {original_key_char} (映射为 {key_char}) at {release_time:.4f}")

            self.process_key_event(original_key_char, key_char, release_time) 

            all_keys_released = not any(state['pressed'] for state in self.key_state.values())
            if all_keys_released and self.in_quick_stop_cooldown:
                self.in_quick_stop_cooldown = False
                self.log_message("所有按键已释放，重置急停冷却状态。")


    def process_key_event(self, key_released_orig, key_released_mapped, release_time):
        key_type = self.get_key_type(key_released_mapped)
        if key_type is None: return

        if key_type == 'AD':
            opposite_key_mapped = 'D' if key_released_mapped == 'A' else 'A'
        else: 
            opposite_key_mapped = 'S' if key_released_mapped == 'W' else 'W'
        
        opposite_key_orig = self.key_mappings[opposite_key_mapped] 
        opposite_key_state = self.key_state[opposite_key_mapped]

        if opposite_key_state['pressed']:
            current_time = time.perf_counter()
            if current_time - self.last_record_time < self.min_time_between_records:
                self.log_message(f"操作过于频繁，忽略此次 {key_type} 急停 (按住反向键松开)。")
            else:
                opposite_key_press_time = opposite_key_state['time']
                time_diff = opposite_key_press_time - release_time
                time_diff_ms = round(time_diff * 1000, 1)

                self.log_message(f"检测到 {key_type} 急停 (按住反向键松开): {key_released_orig} ({key_released_mapped}) -> {opposite_key_orig} ({opposite_key_mapped}), 时间差: {time_diff_ms:.1f}ms")

                if abs(time_diff_ms) > self.filter_threshold:
                    self.log_message(f"时间差 {time_diff_ms:.1f}ms 超过阈值 {self.filter_threshold}ms，忽略记录。")
                else:
                    color = self.get_color(time_diff_ms)
                    timing = '完美急停' if abs(time_diff_ms) <= 2 else ('按早了' if time_diff_ms < 0 else '按晚了')
                    
                    feedback = f"[{key_type}] {timing}：按下{opposite_key_orig}后 {-time_diff_ms:.1f}ms 松开了{key_released_orig}"
                    
                    detail_info = {
                        'events': [
                            {'key': opposite_key_orig, 'event': '按下', 'time': opposite_key_press_time, 'time_str': self.format_time(opposite_key_press_time)},
                            {'key': key_released_orig, 'event': '松开', 'time': release_time, 'time_str': self.format_time(release_time)}
                        ]
                    }
                    self.feedback_signal.emit(feedback, color)
                    self.history_signal.emit(key_type, release_time, time_diff, detail_info, color)
                    if key_type == 'AD': self.ad_data.append({'time': release_time, 'time_diff': time_diff})
                    else: self.ws_data.append({'time': release_time, 'time_diff': time_diff})
                    self.log_message(f"记录 {key_type} 急停 (按住反向键松开): 时间差 {time_diff_ms:.1f}ms")
                    self.last_record_time = current_time
                    self.in_quick_stop_cooldown = True
                    if key_type in self.waiting_for_opposite_key:
                        del self.waiting_for_opposite_key[key_type]
                        self.stop_timer_signal.emit(key_type)
                    return 

        if key_type in self.waiting_for_opposite_key:
            self.log_message(f"覆盖旧的 {key_type} 等待状态。")
            self.stop_timer_signal.emit(key_type)

        self.waiting_for_opposite_key[key_type] = {
            'key': opposite_key_mapped, 
            'release_time': release_time,
            'key_released_orig': key_released_orig, 
            'key_released_mapped': key_released_mapped, 
            'events': [
                {'key': key_released_orig, 'event': '松开', 'time': release_time, 'time_str': self.format_time(release_time)}
            ]
        }
        self.log_message(f"开始等待按下 {self.key_mappings[opposite_key_mapped]} (映射为 {opposite_key_mapped}) 以完成 {key_type} 急停。")
        timer_interval = self.filter_threshold + self.timer_buffer
        self.start_timer_signal.emit(key_type, timer_interval)


    def get_key_type(self, key_char_mapped): 
        if key_char_mapped in ['A', 'D']: return 'AD'
        elif key_char_mapped in ['W', 'S']: return 'WS'
        return None

    def update_feedback(self, feedback, color):
        self.feedback_label.setText(feedback)
        self.feedback_label.setStyleSheet(f"""
            QLabel {{
                color: #FFFFFF; background-color: {color.name()};
                border-radius: 10px; padding: 15px;
            }}
        """)

    def update_history(self, key_type, event_time, time_diff, detail_info, color):
        time_diff_ms = round(time_diff * 1000, 1)
        time_str = time.strftime("%H:%M:%S", time.localtime(event_time)) + f".{int((event_time % 1) * 1000):03d}"
        item_text = f"[{key_type}] {time_str} - 时间差: {time_diff_ms:.1f}ms"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, detail_info)
        item.setBackground(QBrush(color))
        item.setForeground(QBrush(QColor("#000000" if self.is_light_color(color) else "#FFFFFF")))
        self.history_list.addItem(item)
        if self.history_list.count() > 50: self.history_list.takeItem(0)
        self.history_list.scrollToBottom()

        if len(self.ad_data) >= 10 or len(self.ws_data) >= 10:
            if not self.recommendations_button.isVisible(): self.recommendations_button.show()
        self.update_plot()

    def update_plot(self):
        try:
            self.ad_figure_line.clear()
            ax_ad_line = self.ad_figure_line.add_subplot(111)
            ax_ad_line.set_facecolor('none')
            ad_data_list = list(self.ad_data)
            ad_plot_data = ad_data_list[-self.record_count:]
            ad_time_diffs_line = [round(d['time_diff'] * 1000, 1) for d in ad_plot_data]
            start_index_ad = max(0, len(ad_data_list) - self.record_count)
            ad_indices_line = range(start_index_ad + 1, start_index_ad + len(ad_plot_data) + 1)
            ad_colors_line = [self.get_color(diff) for diff in ad_time_diffs_line]

            if ad_time_diffs_line:
                ax_ad_line.scatter(ad_indices_line, ad_time_diffs_line, c=[color.name() for color in ad_colors_line], s=80, edgecolors='black', alpha=0.8)
                mean_value_ad = statistics.mean(ad_time_diffs_line)
                ax_ad_line.axhline(mean_value_ad, color='cyan', linestyle='--', linewidth=1.5, label=f'平均值: {mean_value_ad:.1f}ms')
                ax_ad_line.axhline(0, color='white', linewidth=0.8, linestyle='-')
                ax_ad_line.legend(prop={'family': 'Microsoft YaHei', 'size': 9}, facecolor=(0,0,0,0.5), labelcolor='white')
                for spine_pos in ['bottom', 'left']: ax_ad_line.spines[spine_pos].set_color('white')
                for spine_pos in ['top', 'right']: ax_ad_line.spines[spine_pos].set_visible(False)
                ax_ad_line.tick_params(axis='x', colors='white')
                ax_ad_line.tick_params(axis='y', colors='white')
                ax_ad_line.xaxis.label.set_color('white')
                ax_ad_line.yaxis.label.set_color('white')
                ax_ad_line.title.set_color('white')
            else:
                ax_ad_line.text(0.5, 0.5, '无 AD 数据', ha='center', va='center', transform=ax_ad_line.transAxes, color='white')

            ax_ad_line.set_xlabel('操作次数', fontproperties="Microsoft YaHei", fontsize=10)
            ax_ad_line.set_ylabel('时间差 (ms)', fontproperties="Microsoft YaHei", fontsize=10)
            ax_ad_line.set_title(f'AD 急停时间差 (最近 {len(ad_plot_data)} 次)', fontproperties="Microsoft YaHei", fontsize=12)
            ax_ad_line.grid(True, linestyle='--', alpha=0.3, color='gray')
            self.ad_canvas_line.draw()
        except Exception as e: self.log_message(f"Error updating AD line plot: {e}")

        try:
            self.ad_figure_box.clear()
            ax_ad_box = self.ad_figure_box.add_subplot(111)
            ax_ad_box.set_facecolor('none')
            box_plot_count_ad = min(len(ad_data_list), self.record_count * self.box_plot_multiplier)
            ad_box_data = ad_data_list[-box_plot_count_ad:]
            ad_time_diffs_box = [round(d['time_diff'] * 1000, 1) for d in ad_box_data]

            if len(ad_time_diffs_box) >= 5:
                bp_ad = ax_ad_box.boxplot(ad_time_diffs_box, vert=False, patch_artist=True, showfliers=False, widths=0.6)
                for box in bp_ad['boxes']: box.set(color='#7570b3', linewidth=1.5, facecolor='#1b9e77', alpha=0.7)
                for whisker in bp_ad['whiskers']: whisker.set(color='#7570b3', linewidth=1.5, linestyle='--')
                for cap in bp_ad['caps']: cap.set(color='#7570b3', linewidth=1.5)
                for median in bp_ad['medians']: median.set(color='#b2df8a', linewidth=2)
                ax_ad_box.set_xlabel('时间差 (ms)', fontproperties="Microsoft YaHei", fontsize=10)
                ax_ad_box.set_title(f'AD 时间差分布 (最近 {len(ad_box_data)} 次)', fontproperties="Microsoft YaHei", fontsize=12)
                ax_ad_box.grid(True, linestyle='--', alpha=0.3, axis='x', color='gray')
                ax_ad_box.tick_params(axis='x', colors='white')
                ax_ad_box.tick_params(axis='y', colors='none', length=0)
                ax_ad_box.set_yticks([])
                ax_ad_box.xaxis.label.set_color('white')
                ax_ad_box.title.set_color('white')
                for spine_pos in ['top', 'right', 'left']: ax_ad_box.spines[spine_pos].set_visible(False)
                ax_ad_box.spines['bottom'].set_color('white')
            else:
                ax_ad_box.text(0.5, 0.5, 'AD 数据不足', ha='center', va='center', transform=ax_ad_box.transAxes, color='white')
                ax_ad_box.set_yticks([])
                for spine_pos in ['top', 'right', 'left', 'bottom']: ax_ad_box.spines[spine_pos].set_visible(False)
            self.ad_canvas_box.draw()
        except Exception as e: self.log_message(f"Error updating AD box plot: {e}")

        try:
            self.ws_figure_line.clear()
            ax_ws_line = self.ws_figure_line.add_subplot(111)
            ax_ws_line.set_facecolor('none')
            ws_data_list = list(self.ws_data)
            ws_plot_data = ws_data_list[-self.record_count:]
            ws_time_diffs_line = [round(d['time_diff'] * 1000, 1) for d in ws_plot_data]
            start_index_ws = max(0, len(ws_data_list) - self.record_count)
            ws_indices_line = range(start_index_ws + 1, start_index_ws + len(ws_plot_data) + 1)
            ws_colors_line = [self.get_color(diff) for diff in ws_time_diffs_line]

            if ws_time_diffs_line:
                ax_ws_line.scatter(ws_indices_line, ws_time_diffs_line, c=[color.name() for color in ws_colors_line], s=80, edgecolors='black', alpha=0.8)
                mean_value_ws = statistics.mean(ws_time_diffs_line)
                ax_ws_line.axhline(mean_value_ws, color='cyan', linestyle='--', linewidth=1.5, label=f'平均值: {mean_value_ws:.1f}ms')
                ax_ws_line.axhline(0, color='white', linewidth=0.8, linestyle='-')
                ax_ws_line.legend(prop={'family': 'Microsoft YaHei', 'size': 9}, facecolor=(0,0,0,0.5), labelcolor='white')
                for spine_pos in ['bottom', 'left']: ax_ws_line.spines[spine_pos].set_color('white')
                for spine_pos in ['top', 'right']: ax_ws_line.spines[spine_pos].set_visible(False)
                ax_ws_line.tick_params(axis='x', colors='white')
                ax_ws_line.tick_params(axis='y', colors='white')
                ax_ws_line.xaxis.label.set_color('white')
                ax_ws_line.yaxis.label.set_color('white')
                ax_ws_line.title.set_color('white')
            else:
                ax_ws_line.text(0.5, 0.5, '无 WS 数据', ha='center', va='center', transform=ax_ws_line.transAxes, color='white')

            ax_ws_line.set_xlabel('操作次数', fontproperties="Microsoft YaHei", fontsize=10)
            ax_ws_line.set_ylabel('时间差 (ms)', fontproperties="Microsoft YaHei", fontsize=10)
            ax_ws_line.set_title(f'WS 急停时间差 (最近 {len(ws_plot_data)} 次)', fontproperties="Microsoft YaHei", fontsize=12)
            ax_ws_line.grid(True, linestyle='--', alpha=0.3, color='gray')
            self.ws_canvas_line.draw()
        except Exception as e: self.log_message(f"Error updating WS line plot: {e}")

        try:
            self.ws_figure_box.clear()
            ax_ws_box = self.ws_figure_box.add_subplot(111)
            ax_ws_box.set_facecolor('none')
            box_plot_count_ws = min(len(ws_data_list), self.record_count * self.box_plot_multiplier)
            ws_box_data = ws_data_list[-box_plot_count_ws:]
            ws_time_diffs_box = [round(d['time_diff'] * 1000, 1) for d in ws_box_data]

            if len(ws_time_diffs_box) >= 5:
                bp_ws = ax_ws_box.boxplot(ws_time_diffs_box, vert=False, patch_artist=True, showfliers=False, widths=0.6)
                for box in bp_ws['boxes']: box.set(color='#D95F02', linewidth=1.5, facecolor='#FF7F0E', alpha=0.7)
                for whisker in bp_ws['whiskers']: whisker.set(color='#D95F02', linewidth=1.5, linestyle='--')
                for cap in bp_ws['caps']: cap.set(color='#D95F02', linewidth=1.5)
                for median in bp_ws['medians']: median.set(color='#ffff99', linewidth=2)
                ax_ws_box.set_xlabel('时间差 (ms)', fontproperties="Microsoft YaHei", fontsize=10)
                ax_ws_box.set_title(f'WS 时间差分布 (最近 {len(ws_box_data)} 次)', fontproperties="Microsoft YaHei", fontsize=12)
                ax_ws_box.grid(True, linestyle='--', alpha=0.3, axis='x', color='gray')
                ax_ws_box.tick_params(axis='x', colors='white')
                ax_ws_box.tick_params(axis='y', colors='none', length=0)
                ax_ws_box.set_yticks([])
                ax_ws_box.xaxis.label.set_color('white')
                ax_ws_box.title.set_color('white')
                for spine_pos in ['top', 'right', 'left']: ax_ws_box.spines[spine_pos].set_visible(False)
                ax_ws_box.spines['bottom'].set_color('white')
            else:
                ax_ws_box.text(0.5, 0.5, 'WS 数据不足', ha='center', va='center', transform=ax_ws_box.transAxes, color='white')
                ax_ws_box.set_yticks([])
                for spine_pos in ['top', 'right', 'left', 'bottom']: ax_ws_box.spines[spine_pos].set_visible(False)
            self.ws_canvas_box.draw()
        except Exception as e: self.log_message(f"Error updating WS box plot: {e}")


    def show_detail_info(self, item):
        detail_info = item.data(Qt.UserRole)
        if detail_info and 'events' in detail_info:
            events = detail_info['events']
            message = "按键事件序列:\n" + "-"*20 + "\n"
            try:
                sorted_events = sorted(events, key=lambda x: x['time'])
                for event in sorted_events:
                    key = event.get('key', '?')
                    ev_type = event.get('event', '?')
                    time_str = event.get('time_str', '?')
                    message += f"{time_str} - {key}键 {ev_type}\n"
            except Exception as e:
                message += f"\nError formatting events: {e}"
            QMessageBox.information(self, "详细信息", message)
        else:
            QMessageBox.warning(self, "详细信息", "无法加载详细事件信息。")

    def format_time(self, timestamp):
        return f"{timestamp:.3f}s"

    @pyqtSlot(str, bool) 
    def update_key_state_display(self, key_char_mapped, is_pressed):
        label_mapping = {
            'A': self.a_key_label, 'D': self.d_key_label,
            'W': self.w_key_label, 'S': self.s_key_label
        }
        if key_char_mapped in label_mapping:
            label = label_mapping[key_char_mapped]
            physical_key = self.key_mappings.get(key_char_mapped, key_char_mapped) 
            
            label.setText(f"{physical_key}键 ({key_char_mapped}): {'按下' if is_pressed else '未按下'}")
            if is_pressed:
                label.setStyleSheet("""
                    QLabel {
                        background-color: #90EE90; border: 2px solid #000000; border-radius: 8px;
                        min-width: 100px; padding: 5px; color: #000000;
                    }
                """)
            else:
                label.setStyleSheet("""
                    QLabel {
                        background-color: #D3D3D3; border: 2px solid #000000; border-radius: 8px;
                        min-width: 100px; padding: 5px; color: #2E2E2E;
                    }
                """)

    def get_color(self, time_diff_ms):
        max_time_diff = self.filter_threshold
        normalized_diff = min(abs(time_diff_ms), max_time_diff) / max(max_time_diff, 1e-6)
        perfect_color = QColor(144, 238, 144)
        early_start_color = QColor(173, 216, 230); early_end_color = QColor(0, 0, 139)
        late_start_color = QColor(255, 182, 193); late_end_color = QColor(139, 0, 0)

        if abs(time_diff_ms) <= 2: return perfect_color
        elif time_diff_ms < 0: start_color, end_color = early_start_color, early_end_color
        else: start_color, end_color = late_start_color, late_end_color
        
        r = max(0.0, min(1.0, start_color.redF() + (end_color.redF() - start_color.redF()) * normalized_diff))
        g = max(0.0, min(1.0, start_color.greenF() + (end_color.greenF() - start_color.greenF()) * normalized_diff))
        b = max(0.0, min(1.0, start_color.blueF() + (end_color.blueF() - start_color.blueF()) * normalized_diff))
        return QColor.fromRgbF(r, g, b)

    def is_light_color(self, color):
        return (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000 > 128

    def show_recommendations(self):
        if not self.ad_data and not self.ws_data:
            QMessageBox.information(self, "急停建议", "暂无足够数据可供分析。")
            return
        recommendations = []
        min_data_points = 5
        for key_type_label, data_deque in [("AD", self.ad_data), ("WS", self.ws_data)]:
            if len(data_deque) >= min_data_points:
                filtered_data = [d['time_diff'] * 1000 for d in data_deque if abs(d['time_diff'] * 1000) <= self.filter_threshold]
                if len(filtered_data) >= min_data_points:
                    avg_diff = round(statistics.mean(filtered_data), 1)
                    stdev = round(statistics.stdev(filtered_data), 1) if len(filtered_data) > 1 else 0
                    rec = f"--- {key_type_label} 急停分析 (基于 {len(filtered_data)} 次有效记录) ---\n"
                    rec += f"平均时间差: {avg_diff:.1f}ms\n标准差 (稳定性): {stdev:.1f}ms\n\n"
                    if avg_diff < -5: rec += "趋势: 偏早 (反向键按得太快)\n建议: 尝试略微延迟按反向键的时机，或检查键盘设置 (如 Rapid Trigger 的触发点)。"
                    elif avg_diff > 5: rec += "趋势: 偏晚 (反向键按得太慢)\n建议: 尝试更快地按下反向键，或检查键盘设置 (如缩短触发键程)。"
                    else: rec += "趋势: 良好 (接近同步)\n建议: 继续保持！"
                    if stdev > 15: rec += "\n稳定性提示: 时间差波动较大，尝试更一致地执行急停操作。"
                    recommendations.append(rec)
                else: recommendations.append(f"--- {key_type_label} 急停分析 ---\n有效数据不足 ({len(filtered_data)}/{min_data_points})。")
            else: recommendations.append(f"--- {key_type_label} 急停分析 ---\n数据不足 ({len(data_deque)}/{min_data_points})。")
        QMessageBox.information(self, "急停建议", "\n\n".join(recommendations))

    def show_instructions_dialog(self):
        """ Displays the custom instructions dialog. """
        dialog = InstructionsDialog(self)
        dialog.exec_()


    def show_key_mapping_dialog(self):
        dialog = KeyMappingDialog(self.key_mappings.copy(), self) 
        if dialog.exec_() == QDialog.Accepted:
            new_mappings = dialog.get_mappings()
            if len(set(new_mappings.values())) != len(new_mappings.values()):
                QMessageBox.warning(self, "映射错误", "映射的按键必须唯一。")
                return
            if any(not k for k in new_mappings.values()):
                QMessageBox.warning(self, "映射错误", "映射的按键不能为空。")
                return

            self.key_mappings = new_mappings
            self.reverse_key_mappings = {v: k for k, v in self.key_mappings.items()}
            self.log_message(f"按键映射已更新: {self.key_mappings}")
            self.update_key_labels_signal.emit() 
            QMessageBox.information(self, "按键映射", "按键映射已成功更新！")


    @pyqtSlot(str, int)
    def start_timer(self, key_type, interval):
        if key_type in self.timers:
            safe_interval = max(1, interval)
            self.timers[key_type].start(safe_interval)
            self.log_message(f"启动 {key_type} 等待计时器 ({safe_interval}ms)")

    @pyqtSlot(str)
    def stop_timer(self, key_type):
        if key_type in self.timers and self.timers[key_type].isActive():
            self.timers[key_type].stop()

    def reset_quick_stop(self, key_type):
        if key_type in self.waiting_for_opposite_key:
            timer_interval = self.timers[key_type].interval()
            
            key_released_orig = self.waiting_for_opposite_key[key_type]['key_released_orig']
            expected_key_mapped = self.waiting_for_opposite_key[key_type]['key']
            expected_key_orig = self.key_mappings[expected_key_mapped]

            self.log_message(f"超时 ({timer_interval}ms): 松开 {key_released_orig} 后未及时按下 {expected_key_orig} (映射为 {expected_key_mapped})。取消 {key_type} 等待状态。")
            del self.waiting_for_opposite_key[key_type]
            if not any(state['pressed'] for state in self.key_state.values()):
                if self.in_quick_stop_cooldown:
                    self.in_quick_stop_cooldown = False
                    self.log_message("所有按键已释放 (超时后检查)，重置急停冷却状态。")

    def resizeEvent(self, event):
        if hasattr(self, 'background_label') and self.background_label:
            self.background_label.setGeometry(self.centralWidget().rect())
        super().resizeEvent(event)

    def refresh(self):
        self.log_message("刷新操作已触发。")
        self.ad_data.clear(); self.ws_data.clear()
        self.history_list.clear(); self.output_list.clear()
        self.key_state = {k: {'pressed': False, 'time': None} for k in self.key_state}
        self.waiting_for_opposite_key.clear()
        self.in_quick_stop_cooldown = False
        self.last_record_time = 0
        for timer in self.timers.values(): timer.stop()
        
        self.update_key_labels_signal.emit() 
        for key_char_mapped in ['A', 'D', 'W', 'S']: 
             self.key_state_signal.emit(key_char_mapped, False)


        self.feedback_label.setText("请模拟自己PEEK时进行AD和WS急停")
        self.feedback_label.setStyleSheet("QLabel { color: #FFFFFF; background-color: #2E2E2E; border-radius: 10px; padding: 15px; }")
        self.update_plot()
        self.recommendations_button.hide()
        self.log_message("界面和数据已刷新。")

    def set_record_count(self):
        options = ["10次", "20次", "50次", "100次", "200次"]
        current_option = f"{self.record_count}次"
        if current_option not in options: options.insert(0, current_option)
        dialog = OptionDialog("选择图表记录次数", options, self)
        dialog.set_selected_option(current_option)
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected_option()
            if selected:
                try:
                    new_count = int(selected.replace("次", ""))
                    if new_count > 0:
                        self.record_count = new_count
                        self.log_message(f"图表记录次数已设置为 {self.record_count} 次。")
                        self.update_plot()
                    else: QMessageBox.warning(self, "无效输入", "记录次数必须大于 0。")
                except ValueError: QMessageBox.warning(self, "无效输入", "无法解析选择的次数。")

    def set_filter_threshold(self):
        options = ["20ms", "40ms", "60ms", "80ms", "100ms", "120ms", "150ms", "200ms"]
        current_option = f"{self.filter_threshold}ms"
        if current_option not in options: options.insert(0, current_option)
        dialog = OptionDialog("选择时间差过滤阈值 (ms)", options, self)
        dialog.set_selected_option(current_option)
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected_option()
            if selected:
                try:
                    new_threshold = int(selected.replace("ms", ""))
                    if new_threshold >= 0:
                        self.filter_threshold = new_threshold
                        self.log_message(f"过滤阈值已设置为 {self.filter_threshold}ms。")
                    else: QMessageBox.warning(self, "无效输入", "过滤阈值必须大于或等于 0。")
                except ValueError: QMessageBox.warning(self, "无效输入", "无法解析选择的阈值。")

    def closeEvent(self, event):
        self.log_message("关闭应用程序...")
        if hasattr(self, 'listener') and self.listener and self.listener.is_alive():
            try:
                self.listener.stop()
                self.listener.join(timeout=0.5)
                if self.listener.is_alive(): self.log_message("警告：键盘监听器线程未能及时停止。")
                else: self.log_message("键盘监听器已停止。")
            except Exception as e: self.log_message(f"停止监听器时出错: {e}")
        event.accept()

def main():
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setApplicationName("CS2急停评估工具")
    QApplication.setOrganizationName("CS2ToolDev")

    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"发生未处理的错误: {e}")
        import traceback
        traceback.print_exc()
        QMessageBox.critical(None, "严重错误", f"应用程序遇到无法处理的错误并即将退出。\n\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
