from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QProgressBar, \
    QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QKeyEvent
import Backend


# Clase para procesar señales EEG en un hilo separado
class EEGProcessor(QThread):
    blink_detected = pyqtSignal()
    double_blink_detected = pyqtSignal()
    alpha_wave_detected = pyqtSignal()

    def run(self):
        while True:
            event = Backend.detect_event()
            if event == "blink":
                self.blink_detected.emit()
            elif event == "double_blink":
                self.double_blink_detected.emit()
            elif event == "alpha_wave":
                self.alpha_wave_detected.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interfaz de Terapia EEG")
        self.showFullScreen()

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.bg_label = QLabel(self.central_widget)
        pixmap = QPixmap("EXO_INIT.png")
        if pixmap.isNull():
            print("Imagen 'EXO_INIT.png' no encontrada.")
        else:
            self.bg_label.setPixmap(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding))
            self.bg_label.setGeometry(0, 0, self.width(), self.height())
            self.bg_label.setScaledContents(True)
            self.bg_label.lower()

            self.opacity_effect = QGraphicsOpacityEffect()
            self.opacity_effect.setOpacity(0.7)
            self.bg_label.setGraphicsEffect(self.opacity_effect)

        self.intro_label = QLabel("EXBB-01", self)
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
        QTimer.singleShot(2000, self.animation.start)

        self.progress = 0
        self.progress_bar = None
        self.selected_index = 0

        self.eeg_thread = EEGProcessor()
        self.eeg_thread.blink_detected.connect(self.next_speed)
        self.eeg_thread.double_blink_detected.connect(self.select_speed)
        self.eeg_thread.alpha_wave_detected.connect(self.update_progress)
        self.eeg_thread.start()

    def show_menu(self):
        self.clear_layout()
        self.label = QLabel("Seleccione la velocidad de la terapia", self)
        self.label.setFont(QFont("Arial", 30))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        self.buttons = [QPushButton("Velocidad 1"), QPushButton("Velocidad 2"), QPushButton("Velocidad 3")]
        for i, btn in enumerate(self.buttons):
            btn.setFont(QFont("Arial", 20))
            btn.setStyleSheet("background-color: lightgray;")
            btn.clicked.connect(lambda _, s=i: self.start_therapy(s + 1))
            self.layout.addWidget(btn)
        self.update_selection()

    def next_speed(self):
        self.selected_index = (self.selected_index + 1) % len(self.buttons)
        self.update_selection()

    def select_speed(self):
        self.start_therapy(self.selected_index + 1)

    def update_selection(self):
        for i, btn in enumerate(self.buttons):
            if i == self.selected_index:
                btn.setStyleSheet("background-color: blue; color: black; font-weight: bold;")
            else:
                btn.setStyleSheet("background-color: lightgray; color: black; font-weight: normal;")

    def start_therapy(self, speed):
        self.clear_layout()
        self.label = QLabel(f"Confirmación de Selección, Cierre los ojos {speed}", self)
        self.label.setFont(QFont("Arial", 50))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.layout.addWidget(self.progress_bar)

        self.progress = 0

    def update_progress(self):
        if self.progress < 100:
            self.progress += 10
            self.progress_bar.setValue(self.progress)
            if self.progress >= 100:
                QTimer.singleShot(500, self.show_simulation)

    def show_simulation(self):
        self.clear_layout()
        self.label = QLabel("TERAPIA EN PROCESO...", self)
        self.label.setFont(QFont("Arial", 50))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

    def clear_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
