#include "http_server.h"

#include <Arduino.h>
#include <WiFi.h>
#include <cstring>
#include <esp_camera.h>
#include <esp_http_server.h>

namespace HttpServer {

namespace {

Options g_options;
httpd_handle_t g_httpServer = nullptr;
httpd_handle_t g_streamServer = nullptr;

#define PART_BOUNDARY "123456789000000000000987654321"
const char *STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
const char *STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
const char *STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// Si la cámara falla de forma persistente (no solo un frame suelto) lo más
// simple y confiable en un dispositivo desatendido es reiniciar, en vez de
// intentar repararla en software: es el mismo criterio de resiliencia que
// ya se usa en el resto del firmware (WifiManager, chequeos de memoria).
constexpr int kMaxConsecutiveCameraFailures = 20;
int g_consecutiveCameraFailures = 0;

void noteCameraResult(bool ok) {
  if (ok) {
    g_consecutiveCameraFailures = 0;
    return;
  }
  if (++g_consecutiveCameraFailures >= kMaxConsecutiveCameraFailures) {
    Serial.println("Camara no responde de forma persistente, reiniciando...");
    ESP.restart();
  }
}

// Autenticación simple por header, pensada para una red de laboratorio ya
// segmentada — no reemplaza TLS/VPN si el nodo llegara a exponerse fuera de
// esa red. Deshabilitada por defecto (apiKey vacío) para no complicar la
// puesta en marcha inicial.
bool isAuthorized(httpd_req_t *req) {
  if (g_options.apiKey == nullptr || g_options.apiKey[0] == '\0') {
    return true;
  }

  char header[128];
  if (httpd_req_get_hdr_value_str(req, "X-API-Key", header, sizeof(header)) != ESP_OK) {
    return false;
  }
  return strcmp(header, g_options.apiKey) == 0;
}

esp_err_t sendUnauthorized(httpd_req_t *req) {
  httpd_resp_set_status(req, "401 Unauthorized");
  httpd_resp_send(req, "unauthorized", HTTPD_RESP_USE_STRLEN);
  return ESP_FAIL;
}

esp_err_t handleStream(httpd_req_t *req) {
  if (!isAuthorized(req)) return sendUnauthorized(req);

  esp_err_t res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  while (true) {
    camera_fb_t *fb = esp_camera_fb_get();
    size_t jpgLen = 0;
    uint8_t *jpgBuf = nullptr;

    if (!fb) {
      Serial.println("Camera capture failed");
      res = ESP_FAIL;
    } else if (fb->format != PIXFORMAT_JPEG) {
      const bool converted = frame2jpg(fb, 80, &jpgBuf, &jpgLen);
      esp_camera_fb_return(fb);
      fb = nullptr;
      if (!converted) {
        Serial.println("JPEG compression failed");
        res = ESP_FAIL;
      }
    } else {
      jpgLen = fb->len;
      jpgBuf = fb->buf;
    }
    noteCameraResult(res == ESP_OK);

    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
    }
    if (res == ESP_OK) {
      char header[64];
      const size_t headerLen = snprintf(header, sizeof(header), STREAM_PART, jpgLen);
      res = httpd_resp_send_chunk(req, header, headerLen);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, (const char *)jpgBuf, jpgLen);
    }

    if (fb) {
      esp_camera_fb_return(fb);
    } else if (jpgBuf) {
      free(jpgBuf);
    }

    if (res != ESP_OK) break; // el cliente se desconectó
  }
  return res;
}

esp_err_t handleCapture(httpd_req_t *req) {
  if (!isAuthorized(req)) return sendUnauthorized(req);

  camera_fb_t *fb = esp_camera_fb_get();
  noteCameraResult(fb != nullptr);
  if (!fb) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
  const esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

esp_err_t handleStatus(httpd_req_t *req) {
  if (!isAuthorized(req)) return sendUnauthorized(req);

  const float temperature = g_options.temperatureSensor ? g_options.temperatureSensor->readCelsius() : NAN;
  char temperatureField[16];
  if (isnan(temperature)) {
    snprintf(temperatureField, sizeof(temperatureField), "null");
  } else {
    snprintf(temperatureField, sizeof(temperatureField), "%.2f", temperature);
  }

  char json[256];
  const int len = snprintf(json, sizeof(json),
      "{\"node_id\":\"%s\",\"uptime_s\":%lu,\"rssi_dbm\":%d,\"free_heap\":%u,\"temp_c\":%s}",
      g_options.nodeId, millis() / 1000, WiFi.RSSI(), (unsigned)ESP.getFreeHeap(), temperatureField);

  httpd_resp_set_type(req, "application/json");
  return httpd_resp_send(req, json, len);
}

} // namespace

void start(const Options &options) {
  g_options = options;

  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;
  // NOTA (resiliencia, pendiente): el pool de sockets del ESP32 es chico y
  // se agota con un puñado de conexiones a /stream mal cerradas (visto con
  // hardware real), dejando el nodo sordo hasta reiniciarlo. Se probó
  // reducir recv_wait_timeout/send_wait_timeout + lru_purge_enable, pero
  // rompió el caso normal (ni una conexión limpia respondía) — revertido.
  // Queda pendiente diagnosticar bien antes de tocar esto de nuevo.

  const httpd_uri_t captureUri = {
      .uri = "/capture", .method = HTTP_GET, .handler = handleCapture, .user_ctx = nullptr};
  const httpd_uri_t statusUri = {
      .uri = "/status", .method = HTTP_GET, .handler = handleStatus, .user_ctx = nullptr};
  const httpd_uri_t streamUri = {
      .uri = "/stream", .method = HTTP_GET, .handler = handleStream, .user_ctx = nullptr};

  const esp_err_t httpStartResult = httpd_start(&g_httpServer, &config);
  if (httpStartResult == ESP_OK) {
    httpd_register_uri_handler(g_httpServer, &captureUri);
    httpd_register_uri_handler(g_httpServer, &statusUri);
  } else {
    Serial.printf("ERROR: no se pudo iniciar el servidor HTTP (0x%x)\n", httpStartResult);
  }

  // El streaming bloquea el hilo del servidor mientras hay un cliente
  // conectado; por eso corre en un servidor/puerto aparte (81), si no
  // /capture y /status quedarían colgados mientras alguien mira el video.
  // ctrl_port tiene que ser distinto al del primer servidor (que ya usa el
  // valor por defecto) o falla al crear el socket de control interno.
  config.server_port = 81;
  config.ctrl_port += 1;
  const esp_err_t streamStartResult = httpd_start(&g_streamServer, &config);
  if (streamStartResult == ESP_OK) {
    httpd_register_uri_handler(g_streamServer, &streamUri);
  } else {
    Serial.printf("ERROR: no se pudo iniciar el servidor de streaming (0x%x)\n", streamStartResult);
  }
}

} // namespace HttpServer
