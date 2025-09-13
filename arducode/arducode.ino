// Настройка максимальной скорости
#define BAUD_RATE 2000000  // 2 Мбит/с!
#define SAMPLE_RATE 100000 // 100 кГц

// Разгон АЦП
void setupADC() {
  // Максимальная скорость (делитель 16)
  ADCSRA = (1 << ADEN) | (1 << ADPS2);  // Делитель 16 = 1 МГц
  ADMUX = (1 << REFS0);                 // Опорное 5V
}

// Разгон таймера 1
void setupTimer1() {
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1 = 0;
  
  // Режим CTC
  TCCR1B |= (1 << WGM12);
  
  // Без делителя (1:1)
  TCCR1B |= (1 << CS10);
  
  // Настройка частоты
  OCR1A = (16000000 / SAMPLE_RATE) - 1;
  
  // Разрешить прерывание
  TIMSK1 |= (1 << OCIE1A);
  interrupts();
}

// Быстрое чтение АЦП
int fastADC() {
  ADCSRA |= (1 << ADSC);        // Запуск преобразования
  while (ADCSRA & (1 << ADSC)); // Ожидание
  return ADC;
}

// Переменные для прерывания
volatile int adc_value = 0;
volatile bool data_ready = false;

// Прерывание по таймеру
ISR(TIMER1_COMPA_vect) {
  adc_value = fastADC();
  data_ready = true;
}

void setup() {
  Serial.begin(BAUD_RATE);
  setupADC();
  setupTimer1();
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  if (data_ready) {
    // Бинарная отправка (2 байта)
    Serial.write((byte)(adc_value >> 8));
    Serial.write((byte)(adc_value & 0xFF));
    
    // Индикация работы
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    data_ready = false;
  }
}
