import csv
import os
import time
from collections import deque
import numpy as np
import pywt
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from scipy.signal import butter, filtfilt, iirnotch, lfilter
from scipy.fftpack import fft
from scipy.integrate import simpson, trapezoid

from PAPER_TESTS import resultados_ALPHA, resultados_BLINK

from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds


BLINK_REFRACTORY_S = 1.5


BLINK_AUTO = True
BLINK_FACTOR = 2.5
BLINK_MAX_FACTOR = 20.0
BLINK_REST_WINDOW = 600

BLINK_REST_S = 0.5

LOG_DIR = "registry"

DEBUG_BLINK = False


class EEGProcessor(QObject):
    alpha_signal = pyqtSignal()
    blink_signal = pyqtSignal()

    def __init__(self, low_freqs_filt=1.0, high_freqs_filt=60.0, notch_freq=60.0, Q_notch=50,
                 low_cut_alpha=8.0, high_cut_alpha=13.0, low_cut_blink=1.0, high_cut_blink=13.0,
                 fs=256, buffer_duration=1, board_id=BoardIds.CYTON_BOARD.value, port='COM11'):
        super().__init__()

        self.active = True
        self.running = True
        self.loop_running = False

        self.low_cut_alpha = float(low_cut_alpha)
        self.high_cut_alpha = float(high_cut_alpha)
        self.low_cut_blink = float(low_cut_blink)
        self.high_cut_blink = float(high_cut_blink)
        self.fs = float(fs)

        self.low_freqs_filt = float(low_freqs_filt)
        self.high_freqs_filt = float(high_freqs_filt)
        self.notch_freq = float(notch_freq)
        self.Q_notch = float(Q_notch)

        self.buffer_size = int(buffer_duration * fs)
        self.buffer_data = np.zeros((24, self.buffer_size))
        self.samples_received = 0

        self.phase_counts = {"ones": 0, "zeros": 0}
        self.consecutive_ones = 0
        self.blink_block_until = 0.0
        self.blink_armed = False
        self.blink_history = deque(maxlen=BLINK_REST_WINDOW)
        self.blink_rest = None
        self.blink_cycles = 0
        self.blink_below_since = None
        self.blink_rest_seen = time.monotonic()
        self.last_blink_warning = 0.0

        self.session_id = time.strftime("%Y%m%d_%H%M%S")
        self.participant = "P05"
        self.log_rows = []
        self.log_saved = False
        self.last_alpha = (0.0, 0)
        self.last_debug_print = 0.0
        self.RELAXATION_1 = 0
        self.RELAXATION_2 = 0
        self.BLINK = 0
        self.UNDEFINED = 0

        self.b_alpha, self.a_alpha = self.butter_bandpass(self.low_cut_alpha, self.high_cut_alpha, self.fs)
        self.b_blink, self.a_blink = self.butter_bandpass(self.low_cut_blink, self.high_cut_blink, self.fs)
        self.b_signal, self.a_signal = self.butter_bandpass(self.low_freqs_filt, self.high_freqs_filt, self.fs)
        self.b_notch, self.a_notch = iirnotch(self.notch_freq / (0.5 * self.fs), self.Q_notch)

        self.dx = (self.fs / 2) / (self.buffer_size // 2 - 1)

        k_alpha = 1.0
        self.alpha_low = resultados_ALPHA.mean_auc
        self.alpha_high = resultados_ALPHA.mean_auc + resultados_ALPHA.std_auc * (1 + k_alpha)
        k_blink = 1.0
        self.blink_low = resultados_BLINK.mean_max - resultados_BLINK.std_max
        self.blink_high = resultados_BLINK.mean_max + resultados_BLINK.std_max * (1 + k_blink)

        self.params = BrainFlowInputParams()
        self.params.serial_port = port
        self.board = BoardShim(board_id, self.params)
        self.board.prepare_session()
        self.board.start_stream()

    def pause(self):
        self.active = False

    def resume(self):
        self.active = True

    def stop(self):
        self.running = False
        if not self.loop_running:
            self.release_board()

    def save_log(self):
        if self.log_saved or not self.log_rows:
            return
        self.log_saved = True
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            path = os.path.join(LOG_DIR, f"backend_{self.participant}_{self.session_id}.csv")
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["time", "area_alpha", "alpha", "area_blink", "blink_detectado"])
                writer.writerows(self.log_rows)
            print(f"Registries of Backend saved in {path}")
        except OSError as e:
            print("Saving not successful:", e)

    def release_board(self):
        self.save_log()
        try:
            self.board.stop_stream()
        except Exception:
            pass
        try:
            self.board.release_session()
        except Exception:
            pass

    def butter_bandpass(self, lowcut, highcut, fs, order=4):
        nyquist = 0.5 * fs
        low = lowcut / nyquist
        high = highcut / nyquist
        b, a = butter(order, [low, high], btype='band')
        return b, a

    def butter_bandpass_filter(self, data, b, a):
        return filtfilt(b, a, data)

    def denoise_signal(self, data, wavelet='db4', level=3):
        coeffs = pywt.wavedec(data, wavelet, level=level)
        sigma = np.median(np.abs(coeffs[-1])) / 0.6745
        uthresh = sigma * np.sqrt(2 * np.log(len(data)))
        coeffs[1:] = [pywt.threshold(c, value=uthresh, mode='soft') for c in coeffs[1:]]
        return pywt.waverec(coeffs, wavelet)

    def notch_filter_signal(self, data):
        return lfilter(self.b_notch, self.a_notch, data)

    def fft_magnitude(self, signal, b_band, a_band):
        bpass_signal = self.butter_bandpass_filter(signal, self.b_signal, self.a_signal)
        notch_signal = self.notch_filter_signal(bpass_signal)
        denoised_signal = self.denoise_signal(notch_signal)
        filtered = self.butter_bandpass_filter(denoised_signal, b_band, a_band)
        L = len(filtered)
        return np.abs(fft(filtered)[:L // 2])

    def process_fft_results_alpha(self, area_fft_alpha):
        if self.alpha_low < area_fft_alpha < self.alpha_high:
            self.phase_counts["ones"] += 1
            self.RELAXATION_1 += 1
            self.last_alpha = (area_fft_alpha, 1)
            # print('RELAXATION_1')
            self.alpha_signal.emit()
        else:
            self.phase_counts["zeros"] += 1
            self.last_alpha = (area_fft_alpha, 0)
            # print('0')

    def blink_limits(self, area_fft_blink):
        if not BLINK_AUTO:
            return self.blink_low, self.blink_high, self.blink_low

        self.blink_history.append(area_fft_blink)
        self.blink_cycles += 1
        if len(self.blink_history) < 150:                       # unos 2 s de señal antes de empezar
            return None
        if self.blink_rest is None or self.blink_cycles % 20 == 0:
            primera_vez = self.blink_rest is None
            self.blink_rest = float(np.median(self.blink_history))    # la mediana ignora los parpadeos
            if primera_vez:
                print(f"Parpadeo: nivel de reposo medido = {self.blink_rest:.0f}; "
                      f"se cuenta un parpadeo por encima de {self.blink_rest * BLINK_FACTOR:.0f}")
        rest = self.blink_rest
        return rest * BLINK_FACTOR, rest * BLINK_MAX_FACTOR, rest * BLINK_FACTOR * 0.8

    def process_fft_results_blink(self, area_fft_blink):
        now = time.monotonic()
        detected = 0
        limits = self.blink_limits(area_fft_blink)
        if limits is not None:
            low, high, rest_limit = limits
            if DEBUG_BLINK and now - self.last_debug_print >= 0.5:
                self.last_debug_print = now
                print(f"blink: area = {area_fft_blink:.0f}   umbral = {low:.0f}   tope = {high:.0f}"
                      f"   reposo hasta = {rest_limit:.0f}   seguidos = {self.consecutive_ones}")

            if area_fft_blink <= rest_limit:
                if self.blink_below_since is None:
                    self.blink_below_since = now
                if now - self.blink_below_since >= BLINK_REST_S:    # reposo de verdad, no una bajada momentánea
                    self.blink_armed = True
                    self.blink_rest_seen = now
            else:
                self.blink_below_since = None
            if not BLINK_AUTO and now - self.blink_rest_seen > 5 and now - self.last_blink_warning > 5:
                self.last_blink_warning = now
                print(f"AVISO: el área de parpadeo lleva más de 5 s sin bajar al reposo (vale {area_fft_blink:.0f}; "
                      f"la banda es de {low:.0f} a {high:.0f}). "
                      "Hay que repetir la calibración del parpadeo; mientras tanto no se cuentan parpadeos.")

            if now < self.blink_block_until:
                self.consecutive_ones = 0
            elif self.blink_armed and low < area_fft_blink <= high:
                self.consecutive_ones += 1
            else:
                self.consecutive_ones = 0
            if self.consecutive_ones >= 5:
                print("BLINK detected")
                detected = 1
                self.consecutive_ones = 0
                self.blink_armed = False
                self.blink_block_until = now + BLINK_REFRACTORY_S
                self.blink_signal.emit()

        self.log_rows.append((round(time.time(), 3), round(float(self.last_alpha[0]), 2), self.last_alpha[1],
                              round(float(area_fft_blink), 2), detected))

    def process_once_alpha(self):
        signal = np.mean(self.buffer_data[3:7, :], axis=0)
        fft_magnitude = self.fft_magnitude(signal, self.b_alpha, self.a_alpha)
        area = trapezoid(fft_magnitude, dx=self.dx)
        self.process_fft_results_alpha(area)

    def process_once_blink(self):
        signal = np.mean(self.buffer_data[1:3, :], axis=0)
        fft_magnitude = self.fft_magnitude(signal, self.b_blink, self.a_blink)
        area_blink = simpson(fft_magnitude, dx=self.dx)
        self.process_fft_results_blink(area_blink)

    def process_loop(self):

        self.loop_running = True
        try:
            while self.running:
                if not self.active:
                    QThread.msleep(100)
                    continue

                try:
                    data = self.board.get_board_data()
                    if data is not None and data.shape[1] > 0:
                        self.update_buffer(data)
                        if self.samples_received >= self.buffer_size:
                            self.process_once_alpha()
                            self.process_once_blink()
                except Exception as e:
                    print("Error en process_loop:", e)

                QThread.msleep(10)
        finally:
            self.loop_running = False
            self.release_board()

    def update_buffer(self, new_data):
        new_data = new_data[:, -self.buffer_size:]
        n = new_data.shape[1]
        self.samples_received += n
        self.buffer_data[:, :-n] = self.buffer_data[:, n:]
        self.buffer_data[:, -n:] = new_data


if __name__ == '__main__':
    eeg = EEGProcessor()
    try:
        eeg.process_loop()
    except KeyboardInterrupt:
        eeg.stop()
