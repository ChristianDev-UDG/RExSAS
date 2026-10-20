
# -*- coding: utf-8 -*-
import sys
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import pywt
from pyttsx3 import Engine
from scipy.signal import butter, filtfilt, iirnotch
from scipy.fftpack import fft
import winsound
import time
import pyttsx3
import pathlib
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from scipy.integrate import simpson, trapezoid




engine = pyttsx3.init()
engine.setProperty('rate', 150)
engine.setProperty('volume', 1.0)
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[2].id)

RESULT_PY_FILE = 'resultados_entrenamiento_alpha.py'
RESULT_AUC = 'Captured Areas.py'

training_phases = [
    {"phase": "Preparation", "duration": 2000},
    {"phase": "Eyes Closed", "duration": 4000},
    {"phase": "Eyes Opened", "duration": 4000},
    {"phase": "Eyes Closed", "duration": 4000},
    {"phase": "Eyes Opened", "duration": 4000},
    {"phase": "Eyes Closed", "duration": 4000},
    {"phase": "Eyes Opened", "duration": 4000},
    {"phase": "Eyes Closed", "duration": 4000},
    {"phase": "Eyes Opened", "duration": 4000},
    {"phase": "Eyes Closed", "duration": 10000},
    {"phase": "Finish", "duration": 500}
]

phase_index = 0

next_phase_time = None
current_phase = training_phases[phase_index]["phase"]
phase_start = None        

SETTLE_TIME = 2.0

auc_values = []           
samples_received = 0   


def denoise_signal(data, wavelet='db4', level=3):
    coeffs = pywt.wavedec(data, wavelet, level=level)
    sigma = np.median(np.abs(coeffs[-1])) / 0.6745
    uthresh = sigma * np.sqrt(2 * np.log(len(data)))
    coeffs[1:] = [pywt.threshold(c, value=uthresh, mode='soft') for c in coeffs[1:]]
    return pywt.waverec(coeffs, wavelet)


def butter_bandpass(lowcut, highcut, fs, order=6):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a


def butter_bandpass_filter(data, lowcut, highcut, fs, order=6):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = filtfilt(b, a, data)
    return y
def notch_filter_signal(data, freq, fs, q=30):
    b, a = iirnotch(freq, q, fs)
    return filtfilt(b, a, data)



Fs = 256
buffer_size = int(1 * Fs)

app = QtWidgets.QApplication([])
win = pg.GraphicsLayoutWidget(show=True, title="EEG Signal Real-Time Visualization")
win.resize(1400, 800)
win.setWindowTitle('Real-Time EEG Signal')


raw_plot = win.addPlot(title="Band-pass 1-60 Hz + Notch Signal")  
denoised_plot = win.addPlot(title="Denoised Signal")
win.nextRow()
filtered_plot = win.addPlot(title="Filtered Signal (8-13 Hz)")
fft_plot = win.addPlot(title="FFT of Filtered Signal")
raw_plot.setLabel('left', 'Amplitud')
raw_plot.setLabel('bottom', 'Tiempo (ms)')
raw_plot.showGrid(x=True, y=True)

denoised_plot.setLabel('left', 'Amplitud')
denoised_plot.setLabel('bottom', 'Tiempo (ms)')
denoised_plot.showGrid(x=True, y=True)

filtered_plot.setLabel('left', 'Amplitud')
filtered_plot.setLabel('bottom', 'Tiempo (ms)')
filtered_plot.showGrid(x=True, y=True)

fft_plot.setLabel('left', 'Magnitud')
fft_plot.setLabel('bottom', 'Frecuencia (Hz)')
fft_plot.showGrid(x=True, y=True)
fft_plot.enableAutoRange(axis='y')

raw_curve = raw_plot.plot()
denoised_curve = denoised_plot.plot()
filtered_curve = filtered_plot.plot()
fft_curve = fft_plot.plot()




lowcut = 1.0
highcut = 13.0

low_freqs_filt = 1
high_freqs_filt = 60

notch_freq = 60


b, a = butter_bandpass(lowcut, highcut, Fs)

params = BrainFlowInputParams()
params.serial_port = 'COM11'
board = BoardShim(BoardIds.CYTON_BOARD.value, params)
board.prepare_session()
board.start_stream()

buffer_data = np.zeros((24, buffer_size))


EEG_ROWS = [2, 3]


def update_eeg_signal():
    global buffer_data, samples_received

    data = board.get_board_data()
    if data.shape[1] == 0:
        return

   
    samples_received += data.shape[1]
    data = data[:, -buffer_size:]

    buffer_data = np.roll(buffer_data, -data.shape[1], axis=1)
    buffer_data[:, -data.shape[1]:] = data

  
    if samples_received < buffer_size:
        return

    selected_data = buffer_data[EEG_ROWS, :]
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
    freqs = np.fft.fftfreq(L, d=1.0 / Fs)[:L // 2]  # CAMBIO: eje de frecuencias exacto (pasos de Fs/L)
    fft_curve.setData(freqs, fft_magnitude)

    if np.isnan(fft_magnitude).any() or np.isnan(freqs).any():
        print("Error: fft_magnitude o freqs contiene valores NaN.")
    else:
        area_under_curve = trapezoid(fft_magnitude, dx=freqs[1] - freqs[0])
        eyes_closed_ready = (current_phase == "Eyes Closed"
                             and phase_start is not None
                             and time.time() - phase_start >= SETTLE_TIME)
        if eyes_closed_ready:
            auc_values.append(float(area_under_curve))
            print(f"Área bajo la curva (ojos cerrados): {area_under_curve}")




RESULT_DIR = pathlib.Path("C:/Users/chris/PycharmProjects/exoGUI/PAPER_TESTS")

def save_results_to_py(mean_max, std_max):
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    result_file_path = RESULT_DIR / "resultados_BLINK.py"

    with open(result_file_path, mode='w') as file:
        file.write(f'# Valores calculados del entrenamiento\n')
        file.write(f'mean_max = {mean_max}\n')
        file.write(f'std_max = {std_max}\n')
        file.write(f'#AUC_Vals = {auc_values}\n')  
    print(f"Resultados guardados en {result_file_path}")


def update_phase():
    global phase_index, next_phase_time, current_phase, phase_start
    current_time = time.time()

    if current_time >= next_phase_time:
        phase_index = (phase_index + 1) % len(training_phases)
        next_phase_time = current_time + training_phases[phase_index]["duration"] / 1000

        #engine.say('Cambio')
        #engine.runAndWait()
        #winsound.Beep(800, 100)
        current_phase = training_phases[phase_index]['phase']
        print(f"Fase: {current_phase}")
        winsound.Beep(800, 100)
        if current_phase == "Eyes Opened":
            engine.say("Descansa")
        elif current_phase == "Eyes Closed":
            engine.say("Parpadeo")
        elif current_phase == "Finish":
            engine.say("Finalizado")

        engine.runAndWait()
        phase_start = time.time()

        if phase_index == 0:
            print("Entrenamiento finalizado. Calculando estadísticas...")
            if auc_values:
                filtered_auc_values = [val for val in auc_values if val < 999999 and val > 100]

                if filtered_auc_values:
                    mean_max = np.mean(filtered_auc_values)
                    std_max = np.std(filtered_auc_values)
                    print(f"MEAN AUC: {mean_max}")
                    print(f"STD AUC: {std_max}")

                    save_results_to_py(mean_max, std_max)

                else:
                    print("No se encontraron valores de AUC dentro del rango válido (100 a 999999).")
            else:
                print("No se encontraron datos de AUC.")

           
            eeg_timer.stop()
            phase_timer.stop()
            app.quit()


eeg_timer = QtCore.QTimer()
eeg_timer.timeout.connect(update_eeg_signal)
eeg_timer.start(100)

phase_timer = QtCore.QTimer()
phase_timer.timeout.connect(update_phase)


board.get_board_data()
next_phase_time = time.time() + training_phases[phase_index]["duration"] / 1000
phase_start = time.time()
phase_timer.start(100)

try:
    QtGui.QGuiApplication.instance().exec()
finally:
    board.stop_stream()
    board.release_session()
