import cv2
import numpy as np
import time
from supabase import create_client, Client

# --- CONEXIÓN DIRECTA A SUPABASE ---
SUPABASE_URL = "https://mdekqtmpttchanmllzus.supabase.co"
SUPABASE_KEY = "sb_publishable_A7yLQoU_B6spnL1NPCARVg_htc3C39n"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# URL del streaming de tu ESP32-CAM
URL_ESP32_CAM = "http://10.63.198.252" 

def guardar_alerta(diagnostico):
    """Envía la alerta detectada a la tabla Alertas_Fallas en Supabase."""
    try:
        datos = {"diagnostico": diagnostico}
        supabase.table('Alertas_Fallas').insert(datos).execute()
        print(f"✅ Alerta guardada en Supabase: {diagnostico}")
    except Exception as e:
        print(f"❌ Error al guardar en Supabase: {e}")

def detectar_raya_carton():
    cap = cv2.VideoCapture(URL_ESP32_CAM)

    if not cap.isOpened():
        print("❌ No se pudo conectar a la ESP32-CAM. Revisa la IP.")
        return

    print("🎥 Conectado a la ESP32-CAM. Iniciando prueba de detección de raya...")

    tiempo_ultima_alerta = 0
    cooldown = 8  # Espera 8 segundos entre alertas para no saturar la base de datos

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(1)
            continue

        # Redimensionar para procesar más rápido
        frame = cv2.resize(frame, (640, 480))
        
        # Convertir a escala de grises y desenfocar
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Umbralizado (Threshold): Detecta trazos oscuros (la raya) sobre fondos claros (el cartón)
        _, thresh = cv2.threshold(blurred, 80, 255, cv2.THRESH_BINARY_INV)

        # Buscar contornos de la marca/raya
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        falla_detectada = False
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Si el área de la marca oscura es suficientemente grande, se considera la falla
            if area > 1500:  
                falla_detectada = True
                x, y, w, h = cv2.boundingRect(cnt)
                # Dibujar un recuadro rojo sobre la raya detectada
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(frame, "FALLA DETECTADA (RAYA)", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Estado en pantalla
        estado_texto = "ESTADO: DEFECTUOSO (Raya detectada)" if falla_detectada else "ESTADO: CORRECTO (Sin raya)"
        color_texto = (0, 0, 255) if falla_detectada else (0, 255, 0)
        cv2.putText(frame, estado_texto, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_texto, 2)

        # Guardar en Supabase si se detectó la raya y ya pasó el tiempo de cooldown
        tiempo_actual = time.time()
        if falla_detectada and (tiempo_actual - tiempo_ultima_alerta > cooldown):
            guardar_alerta("Falla en cartón: Se detectó raya/fisura en la pieza")
            tiempo_ultima_alerta = tiempo_actual

        # Mostrar la ventana en vivo
        cv2.imshow("Prueba de Monitoreo - ESP32 CAM", frame)

        # Presiona 'q' en el teclado para cerrar
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    detectar_raya_carton()