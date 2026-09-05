#pragma once

// ============================================================
// Copiá este archivo como "config.h" (misma carpeta) y completá
// tus datos. "config.h" está en .gitignore para no subir
// credenciales de WiFi al repositorio.
// ============================================================

// --- WiFi ---
#define WIFI_SSID       "TU_RED_WIFI"
#define WIFI_PASSWORD   "TU_PASSWORD"

// --- Identidad del nodo ---
// Usá un nombre único por jaula, ej: "jaula_01", "rack_a_fila_2", etc.
// Aparece en el JSON de /status y en los logs por serial.
#define NODE_ID         "jaula_01"

// --- IP estática (opcional) ---
// Dejar USE_STATIC_IP en 0 para usar DHCP (recomendado al principio).
// Si vas a tener muchos nodos, conviene fijar IP para identificarlos fácil.
#define USE_STATIC_IP   0
#define STATIC_IP       192, 168, 1, 50
#define STATIC_GATEWAY  192, 168, 1, 1
#define STATIC_SUBNET   255, 255, 255, 0

// --- Cámara ---
// FRAMESIZE_QVGA (320x240) o FRAMESIZE_VGA (640x480, recomendado, ver notas del proyecto)
#define CAMERA_FRAMESIZE   FRAMESIZE_VGA
#define CAMERA_JPEG_QUALITY 12   // 10-63 -> menor número = mejor calidad / más peso por frame

// Ajustar según cómo quede montada físicamente la cámara en el estante
#define CAMERA_VFLIP     0   // 1 = invertir verticalmente
#define CAMERA_HMIRROR   0   // 1 = espejar horizontalmente

// --- Sensor de temperatura DS18B20 (opcional, se puede sumar después) ---
#define ENABLE_TEMP_SENSOR 0
#define TEMP_SENSOR_PIN    13
