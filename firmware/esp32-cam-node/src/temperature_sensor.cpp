#include "temperature_sensor.h"

#include <cmath>

#include "config.h"

#if ENABLE_TEMP_SENSOR

#include <DallasTemperature.h>
#include <OneWire.h>

namespace {
OneWire oneWire(TEMP_SENSOR_PIN);
DallasTemperature sensor(&oneWire);
} // namespace

void TemperatureSensor::begin() { sensor.begin(); }

float TemperatureSensor::readCelsius() {
  sensor.requestTemperatures();
  const float value = sensor.getTempCByIndex(0);
  return (value == DEVICE_DISCONNECTED_C) ? NAN : value;
}

#else

void TemperatureSensor::begin() {}
float TemperatureSensor::readCelsius() { return NAN; }

#endif
