from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QWidget, QProgressBar, QGraphicsOpacityEffect, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QObject, QPropertyAnimation, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from Backend import EEGProcessor
import serial
import time
import serial.tools.list_ports
import sys
import threading
import csv
import random
from pathlib import Path

try:
    import winsound
except ImportError:
    winsound = None

ARDUINO_PORT = 'COM4'
ARDUINO_BAUD = 115200

PARTICIPANTE = ["RXS-P01","RXS-P02","RXS-P03","RXS-P04","RXS-P05","RXS-P06",
                "RXS-P07","RXS-P08","RXS-P09","RXS-P10","RXS-P11","RXS-P12","RXS-13","RXS-P14"]
CARPETA_REGISTROS = Path("registros")
N_ENSAYOS = 10
TIEMPO_LIMITE_S = 45
REPOSO_S = 60
PREPARACION_S = 1

BEEP_FREQ = 880
BEEP_MS = 800

SPEED_COMMANDS = ['a', 'b', 'c']
THERAPY_S = 30
VARIABLE_PROFILES = [
    ("Ramp up", [0, 1, 2]),
    ("Up and down", [0, 1, 2, 1, 0]),
    ("Interactive", None),
]


def play_confirm_beep():
    if winsound is not None:
        threading.Thread(target=winsound.Beep, args=(BEEP_FREQ, BEEP_MS), daemon=True).start()
    else:
        QApplication.beep()


MODE_BUTTON_STYLE = """
QPushButton {
    background-color: #f4f6f8; color: #1c2126;
    border: 3px solid #9aa4af; border-radius: 22px; padding: 30px;
}
QPushButton:hover { background-color: #dcebff; border-color: #1f6feb; }
QPushButton:pressed { background-color: #bcd6ff; }
"""


def speed_button_style(selected, progress=0, total=500):
    if not selected:
        return ("QPushButton { background-color: lightgray; color: #1c2126; border: 2px solid #b4bac2;"
                " border-radius: 16px; padding: 18px; }")
    green_intensity = int(255 * (progress / total))
    return (f"QPushButton {{ background-color: rgb({255 - green_intensity}, 255, {255 - green_intensity});"
            " color: #1c2126; border: 5px solid #1f6feb; border-radius: 16px; padding: 18px; font-weight: bold; }")


class EEGThreadManager(QObject):
    def __init__(self):
        super().__init__()
        self.thread = QThread()
        self.processor = EEGProcessor()
        self.processor.moveToThread(self.thread)

    def connect_blink(self, slot):
        self.processor.blink_signal.connect(slot)

    def connect_alpha(self, slot):
        self.processor.alpha_signal.connect(slot)

    def start(self):
        self.thread.started.connect(self.processor.process_loop)
        self.thread.start()

    def stop(self):
        self.processor.stop()
        self.thread.quit()
        self.thread.wait()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RExSAS_Therapy_Window")
        self.showFullScreen()

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.bg_label = QLabel(self.central_widget)
        self.setup_background()

        self.mode_label = QLabel("", self.central_widget)
        self.mode_label.setFont(QFont("Arial", 12))
        self.mode_label.setStyleSheet("color: #444444;")

        self.progress = 0
        self.progress_bar = None
        self.selected_index = 0
        self.buttons = []
        self.progress_labels = []
        self.progress_per_button = [0] * 3
        self.confirmed = False
        self.simulation = True
        self.arduino = None
        self.therapy_type = "fixed"
        self.therapy_speed = 0
        self.therapy_profile = None
        self.interactive_therapy = False
        self.intro_shown = False

        self.events = []
        self.trials = []
        self.test_mode = False
        self.test_kind = None
        self.test_target = None
        self.step_open = False
        self.awaiting_enter = False
        self.trial_blinks = 0
        self.trial_alpha = 0
        self.false_confirmations = 0

        self.eeg_thread = EEGThreadManager()
        self.eeg_thread.connect_blink(self.next_option)
        self.eeg_thread.connect_alpha(self.update_progress)
        self.eeg_thread.start()

        self.eeg_thread.processor.participant = PARTICIPANTE
        self.session_id = getattr(self.eeg_thread.processor, "session_id", time.strftime("%Y%m%d_%H%M%S"))

        self.show_mode_page()


    def show_mode_page(self):
        self.clear_layout()

        title = QLabel("RExSAS V1.0.2", self)
        title.setFont(QFont("Arial", 100))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title)

        self.label = QLabel("Choose the operation mode", self)
        self.label.setFont(QFont("Arial", 30))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setSpacing(60)
        row_layout.setContentsMargins(60, 20, 60, 20)

        sim_button = QPushButton("Simulation\n\nNo Arduino")
        real_button = QPushButton(f"Real\n\nArduino on {ARDUINO_PORT}")
        for btn in (sim_button, real_button):
            btn.setFont(QFont("Arial", 28))
            btn.setMinimumHeight(260)
            btn.setStyleSheet(MODE_BUTTON_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            row_layout.addWidget(btn, 1)
        sim_button.clicked.connect(lambda: self.choose_mode(simulation=True))
        real_button.clicked.connect(lambda: self.choose_mode(simulation=False))
        self.layout.addWidget(row)

        self.test_checkbox = QCheckBox("Test mode: guided selections and rest periods (results are saved)")
        self.test_checkbox.setFont(QFont("Arial", 18))
        self.test_checkbox.setStyleSheet("QCheckBox { spacing: 14px; } QCheckBox::indicator { width: 28px; height: 28px; }")
        self.test_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.layout.addWidget(self.test_checkbox, alignment=Qt.AlignmentFlag.AlignCenter)

        self.mode_error = QLabel("", self)
        self.mode_error.setFont(QFont("Arial", 16))
        self.mode_error.setStyleSheet("color: #b3261e;")
        self.mode_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.mode_error)

    def choose_mode(self, simulation):
        if simulation:
            self.arduino = None
        else:
            try:
                self.arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
            except serial.SerialException as e:
                self.mode_error.setText(f"Could not open the Arduino on {ARDUINO_PORT}. "
                                        "Check the cable or choose Simulation.")
                print(f"Error al abrir {ARDUINO_PORT}: {e}")
                return
        self.simulation = simulation
        self.test_mode = self.test_checkbox.isChecked()
        self.log_event("session_start", f"{'simulation' if simulation else 'real'}; "
                                        f"{'test mode' if self.test_mode else 'normal mode'}")
        self.therapy_type = "fixed"
        self.update_mode_label()
        if not simulation and not self.test_mode:
            self.show_therapy_type_page()
            return
        self.start_intro()

    def show_therapy_type_page(self):
        self.clear_layout()

        title = QLabel("Therapy type", self)
        title.setFont(QFont("Arial", 60))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title)

        self.label = QLabel("Choose how the exoskeleton speed will work", self)
        self.label.setFont(QFont("Arial", 30))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setSpacing(60)
        row_layout.setContentsMargins(60, 20, 60, 20)

        fixed_button = QPushButton("Fixed speed\n\nSpeed 1, 2 or 3\nduring the whole session")
        variable_button = QPushButton("Variable speed\n\nRamp up, up and down\nor interactive (blinks)")
        for btn in (fixed_button, variable_button):
            btn.setFont(QFont("Arial", 28))
            btn.setMinimumHeight(260)
            btn.setStyleSheet(MODE_BUTTON_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            row_layout.addWidget(btn, 1)
        fixed_button.clicked.connect(lambda: self.choose_therapy_type("fixed"))
        variable_button.clicked.connect(lambda: self.choose_therapy_type("variable"))
        self.layout.addWidget(row)

        hint = QLabel("In the speed menu, press Backspace to come back to this page", self)
        hint.setFont(QFont("Arial", 16))
        hint.setStyleSheet("color: #444444;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(hint)

    def choose_therapy_type(self, kind):
        self.therapy_type = kind
        self.log_event("therapy_type", kind)
        self.update_mode_label()
        if self.intro_shown:
            self.show_menu()
        else:
            self.start_intro()

    def option_name(self, index):
        if self.therapy_type == "variable":
            return VARIABLE_PROFILES[index][0]
        return f"Speed {index + 1}"

    def start_intro(self):
        self.intro_shown = True
        self.clear_layout()
        self.intro_label = QLabel("RExSAS V1.0.2", self)
        self.setup_intro_label()
        QTimer.singleShot(2000, self.start_fade_animation)

    def update_mode_label(self, last_command=None):
        text = "SIMULATION MODE (no Arduino)" if self.simulation else f"REAL MODE (Arduino on {ARDUINO_PORT})"
        if not self.simulation and not self.test_mode:
            text += f"   |   {self.therapy_type} speed therapy"
        if last_command is not None:
            text += f"   |   last command: {last_command}"
        self.mode_label.setText(text)
        self.mode_label.adjustSize()
        self.mode_label.move(20, self.central_widget.height() - self.mode_label.height() - 12)
        self.mode_label.raise_()

    def pause_eeg_processing(self):
        self.eeg_thread.processor.pause()
        print("Procesamiento EEG PAUSADO.")

    def resume_eeg_processing(self):
        self.eeg_thread.processor.resume()
        print("Procesamiento EEG REANUDADO.")

    def send_arduino_command(self, command):
        if self.arduino is None:
            print(f'Comando Simulado: {command}')
        elif self.arduino.is_open:
            try:
                self.arduino.write(command.encode())
                print(f'Comando Enviado: {command}')
            except serial.SerialTimeoutException:
                print("Error: Tiempo de espera excedido.")
        self.log_event("command", command)
        self.update_mode_label(command)

    def setup_background(self):
        pixmap = QPixmap("EXO_INIT.png")
        if pixmap.isNull():
            print("Imagen 'EXO_INIT.png' no encontrada.")
        else:
            self.bg_label.setPixmap(pixmap)
            self.bg_label.setGeometry(0, 0, self.width(), self.height())
            self.bg_label.setScaledContents(True)
            self.bg_label.lower()

            opacity = QGraphicsOpacityEffect()
            opacity.setOpacity(0.65)
            self.bg_label.setGraphicsEffect(opacity)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "mode_label"):
            return
        self.bg_label.setGeometry(0, 0, self.central_widget.width(), self.central_widget.height())
        self.mode_label.move(20, self.central_widget.height() - self.mode_label.height() - 12)

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
        self.animation.finished.connect(self.start_test if self.test_mode else self.show_menu)

    def start_fade_animation(self):
        self.animation.start()

    def show_menu(self):
        self.resume_eeg_processing()

        self.clear_layout()
        title = "Choose your variable-speed therapy" if self.therapy_type == "variable" else "Choose your therapy speed"
        self.label = QLabel(title, self)
        self.label.setFont(QFont("Arial", 30))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        self.buttons = [QPushButton(self.option_name(i)) for i in range(3)]
        self.progress_labels = [QLabel("Progress: 0%", self) for _ in range(3)]
        self.progress_per_button = [0] * len(self.buttons)
        self.selected_index = 0
        self.confirmed = False

        for i, btn in enumerate(self.buttons):
            btn.setFont(QFont("Arial", 24))
            btn.setMinimumHeight(110)
            self.layout.addWidget(btn)

            self.progress_labels[i].setFont(QFont("Arial", 14))
            self.progress_labels[i].setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.progress_labels[i])

        self.update_selection()

    def next_option(self):
        if self.interactive_therapy:                     # terapia interactiva: el parpadeo cambia la velocidad
            self.change_therapy_speed((self.therapy_speed + 1) % 3, "blink")
            return
        if not self.buttons or self.confirmed:
            return

        prev_index = self.selected_index
        self.progress_per_button[prev_index] = 0
        self.progress_labels[prev_index].setText("Progress: 0%")

        self.selected_index = (self.selected_index + 1) % len(self.buttons)
        self.trial_blinks += 1
        self.log_event("blink", f"moved to {self.option_name(self.selected_index)}")
        self.update_selection()
        self.send_arduino_command('u')

    def update_selection(self):
        for i, btn in enumerate(self.buttons):
            selected = (i == self.selected_index)
            btn.setStyleSheet(speed_button_style(selected, self.progress_per_button[i]))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.awaiting_enter:                      # fin del modo de prueba: sigue el menú normal
                self.awaiting_enter = False
                self.show_menu()
            elif self.buttons and not self.confirmed and not self.test_mode:
                self.confirmed = True
                self.log_event("operator_start", f"Speed {self.selected_index + 1}")
                self.start_therapy(self.selected_index + 1)
        elif event.key() == Qt.Key.Key_Backspace:            # volver a elegir el tipo de terapia (modo REAL)
            if self.buttons and not self.confirmed and not self.test_mode and not self.simulation:
                self.show_therapy_type_page()

    def update_progress(self):
        if not self.buttons or self.confirmed:
            return

        self.trial_alpha += 1
        if self.progress_per_button[self.selected_index] < 500:
            self.progress_per_button[self.selected_index] += 1
            progress = self.progress_per_button[self.selected_index]

            self.buttons[self.selected_index].setStyleSheet(speed_button_style(True, progress))
            self.progress_labels[self.selected_index].setText(f"Progress: {progress / 5:.0f}%")

            if progress >= 500:
                speed = self.selected_index + 1
                self.log_event("alpha_confirm", self.option_name(self.selected_index))
                if self.test_mode and self.test_kind == "rest":
                    self.false_confirmations += 1
                    self.progress_per_button[self.selected_index] = 0
                    self.progress_labels[self.selected_index].setText("Progress: 0%")
                    self.update_selection()
                    return
                self.confirmed = True
                self.label.setText(f"{self.option_name(self.selected_index)} confirmed.")
                play_confirm_beep()              # aviso: ya puede abrir los ojos
                if self.test_mode:
                    # En modo de prueba no se inicia la terapia: se anota el resultado y sigue el siguiente ensayo
                    self.finish_test_step("correct" if self.selected_index == self.test_target else "wrong")
                else:
                    QTimer.singleShot(1000, lambda: self.start_therapy(speed))

    def start_therapy(self, speed):
        self.pause_eeg_processing()

        self.clear_layout()
        text = (f"Session initialized: {self.option_name(speed - 1)}" if self.therapy_type == "variable"
                else f"Session initialized at Speed {speed}")
        self.label = QLabel(text, self)
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
        self.progress += 10
        self.progress_bar.setValue(self.progress)

        if self.progress >= 1000:
            if self.therapy_type == "variable":              # velocidad variable: siempre empieza en Speed 1
                self.therapy_profile = VARIABLE_PROFILES[self.selected_index][1]
                self.therapy_speed = 0
            else:
                self.therapy_profile = None
                self.therapy_speed = self.selected_index
            command = SPEED_COMMANDS[self.therapy_speed]  # Enviar según la velocidad seleccionada
            print(f'ALPHA WAVEBAND COMMAND SENT: {command}')
            self.send_arduino_command(command)
            self.therapy_timer.stop()
            self.start_countdown()

    def start_countdown(self):
        self.clear_layout()
        self.count = THERAPY_S
        self.label = QLabel("Rehabilitation Therapy", self)
        self.label.setFont(QFont("Arial", 40))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        if self.therapy_type == "variable":
            self.speed_label = QLabel("", self)
            self.speed_label.setFont(QFont("Arial", 30))
            self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.speed_label)
            self.update_speed_label()
            if self.therapy_profile is None:
                self.interactive_therapy = True
                self.resume_eeg_processing()

        self.countdown_label = QLabel(f"Therapy Session During {self.count} s", self)
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
            self.interactive_therapy = False
            self.send_arduino_command('x')

            self.resume_eeg_processing()
            self.show_menu()
        else:
            self.countdown_label.setText(f"Finishing in {self.count} s")
            if self.therapy_profile:
                part = THERAPY_S / len(self.therapy_profile)
                speed = self.therapy_profile[min(int((THERAPY_S - self.count) / part), len(self.therapy_profile) - 1)]
                if speed != self.therapy_speed:
                    self.change_therapy_speed(speed, "profile")

    def change_therapy_speed(self, speed, reason):
        self.therapy_speed = speed
        self.log_event("speed_change", f"Speed {speed + 1}; {reason}")
        self.send_arduino_command(SPEED_COMMANDS[speed])
        self.update_speed_label()

    def update_speed_label(self):
        text = f"{VARIABLE_PROFILES[self.selected_index][0]}  |  current: Speed {self.therapy_speed + 1}"
        if self.therapy_profile is None:
            text += "\nBlink to change the speed"
        self.speed_label.setText(text)


    def log_event(self, event, detail=""):
        self.events.append({"tiempo": round(time.time(), 3), "evento": event, "detalle": detail})

    def save_csv(self, name, rows):
        if not rows:
            return
        try:
            CARPETA_REGISTROS.mkdir(parents=True, exist_ok=True)
            path = CARPETA_REGISTROS / f"{name}_{PARTICIPANTE}_{self.session_id}.csv"
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            print(f"Guardado: {path}")
        except OSError as e:
            print(f"No se pudo guardar {name}: {e}")

    def start_test(self):
        targets = [i % 3 for i in range(N_ENSAYOS)]
        random.shuffle(targets)
        self.plan = [("rest", None)] + [("trial", t) for t in targets] + [("rest", None)]
        self.plan_index = -1
        self.trials = []
        self.next_test_step()

    def next_test_step(self):
        self.plan_index += 1
        if self.plan_index >= len(self.plan):
            self.finish_test()
            return
        self.test_kind, self.test_target = self.plan[self.plan_index]
        self.show_menu()
        self.confirmed = True
        if self.test_kind == "trial":
            self.label.setText(f"Select: Speed {self.test_target + 1}")
        else:
            self.label.setText("REST: keep your eyes open and do not select anything")
        self.log_event("step_shown", f"{self.test_kind}; target={'' if self.test_target is None else self.test_target + 1}")
        QTimer.singleShot(PREPARACION_S * 1000, self.activate_test_step)

    def activate_test_step(self):
        step = self.plan_index
        self.confirmed = False
        self.step_open = True
        self.trial_blinks = 0
        self.trial_alpha = 0
        self.false_confirmations = 0
        self.trial_start = time.time()
        self.log_event("step_start", self.test_kind)
        limit = TIEMPO_LIMITE_S if self.test_kind == "trial" else REPOSO_S
        QTimer.singleShot(limit * 1000, lambda: self.test_step_timeout(step))

    def test_step_timeout(self, step):
        if step != self.plan_index or not self.step_open:    # ese paso ya había terminado
            return
        if self.test_kind == "trial":
            self.label.setText("Time is up")
            self.finish_test_step("timeout")
        else:
            self.label.setText("Rest finished")
            self.finish_test_step("rest")

    def finish_test_step(self, result):
        self.step_open = False
        self.confirmed = True
        is_trial = self.test_kind == "trial"
        self.trials.append({
            "participante": PARTICIPANTE, "sesion": self.session_id, "paso": self.plan_index + 1,
            "tipo": self.test_kind,
            "objetivo": f"Speed {self.test_target + 1}" if is_trial else "",
            "seleccion": f"Speed {self.selected_index + 1}" if result in ("correct", "wrong") else "",
            "resultado": result,
            "tiempo_s": round(time.time() - self.trial_start, 3),
            "parpadeos": self.trial_blinks,
            "parpadeos_minimos": self.test_target if is_trial else "",
            "parpadeos_extra": self.trial_blinks - self.test_target if result == "correct" else "",
            "eventos_alfa": self.trial_alpha,
            "confirmaciones_falsas": "" if is_trial else self.false_confirmations,
        })
        self.log_event("step_end", f"{self.test_kind}; {result}")
        QTimer.singleShot(2000, self.next_test_step)

    def test_summary(self):
        sel = [t for t in self.trials if t["tipo"] == "trial"]
        rest = [t for t in self.trials if t["tipo"] == "rest"]
        correct = [t for t in sel if t["resultado"] == "correct"]
        extra = [t["parpadeos_extra"] for t in correct]
        minutes = sum(t["tiempo_s"] for t in rest) / 60.0
        return {
            "participante": PARTICIPANTE, "sesion": self.session_id,
            "modo": "simulacion" if self.simulation else "real",
            "ensayos": len(sel),
            "correctos": len(correct),
            "incorrectos": sum(t["resultado"] == "wrong" for t in sel),
            "sin_respuesta": sum(t["resultado"] == "timeout" for t in sel),
            "exactitud": round(len(correct) / len(sel), 4) if sel else "",
            "tiempo_medio_correctos_s": round(sum(t["tiempo_s"] for t in correct) / len(correct), 2) if correct else "",
            "parpadeos_extra_promedio": round(sum(extra) / len(extra), 2) if extra else "",
            "minutos_de_reposo": round(minutes, 2),
            "parpadeos_por_min_en_reposo": round(sum(t["parpadeos"] for t in rest) / minutes, 2) if minutes else "",
            "confirmaciones_falsas_en_reposo": sum(t["confirmaciones_falsas"] for t in rest),
        }

    def finish_test(self):
        self.test_mode = False
        s = self.test_summary()
        self.save_csv("ensayos", self.trials)
        self.save_csv("resumen", [s])
        self.save_csv("eventos", self.events)

        self.clear_layout()
        self.label = QLabel("Test finished", self)
        self.label.setFont(QFont("Arial", 40))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)
        accuracy = f"{s['exactitud']:.0%}" if s["exactitud"] != "" else "n/a"
        text = (f"Correct selections: {s['correctos']} of {s['ensayos']}  ({accuracy})\n"
                f"Wrong: {s['incorrectos']}     No response: {s['sin_respuesta']}\n"
                f"Mean time per correct selection: {s['tiempo_medio_correctos_s']} s\n\n"
                f"At rest: {s['parpadeos_por_min_en_reposo']} blinks per minute, "
                f"{s['confirmaciones_falsas_en_reposo']} false confirmations\n\n"
                f"Results saved in '{CARPETA_REGISTROS}'.  Press Enter to continue.")
        summary = QLabel(text, self)
        summary.setFont(QFont("Arial", 22))
        summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(summary)
        self.awaiting_enter = True

    def clear_layout(self):
        self.buttons = []
        self.progress_labels = []
        self.progress_bar = None
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def closeEvent(self, event):
        self.log_event("session_end")
        self.save_csv("eventos", self.events)
        if self.trials and self.test_mode:
            self.save_csv("ensayos", self.trials)
        self.eeg_thread.stop()
        if self.arduino and self.arduino.is_open:
            self.arduino.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
