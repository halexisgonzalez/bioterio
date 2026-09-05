// ============================================================
// Nodo de captura ESP32-CAM - Proyecto Bioterio
//
// Este firmware NO hace tracking ni IA: solo transmite video (MJPEG por
// HTTP) y telemetría (JSON) a la red. Todo el procesamiento de visión se
// hace en la PC central (Python).
//
// Estructura (separación de responsabilidades — cada módulo se puede leer,
// probar y cambiar sin tocar los demás):
//   wifi_manager        -> conexión y reconexión a WiFi
//   camera_manager       -> inicialización de la cámara
//   temperature_sensor   -> lectura de temperatura (opcional)
//   http_server          -> endpoints /stream, /capture, /status
//   main.cpp (este archivo) -> arma las piezas de arriba y agrega las
//                              salvaguardas de resiliencia de todo el nodo
// ============================================================

#include <Arduino.h>
#include <ESPmDNS.h>
#include <WiFi.h>

#include "camera_manager.h"
#include "camera_pins.h"
#include "http_server.h"
#include "temperature_sensor.h"
#include "wifi_manager.h"

#if __has_include("config.h")
#include "config.h"
#else
#error "Falta include/config.h -> copia config.example.h como config.h y completa tus datos (ver README.md)"
#endif

// Valores por defecto para settings opcionales de config.h, para no romper
// instalaciones existentes que todavía no los definen.
#ifndef API_KEY
#define API_KEY ""
#endif
#ifndef MIN_FREE_HEAP_BYTES
#define MIN_FREE_HEAP_BYTES 20000
#endif
#ifndef MAX_UPTIME_BEFORE_RESTART_S
#define MAX_UPTIME_BEFORE_RESTART_S (7UL * 24 * 3600) // reinicio preventivo semanal
#endif

namespace {

WifiManager wifiManager(WIFI_SSID, WIFI_PASSWORD);
TemperatureSensor temperatureSensor;

void logHealth() {
  Serial.printf("[%s] uptime=%lus rssi=%ddBm heap=%u\n", NODE_ID, millis() / 1000, WiFi.RSSI(),
                 (unsigned)ESP.getFreeHeap());
}

// Salvaguardas para un dispositivo pensado para estar prendido 24/7 durante
// semanas sin supervisión: si la memoria libre cae por debajo de un umbral
// (fragmentación tras días de streaming continuo) o pasa demasiado tiempo
// prendido, reiniciamos de forma preventiva en vez de esperar a que se
// cuelgue solo y alguien tenga que ir físicamente a resetearlo.
void runResilienceChecks() {
  if (ESP.getFreeHeap() < MIN_FREE_HEAP_BYTES) {
    Serial.println("Memoria libre critica, reiniciando de forma preventiva...");
    ESP.restart();
  }
  if (millis() / 1000 > MAX_UPTIME_BEFORE_RESTART_S) {
    Serial.println("Reinicio preventivo programado (uptime maximo alcanzado)...");
    ESP.restart();
  }
}

// Permite acceder al nodo como http://<NODE_ID>.local en vez de memorizar
// su IP — importante cuando hay muchos nodos y no se fijaron IPs estáticas.
void startMdns() {
  if (!MDNS.begin(NODE_ID)) {
    Serial.println("No se pudo iniciar mDNS (el nodo sigue funcionando por IP)");
    return;
  }
  MDNS.addService("http", "tcp", 80);
  Serial.printf("mDNS activo: http://%s.local\n", NODE_ID);
}

} // namespace

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(false);

  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  const CameraManager::Settings cameraSettings{
      .frameSize = CAMERA_FRAMESIZE,
      .jpegQuality = CAMERA_JPEG_QUALITY,
      .verticalFlip = (bool)CAMERA_VFLIP,
      .horizontalMirror = (bool)CAMERA_HMIRROR,
  };
  if (!CameraManager::begin(cameraSettings)) {
    Serial.println("Reiniciando por error de camara...");
    delay(3000);
    ESP.restart();
  }

  temperatureSensor.begin();
  wifiManager.connectBlocking();
  startMdns();

  HttpServer::start({
      .nodeId = NODE_ID,
      .apiKey = API_KEY,
      .temperatureSensor = &temperatureSensor,
  });

  Serial.printf("\nNodo '%s' listo.\n", NODE_ID);
  Serial.printf("  Video:   http://%s:81/stream\n", WiFi.localIP().toString().c_str());
  Serial.printf("  Foto:    http://%s/capture\n", WiFi.localIP().toString().c_str());
  Serial.printf("  Estado:  http://%s/status\n", WiFi.localIP().toString().c_str());
}

void loop() {
  wifiManager.ensureConnected();
  runResilienceChecks();

  static uint32_t lastLogAtMs = 0;
  const uint32_t now = millis();
  if (now - lastLogAtMs >= 10000) {
    logHealth();
    lastLogAtMs = now;
  }

  delay(200); // loop liviano: no retrasa la reconexión de wifi ni los chequeos de salud
}
