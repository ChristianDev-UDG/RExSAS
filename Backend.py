# Backend.py (versión con process_loop: llama alternadamente a alpha y blink)
import sys
import numpy as np
import pywt
import time
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from scipy.signal import butter, filtfilt, iirnotch, lfilter
from scipy.fftpack import fft
from scipy.integrate import simpson, trapezoid

from HELPERS import resultados_ALPHA, resultados_BLINK

from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds


class EEGProcessor(QObject):
    alpha_signal = pyqtSignal()
    blink_signal = pyqtSignal()

    def __init__(self, low_freqs_filt=1.0, high_freqs_filt=60.0, notch_freq=60.0, Q_notch=50,
                 low_cut_alpha=8.0, high_cut_alpha=13.0, low_cut_blink=4.0, high_cut_blink=20.0,
                 fs=250, buffer_duration=1, board_id=BoardIds.CYTON_BOARD.value, port='COM4'):
        super().__init__()

        # Control flags
        self.active = True
        self.running = True

        # Parámetros
        self.low_cut_alpha = float(low_cut_alpha)
        self.high_cut_alpha = float(high_cut_alpha)
        self.low_cut_blink = float(low_cut_blink)
        self.high_cut_blink = float(high_cut_blink)
        self.fs = float(fs)

        self.low_freqs_filt = float(low_freqs_filt)
        self.high_freqs_filt = float(high_freqs_filt)
        self.notch_freq = float(notch_freq)
        self.Q_notch = float(Q_notch)

        # Buffer
        self.buffer_size = int(buffer_duration * fs)
        self.buffer_data = np.zeros((24, self.buffer_size))

        # Estado
        self.phase_counts = {"ones": 0, "zeros": 0}
        self.consecutive_ones = 0
        self.RELAXATION_1 = 0
        self.RELAXATION_2 = 0
        self.BLINK = 0
        self.UNDEFINED = 0

        # Filtros
        self.b_alpha, self.a_alpha = self.butter_bandpass(self.low_cut_alpha, self.high_cut_alpha, self.fs)
        self.b_blink, self.a_blink = self.butter_bandpass(self.low_cut_blink, self.high_cut_blink, self.fs)
        self.b_signal, self.a_signal = self.butter_bandpass(self.low_freqs_filt, self.high_freqs_filt, self.fs)

        # Board (iniciar stream aquí está OK; la GUI moverá este objeto a QThread)
        self.params = BrainFlowInputParams()
        self.params.serial_port = port
        self.board = BoardShim(board_id, self.params)
        self.board.prepare_session()
        self.board.start_stream()

    # Control externo
    def pause(self):
        self.active = False

    def resume(self):
        self.active = True

    def stop(self):
        self.running = False
        try:
            self.board.stop_stream()
        except Exception:
            pass
        try:
            self.board.release_session()
        except Exception:
            pass

    # Filtros / utilidades (idénticas)
    def butter_bandpass(self, lowcut, highcut, fs, order=4):
        nyquist = 0.5 * fs
        low = lowcut / nyquist
        high = highcut / nyquist
        b, a = butter(order, [low, high], btype='band')
        return b, a

    def butter_bandpass_filter(self, data, b, a):
        try:
            return filtfilt(b, a, data)
        except Exception:
            return data

    def denoise_signal(self, data, wavelet='db4', level=3):
        try:
            coeffs = pywt.wavedec(data, wavelet, level=level)
            sigma = np.median(np.abs(coeffs[-1])) / 0.6745
            uthresh = sigma * np.sqrt(2 * np.log(len(data)))
            coeffs[1:] = [pywt.threshold(c, value=uthresh, mode='soft') for c in coeffs[1:]]
            return pywt.waverec(coeffs, wavelet)
        except Exception:
            return data

    def notch_filter_signal(self, data, freq, Q, fs):
        try:
            b_notch, a_notch = iirnotch(freq / (0.5 * fs), Q)
            return lfilter(b_notch, a_notch, data)
        except Exception:
            return data

    # Resultados FFT alpha/blink (idénticos)
    def process_fft_results_alpha(self, area_fft_alpha):
        mean_auc_alpha = resultados_ALPHA.mean_auc
        std_auc_alpha = resultados_ALPHA.std_auc
        k = 0.5
        if area_fft_alpha > (mean_auc_alpha) and area_fft_alpha < (mean_auc_alpha + (std_auc_alpha + std_auc_alpha * k)):
            self.phase_counts["ones"] += 1
            self.RELAXATION_1 += 1
            print('RELAXATION_1')
            try:
                self.alpha_signal.emit()
            except Exception:
                pass
        else:
            self.phase_counts["zeros"] += 1
            # print('0')

    def process_fft_results_blink(self, area_fft_blink):
        mean_auc_blink = resultados_BLINK.mean_max
        std_auc_blink = resultados_BLINK.std_max
        k = 1.0
        if mean_auc_blink + std_auc_blink >= area_fft_blink and area_fft_blink > mean_auc_blink - std_auc_blink:
            self.consecutive_ones += 1
        elif mean_auc_blink + std_auc_blink < area_fft_blink <= mean_auc_blink + (std_auc_blink * k) + std_auc_blink:
            self.consecutive_ones += 1
        else:
            self.consecutive_ones = 0
        if self.consecutive_ones >= 10:
            print("BLINK detected")
            self.consecutive_ones = 0
            try:
                self.blink_signal.emit()
            except Exception:
                pass

    # --- Funciones que realizan una sola pasada (no bucle infinito) ---
    def process_once_alpha(self):
        """Una sola pasada de procesamiento alpha (no bucle infinito)."""
        try:
            data = self.board.get_board_data()
        except Exception:
            return
        if data is None or data.shape[1] == 0:
            return
        self.update_buffer(data)
        selected_data = self.buffer_data[5:7, :]
        signal = np.mean(selected_data, axis=0)
        bpass_signal = self.butter_bandpass_filter(signal, self.b_signal, self.a_signal)
        notch_signal = self.notch_filter_signal(bpass_signal, self.notch_freq, self.Q_notch, self.fs)
        denoised_signal = self.denoise_signal(notch_signal)
        filtered = self.butter_bandpass_filter(denoised_signal, self.b_alpha, self.a_alpha)
        L = len(filtered)
        if L < 2:
            return
        fft_result = fft(filtered)
        fft_magnitude = np.abs(fft_result[:L // 2])
        freqs = np.linspace(0.0, self.fs / 2, L // 2)
        dx = (freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
        area = trapezoid(fft_magnitude, dx=dx)
        self.process_fft_results_alpha(area)

    def process_once_blink(self):
        """Una sola pasada de procesamiento blink (no bucle infinito)."""
        try:
            data = self.board.get_board_data()
        except Exception:
            return
        if data is None or data.shape[1] == 0:
            return
        self.update_buffer(data)
        selected_data = self.buffer_data[1:2, :]
        signal = np.mean(selected_data, axis=0)
        bpass_signal = self.butter_bandpass_filter(signal, self.b_signal, self.a_signal)
        notch_signal = self.notch_filter_signal(bpass_signal, self.notch_freq, self.Q_notch, self.fs)
        denoised_signal = self.denoise_signal(notch_signal)
        filtered = self.butter_bandpass_filter(denoised_signal, self.b_blink, self.a_blink)
        L = len(filtered)
        if L < 2:
            return
        fft_result = fft(filtered)
        fft_magnitude = np.abs(fft_result[:L // 2])
        freqs = np.linspace(0.0, self.fs / 2, L // 2)
        dx = (freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
        area_blink = simpson(fft_magnitude, dx=dx)
        self.process_fft_results_blink(area_blink)

    # --- Bucle principal que se conecta a QThread.started ---
    def process_loop(self):
        """Bucle que ejecuta alternadamente process_once_alpha y process_once_blink.
           Diseñado para ejecutarse dentro de un QThread (no crear hilos internos)."""
        while self.running:
            if not self.active:
                QThread.msleep(100)
                continue

            # Una pasada alpha
            try:
                self.process_once_alpha()
            except Exception as e:
                print("Error process_once_alpha:", e)

            # Una pasada blink
            try:
                self.process_once_blink()
            except Exception as e:
                print("Error process_once_blink:", e)

            # Pequeña pausa para evitar busy-loop; ajusta si necesitas más/menos frecuencia
            QThread.msleep(10)

    def update_buffer(self, new_data):
        try:
            self.buffer_data = np.roll(self.buffer_data, -new_data.shape[1], axis=1)
            self.buffer_data[:, -new_data.shape[1]:] = new_data
        except Exception:
            pass


if __name__ == '__main__':
    # Solo para pruebas unitarias; en la GUI no se debe instanciar automáticamente
    eeg = EEGProcessor()
    try:
        while True:
            QThread.msleep(1000)
    except KeyboardInterrupt:
        eeg.stop()
