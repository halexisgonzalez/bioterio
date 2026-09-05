#pragma once

// Sensor de temperatura opcional (DS18B20).
//
// El resto del firmware solo llama a readCelsius() y nunca necesita saber
// si el sensor está habilitado, ni qué librería usa por debajo (DIP): esto
// es lo único que sabe de ENABLE_TEMP_SENSOR/config.h en todo el proyecto.
// Si el día de mañana se cambia de sensor, solo se toca este archivo.
class TemperatureSensor {
public:
  void begin();

  // Devuelve NAN si el sensor está deshabilitado o no responde (nunca
  // lanza ni bloquea indefinidamente).
  float readCelsius();
};
