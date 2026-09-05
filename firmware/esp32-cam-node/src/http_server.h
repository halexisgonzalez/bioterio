#pragma once

#include "temperature_sensor.h"

// Servidor HTTP del nodo: expone /capture, /status y /stream.
//
// No conoce nada de WiFi ni de cómo se configuró la cámara más allá de la
// API pública de esp_camera; recibe lo que necesita por Options en vez de
// leer macros de config.h directamente, para quedar desacoplado y ser
// testeable/reutilizable.
namespace HttpServer {

struct Options {
  const char *nodeId;
  const char *apiKey; // vacío ("") deshabilita la autenticación
  TemperatureSensor *temperatureSensor;
};

void start(const Options &options);

} // namespace HttpServer
