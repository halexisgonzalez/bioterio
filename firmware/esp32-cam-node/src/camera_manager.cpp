#include "camera_manager.h"

#include <Arduino.h>

#include "camera_pins.h"

namespace CameraManager {

bool begin(const Settings &settings) {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  // NOTA: en algunas versiones del core arduino-esp32 estos campos se llaman
  // pin_sscb_sda / pin_sscb_scl en lugar de pin_sccb_sda / pin_sccb_scl (es
  // el mismo pin físico, cambió el nombre del campo entre versiones).
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size = settings.frameSize;
    config.jpeg_quality = settings.jpegQuality;
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST; // descarta frames viejos: prioriza video en vivo sobre completitud
  } else {
    // Sin PSRAM no hay memoria para buffers grandes: bajamos resolución y
    // usamos un solo framebuffer.
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 15;
    config.fb_count = 1;
  }

  const esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("ERROR: fallo al iniciar la camara (0x%x)\n", err);
    return false;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  if (sensor) {
    sensor->set_vflip(sensor, settings.verticalFlip);
    sensor->set_hmirror(sensor, settings.horizontalMirror);
  }

  return true;
}

} // namespace CameraManager
