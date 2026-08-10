import cv2
import os
import time
import requests
import numpy as np

ESP32_CAM_URL = "http://192.168.101.27"  # <-- pon aqui la IP real de tu camara

CATEGORIAS = {
    ord('n'): "normal",
    ord('r'): "roto",
    ord('a'): "arrugado",
    ord('l'): "linea",
    ord('s'): "sin_componente",
}

CARPETA_BASE = "muestras"


def obtener_frame():
    """Descarga un frame actual desde la ESP32-CAM (igual que hace el server)."""
    try:
        resp = requests.get(f"{ESP32_CAM_URL}/capture", timeout=3)
        if resp.status_code != 200:
            resp = requests.get(f"{ESP32_CAM_URL}/hi.jpg", timeout=3)
        if resp.status_code == 200:
            arr = np.frombuffer(resp.content, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return frame
    except Exception as e:
        print(f"Error al obtener frame: {e}")
    return None


def siguiente_nombre(carpeta):
    existentes = [f for f in os.listdir(carpeta) if f.startswith("foto_")]
    return f"foto_{len(existentes) + 1:03d}.jpg"


def main():
    for categoria in CATEGORIAS.values():
        os.makedirs(os.path.join(CARPETA_BASE, categoria), exist_ok=True)

    print("Presiona: n=normal  r=roto  a=arrugado  l=linea  s=sin_componente  q=salir")

    while True:
        frame = obtener_frame()
        if frame is None:
            print("No se pudo obtener imagen, reintentando...")
            time.sleep(1)
            continue

        vista = frame.copy()
        cv2.putText(vista, "n/r/a/l/s = guardar  |  q = salir",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.imshow("Captura de muestras - ESP32 CAM", vista)

        tecla = cv2.waitKey(1) & 0xFF

        if tecla == ord('q'):
            break
        elif tecla in CATEGORIAS:
            categoria = CATEGORIAS[tecla]
            carpeta = os.path.join(CARPETA_BASE, categoria)
            nombre = siguiente_nombre(carpeta)
            ruta = os.path.join(carpeta, nombre)
            cv2.imwrite(ruta, frame)
            print(f"Guardada: {ruta}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()