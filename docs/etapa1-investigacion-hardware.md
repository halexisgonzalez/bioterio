# Proyecto Bioterio — Tracking por Visión por Computadora

## Etapa 1: Investigación de Hardware (Cámara y Nodo de Captura)

**Fecha:** 2026-08-18
**Responsable de investigación:** Agustín (becario)

---

## 1. Objetivo del proyecto

Diseñar un sistema de visión por computadora para monitorear ratones dentro de jaulas de bioterio, registrando su evolución y comportamiento (trayectoria, actividad, uso del espacio, temperatura) de forma continua durante varias semanas, en múltiples jaulas (nodos) simultáneamente.

---

## 2. Contexto del entorno (relevado con fotos del bioterio)

- Las jaulas están dispuestas en racks metálicos, apiladas en estantes.
- La distancia vertical entre la tapa de una jaula y la base del estante superior es **reducida** (~20-30 cm).
- Las jaulas (tipo Fauni) tienen tapa de reja metálica; se evalúa reemplazarla por una **tapa de acrílico transparente** para permitir cámara cenital sin que los ratones la roan.
- Hay comedero/tolva que ocupa buena parte del área superior y genera oclusión.
- Puede haber objetos dentro de la jaula (casitas, juguetes, ruedas) que ocluyen al animal.
- Puede haber uno o varios ratones por jaula.
- Monitoreo requerido: **24/7, durante varias semanas**, sin restricciones relevantes de alimentación eléctrica ni de ancho de banda.
- Múltiples jaulas (nodos) en simultáneo — la solución debe escalar a varios racks.

---

## 3. Decisión de arquitectura (ya definida)

- **No usar Raspberry Pi** (costo elevado por nodo).
- Usar **ESP32-CAM** como nodo económico en cada jaula: solo captura y transmite video (streaming), no procesa IA localmente.
- **Todo el procesamiento de visión (IA/tracking) se hace en una PC central**, que recibe el streaming de todos los nodos por Wi-Fi.
- Los resultados (coordenadas, IDs, temperatura, estados) se almacenan en **MySQL**.
- Costo estimado por nodo: **~10-15 USD** (vs. ~60-80 USD con Raspberry Pi).

---

## 4. Ítems a investigar — ENFOQUE PRINCIPAL: CÁMARA

Estos son los puntos clave que se debe cotizar/investigar, priorizando la parte de visión:

### 4.1 Sensor de cámara — NoIR (visión nocturna)
- Buscar específicamente **ESP32-CAM con sensor OV2640 versión NoIR** (sin filtro infrarrojo).
- **Crítico:** el sensor estándar (con filtro IR) queda ciego en oscuridad total. Como el monitoreo es 24/7 y los ratones son nocturnos, sin NoIR no hay imagen útil durante la noche.
- Confirmar que el vendedor aclare explícitamente "NoIR" / "sin filtro IR" en la publicación (no siempre está bien etiquetado).

### 4.2 Lente — gran angular (FOV)
- Buscar módulos con **lente fisheye / gran angular de 120° a 160°**.
- La lente estándar que trae la ESP32-CAM (~65° FOV) no alcanza a cubrir toda la superficie de la jaula dada la poca altura disponible entre la tapa y el estante superior → generaría zonas ciegas.
- Verificar compatibilidad de rosca/montaje del lente con el sensor OV2640.

### 4.3 Iluminación infrarroja
- Buscar **LEDs IR de 940nm** (no 850nm).
- Los de 940nm son prácticamente invisibles al ojo (y presumiblemente al ratón), evitando alterar el ciclo circadiano/sueño del animal. Los de 850nm emiten un resplandor rojo tenue visible.
- Puede ser un anillo de LEDs IR o LEDs sueltos a acoplar cerca del lente.

### 4.4 Antena Wi-Fi externa
- Buscar versión de placa ESP32-CAM con **conector IPEX (u-FL) para antena externa**.
- Motivo: las placas van a quedar ubicadas entre estructuras metálicas del rack y el acrílico de la jaula, lo cual puede degradar mucho la señal de la antena PCB integrada. Una antena externa con cable permite sacarla del "jaula de Faraday" metálica del rack.

---

## 5. Ítems secundarios (para etapas posteriores, no urgente)

- Sensor de temperatura ambiente/animal (DS18B20, BME280 o AHT10) para telemetría por nodo.
- Fuente de alimentación 5V 2A por nodo, o fuente switching centralizada para toda una columna de jaulas.
- Diseño de carcasa/soporte (idealmente impresión 3D) para fijar la placa al estante superior apuntando hacia abajo, evitando reflejos del acrílico.
- Cable flex extendido (7-10 cm) entre sensor y placa, para facilitar el montaje separado de la cámara y la placa ESP32.

---


## 6. Próximos pasos (después de esta investigación)

1. Comprar 1 unidad de cada componente para armar un **nodo de prueba**.
2. Validar de noche: que el sensor NoIR + LEDs 940nm capturen imagen utilizable.
3. Validar el FOV real de la lente gran angular contra la altura disponible en el rack.
4. Probar estabilidad de la señal Wi-Fi con la antena externa en la posición real de montaje.
5. Recién después, avanzar con el pipeline de software (Python + OpenCV + YOLO + MySQL).
