import serial
import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import butter, filtfilt
import time
import threading
import tkinter as tk
from tkinter import Scale, Button

class AMReceiver:
    def __init__(self):
        self.ser = None
        self.sample_rate = 44100
        self.carrier_freq = 1000  # 1 kHz
        self.volume = 0.8
        self.recording = False
        self.samples = []
        
    def connect_arduino(self, port='COM3'):
        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
            print(f"Подключено к {port}")
            return True
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return False
    
    def am_demodulate(self, signal):
        """АМ-демодуляция в реальном времени"""
        t = np.arange(len(signal)) / self.sample_rate
        carrier = np.sin(2 * np.pi * self.carrier_freq * t)
        
        # Детектирование огибающей
        modulated = signal * carrier
        b, a = butter(4, 4000/(0.5*self.sample_rate), 'low')
        envelope = filtfilt(b, a, np.abs(modulated))
        
        return envelope * self.volume
    
    def audio_callback(self, outdata, frames, time_info, status):
        """Callback для звуковой карты"""
        if self.ser and self.ser.in_waiting:
            try:
                # Чтение данных порциями
                raw_data = []
                for _ in range(frames):
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode('ascii', errors='ignore').strip()
                        if line:
                            raw_data.append(int(line) / 1023.0)
                
                if len(raw_data) == frames:
                    # Демодуляция
                    demodulated = self.am_demodulate(np.array(raw_data))
                    outdata[:] = demodulated.reshape(-1, 1)
                    
                    # Запись если включено
                    if self.recording:
                        self.samples.extend(demodulated)
                        
            except Exception as e:
                print(f"Ошибка обработки: {e}")
    
    def start_receiver(self):
        """Запуск приемника"""
        if not self.ser:
            print("Сначала подключите Arduino!")
            return
        
        print("Запуск приемника... Ctrl+C для остановки")
        
        with sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self.audio_callback,
            blocksize=256
        ):
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("Остановка приемника")
    
    def start_recording(self):
        """Начать запись"""
        self.recording = True
        self.samples = []
        print("Запись начата...")
    
    def stop_recording(self):
        """Остановить запись и сохранить"""
        self.recording = False
        if self.samples:
            filename = f"am_record_{int(time.time())}.wav"
            sf.write(filename, np.array(self.samples), self.sample_rate)
            print(f"Запись сохранена: {filename}")
        else:
            print("Нет данных для записи")

def create_gui(receiver):
    """Создание графического интерфейса"""
    root = tk.Tk()
    root.title("AM Receiver")
    root.geometry("300x200")
    
    # Регулятор частоты
    freq_label = tk.Label(root, text="Частота настройки (Гц)")
    freq_label.pack()
    
    freq_scale = Scale(root, from_=500, to=2000, orient='horizontal',
                      command=lambda v: setattr(receiver, 'carrier_freq', float(v)))
    freq_scale.set(1000)
    freq_scale.pack()
    
    # Регулятор громкости
    vol_label = tk.Label(root, text="Громкость")
    vol_label.pack()
    
    vol_scale = Scale(root, from_=0, to=100, orient='horizontal',
                     command=lambda v: setattr(receiver, 'volume', float(v)/100))
    vol_scale.set(80)
    vol_scale.pack()
    
    # Кнопки управления
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    
    record_btn = Button(btn_frame, text="Запись", 
                       command=receiver.start_recording)
    record_btn.pack(side='left', padx=5)
    
    stop_btn = Button(btn_frame, text="Стоп", 
                     command=receiver.stop_recording)
    stop_btn.pack(side='left', padx=5)
    
    return root

def main():
    # Создаем приемник
    receiver = AMReceiver()
    
    # Подключаем Arduino
    if not receiver.connect_arduino('COM3'):  # Укажи свой порт
        return
    
    # Запускаем GUI в отдельном потоке
    gui_thread = threading.Thread(target=lambda: create_gui(receiver).mainloop())
    gui_thread.daemon = True
    gui_thread.start()
    
    # Запускаем приемник
    receiver.start_receiver()

if __name__ == "__main__":
    main()