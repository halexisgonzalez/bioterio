#pragma once

#include <esp_camera.h>

// Inicialización de la cámara OV2640.
//
// Responsabilidad única: traducir "Settings" (lo que le importa al resto
// del firmware) al camera_config_t de bajo nivel de esp_camera. Nadie fuera
// de este archivo necesita conocer los pines ni los campos de esp_camera.
namespace CameraManager {

struct Settings {
  framesize_t frameSize;
  int jpegQuality;
  bool verticalFlip;
  bool horizontalMirror;
};

// Devuelve false si la cámara no pudo inicializarse (el detalle del error
// queda en el log serie).
bool begin(const Settings &settings);

} // namespace CameraManager
