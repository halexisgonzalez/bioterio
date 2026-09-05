#pragma once

#include <cstdint>

// Administra la conexión WiFi del nodo.
//
// Responsabilidad única: conectar al arrancar y detectar/reparar cortes de
// señal durante la operación. El resto del firmware no sabe nada de
// reintentos ni de WiFi.h — solo pregunta isConnected()/rssi().
class WifiManager {
public:
  WifiManager(const char *ssid, const char *password);

  // Bloquea hasta conectar. Si no logra conectar en timeoutMs, reinicia el
  // equipo: sin red el nodo no cumple ninguna función, así que no tiene
  // sentido seguir arrancando en ese estado.
  void connectBlocking(uint32_t timeoutMs = 30000);

  // Llamar en cada vuelta de loop(). Si la conexión se cayó, reintenta con
  // backoff exponencial (tope 30s) sin bloquear el resto del loop ni
  // reiniciar de entrada — tolera cortes breves de WiFi, algo esperable en
  // un dispositivo prendido 24/7 durante semanas.
  void ensureConnected();

  bool isConnected() const;
  int rssi() const;

private:
  const char *ssid_;
  const char *password_;
  uint32_t nextRetryAtMs_ = 0;
  uint32_t backoffMs_ = 1000;
  static constexpr uint32_t kMaxBackoffMs = 30000;
};
