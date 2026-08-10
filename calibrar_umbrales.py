import cv2
import os
import numpy as np

CARPETA_BASE = "muestras"
CATEGORIAS = ["normal", "roto", "arrugado", "linea", "sin_componente"]


def calcular_metricas(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    brillo_promedio = float(np.mean(gray))

    edges = cv2.Canny(gray, 60, 180)
    conteo_bordes = int(np.sum(edges > 0))

    lineas = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60,
                              minLineLength=90, maxLineGap=8)
    linea_larga = False
    largo_max_linea = 0
    if lineas is not None:
        for l in lineas:
            x1, y1, x2, y2 = l[0]
            largo = float(np.hypot(x2 - x1, y2 - y1))
            largo_max_linea = max(largo_max_linea, largo)
            if largo > 110:
                linea_larga = True

    contornos, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    num_contornos = len(contornos)
    area_contorno_mayor = max((cv2.contourArea(c) for c in contornos), default=0)

    return {
        "brillo_promedio": round(brillo_promedio, 1),
        "conteo_bordes": conteo_bordes,
        "num_contornos": num_contornos,
        "area_contorno_mayor": round(float(area_contorno_mayor), 1),
        "linea_larga": linea_larga,
        "largo_max_linea": round(largo_max_linea, 1),
    }


def resumen(valores):
    if not valores:
        return None
    return {
        "min": round(min(valores), 1),
        "max": round(max(valores), 1),
        "promedio": round(sum(valores) / len(valores), 1),
    }


def main():
    resultados_por_categoria = {cat: [] for cat in CATEGORIAS}

    for categoria in CATEGORIAS:
        carpeta = os.path.join(CARPETA_BASE, categoria)
        if not os.path.isdir(carpeta):
            continue

        archivos = sorted(f for f in os.listdir(carpeta) if f.lower().endswith((".jpg", ".jpeg", ".png")))
        if not archivos:
            print(f"\n[{categoria}] No hay fotos en {carpeta}/")
            continue

        print(f"\n=== Categoria: {categoria} ({len(archivos)} fotos) ===")
        for archivo in archivos:
            ruta = os.path.join(carpeta, archivo)
            frame = cv2.imread(ruta)
            if frame is None:
                print(f"  {archivo}: no se pudo leer")
                continue
            m = calcular_metricas(frame)
            resultados_por_categoria[categoria].append(m)
            print(f"  {archivo}: brillo={m['brillo_promedio']}  bordes={m['conteo_bordes']}  "
                  f"contornos={m['num_contornos']}  area_max={m['area_contorno_mayor']}  "
                  f"linea_larga={m['linea_larga']} (largo={m['largo_max_linea']})")

    print("\n" + "=" * 70)
    print("RESUMEN POR CATEGORIA (para ajustar los umbrales en app.py)")
    print("=" * 70)

    for categoria in CATEGORIAS:
        datos = resultados_por_categoria[categoria]
        if not datos:
            continue
        print(f"\n[{categoria}]")
        for campo in ["brillo_promedio", "conteo_bordes", "num_contornos", "area_contorno_mayor"]:
            r = resumen([d[campo] for d in datos])
            print(f"  {campo:22s} -> min={r['min']:<10} max={r['max']:<10} promedio={r['promedio']}")
        proporcion_linea = sum(1 for d in datos if d["linea_larga"]) / len(datos)
        print(f"  {'linea_larga_detectada':22s} -> en {proporcion_linea * 100:.0f}% de las fotos")

    print("\nCon estos numeros, compara los rangos de 'conteo_bordes' y 'area_contorno_mayor'")
    print("entre 'roto' y 'arrugado': el punto medio entre el max de uno y el min del otro")
    print("es un buen candidato para el umbral en analizar_imagen_carton() de app.py.")


if __name__ == "__main__":
    main()