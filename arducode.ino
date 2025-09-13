#include <Wire.h>

// Настройки таймера
#define SAMPLE_INTERVAL 20  // 20 мс = 50 Гц

// Пины
const int antennaPin = A0;
const int statusLed = 13;

// Переменные
volatile unsigned long lastSampleTime = 0;
int rawValue = 0;
int filteredValue = 0;

// Прерывание таймера
ISR(TIMER1_COMPA_vect) {
  if (millis() - lastSampleTime >= SAMPLE_INTERVAL) {
    // Чтение антенны с усреднением
    long sum = 0;
    for (int i = 0; i < 16; i++) {
      sum += analogRead(antennaPin);
      delayMicroseconds(50);
    }
    rawValue = sum / 16;
    
    // Простая фильтрация
    filteredValue = (filteredValue * 0.8) + (rawValue * 0.2);
    
    lastSampleTime = millis();
  }
}

void setupTimer1() {
  // Настройка таймера 1 для прерываний
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1 = 0;
  
  OCR1A = 15624;  // 1 секунда (16MHz/1024/1Hz)
  TCCR1B |= (1 << WGM12);  // CTC mode
  TCCR1B |= (1 << CS12) | (1 << CS10);  // 1024 prescaler
  TIMSK1 |= (1 << OCIE1A);  // Enable timer compare interrupt
  
  interrupts();
}

void setup() {
  Serial.begin(115200);
  pinMode(statusLed, OUTPUT);
  
  // Ускоряем АЦП
  ADCSRA = (1 << ADEN) | (1 << ADPS2);  // Делитель 16
  
  setupTimer1();  // Инициализация таймера
  
  Serial.println("ARDUINO_READY");
}

void loop() {
  // Мигаем светодиодом для индикации работы
  static unsigned long lastBlink = 0;
  if (millis() - lastBlink > 1000) {
    digitalWrite(statusLed, !digitalRead(statusLed));
    lastBlink = millis();
  }
  
  // Отправка данных (в прерывании заполняются)
  Serial.print("DATA,");
  Serial.print(rawValue);
  Serial.print(",");
  Serial.println(filteredValue);
  
  delay(10);
}