import sys
import numpy as np
import pyqtgraph as pg
from PyQt5.uic.Compiler.qtproxies import QtWidgets
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import pywt
import pathlib
from scipy.signal import butter, filtfilt, iirnotch
from scipy.fftpack import fft
import winsound
import pywin
import time
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from scipy.integrate import simpson  # Para el cálculo del área bajo la curva (AUC)
import pyttsx3


engine = pyttsx3.init()
engine.setProperty('rate', 150)
engine.setProperty('volume', 1.0)
voices = engine.getProperty('voices')

engine.setProperty('voice', voices[2].id)


RESULT_PY_FILE = 'entrenamiento_pestañeo.py'

training_phases = [
    {"phase": "Preparation", "duration": 3000},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "No blink", "duration": 3000},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "No blink", "duration": 3000},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "No blink", "duration": 3000},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "No blink", "duration": 3000},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "Blink", "duration": 500},
    {"phase": "No blink", "duration": 3000},
    {"phase": "Finish", "duration": 1000}



]

phase_index = 0
next_phase_time = time.time() + training_phases[phase_index]["duration"] / 1000

auc_values = []

def butter_bandpass(lowcut, highcut, fs, order=4):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    return butter(order, [low, high], btype='band')

def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    b, a = butter_bandpass(lowcut, highcut, fs, order)
    return filtfilt(b, a, data)


def notch_filter_signal(data, freq, fs, q=30):
    b, a = iirnotch(freq, q, fs)
    return filtfilt(b, a, data)

def denoise_signal(data, wavelet='db4', level=3):
    coeffs = pywt.wavedec(data, wavelet, level=level)
    sigma = np.median(np.abs(coeffs[-1])) / 0.6745
    uthresh = sigma * np.sqrt(2 * np.log(len(data)))
    coeffs[1:] = [pywt.threshold(c, value=uthresh, mode='soft') for c in coeffs[1:]]
    return pywt.waverec(coeffs, wavelet)


Fs = 250
buffer_size = int(1 * Fs)

app = QtWidgets.QApplication([])
win = pg.GraphicsLayoutWidget(show=True, title="EEG Signal Real-Time Visualization")
win.resize(1400, 800)
win.setWindowTitle('Real-Time EEG Signal')

raw_plot = win.addPlot(title="Raw Signal")
denoised_plot = win.addPlot(title="Denoised Signal")
win.nextRow()
filtered_plot = win.addPlot(title="Filtered Signal (4-15 Hz)")
fft_plot = win.addPlot(title="FFT of Filtered Signal")

raw_curve = raw_plot.plot()
denoised_curve = denoised_plot.plot()
filtered_curve = filtered_plot.plot()
fft_curve = fft_plot.plot()

lowcut = 4.0
highcut = 15.0

low_freqs_filt = 1
high_freqs_filt = 60


notch_freq = 60


b, a = butter_bandpass(lowcut, highcut, Fs)

params = BrainFlowInputParams()
params.serial_port = 'COM4'
board = BoardShim(BoardIds.CYTON_BOARD.value, params)
board.prepare_session()
board.start_stream()

buffer_data = np.zeros((24, buffer_size))


def update_eeg_signal():
    global buffer_data, current_phase
    data = board.get_board_data()
    if data.shape[1] == 0:
        return

    buffer_data = np.roll(buffer_data, -data.shape[1], axis=1)
    buffer_data[:, -data.shape[1]:] = data

    selected_data = buffer_data[1:2, :]
    combined_signal = np.mean(selected_data, axis=0)

    bpass_signal = butter_bandpass_filter(combined_signal, low_freqs_filt, high_freqs_filt, fs=Fs)
    notch_signal = notch_filter_signal(bpass_signal, notch_freq, fs=Fs)
    denoised_signal = denoise_signal(notch_signal)
    filtered_signal = butter_bandpass_filter(denoised_signal, lowcut, highcut, Fs)

    raw_curve.setData(notch_signal)
    denoised_curve.setData(denoised_signal)
    filtered_curve.setData(filtered_signal)

    L = len(filtered_signal)
    fft_result = fft(filtered_signal)
    fft_magnitude = np.abs(fft_result[:L // 2])
    freqs = np.linspace(0.0, Fs / 2, L // 2)
    fft_curve.setData(freqs, fft_magnitude)

    if np.isnan(fft_magnitude).any() or np.isnan(freqs).any():
        print("Error: fft_magnitude o freqs contiene valores NaN.")
    elif current_phase == "Blink":
        area_under_curve = simpson(fft_magnitude, x=freqs)
        auc_values.append(area_under_curve)
        print(f"Área bajo la curva en esta fase: {area_under_curve}")

    else:
        return



RESULT_DIR = pathlib.Path("C:/Users/chris/PycharmProjects/exoGUI/HELPERS")  # Cambia esto a la carpeta que desees

def save_results_to_py(mean_max, std_max):
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    result_file_path = RESULT_DIR / "resultados_BLINK.py"

    # Escribe los resultados en el archivo
    with open(result_file_path, mode='w') as file:
        file.write(f'# Valores calculados del entrenamiento\n')
        file.write(f'mean_max = {mean_max}\n')
        file.write(f'std_max = {std_max}\n')
        file.write(f'MAX_Vals = {auc_values}\n')  # Asegúrate de que auc_values esté definido
    print(f"Resultados guardados en {result_file_path}")
current_phase = None


def update_phase():
    global phase_index, next_phase_time, current_phase
    current_time = time.time()

    if current_time >= next_phase_time:
        phase_index = (phase_index + 1) % len(training_phases)
        current_phase = training_phases[phase_index]['phase']
        next_phase_time = current_time + training_phases[phase_index]["duration"] / 1000

        #winsound.Beep(800, 500)

        # Obtener la fase actual
        current_phase = training_phases[phase_index]['phase']
        print(f"Fase: {current_phase}")

        if current_phase == "Blink":
            engine.say("pestañeo")
        elif current_phase == "No blink":
            engine.say("Alto")
        elif current_phase == "Finish":
            engine.say("Test terminado")
        winsound.Beep(500, 100)
        engine.runAndWait()

        # Verificar si el entrenamiento ha terminado
        if phase_index == 0:  # Si volvemos al inicio, el entrenamiento ha terminado
            print("Entrenamiento finalizado. Calculando estadísticas...")
            if auc_values:
                filtered_max_values = [val for val in auc_values if 29000 > val > 1000]

                if filtered_max_values:
                    max_mean = np.mean(filtered_max_values)
                    max_std = np.std(filtered_max_values)
                    print(f"Mean Area Under the Curve: {max_mean}")
                    print(f"Standard Deviation: {max_std}")

                    save_results_to_py(max_mean, max_std)

                else:
                    print("No se encontraron valores de AUC adecuados.")
            else:
                print("No se encontraron datos de AUC.")

            sys.exit()


eeg_timer = QtCore.QTimer()
eeg_timer.timeout.connect(update_eeg_signal)
eeg_timer.start(100)

phase_timer = QtCore.QTimer()
phase_timer.timeout.connect(update_phase)
phase_timer.start(100)

QtGui.QGuiApplication.instance().exec()

board.stop_stream()
board.release_session()