// ============================================================
// Nodo de captura ESP32-CAM - Proyecto Bioterio
//
// Este firmware NO hace tracking ni IA: solo transmite video
// (MJPEG por HTTP) y telemetría (JSON) a la red. Todo el
// procesamiento de visión se hace en la PC central (Python).
//
// Endpoints expuestos:
//   http://<ip>:81/stream   -> video MJPEG en vivo
//   http://<ip>/capture     -> una sola foto JPEG
//   http://<ip>/status      -> JSON con estado del nodo (uptime, rssi, temp, etc.)
// ============================================================

#include <Arduino.h>
#include <WiFi.h>
#include <esp_camera.h>
#include <esp_http_server.h>

#include "camera_pins.h"

#if __has_include("config.h")
  #include "config.h"
#else
  #error "Falta include/config.h -> copia config.example.h como config.h y completa tus datos (ver README.md)"
#endif

#if ENABLE_TEMP_SENSOR
  #include <OneWire.h>
  #include <DallasTemperature.h>
  static OneWire oneWire(TEMP_SENSOR_PIN);
  static DallasTemperature tempSensor(&oneWire);
#endif

static httpd_handle_t camera_httpd = NULL;
static httpd_handle_t stream_httpd = NULL;

// ------------------------------------------------------------
// Cámara
// ------------------------------------------------------------
bool initCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk  = XCLK_GPIO_NUM;
  config.pin_pclk  = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href  = HREF_GPIO_NUM;
  // NOTA: en algunas versiones del core arduino-esp32 estos campos se llaman
  // pin_sscb_sda / pin_sscb_scl en lugar de pin_sccb_sda / pin_sccb_scl.
  // Si falla la compilación con "no member named pin_sccb_sda", cambiá estas
  // dos líneas por pin_sscb_sda / pin_sscb_scl.
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn  = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format  = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size   = CAMERA_FRAMESIZE;
    config.jpeg_quality  = CAMERA_JPEG_QUALITY;
    config.fb_count      = 2;
    config.grab_mode     = CAMERA_GRAB_LATEST;
  } else {
    // Sin PSRAM, hay que bajar la resolución y usar un solo buffer.
    config.frame_size  = FRAMESIZE_QVGA;
    config.jpeg_quality = 15;
    config.fb_count     = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("ERROR: fallo al iniciar la camara (0x%x)\n", err);
    return false;
  }

  sensor_t *s = esp_camera_sensor_get();
  if (s) {
    s->set_vflip(s, CAMERA_VFLIP);
    s->set_hmirror(s, CAMERA_HMIRROR);
  }

  return true;
}

// ------------------------------------------------------------
// Temperatura (opcional)
// ------------------------------------------------------------
float readTemperatureC() {
#if ENABLE_TEMP_SENSOR
  tempSensor.requestTemperatures();
  return tempSensor.getTempCByIndex(0);
#else
  return NAN;
#endif
}

// ------------------------------------------------------------
// HTTP handlers
// ------------------------------------------------------------
#define PART_BOUNDARY "123456789000000000000987654321"
static const char *STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char *STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char *STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t *fb = NULL;
  esp_err_t res = ESP_OK;
  size_t jpg_buf_len = 0;
  uint8_t *jpg_buf = NULL;
  char part_buf[128];

  res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      res = ESP_FAIL;
    } else {
      if (fb->format != PIXFORMAT_JPEG) {
        bool converted = frame2jpg(fb, 80, &jpg_buf, &jpg_buf_len);
        esp_camera_fb_return(fb);
        fb = NULL;
        if (!converted) {
          Serial.println("JPEG compression failed");
          res = ESP_FAIL;
        }
      } else {
        jpg_buf_len = fb->len;
        jpg_buf = fb->buf;
      }
    }

    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
    }
    if (res == ESP_OK) {
      size_t hlen = snprintf(part_buf, sizeof(part_buf), STREAM_PART, jpg_buf_len);
      res = httpd_resp_send_chunk(req, part_buf, hlen);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, (const char *)jpg_buf, jpg_buf_len);
    }

    if (fb) {
      esp_camera_fb_return(fb);
      fb = NULL;
      jpg_buf = NULL;
    } else if (jpg_buf) {
      free(jpg_buf);
      jpg_buf = NULL;
    }

    if (res != ESP_OK) break; // el cliente se desconectó
  }
  return res;
}

static esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
  esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

static esp_err_t status_handler(httpd_req_t *req) {
  char json[256];
  float temp = readTemperatureC();
  char temp_field[32];
  if (isnan(temp)) {
    snprintf(temp_field, sizeof(temp_field), "null");
  } else {
    snprintf(temp_field, sizeof(temp_field), "%.2f", temp);
  }

  int n = snprintf(json, sizeof(json),
    "{\"node_id\":\"%s\",\"uptime_s\":%lu,\"rssi_dbm\":%d,\"free_heap\":%u,\"temp_c\":%s}",
    NODE_ID, millis() / 1000, WiFi.RSSI(), (unsigned)ESP.getFreeHeap(), temp_field);

  httpd_resp_set_type(req, "application/json");
  return httpd_resp_send(req, json, n);
}

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;

  httpd_uri_t capture_uri = {
    .uri = "/capture", .method = HTTP_GET, .handler = capture_handler, .user_ctx = NULL
  };
  httpd_uri_t status_uri = {
    .uri = "/status", .method = HTTP_GET, .handler = status_handler, .user_ctx = NULL
  };
  httpd_uri_t stream_uri = {
    .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL
  };

  if (httpd_start(&camera_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(camera_httpd, &capture_uri);
    httpd_register_uri_handler(camera_httpd, &status_uri);
  }

  // El stream se sirve en un servidor/puerto aparte para no bloquear
  // /capture y /status mientras hay un cliente viendo video.
  config.server_port = 81;
  config.ctrl_port += 1; // debe ser distinto al del primer servidor (ambos corren a la vez)
  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
  }
}

// ------------------------------------------------------------
// WiFi
// ------------------------------------------------------------
void connectWiFi() {
  WiFi.mode(WIFI_STA);

#if USE_STATIC_IP
  IPAddress ip(STATIC_IP);
  IPAddress gateway(STATIC_GATEWAY);
  IPAddress subnet(STATIC_SUBNET);
  WiFi.config(ip, gateway, subnet);
#endif

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Conectando a WiFi '%s'", WIFI_SSID);

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
    if (millis() - start > 30000) {
      Serial.println("\nNo se pudo conectar en 30s, reiniciando...");
      ESP.restart();
    }
  }
  Serial.println(" conectado.");
}

// ------------------------------------------------------------
// Setup / Loop
// ------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(false);

  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  if (!initCamera()) {
    Serial.println("Reiniciando por error de camara...");
    delay(3000);
    ESP.restart();
  }

#if ENABLE_TEMP_SENSOR
  tempSensor.begin();
#endif

  connectWiFi();
  startCameraServer();

  Serial.printf("\nNodo '%s' listo.\n", NODE_ID);
  Serial.printf("  Video:   http://%s:81/stream\n", WiFi.localIP().toString().c_str());
  Serial.printf("  Foto:    http://%s/capture\n", WiFi.localIP().toString().c_str());
  Serial.printf("  Estado:  http://%s/status\n", WiFi.localIP().toString().c_str());
}

void loop() {
  delay(10000);
  Serial.printf("[%s] uptime=%lus rssi=%ddBm heap=%u\n",
                 NODE_ID, millis() / 1000, WiFi.RSSI(), (unsigned)ESP.getFreeHeap());
}
