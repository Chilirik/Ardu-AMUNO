import serial
import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import butter, filtfilt, iirnotch
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports

class TunableReceiver:
    def __init__(self):
        self.ser = None
        self.sample_rate = 8192  # 1 кГц
        self.volume = 0.8
        self.recording = False
        self.samples = []
        self.is_running = False
        self.antenna_type = "wire"
        self.center_freq = 1000    # Центральная частота (Гц)
        self.bandwidth = 500       # Ширина полосы (Гц)
        self.notch_freq = 0        # Подавляемая частота (Гц)
        
    def get_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]
    
    def connect(self, port):
        try:
            if self.ser:
                self.ser.close()
            self.ser = serial.Serial(port, 2000000, timeout=1)
            time.sleep(2)
            return True
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return False
    
    def set_antenna_type(self, antenna_type):
        self.antenna_type = antenna_type
        print(f"Тип антенны: {antenna_type}")
    
    def set_center_frequency(self, freq):
        self.center_freq = freq
        print(f"Центральная частота: {freq} Гц")
    
    def set_bandwidth(self, bw):
        self.bandwidth = bw
        print(f"Ширина полосы: {bw} Гц")
    
    def set_notch_frequency(self, freq):
        self.notch_freq = freq
        print(f"Подавляемая частота: {freq} Гц")
    
    def create_bandpass_filter(self, lowcut, highcut):
        """Создание полосового фильтра"""
        nyq = 0.5 * self.sample_rate
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(4, [low, high], btype='band')
        return b, a
    
    def create_notch_filter(self, freq, quality=30):
        """Создание режекторного фильтра"""
        if freq == 0:
            return None, None
        nyq = 0.5 * self.sample_rate
        freq_norm = freq / nyq
        b, a = iirnotch(freq_norm, quality)
        return b, a
    
    def process_signal(self, signal):
        """Обработка сигнала с настройкой частоты"""
        # Полосовая фильтрация
        lowcut = self.center_freq - self.bandwidth/2
        highcut = self.center_freq + self.bandwidth/2
        
        # Ограничение частот
        lowcut = max(1, lowcut)
        highcut = min(self.sample_rate/2 - 1, highcut)
        
        if highcut > lowcut:
            b_bp, a_bp = self.create_bandpass_filter(lowcut, highcut)
            signal = filtfilt(b_bp, a_bp, signal)
        
        # Режекторный фильтр (подавление помех)
        if self.notch_freq > 0:
            b_notch, a_notch = self.create_notch_filter(self.notch_freq)
            if b_notch is not None:
                signal = filtfilt(b_notch, a_notch, signal)
        
        return signal * self.volume
    
    def audio_callback(self, outdata, frames, time_info, status):
        if self.ser and self.ser.in_waiting >= 2 * frames:
            try:
                raw_data = self.ser.read(2 * frames)
                processed_data = []
                
                for i in range(frames):
                    high_byte = raw_data[2*i]
                    low_byte = raw_data[2*i + 1]
                    value = (high_byte << 8) | low_byte
                    normalized = (value / 512.0) - 1.0
                    processed_data.append(normalized)
                
                # Обработка с текущими настройками частоты
                filtered = self.process_signal(np.array(processed_data))
                outdata[:] = filtered.reshape(-1, 1)
                
                if self.recording:
                    self.samples.extend(filtered)
                    
            except Exception as e:
                print(f"Ошибка обработки: {e}")
    
    def start_receiver(self):
        if not self.ser:
            return False
        
        self.is_running = True
        print(f"Запуск на {self.sample_rate} Гц")
        print(f"Настройка: {self.center_freq} Гц ± {self.bandwidth} Гц")
        
        with sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self.audio_callback,
            blocksize=1024
        ):
            while self.is_running:
                time.sleep(0.1)
        return True
    
    def start_recording(self):
        self.recording = True
        self.samples = []
        print("Запись начата")
    
    def stop_recording(self):
        self.recording = False
        if self.samples:
            filename = f"record_{self.center_freq}Hz.wav"
            sf.write(filename, np.array(self.samples), self.sample_rate)
            print(f"Запись сохранена: {filename}")
            return filename
        return None

def create_gui():
    receiver = TunableReceiver()
    
    root = tk.Tk()
    root.title("Настраиваемый радиоприемник")
    root.geometry("600x600")
    
    # Стиль
    style = ttk.Style()
    style.configure('TFrame', background='#f0f0f0')
    style.configure('TLabel', background='#f0f0f0', font=('Arial', 9))
    style.configure('TButton', font=('Arial', 9))
    
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Заголовок
    title_label = ttk.Label(main_frame, text="Настраиваемый приемник", 
                           font=('Arial', 14, 'bold'))
    title_label.pack(pady=(0, 15))
    
    # Выбор порта
    port_frame = ttk.Frame(main_frame)
    port_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(port_frame, text="COM порт:").pack(side=tk.LEFT)
    port_var = tk.StringVar()
    port_combo = ttk.Combobox(port_frame, textvariable=port_var, width=15)
    port_combo.pack(side=tk.LEFT, padx=5)
    
    def refresh_ports():
        ports = receiver.get_ports()
        port_combo['values'] = ports
        if ports:
            port_combo.set(ports[0])
    
    ttk.Button(port_frame, text="Обновить", command=refresh_ports).pack(side=tk.LEFT, padx=5)
    
    # Выбор антенны
    antenna_frame = ttk.LabelFrame(main_frame, text="Тип антенны", padding="10")
    antenna_frame.pack(fill=tk.X, pady=10)
    
    antenna_var = tk.StringVar(value="wire")
    ttk.Radiobutton(antenna_frame, text="Проволочная", variable=antenna_var, 
                   value="wire", command=lambda: receiver.set_antenna_type("wire")).pack(anchor=tk.W)
    ttk.Radiobutton(antenna_frame, text="ТВ антенна", variable=antenna_var, 
                   value="tv", command=lambda: receiver.set_antenna_type("tv")).pack(anchor=tk.W)
    
    # Настройки частоты
    freq_frame = ttk.LabelFrame(main_frame, text="Настройка частоты", padding="10")
    freq_frame.pack(fill=tk.X, pady=10)
    
    # Центральная частота
    ttk.Label(freq_frame, text="Центральная частота (Гц):").grid(row=0, column=0, sticky=tk.W, pady=2)
    center_freq_var = tk.IntVar(value=1000)
    center_freq_scale = ttk.Scale(freq_frame, from_=50, to=5000, variable=center_freq_var,
                                 orient=tk.HORIZONTAL, command=lambda v: receiver.set_center_frequency(int(float(v))))
    center_freq_scale.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
    center_freq_label = ttk.Label(freq_frame, text="1000 Гц")
    center_freq_label.grid(row=0, column=2, padx=5)
    
    # Ширина полосы
    ttk.Label(freq_frame, text="Ширина полосы (Гц):").grid(row=1, column=0, sticky=tk.W, pady=2)
    bandwidth_var = tk.IntVar(value=500)
    bandwidth_scale = ttk.Scale(freq_frame, from_=10, to=2000, variable=bandwidth_var,
                               orient=tk.HORIZONTAL, command=lambda v: receiver.set_bandwidth(int(float(v))))
    bandwidth_scale.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
    bandwidth_label = ttk.Label(freq_frame, text="500 Гц")
    bandwidth_label.grid(row=1, column=2, padx=5)
    
    # Режекторный фильтр
    ttk.Label(freq_frame, text="Подавить частоту (Гц):").grid(row=2, column=0, sticky=tk.W, pady=2)
    notch_var = tk.IntVar(value=0)
    notch_scale = ttk.Scale(freq_frame, from_=0, to=3000, variable=notch_var,
                           orient=tk.HORIZONTAL, command=lambda v: receiver.set_notch_frequency(int(float(v))))
    notch_scale.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
    notch_label = ttk.Label(freq_frame, text="0 Гц")
    notch_label.grid(row=2, column=2, padx=5)
    
    # Обновление лейблов
    def update_labels(*args):
        center_freq_label.config(text=f"{center_freq_var.get()} Гц")
        bandwidth_label.config(text=f"{bandwidth_var.get()} Гц")
        notch_label.config(text=f"{notch_var.get()} Гц")
    
    center_freq_var.trace('w', update_labels)
    bandwidth_var.trace('w', update_labels)
    notch_var.trace('w', update_labels)
    
    # Громкость
    volume_frame = ttk.Frame(main_frame)
    volume_frame.pack(fill=tk.X, pady=10)
    
    ttk.Label(volume_frame, text="Громкость:").pack(side=tk.LEFT)
    volume_var = tk.DoubleVar(value=0.8)
    volume_scale = ttk.Scale(volume_frame, from_=0.0, to=1.0, variable=volume_var,
                            orient=tk.HORIZONTAL, command=lambda v: setattr(receiver, 'volume', float(v)))
    volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Label(volume_frame, text="80%").pack(side=tk.RIGHT)
    
    volume_var.trace('w', lambda *args: volume_scale.master.winfo_children()[-1].config(
        text=f"{int(volume_var.get() * 100)}%"))
    
    # Кнопки управления
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=15)
    
    def connect_device():
        if receiver.connect(port_var.get()):
            messagebox.showinfo("Успех", "Устройство подключено!")
        else:
            messagebox.showerror("Ошибка", "Не удалось подключиться!")
    
    def start_receiver():
        receiver.set_antenna_type(antenna_var.get())
        threading.Thread(target=receiver.start_receiver, daemon=True).start()
    
    ttk.Button(button_frame, text="Подключить", command=connect_device).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Старт", command=start_receiver).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Запись", command=receiver.start_recording).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Стоп записи", command=receiver.stop_recording).pack(side=tk.LEFT, padx=5)
   
    ttk.Button(button_frame, text="Стоп", command=lambda: setattr(receiver, 'is_running', False)).pack(side=tk.LEFT, padx=5)
    
    # Статус
    status_var = tk.StringVar(value="Готов к работе")
    status_label = ttk.Label(main_frame, textvariable=status_var, font=('Arial', 10, 'italic'))
    status_label.pack(pady=5)
    
    # Настройка весов
    freq_frame.columnconfigure(1, weight=1)
    
    # Первоначальное обновление
    refresh_ports()
    
    return root

def main():
    print("Настраиваемый радиоприемник запущен")
    print("Регулировка частот доступна!")
    
    root = create_gui()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nПриложение завершено")

if __name__ == "__main__":
    main()