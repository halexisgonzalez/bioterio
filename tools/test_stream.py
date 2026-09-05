"""
Script simple para validar el streaming MJPEG de un nodo ESP32-CAM
antes de integrarlo al pipeline central de Python.

Uso:
    python test_stream.py <ip_del_nodo>

Ejemplo:
    python test_stream.py 192.168.1.114

Requiere: opencv-python, requests (ver requirements.txt)
"""
import sys

import cv2
import requests


def main():
    if len(sys.argv) < 2:
        print("Uso: python test_stream.py <ip_del_nodo>")
        sys.exit(1)

    ip = sys.argv[1]
    stream_url = f"http://{ip}:81/stream"
    status_url = f"http://{ip}/status"

    try:
        r = requests.get(status_url, timeout=3)
        print("Estado del nodo:", r.json())
    except Exception as e:
        print(f"Aviso: no se pudo leer {status_url} ({e}). Sigo igual con el stream.")

    print(f"Conectando a {stream_url} ...")
    cap = cv2.VideoCapture(stream_url)

    if not cap.isOpened():
        print("No se pudo abrir el stream. Verificá la IP y que el nodo esté encendido.")
        sys.exit(1)

    print("Mostrando video. Presioná 'q' en la ventana para salir.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame perdido, reintentando...")
            continue

        cv2.imshow(f"ESP32-CAM {ip}", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
