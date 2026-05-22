from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel,
    QVBoxLayout, QWidget, QProgressBar, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation
from PyQt6.QtGui import QFont, QPixmap
import sys


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Brain-Computer Interface")
        self.showFullScreen()

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.bg_label = QLabel(self.central_widget)
        self.setup_background()

        self.intro_label = QLabel("EXBB-01", self)
        self.setup_intro_label()

        self.progress = 0
        self.progress_bar = None
        self.selected_index = 0
        self.buttons = []
        self.progress_per_button = [0] * 3  # Para 3 botones

        QTimer.singleShot(2000, self.start_fade_animation)

    def setup_background(self):
        pixmap = QPixmap("EXO_INIT.png")
        if not pixmap.isNull():
            self.bg_label.setPixmap(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding))
            self.bg_label.setGeometry(0, 0, self.width(), self.height())
            self.bg_label.setScaledContents(True)
            self.bg_label.lower()

            opacity = QGraphicsOpacityEffect()
            opacity.setOpacity(0.55)
            self.bg_label.setGraphicsEffect(opacity)

    def setup_intro_label(self):
        self.intro_label.setFont(QFont("Arial", 50))
        self.intro_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.intro_label)

        self.fade_effect = QGraphicsOpacityEffect()
        self.intro_label.setGraphicsEffect(self.fade_effect)

        self.animation = QPropertyAnimation(self.fade_effect, b"opacity")
        self.animation.setDuration(2000)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.finished.connect(self.show_menu)

    def start_fade_animation(self):
        self.animation.start()

    def show_menu(self):
        self.clear_layout()
        self.label = QLabel("Choose the flexion-extension speed for therapy", self)
        self.label.setFont(QFont("Arial", 30))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        self.buttons = [QPushButton(f"Speed {i + 1}") for i in range(3)]
        self.progress_labels = [QLabel("Selection Progress: 0%", self) for _ in range(3)]
        self.progress_per_button = [0] * len(self.buttons)

        for i, btn in enumerate(self.buttons):
            btn.setFont(QFont("Arial", 20))
            btn.setStyleSheet("background-color: lightgray;")
            self.layout.addWidget(btn)

            self.progress_labels[i].setFont(QFont("Arial", 14))
            self.progress_labels[i].setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.progress_labels[i])

        self.update_selection()

    def update_selection(self):
        for i, btn in enumerate(self.buttons):
            if i == self.selected_index:
                btn.setStyleSheet("background-color: lightblue;")
            else:
                btn.setStyleSheet("background-color: lightgray;")

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key.Key_Z:
            self.update_progress()

        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.next_option(direction=-1 if key == Qt.Key.Key_Up else 1)

        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.progress_bar is None:
                self.start_therapy(self.selected_index + 1)

    def next_option(self, direction):
        if not self.buttons:
            return

        self.selected_index = (self.selected_index + direction) % len(self.buttons)
        self.update_selection()

    def update_progress(self):
        if not self.buttons:
            return

        if self.progress_per_button[self.selected_index] < 500:
            self.progress_per_button[self.selected_index] += 1
            progress = self.progress_per_button[self.selected_index]

            green_intensity = int(255 * (progress / 500))
            self.buttons[self.selected_index].setStyleSheet(
                f"background-color: rgb({255 - green_intensity}, 255, {255 - green_intensity});"
            )

            self.progress_labels[self.selected_index].setText(f"Progress: {progress/5:.1f}%")

            if progress >= 500:
                self.label.setText(f"Speed {self.selected_index + 1} Selected. Close your Eyer.")
                QTimer.singleShot(1000, lambda: self.start_therapy(self.selected_index + 1))

    def start_therapy(self, speed):
        self.clear_layout()
        self.label = QLabel(f"Therapy Starting with Speed #{speed}", self)
        self.label.setFont(QFont("Arial", 40))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(1000)
        self.layout.addWidget(self.progress_bar)

        self.progress = 0

        self.therapy_timer = QTimer()
        self.therapy_timer.timeout.connect(self.update_therapy_progress)
        self.therapy_timer.start(50)

    def update_therapy_progress(self):
        self.progress += 5
        self.progress_bar.setValue(self.progress)

        if self.progress >= 1000:
            self.therapy_timer.stop()
            self.start_countdown()

    def start_countdown(self):
        self.clear_layout()
        self.count = 30
        self.label = QLabel("THERAPY", self)
        self.label.setFont(QFont("Arial", 40))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        self.countdown_label = QLabel(f"Rehabilitation process during {self.count} s", self)
        self.countdown_label.setFont(QFont("Arial", 30))
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.countdown_label)

        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)

    def update_countdown(self):
        self.count -= 1
        if self.count <= 0:
            self.countdown_timer.stop()
            self.show_menu()
        else:
            self.countdown_label.setText(f"Finishing in  {self.count} s")

    def clear_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def closeEvent(self, event):
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
