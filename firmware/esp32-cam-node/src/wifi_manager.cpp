#include "wifi_manager.h"

#include <Arduino.h>
#include <WiFi.h>
#include <algorithm>

WifiManager::WifiManager(const char *ssid, const char *password)
    : ssid_(ssid), password_(password) {}

void WifiManager::connectBlocking(uint32_t timeoutMs) {
  // No persistir credenciales en flash: en un dispositivo pensado para
  // estar prendido semanas sin reiniciar, escribir en flash en cada boot
  // es desgaste innecesario (la flash tiene un número limitado de ciclos
  // de escritura).
  WiFi.persistent(false);
  // El modo ahorro de energía de WiFi introduce latencia/cortes que se
  // notan en el streaming de video; lo desactivamos porque el nodo está
  // siempre alimentado por cable, no corre a batería.
  WiFi.setSleep(false);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid_, password_);

  Serial.printf("Conectando a WiFi '%s'", ssid_);
  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
    if (millis() - start > timeoutMs) {
      Serial.println("\nNo se pudo conectar, reiniciando...");
      ESP.restart();
    }
  }
  Serial.println(" conectado.");
  backoffMs_ = 1000;
}

void WifiManager::ensureConnected() {
  if (WiFi.status() == WL_CONNECTED) {
    backoffMs_ = 1000;
    return;
  }

  const uint32_t now = millis();
  if (now < nextRetryAtMs_) {
    return; // todavía esperando el próximo intento (backoff)
  }

  Serial.println("WiFi desconectado, reintentando...");
  WiFi.disconnect();
  WiFi.begin(ssid_, password_);

  nextRetryAtMs_ = now + backoffMs_;
  backoffMs_ = std::min(backoffMs_ * 2, kMaxBackoffMs);
}

bool WifiManager::isConnected() const {
  return WiFi.status() == WL_CONNECTED;
}

int WifiManager::rssi() const {
  return WiFi.RSSI();
}
