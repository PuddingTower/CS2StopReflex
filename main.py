import sys
import os
import time
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QHBoxLayout, QListWidget, QMessageBox, QListWidgetItem, QPushButton, 
    QSizePolicy, QSpacerItem, QGridLayout, QGroupBox, QDialog, 
    QRadioButton, QButtonGroup, QShortcut
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QSize, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon, QDesktopServices, QPixmap, QPainter, QKeySequence
from pynput import keyboard
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import statistics
from matplotlib import rcParams

rcParams['font.sans-serif'] = ['Microsoft YaHei']
rcParams['axes.unicode_minus'] = False

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):  # 如果是打包后的可执行文件
        current_dir = sys._MEIPASS  # 打包后的临时目录
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, relative_path)

class BackgroundLabel(QLabel):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.pixmap_original = QPixmap(image_path)
        self.opacity = 0.8
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setScaledContents(False)
        self.update_pixmap()

    def set_opacity(self, opacity):
        self.opacity = opacity
        self.update_pixmap()

    def update_pixmap(self):
        if self.pixmap_original.isNull():
            return
        size = self.size()
        scaled_pixmap = self.pixmap_original.scaled(
            size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )

        pixmap_with_opacity = QPixmap(size)
        pixmap_with_opacity.fill(Qt.transparent)
        painter = QPainter(pixmap_with_opacity)
        painter.setOpacity(self.opacity)

        x = (size.width() - scaled_pixmap.width()) // 2
        y = (size.height() - scaled_pixmap.height()) // 2

        painter.drawPixmap(x, y, scaled_pixmap)

        painter.setOpacity(0.3)
        painter.fillRect(pixmap_with_opacity.rect(), QColor(255, 255, 255))
        painter.end()
        super().setPixmap(pixmap_with_opacity)

    def resizeEvent(self, event):
        self.update_pixmap()
        super().resizeEvent(event)

class OptionDialog(QDialog):
    def __init__(self, title, options, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.selected_option = None

        layout = QVBoxLayout()

        self.button_group = QButtonGroup(self)
        for option in options:
            radio_button = QRadioButton(option)
            self.button_group.addButton(radio_button)
            layout.addWidget(radio_button)
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

    def get_selected_option(self):
        selected_button = self.button_group.checkedButton()
        if selected_button:
            return selected_button.text()
        return None

class MainWindow(QMainWindow):
    feedback_signal = pyqtSignal(str, QColor)
    history_signal = pyqtSignal(str, float, float, dict, QColor)
    key_state_signal = pyqtSignal(str, bool)
    start_timer_signal = pyqtSignal(str)
    stop_timer_signal = pyqtSignal(str)
    key_press_signal = pyqtSignal(str, float)
    key_release_signal = pyqtSignal(str, float)
    
    # 添加新的日志信号
    log_signal = pyqtSignal(str)

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
            self.background_label = BackgroundLabel(background_path, self)
            self.background_label.setGeometry(self.rect())
            self.background_label.set_opacity(0.8)
            self.background_label.lower()
        else:
            print("背景图片 background.png 未找到。")

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
                color: #FFFFFF;
                background-color: #2E2E2E;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        left_layout.addWidget(self.feedback_label)

        key_status_layout = QGridLayout()

        self.w_key_label = self.create_key_label("W键：未按下", font_key)
        key_status_layout.addWidget(self.w_key_label, 0, 1)

        self.a_key_label = self.create_key_label("A键：未按下", font_key)
        key_status_layout.addWidget(self.a_key_label, 1, 0)

        self.s_key_label = self.create_key_label("S键：未按下", font_key)
        key_status_layout.addWidget(self.s_key_label, 1, 1)

        self.d_key_label = self.create_key_label("D键：未按下", font_key)
        key_status_layout.addWidget(self.d_key_label, 1, 2)

        left_layout.addLayout(key_status_layout)

        # 历史记录列表
        self.history_list = QListWidget()
        self.history_list.setFont(font_small)
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid #CCCCCC;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: #ADD8E6;
            }
        """)
        self.history_list.itemClicked.connect(self.show_detail_info)
        left_layout.addWidget(self.history_list, stretch=2)  # 调整伸缩因子

        # 新增的输出日志列表
        self.output_list = QListWidget()
        self.output_list.setFont(font_small)
        self.output_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid #CCCCCC;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: #ADD8E6;
            }
        """)
        left_layout.addWidget(self.output_list, stretch=1)  # 添加到左侧布局，伸缩因子为1

        left_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        help_button_layout = QHBoxLayout()
        help_button_layout.addStretch()

        self.info_button = QPushButton("i")
        self.info_button.setFont(QFont("Arial", 16, QFont.Bold))
        self.info_button.setFixedSize(40, 40)
        self.info_button.setStyleSheet("""
            QPushButton {
                background-color: #2E2E2E;
                color: #FFFFFF;
                border: none;
                border-radius: 20px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        self.info_button.clicked.connect(self.show_recommendations)
        self.info_button.hide()
        help_button_layout.addWidget(self.info_button)

        self.question_button = QPushButton("❓")
        self.question_button.setFont(QFont("Arial", 16, QFont.Bold))
        self.question_button.setFixedSize(40, 40)
        self.question_button.setStyleSheet("""
            QPushButton {
                background-color: #2E2E2E;
                color: #FFFFFF;
                border: none;
                border-radius: 20px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        self.question_button.clicked.connect(self.open_help_link)
        self.question_button.hide()
        help_button_layout.addWidget(self.question_button)

        # 添加F5刷新按钮
        self.refresh_button = QPushButton("F5")
        self.refresh_button.setFont(QFont("Arial", 14, QFont.Bold))
        self.refresh_button.setFixedSize(40, 40)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #2E2E2E;
                color: #FFFFFF;
                border: none;
                border-radius: 20px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        self.refresh_button.clicked.connect(self.refresh)
        help_button_layout.addWidget(self.refresh_button)

        # 添加自定义记录次数按钮
        self.record_count_button = QPushButton("记录次数")
        self.record_count_button.setFont(QFont("Arial", 12))
        self.record_count_button.setFixedSize(100, 40)
        self.record_count_button.setStyleSheet("""
            QPushButton {
                background-color: #2E2E2E;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        self.record_count_button.clicked.connect(self.set_record_count)
        help_button_layout.addWidget(self.record_count_button)

        # 添加过滤阈值按钮
        self.filter_threshold_button = QPushButton("过滤阈值")
        self.filter_threshold_button.setFont(QFont("Arial", 12))
        self.filter_threshold_button.setFixedSize(100, 40)
        self.filter_threshold_button.setStyleSheet("""
            QPushButton {
                background-color: #2E2E2E;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        self.filter_threshold_button.clicked.connect(self.set_filter_threshold)
        help_button_layout.addWidget(self.filter_threshold_button)

        left_layout.addLayout(help_button_layout)

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
            QMainWindow {
                background-color: transparent;
            }
            QLabel {
                color: #2E2E2E;
            }
            QListWidget {
                background-color: rgba(255, 255, 255, 180);
            }
        """)

        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

        self.key_state = {
            'A': {'pressed': False, 'time': None},
            'D': {'pressed': False, 'time': None},
            'W': {'pressed': False, 'time': None},
            'S': {'pressed': False, 'time': None}
        }
        self.waiting_for_opposite_key = {}
        self.ad_data = deque(maxlen=200)  # 修改maxlen为200
        self.ws_data = deque(maxlen=200)  # 修改maxlen为200
        self.last_record_time = 0
        self.min_time_between_records = 0.05

        self.in_quick_stop = False

        self.feedback_signal.connect(self.update_feedback)
        self.history_signal.connect(self.update_history)
        self.key_state_signal.connect(self.update_key_state_display)
        self.start_timer_signal.connect(self.start_timer)
        self.stop_timer_signal.connect(self.stop_timer)
        self.key_press_signal.connect(self.on_key_press_main_thread)
        self.key_release_signal.connect(self.on_key_release_main_thread)
        
        # 连接新的日志信号到槽函数
        self.log_signal.connect(self.append_log)

        self.timers = {
            'AD': QTimer(self),
            'WS': QTimer(self)
        }
        self.timers['AD'].setSingleShot(True)
        # 将定时器从150ms改为120ms
        self.timers['AD'].timeout.connect(lambda: self.reset_quick_stop('AD'))
        self.timers['WS'].setSingleShot(True)
        self.timers['WS'].timeout.connect(lambda: self.reset_quick_stop('WS'))

        # 添加F5快捷键
        self.f5_shortcut = QShortcut(QKeySequence("F5"), self)
        self.f5_shortcut.activated.connect(self.refresh)

        # 初始化自定义参数
        self.record_count = 10  # 默认箱线图记录次数
        self.filter_threshold = 120  # 默认过滤阈值(ms)

    def create_key_label(self, text, font_key):
        label = QLabel(text)
        label.setFont(font_key)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                background-color: #D3D3D3;
                border: 2px solid #000000;
                border-radius: 8px;
            }
        """)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return label

    # 新增槽函数，用于将日志添加到output_list
    @pyqtSlot(str)
    def append_log(self, message):
        self.output_list.addItem(message)
        self.output_list.scrollToBottom()
        # 可选：限制日志条目数量，例如最多100条
        if self.output_list.count() > 100:
            self.output_list.takeItem(0)

    # 新增日志记录函数，同时输出到控制台和GUI
    def log_message(self, msg):
        print(msg)
        self.log_signal.emit(msg)

    def on_press(self, key):
        try:
            key_char = key.char.upper()
            if key_char in ['A', 'D', 'W', 'S']:
                press_time = time.perf_counter()
                self.key_press_signal.emit(key_char, press_time)
        except AttributeError:
            pass

    def on_release(self, key):
        try:
            key_char = key.char.upper()
            if key_char in ['A', 'D', 'W', 'S']:
                release_time = time.perf_counter()
                self.key_release_signal.emit(key_char, release_time)
        except AttributeError:
            pass

    @pyqtSlot(str, float)
    def on_key_press_main_thread(self, key_char, press_time):
        if not self.key_state[key_char]['pressed']:
            self.key_state[key_char]['pressed'] = True
            self.key_state[key_char]['time'] = press_time
            self.key_state_signal.emit(key_char, True)

            # 使用新的日志函数
            self.log_message(f"按下: {key_char} at {press_time}")

            key_type = self.get_key_type(key_char)
            if not self.in_quick_stop and key_type in self.waiting_for_opposite_key:
                current_time = time.perf_counter()
                if current_time - self.last_record_time < self.min_time_between_records:
                    self.log_message("操作过于频繁，忽略此次按键。")
                    return

                expected_opposite_key = self.waiting_for_opposite_key[key_type]['key']
                release_time = self.waiting_for_opposite_key[key_type]['release_time']
                time_diff = self.key_state[key_char]['time'] - release_time

                # 将时间差从秒转换为毫秒并保留一位小数
                time_diff_ms = round(time_diff * 1000, 1)

                self.log_message(f"按键类型: {key_type}, 时间差: {time_diff_ms}ms")

                # 将阈值从200ms改为根据过滤阈值
                if abs(time_diff) > self.filter_threshold / 1000:
                    self.log_message("时间差超过阈值，忽略此次按键。")
                    del self.waiting_for_opposite_key[key_type]
                    return

                color = self.get_color(time_diff_ms)

                if abs(time_diff_ms) <= 2:
                    timing = '完美急停'
                elif time_diff_ms < 0:
                    timing = '按早了'
                else:
                    timing = '按晚了'

                feedback = f"[{key_type}] {timing}：松开{self.waiting_for_opposite_key[key_type]['key_released']}后{abs(time_diff_ms):.1f}ms按下了{key_char}"

                detail_info = {
                    'events': self.waiting_for_opposite_key[key_type]['events'] + [
                        {'key': key_char, 'event': '按下', 'time': self.key_state[key_char]['time'], 'time_str': self.format_time(self.key_state[key_char]['time'])}
                    ]
                }

                if key_type == 'AD':
                    self.feedback_signal.emit(feedback, color)
                    self.history_signal.emit('AD', self.key_state[key_char]['time'], time_diff, detail_info, color)
                    if abs(time_diff_ms) <= self.filter_threshold:
                        self.ad_data.append({'time': self.key_state[key_char]['time'], 'time_diff': time_diff})
                        self.log_message(f"记录 AD 急停: 时间差 {time_diff_ms}ms")
                elif key_type == 'WS':
                    self.feedback_signal.emit(feedback, color)
                    self.history_signal.emit('WS', self.key_state[key_char]['time'], time_diff, detail_info, color)
                    if abs(time_diff_ms) <= self.filter_threshold:
                        self.ws_data.append({'time': self.key_state[key_char]['time'], 'time_diff': time_diff})
                        self.log_message(f"记录 WS 急停: 时间差 {time_diff_ms}ms")

                self.last_record_time = current_time
                self.in_quick_stop = True
                del self.waiting_for_opposite_key[key_type]
                self.stop_timer_signal.emit(key_type)

    @pyqtSlot(str, float)
    def on_key_release_main_thread(self, key_char, release_time):
        if self.key_state[key_char]['pressed']:
            self.key_state[key_char]['pressed'] = False
            self.key_state_signal.emit(key_char, False)
            self.log_message(f"松开: {key_char} at {release_time}")
            self.process_key_event(key_char, release_time)

            if not any(state['pressed'] for state in self.key_state.values()):
                self.in_quick_stop = False
                self.log_message("所有按键已释放，重置急停状态。")

    def process_key_event(self, key_released, release_time):
        key_type = self.get_key_type(key_released)
        if key_type == 'AD':
            opposite_key = 'D' if key_released == 'A' else 'A'
        elif key_type == 'WS':
            opposite_key = 'S' if key_released == 'W' else 'W'
        else:
            opposite_key = None

        if opposite_key is None:
            return

        key_state = self.key_state[opposite_key]

        if key_state['pressed'] and not self.in_quick_stop:
            time_diff = key_state['time'] - release_time
            time_diff_ms = round(time_diff * 1000, 1)
            self.log_message(f"按键类型: {key_type}, 时间差: {time_diff_ms}ms")

            # 将阈值从200ms改为根据过滤阈值
            if abs(time_diff) > self.filter_threshold / 1000:
                self.log_message(f"时间差 {time_diff_ms}ms 超过阈值，忽略此次按键。")
                return

            color = self.get_color(time_diff_ms)

            if abs(time_diff_ms) <= 2:
                timing = '完美急停'
            elif time_diff_ms < 0:
                timing = '按早了'
            else:
                timing = '按晚了'

            feedback = f"[{key_type}] {timing}：未松开{key_released}就按下了{opposite_key}，{abs(time_diff_ms):.1f}ms"

            detail_info = {
                'events': [
                    {'key': key_released, 'event': '松开', 'time': release_time, 'time_str': self.format_time(release_time)},
                    {'key': opposite_key, 'event': '按下', 'time': key_state['time'], 'time_str': self.format_time(key_state['time'])}
                ]
            }

            if key_type == 'AD':
                self.feedback_signal.emit(feedback, color)
                self.history_signal.emit('AD', key_state['time'], time_diff, detail_info, color)
                if abs(time_diff_ms) <= self.filter_threshold:
                    self.ad_data.append({'time': key_state['time'], 'time_diff': time_diff})
                    self.log_message(f"记录 AD 急停: 时间差 {time_diff_ms}ms")
            elif key_type == 'WS':
                self.feedback_signal.emit(feedback, color)
                self.history_signal.emit('WS', key_state['time'], time_diff, detail_info, color)
                if abs(time_diff_ms) <= self.filter_threshold:
                    self.ws_data.append({'time': key_state['time'], 'time_diff': time_diff})
                    self.log_message(f"记录 WS 急停: 时间差 {time_diff_ms}ms")

            self.last_record_time = time.perf_counter()
            self.in_quick_stop = True
            self.stop_timer_signal.emit(key_type)
        else:
            key_type = self.get_key_type(key_released)
            opposite_key = 'D' if key_released == 'A' else 'A' if key_type == 'AD' else 'S' if key_released == 'W' else 'W'
            self.waiting_for_opposite_key[key_type] = {
                'key': opposite_key,
                'release_time': release_time,
                'key_released': key_released,
                'events': [
                    {'key': key_released, 'event': '松开', 'time': release_time, 'time_str': self.format_time(release_time)}
                ]
            }
            self.log_message(f"等待按下 {opposite_key} 以完成急停。")
            self.start_timer_signal.emit(key_type)

    def get_key_type(self, key_char):
        if key_char in ['A', 'D']:
            return 'AD'
        elif key_char in ['W', 'S']:
            return 'WS'
        else:
            return None

    def update_feedback(self, feedback, color):
        self.feedback_label.setText(feedback)
        self.feedback_label.setStyleSheet(f"""
            QLabel {{
                color: #FFFFFF;
                background-color: {color.name()};
                border-radius: 10px;
                padding: 15px;
            }}
        """)

    def update_history(self, key_type, press_time, time_diff, detail_info, color):
        time_diff_ms = round(time_diff * 1000, 1)
        time_str = self.format_time(press_time)
        item_text = f"[{key_type}] {time_str} - 时间差：{time_diff_ms:.1f}ms"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, detail_info)
        item.setBackground(QBrush(color))

        if self.is_light_color(color):
            item.setForeground(QBrush(QColor("#000000")))
        else:
            item.setForeground(QBrush(QColor("#FFFFFF")))
        self.history_list.addItem(item)

        if self.history_list.count() > 25:
            self.history_list.takeItem(0)

        # 自动滚动到最新记录
        self.history_list.scrollToBottom()

        if len(self.ad_data) >= 20 or len(self.ws_data) >= 20:
            if not self.info_button.isVisible():
                self.info_button.show()
            if not self.question_button.isVisible():
                self.question_button.show()

        self.update_plot()

    def update_plot(self):
        # 更新AD图表
        self.ad_figure_line.clear()
        ax_ad = self.ad_figure_line.add_subplot(111)
        ax_ad.set_facecolor('none')  # 设置轴背景透明

        ad_time_diffs = [round(d['time_diff'] * 1000, 1) for d in list(self.ad_data)[-self.record_count:]]
        ad_jump_numbers = range(len(self.ad_data) - len(ad_time_diffs) + 1, len(self.ad_data) + 1)

        ad_colors = [self.get_color(diff) for diff in ad_time_diffs]

        scatter_ad = ax_ad.scatter(ad_jump_numbers, ad_time_diffs, c=[color.name() for color in ad_colors], s=100, edgecolors='black')

        if ad_time_diffs:
            mean_value_ad = statistics.mean(ad_time_diffs)
            ax_ad.axhline(mean_value_ad, color='blue', linestyle='--', linewidth=2, label=f'平均值：{mean_value_ad:.1f}ms')

            ax_ad.axhline(0, color='black', linewidth=1, linestyle='-')

        ax_ad.set_xticks(ad_jump_numbers)
        ax_ad.set_xlabel('操作次数', fontproperties="Microsoft YaHei", fontsize=12)
        ax_ad.set_ylabel('时间差（ms）', fontproperties="Microsoft YaHei", fontsize=12)
        ax_ad.set_title('AD提前或滞后时间差（最近{}次）'.format(self.record_count), fontproperties="Microsoft YaHei", fontsize=14)
        ax_ad.legend(prop={'family': 'Microsoft YaHei', 'size': 10})

        ax_ad.spines['top'].set_visible(False)
        ax_ad.spines['right'].set_visible(False)
        ax_ad.grid(True, linestyle='--', alpha=0.6)

        self.ad_canvas_line.draw()

        # 更新AD箱线图
        if len(self.ad_data) >= self.record_count * 2:
            self.ad_figure_box.clear()
            ax_ad_box = self.ad_figure_box.add_subplot(111)
            ax_ad_box.set_facecolor('none')  # 设置轴背景透明

            ad_time_diffs_box = [round(d['time_diff'] * 1000, 1) for d in list(self.ad_data)[-self.record_count * 2:]]  # 使用更大的数据集

            bp_ad = ax_ad_box.boxplot(ad_time_diffs_box, vert=False, patch_artist=True, showfliers=False)

            for box in bp_ad['boxes']:
                box.set(color='#7570b3', linewidth=2)
                box.set(facecolor='#1b9e77')

            for whisker in bp_ad['whiskers']:
                whisker.set(color='#7570b3', linewidth=2)

            for cap in bp_ad['caps']:
                cap.set(color='#7570b3', linewidth=2)

            for median in bp_ad['medians']:
                median.set(color='#b2df8a', linewidth=2)

            ax_ad_box.set_xlabel('时间差（ms）', fontproperties="Microsoft YaHei", fontsize=12)
            ax_ad_box.set_title('AD时间差箱线图（最近{}次）'.format(self.record_count * 2), fontproperties="Microsoft YaHei", fontsize=14)

            ax_ad_box.grid(True, linestyle='--', alpha=0.6)

            ax_ad_box.spines['top'].set_visible(False)
            ax_ad_box.spines['right'].set_visible(False)

            self.ad_canvas_box.draw()
        else:
            self.ad_figure_box.clear()
            self.ad_canvas_box.draw()

        # 更新WS图表
        self.ws_figure_line.clear()
        ax_ws = self.ws_figure_line.add_subplot(111)
        ax_ws.set_facecolor('none')  # 设置轴背景透明

        ws_time_diffs = [round(d['time_diff'] * 1000, 1) for d in list(self.ws_data)[-self.record_count:]]
        ws_jump_numbers = range(len(self.ws_data) - len(ws_time_diffs) + 1, len(self.ws_data) + 1)

        ws_colors = [self.get_color(diff) for diff in ws_time_diffs]

        scatter_ws = ax_ws.scatter(ws_jump_numbers, ws_time_diffs, c=[color.name() for color in ws_colors], s=100, edgecolors='black')

        if ws_time_diffs:
            mean_value_ws = statistics.mean(ws_time_diffs)
            ax_ws.axhline(mean_value_ws, color='blue', linestyle='--', linewidth=2, label=f'平均值：{mean_value_ws:.1f}ms')

            ax_ws.axhline(0, color='black', linewidth=1, linestyle='-')

        ax_ws.set_xticks(ws_jump_numbers)
        ax_ws.set_xlabel('操作次数', fontproperties="Microsoft YaHei", fontsize=12)
        ax_ws.set_ylabel('时间差（ms）', fontproperties="Microsoft YaHei", fontsize=12)
        ax_ws.set_title('WS提前或滞后时间差（最近{}次）'.format(self.record_count), fontproperties="Microsoft YaHei", fontsize=14)
        ax_ws.legend(prop={'family': 'Microsoft YaHei', 'size': 10})

        ax_ws.spines['top'].set_visible(False)
        ax_ws.spines['right'].set_visible(False)
        ax_ws.grid(True, linestyle='--', alpha=0.6)

        self.ws_canvas_line.draw()

        # 更新WS箱线图
        if len(self.ws_data) >= self.record_count * 2:
            self.ws_figure_box.clear()
            ax_ws_box = self.ws_figure_box.add_subplot(111)
            ax_ws_box.set_facecolor('none')  # 设置轴背景透明

            ws_time_diffs_box = [round(d['time_diff'] * 1000, 1) for d in list(self.ws_data)[-self.record_count * 2:]]  # 使用更大的数据集

            bp_ws = ax_ws_box.boxplot(ws_time_diffs_box, vert=False, patch_artist=True, showfliers=False)

            for box in bp_ws['boxes']:
                box.set(color='#D95F02', linewidth=2)
                box.set(facecolor='#FF7F0E')

            for whisker in bp_ws['whiskers']:
                whisker.set(color='#D95F02', linewidth=2)

            for cap in bp_ws['caps']:
                cap.set(color='#D95F02', linewidth=2)

            for median in bp_ws['medians']:
                median.set(color='#b2df8a', linewidth=2)

            ax_ws_box.set_xlabel('时间差（ms）', fontproperties="Microsoft YaHei", fontsize=12)
            ax_ws_box.set_title('WS时间差箱线图（最近{}次）'.format(self.record_count * 2), fontproperties="Microsoft YaHei", fontsize=14)

            ax_ws_box.grid(True, linestyle='--', alpha=0.6)

            ax_ws_box.spines['top'].set_visible(False)
            ax_ws_box.spines['right'].set_visible(False)

            self.ws_canvas_box.draw()
        else:
            self.ws_figure_box.clear()
            self.ws_canvas_box.draw()

    def show_detail_info(self, item):
        detail_info = item.data(Qt.UserRole)
        if detail_info:
            events = detail_info['events']
            message = ""
            for event in events:
                message += f"{event['time_str']} - {event['key']}键 {event['event']}\n"
            QMessageBox.information(self, "详细信息", message)

    def format_time(self, timestamp):
        return f"{timestamp:.3f}秒"

    def update_key_state_display(self, key_char, is_pressed):
        label_mapping = {
            'A': self.a_key_label,
            'D': self.d_key_label,
            'W': self.w_key_label,
            'S': self.s_key_label
        }

        if key_char in label_mapping:
            label = label_mapping[key_char]
            if is_pressed:
                label.setText(f"{key_char}键：按下")
                label.setStyleSheet("""
                    QLabel {
                        background-color: #90EE90;
                        border: 2px solid #000000;
                        border-radius: 8px;
                    }
                """)
            else:
                label.setText(f"{key_char}键：未按下")
                label.setStyleSheet("""
                    QLabel {
                        background-color: #D3D3D3;
                        border: 2px solid #000000;
                        border-radius: 8px;
                    }
                """)

    def get_color(self, time_diff_ms):
        max_time_diff = self.filter_threshold  # 使用用户设置的过滤阈值
        normalized_diff = min(abs(time_diff_ms), max_time_diff) / max_time_diff

        if time_diff_ms < 0:
            start_color = QColor(173, 216, 230)
            end_color = QColor(0, 0, 139)
        elif time_diff_ms > 0:
            start_color = QColor(255, 182, 193)
            end_color = QColor(139, 0, 0)
        else:
            return QColor(144, 238, 144)

        r = start_color.red() + (end_color.red() - start_color.red()) * normalized_diff
        g = start_color.green() + (end_color.green() - start_color.green()) * normalized_diff
        b = start_color.blue() + (end_color.blue() - start_color.blue()) * normalized_diff

        return QColor(int(round(r)), int(round(g)), int(round(b)))

    def is_light_color(self, color):
        brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
        return brightness > 128

    def open_help_link(self):
        QDesktopServices.openUrl(QUrl("https://space.bilibili.com/13723713"))

    def show_recommendations(self):
        if not self.ad_data and not self.ws_data:
            QMessageBox.information(self, "急停建议", "暂无数据可供分析。")
            return

        recommendations = []

        if self.ad_data:
            filtered_ad_data = [d['time_diff'] for d in self.ad_data if abs(d['time_diff'] * 1000) <= self.filter_threshold]
            if not filtered_ad_data:
                QMessageBox.information(self, "急停建议", "AD数据均被过滤，无法提供建议。")
                return

            avg_time_diff_ad = statistics.mean(filtered_ad_data)
            avg_time_diff_ms_ad = round(avg_time_diff_ad * 1000, 2)

            if avg_time_diff_ms_ad < -5:
                recommendation_ad = (
                    f"您的 AD 平均时间差为 {avg_time_diff_ms_ad:.2f}ms，偏早。\n\n"
                    "建议：\n"
                    "- 使用更短的反应时间 (RT)。\n"
                    "- 使用更长的死区（触发键程）。\n"
                    "- 考虑开启 Snaptap 相关辅助功能。"
                )
            elif avg_time_diff_ms_ad > 5:
                recommendation_ad = (
                    f"您的 AD 平均时间差为 {avg_time_diff_ms_ad:.2f}ms，偏晚。\n\n"
                    "建议：\n"
                    "- 使用更长的反应时间 (RT)。\n"
                    "- 使用更短的死区（触发键程）。"
                )
            else:
                recommendation_ad = (
                    f"您的 AD 平均时间差为 {avg_time_diff_ms_ad:.2f}ms。\n\n"
                    "您表现出色！继续保持您的 AD 急停技巧！"
                )
            recommendations.append(recommendation_ad)

        if self.ws_data:
            filtered_ws_data = [d['time_diff'] for d in self.ws_data if abs(d['time_diff'] * 1000) <= self.filter_threshold]
            if not filtered_ws_data:
                QMessageBox.information(self, "急停建议", "WS数据均被过滤，无法提供建议。")
                return

            avg_time_diff_ws = statistics.mean(filtered_ws_data)
            avg_time_diff_ms_ws = round(avg_time_diff_ws * 1000, 2)

            if avg_time_diff_ms_ws < -5:
                recommendation_ws = (
                    f"您的 WS 平均时间差为 {avg_time_diff_ms_ws:.2f}ms，偏早。\n\n"
                    "建议：\n"
                    "- 使用更短的反应时间 (RT)。\n"
                    "- 使用更长的死区（触发键程）。\n"
                    "- 考虑开启 Snaptap 相关辅助功能。"
                )
            elif avg_time_diff_ms_ws > 5:
                recommendation_ws = (
                    f"您的 WS 平均时间差为 {avg_time_diff_ms_ws:.2f}ms，偏晚。\n\n"
                    "建议：\n"
                    "- 使用更长的反应时间 (RT)。\n"
                    "- 使用更短的死区（触发键程）。"
                )
            else:
                recommendation_ws = (
                    f"您的 WS 平均时间差为 {avg_time_diff_ms_ws:.2f}ms。\n\n"
                    "您表现出色！继续保持您的 WS 急停技巧！"
                )
            recommendations.append(recommendation_ws)

        QMessageBox.information(self, "急停建议", "\n\n".join(recommendations))

    @pyqtSlot(str)
    def start_timer(self, key_type):
        if key_type in self.timers:
            self.timers[key_type].start(120)  # 将定时器从150ms改为120ms

    @pyqtSlot(str)
    def stop_timer(self, key_type):
        if key_type in self.timers:
            self.timers[key_type].stop()

    def reset_quick_stop(self, key_type):
        if key_type in self.waiting_for_opposite_key:
            # 将150ms改为120ms
            self.log_message(f"未在120ms内按下预期的反向按键，重置 {key_type} 急停状态。")
            del self.waiting_for_opposite_key[key_type]
            self.in_quick_stop = False

    def resizeEvent(self, event):
        if hasattr(self, 'background_label'):
            self.background_label.setGeometry(self.rect())
        super().resizeEvent(event)

    def refresh(self):
        """
        刷新图表和记录显示
        """
        self.log_message("刷新操作已触发。")
        self.update_plot()
        # 清除历史记录和输出日志
        self.history_list.clear()
        self.output_list.clear()
        # 清除数据
        self.ad_data.clear()
        self.ws_data.clear()
        # 重置急停状态
        self.in_quick_stop = False
        self.waiting_for_opposite_key.clear()
        # 更新键状态显示为未按下
        for key in self.key_state:
            if self.key_state[key]['pressed']:
                self.key_state[key]['pressed'] = False
                self.key_state_signal.emit(key, False)

    def set_record_count(self):
        dialog = OptionDialog("选择记录次数", ["5次", "20次", "50次", "100次"], self)  # 增加"50次"选项以匹配默认值
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected_option()
            if selected:
                self.record_count = int(selected.replace("次", ""))
                self.log_message(f"记录次数已设置为 {self.record_count} 次。")
                self.update_plot()

    def set_filter_threshold(self):
        dialog = OptionDialog("选择过滤阈值", ["20ms", "40ms", "60ms", "80ms", "100ms", "120ms"], self)
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected_option()
            if selected:
                self.filter_threshold = int(selected.replace("ms", ""))
                self.log_message(f"过滤阈值已设置为 {self.filter_threshold}ms。")
                self.update_plot()

    def closeEvent(self, event):
        # 关闭应用时停止监听器
        self.listener.stop()
        event.accept()

def main():
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()
