void setup() {
  Serial.begin(115200);
  // Ускоряем АЦП в 4 раза
  ADCSRA = (1 << ADEN) | (1 << ADPS2);  // Делитель 16 вместо 128
}

void loop() {
  // Чтение антенны с усреднением для стабильности
  long sum = 0;
  for (int i = 0; i < 32; i++) {
    sum += analogRead(A0);
    delayMicroseconds(50);  // 20 кГц семплирование
  }
  int signal = sum / 32;
  
  // Отправка сырого сигнала
  Serial.println(signal);
}