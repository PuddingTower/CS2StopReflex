import sys
import os
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QHBoxLayout, QListWidget, QMessageBox, QListWidgetItem, QPushButton, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon, QDesktopServices
from pynput import keyboard
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import statistics
from matplotlib import rcParams

rcParams['font.sans-serif'] = ['Microsoft YaHei']
rcParams['axes.unicode_minus'] = False

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

class MainWindow(QMainWindow):
    feedback_signal = pyqtSignal(str, QColor)
    history_signal = pyqtSignal(float, float, dict, QColor)
    key_state_signal = pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CS2急停评估工具")
        self.setGeometry(100, 100, 1400, 900)

        icon_path = resource_path("CS2.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print("图标文件 CS2.ico 未找到。")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        left_layout = QVBoxLayout()

        font_large = QFont("Microsoft YaHei", 18)
        font_small = QFont("Microsoft YaHei", 12)
        font_key = QFont("Microsoft YaHei", 14, QFont.Bold)

        self.feedback_label = QLabel("请模拟自己PEEK时进行AD大拉")
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

        key_status_layout = QHBoxLayout()

        self.a_key_label = QLabel("A键：未按下")
        self.a_key_label.setFont(font_key)
        self.a_key_label.setAlignment(Qt.AlignCenter)
        self.a_key_label.setStyleSheet("""
            QLabel {
                background-color: #D3D3D3;
                border: 2px solid #000000;
                border-radius: 8px;
            }
        """)
        self.a_key_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        key_status_layout.addWidget(self.a_key_label)

        self.d_key_label = QLabel("D键：未按下")
        self.d_key_label.setFont(font_key)
        self.d_key_label.setAlignment(Qt.AlignCenter)
        self.d_key_label.setStyleSheet("""
            QLabel {
                background-color: #D3D3D3;
                border: 2px solid #000000;
                border-radius: 8px;
            }
        """)
        self.d_key_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        key_status_layout.addWidget(self.d_key_label)

        left_layout.addLayout(key_status_layout)

        self.history_list = QListWidget()
        self.history_list.setFont(font_small)
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: #ADD8E6;
            }
        """)
        self.history_list.itemClicked.connect(self.show_detail_info)
        left_layout.addWidget(self.history_list, stretch=1)

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

        left_layout.addLayout(help_button_layout)

        right_layout = QVBoxLayout()

        self.figure_line = Figure(figsize=(6, 4))
        self.canvas_line = FigureCanvas(self.figure_line)
        right_layout.addWidget(self.canvas_line)

        self.figure_box = Figure(figsize=(6, 4))
        self.canvas_box = FigureCanvas(self.figure_box)
        right_layout.addWidget(self.canvas_box)

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 2)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #F0F0F0;
            }
            QLabel {
                color: #2E2E2E;
            }
            QListWidget {
                background-color: #FFFFFF;
            }
        """)

        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

        self.key_state = {'A': {'pressed': False, 'time': None}, 'D': {'pressed': False, 'time': None}}
        self.waiting_for_opposite_key = None
        self.data = []
        self.last_record_time = 0
        self.min_time_between_records = 0.05

        self.feedback_signal.connect(self.update_feedback)
        self.history_signal.connect(self.update_history)
        self.key_state_signal.connect(self.update_key_state_display)

    def on_press(self, key):
        try:
            key_char = key.char.upper()
            if key_char in ['A', 'D']:
                if not self.key_state[key_char]['pressed']:
                    self.key_state[key_char]['pressed'] = True
                    self.key_state[key_char]['time'] = time.perf_counter()
                    self.key_state_signal.emit(key_char, True)

                    if self.waiting_for_opposite_key and self.waiting_for_opposite_key['key'] == key_char:
                        current_time = time.perf_counter()
                        if current_time - self.last_record_time < self.min_time_between_records:
                            return

                        press_time = self.key_state[key_char]['time']
                        release_time = self.waiting_for_opposite_key['release_time']
                        time_diff = press_time - release_time
                        if abs(time_diff) > 0.2:
                            self.waiting_for_opposite_key = None
                            return

                        time_diff_ms = round(time_diff * 1000, 1)

                        color = self.get_color(time_diff_ms)

                        if abs(time_diff_ms) <= 2:
                            timing = '完美急停'
                        elif time_diff_ms < 0:
                            timing = '按早了'
                        else:
                            timing = '按晚了'

                        feedback = f"{timing}：松开{self.waiting_for_opposite_key['key_released']}后{abs(time_diff_ms):.1f}ms按下了{key_char}"

                        detail_info = {
                            'events': self.waiting_for_opposite_key['events'] + [
                                {'key': key_char, 'event': '按下', 'time': press_time, 'time_str': self.format_time(press_time)}
                            ]
                        }

                        self.feedback_signal.emit(feedback, color)
                        self.history_signal.emit(press_time, time_diff, detail_info, color)

                        self.data.append({'time': press_time, 'time_diff': time_diff})
                        if len(self.data) > 50:
                            self.data.pop(0)

                        self.last_record_time = current_time
                        self.waiting_for_opposite_key = None
        except AttributeError:
            pass

    def on_release(self, key):
        try:
            key_char = key.char.upper()
            if key_char in ['A', 'D']:
                if self.key_state[key_char]['pressed']:
                    release_time = time.perf_counter()
                    self.key_state[key_char]['pressed'] = False
                    self.key_state_signal.emit(key_char, False)
                    self.process_key_event(key_char, release_time)
        except AttributeError:
            pass

    def process_key_event(self, key_released, release_time):
        opposite_key = 'D' if key_released == 'A' else 'A'
        key_state = self.key_state[opposite_key]

        if key_state['pressed']:
            time_diff = key_state['time'] - release_time
            if abs(time_diff) > 0.2:
                return
            time_diff_ms = round(time_diff * 1000, 1)

            current_time = time.perf_counter()
            if current_time - self.last_record_time < self.min_time_between_records:
                return

            color = self.get_color(time_diff_ms)

            if abs(time_diff_ms) <= 2:
                timing = '完美急停'
            elif time_diff_ms < 0:
                timing = '按早了'
            else:
                timing = '按晚了'

            feedback = f"{timing}：未松开{key_released}就按下了{opposite_key}，{abs(time_diff_ms):.1f}ms"

            detail_info = {
                'events': [
                    {'key': key_released, 'event': '松开', 'time': release_time, 'time_str': self.format_time(release_time)},
                    {'key': opposite_key, 'event': '按下', 'time': key_state['time'], 'time_str': self.format_time(key_state['time'])}
                ]
            }

            self.feedback_signal.emit(feedback, color)
            self.history_signal.emit(key_state['time'], time_diff, detail_info, color)

            self.data.append({'time': key_state['time'], 'time_diff': time_diff})
            if len(self.data) > 50:
                self.data.pop(0)

            self.last_record_time = current_time
        else:
            self.waiting_for_opposite_key = {
                'key': opposite_key,
                'release_time': release_time,
                'key_released': key_released,
                'events': [
                    {'key': key_released, 'event': '松开', 'time': release_time, 'time_str': self.format_time(release_time)}
                ]
            }

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

    def update_history(self, press_time, time_diff, detail_info, color):
        time_diff_ms = round(time_diff * 1000, 1)
        time_str = self.format_time(press_time)
        item_text = f"{time_str} - 时间差：{time_diff_ms:.1f}ms"
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

        if len(self.data) >= 20:
            if not self.info_button.isVisible():
                self.info_button.show()
            if not self.question_button.isVisible():
                self.question_button.show()

        self.update_plot()
        self.update_boxplot()

    def update_plot(self):
        self.figure_line.clear()
        ax = self.figure_line.add_subplot(111)

        time_diffs = [round(d['time_diff'] * 1000, 1) for d in self.data[-25:]]
        jump_numbers = range(len(self.data) - len(time_diffs) + 1, len(self.data) + 1)

        colors = [self.get_color(diff) for diff in time_diffs]

        scatter = ax.scatter(jump_numbers, time_diffs, c=[color.name() for color in colors], s=100, edgecolors='black')

        if time_diffs:
            mean_value = statistics.mean(time_diffs)
            ax.axhline(mean_value, color='blue', linestyle='--', linewidth=2, label=f'平均值：{mean_value:.1f}ms')

            ax.axhline(0, color='black', linewidth=1, linestyle='-')

        ax.set_xticks(jump_numbers)
        ax.set_xlabel('操作次数', fontproperties="Microsoft YaHei", fontsize=12)
        ax.set_ylabel('时间差（ms）', fontproperties="Microsoft YaHei", fontsize=12)
        ax.set_title('提前或滞后时间差（最近25次）', fontproperties="Microsoft YaHei", fontsize=14)
        ax.legend(prop={'family': 'Microsoft YaHei', 'size': 10})

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, linestyle='--', alpha=0.6)

        self.canvas_line.draw()

    def update_boxplot(self):
        if len(self.data) >= 20:
            time_diffs = [round(d['time_diff'] * 1000, 1) for d in self.data[-50:]]

            self.figure_box.clear()
            ax = self.figure_box.add_subplot(111)

            bp = ax.boxplot(time_diffs, vert=False, patch_artist=True, showfliers=False)

            for box in bp['boxes']:
                box.set(color='#7570b3', linewidth=2)
                box.set(facecolor='#1b9e77')

            for whisker in bp['whiskers']:
                whisker.set(color='#7570b3', linewidth=2)

            for cap in bp['caps']:
                cap.set(color='#7570b3', linewidth=2)

            for median in bp['medians']:
                median.set(color='#b2df8a', linewidth=2)

            ax.set_xlabel('时间差（ms）', fontproperties="Microsoft YaHei", fontsize=12)
            ax.set_title('时间差箱线图（最近50次）', fontproperties="Microsoft YaHei", fontsize=14)

            ax.grid(True, linestyle='--', alpha=0.6)

            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            self.canvas_box.draw()
        else:
            self.figure_box.clear()
            self.canvas_box.draw()

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
        if key_char == 'A':
            if is_pressed:
                self.a_key_label.setText("A键：按下")
                self.a_key_label.setStyleSheet("""
                    QLabel {
                        background-color: #90EE90;
                        border: 2px solid #000000;
                        border-radius: 8px;
                    }
                """)
            else:
                self.a_key_label.setText("A键：未按下")
                self.a_key_label.setStyleSheet("""
                    QLabel {
                        background-color: #D3D3D3;
                        border: 2px solid #000000;
                        border-radius: 8px;
                    }
                """)
        elif key_char == 'D':
            if is_pressed:
                self.d_key_label.setText("D键：按下")
                self.d_key_label.setStyleSheet("""
                    QLabel {
                        background-color: #90EE90;
                        border: 2px solid #000000;
                        border-radius: 8px;
                    }
                """)
            else:
                self.d_key_label.setText("D键：未按下")
                self.d_key_label.setStyleSheet("""
                    QLabel {
                        background-color: #D3D3D3;
                        border: 2px solid #000000;
                        border-radius: 8px;
                    }
                """)

    def get_color(self, time_diff_ms):
        max_time_diff = 200
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
        if not self.data:
            QMessageBox.information(self, "急停建议", "暂无数据可供分析。")
            return

        avg_time_diff = statistics.mean([d['time_diff'] for d in self.data])
        avg_time_diff_ms = round(avg_time_diff * 1000, 2)

        if avg_time_diff_ms < -5:
            recommendation = (
                f"您的平均时间差为 {avg_time_diff_ms:.2f}ms，偏早。\n\n"
                "建议：\n"
                "- 使用更短的反应时间 (RT)。\n"
                "- 使用更长的死区（触发键程）。\n"
                "- 考虑开启 Snaptap 相关残疾辅助功能。"
            )
        elif avg_time_diff_ms > 5:
            recommendation = (
                f"您的平均时间差为 {avg_time_diff_ms:.2f}ms，偏晚。\n\n"
                "建议：\n"
                "- 使用更长的反应时间 (RT)。\n"
                "- 使用更短的死区（触发键程）。"
            )
        else:
            recommendation = (
                f"您的平均时间差为 {avg_time_diff_ms:.2f}ms。\n\n"
                "您表现出色！继续保持您的急停技巧！"
            )

        QMessageBox.information(self, "急停建议", recommendation)

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
