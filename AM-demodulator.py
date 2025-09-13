import serial
import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import butter, filtfilt
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports

class UniversalReceiver:
    def __init__(self):
        self.ser = None
        self.sample_rate = 44100
        self.antenna_type = "tv"  # "tv" или "wire"
        self.carrier_freq = 1000000  # 1 МГц для проволоки
        self.fm_freq = 100000000    # 100 МГц для ТВ
        self.volume = 0.8
        self.recording = False
        self.samples = []
        self.is_running = False
        
    def get_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]
    
    def connect(self, port):
        try:
            if self.ser:
                self.ser.close()
            self.ser = serial.Serial(port, 115200, timeout=1)
            # Ждем готовности Arduino
            start_time = time.time()
            while time.time() - start_time < 5:
                line = self.ser.readline().decode().strip()
                if "ARDUINO_READY" in line:
                    return True
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def set_antenna_type(self, antenna_type):
        self.antenna_type = antenna_type
        print(f"Антенна: {antenna_type}")
    
    def process_tv_signal(self, signal):
        """Обработка для ТВ-антенны (УКВ)"""
        # Полосовой фильтр для FM диапазона
        b, a = butter(4, [88000000/(0.5*self.sample_rate), 
                        108000000/(0.5*self.sample_rate)], 'bandpass')
        filtered = filtfilt(b, a, signal)
        
        # FM детектирование (упрощенное)
        diff = np.diff(filtered, prepend=0)
        audio = np.abs(diff) * 50  # Усиление
        
        # НЧ фильтр для аудио
        b_low, a_low = butter(4, 15000/(0.5*self.sample_rate), 'low')
        return filtfilt(b_low, a_low, audio) * self.volume
    
    def process_wire_signal(self, signal):
        """Обработка для проволочной антенны (НЧ)"""
        # AM детектирование
        t = np.arange(len(signal)) / self.sample_rate
        carrier = np.sin(2 * np.pi * self.carrier_freq * t)
        
        modulated = signal * carrier
        b, a = butter(4, 5000/(0.5*self.sample_rate), 'low')
        envelope = filtfilt(b, a, np.abs(modulated))
        
        return envelope * self.volume
    
    def audio_callback(self, outdata, frames, time_info, status):
        if self.ser and self.ser.in_waiting:
            try:
                raw_data = []
                for _ in range(frames):
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode('ascii', errors='ignore').strip()
                        if line.startswith("DATA,"):
                            parts = line.split(',')
                            if len(parts) >= 3:
                                value = int(parts[2]) / 1023.0  # filtered value
                                raw_data.append(value)
                
                if len(raw_data) == frames:
                    if self.antenna_type == "tv":
                        processed = self.process_tv_signal(np.array(raw_data))
                    else:
                        processed = self.process_wire_signal(np.array(raw_data))
                    
                    outdata[:] = processed.reshape(-1, 1)
                    
                    if self.recording:
                        self.samples.extend(processed)
                        
            except Exception as e:
                print(f"Processing error: {e}")
    
    def start_receiver(self):
        if not self.ser:
            return False
        
        self.is_running = True
        with sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self.audio_callback,
            blocksize=512
        ):
            while self.is_running:
                time.sleep(0.1)
        return True
    
    def start_recording(self):
        self.recording = True
        self.samples = []
    
    def stop_recording(self):
        self.recording = False
        if self.samples:
            filename = f"record_{self.antenna_type}_{int(time.time())}.wav"
            sf.write(filename, np.array(self.samples), self.sample_rate)
            return filename
        return None

def create_gui():
    receiver = UniversalReceiver()
    
    root = tk.Tk()
    root.title("Универсальный радиоприемник")
    root.geometry("400x400")
    
    # Стиль
    style = ttk.Style()
    style.configure('TFrame', background='#f0f0f0')
    style.configure('TLabel', background='#f0f0f0', font=('Arial', 10))
    style.configure('TButton', font=('Arial', 10))
    
    main_frame = ttk.Frame(root, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    # Выбор порта
    ttk.Label(main_frame, text="COM порт:").grid(row=0, column=0, sticky=tk.W, pady=5)
    port_var = tk.StringVar()
    port_combo = ttk.Combobox(main_frame, textvariable=port_var, width=15)
    port_combo['values'] = receiver.get_ports()
    port_combo.grid(row=0, column=1, pady=5)
    
    def refresh_ports():
        port_combo['values'] = receiver.get_ports()
    
    ttk.Button(main_frame, text="Обновить", command=refresh_ports).grid(row=0, column=2, padx=5)
    
    # Выбор антенны
    ttk.Label(main_frame, text="Тип антенны:").grid(row=1, column=0, sticky=tk.W, pady=5)
    antenna_var = tk.StringVar(value="tv")
    ttk.Radiobutton(main_frame, text="ТВ антенна", variable=antenna_var, value="tv").grid(row=1, column=1, sticky=tk.W)
    ttk.Radiobutton(main_frame, text="Проволочная", variable=antenna_var, value="wire").grid(row=2, column=1, sticky=tk.W)
    
    # Настройки частоты
    ttk.Label(main_frame, text="Несущая частота:").grid(row=3, column=0, sticky=tk.W, pady=5)
    freq_var = tk.IntVar(value=1000)
    freq_scale = ttk.Scale(main_frame, from_=500, to=1500, variable=freq_var, orient=tk.HORIZONTAL)
    freq_scale.grid(row=3, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
    freq_label = ttk.Label(main_frame, text="1000 Hz")
    freq_label.grid(row=4, column=1, sticky=tk.W)
    
    def update_freq_label(val):
        freq_label.config(text=f"{int(float(val))} Hz")
        receiver.carrier_freq = int(float(val)) * 1000
    
    freq_scale.configure(command=update_freq_label)
    
    # Громкость
    ttk.Label(main_frame, text="Громкость:").grid(row=5, column=0, sticky=tk.W, pady=5)
    vol_var = tk.IntVar(value=80)
    ttk.Scale(main_frame, from_=0, to=100, variable=vol_var, orient=tk.HORIZONTAL,
             command=lambda v: setattr(receiver, 'volume', float(v)/100)).grid(row=5, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
    
    # Кнопки управления
    btn_frame = ttk.Frame(main_frame)
    btn_frame.grid(row=6, column=0, columnspan=3, pady=10)
    
    def connect_arduino():
        if receiver.connect(port_var.get()):
            receiver.set_antenna_type(antenna_var.get())
            messagebox.showinfo("Успех", "Arduino подключена!")
        else:
            messagebox.showerror("Ошибка", "Не удалось подключиться!")
    
    def start_listening():
        receiver.set_antenna_type(antenna_var.get())
        threading.Thread(target=receiver.start_receiver, daemon=True).start()
    
    ttk.Button(btn_frame, text="Подключить", command=connect_arduino).grid(row=0, column=0, padx=5)
    ttk.Button(btn_frame, text="Старт", command=start_listening).grid(row=0, column=1, padx=5)
    ttk.Button(btn_frame, text="Запись", command=receiver.start_recording).grid(row=0, column=2, padx=5)
    ttk.Button(btn_frame, text="Стоп", command=lambda: setattr(receiver, 'is_running', False)).grid(row=0, column=3, padx=5)
    
    # Статус
    status_var = tk.StringVar(value="Не подключено")
    ttk.Label(main_frame, textvariable=status_var).grid(row=7, column=0, columnspan=3, pady=10)
    
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    main_frame.columnconfigure(1, weight=1)
    
    return root

def main():
    print("Универсальный радиоприемник запущен")
    print("Поддерживает ТВ-антенны и проволочные антенны")
    
    root = create_gui()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nПрограмма завершена")

if __name__ == "__main__":
    main()