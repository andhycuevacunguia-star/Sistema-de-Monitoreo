from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import cv2
import numpy as np
import requests
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_super_segura'

SUPABASE_URL = "https://mdekqtmpttchanmllzus.supabase.co"
SUPABASE_KEY = "sb_publishable_A7yLQoU_B6spnL1NPCARVg_htc3C39n"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ESP32_CAM_URL = "http://192.168.101.27"

@app.route('/')
def index():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        try:
            response = supabase.table('Usuarios').select('*').eq('usuario', usuario).eq('password', password).execute()
            if response.data:
                user = response.data[0]
                session['usuario'] = user['usuario']
                session['rol'] = user['rol']
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error="Usuario o contraseña incorrectos")
        except Exception as e:
            return render_template('login.html', error=f"Error de conexión: {e}")
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        rol = request.form['rol']
        try:
            supabase.table('Usuarios').insert({'usuario': usuario, 'password': password, 'rol': rol}).execute()
            return redirect(url_for('login'))
        except Exception as e:
            return render_template('registro.html', error="El usuario ya existe o hubo un error al registrar.")
    return render_template('registro.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    try:
        sensores_res = supabase.table('Lecturas').select('*').order('created_at', desc=True).limit(5).execute()
        sensores = sensores_res.data
        
        fallas_res = supabase.table('Alertas_Fallas').select('*').order('created_at', desc=True).execute()
        fallas = fallas_res.data
        
        videos_res = supabase.table('Tutoriales').select('*').order('created_at', desc=True).execute()
        videos = videos_res.data
        
        usuarios = []
        if session.get('rol') == 'admin':
            usuarios_res = supabase.table('Usuarios').select('*').execute()
            usuarios = usuarios_res.data
    except Exception as e:
        sensores, fallas, videos, usuarios = [], [], [], []

    return render_template('dashboard.html', 
                           usuario=session['usuario'], 
                           rol=session['rol'],
                           sensores=sensores,
                           fallas=fallas,
                           videos=videos,
                           usuarios=usuarios,
                           esp32_ip=ESP32_CAM_URL)

def analizar_imagen_carton(frame):
    """
    Analiza el frame capturado y determina el estado del carton:
    - sin_componente: no hay nada en la zona de escaneo
    - roto: el carton esta partido o con un corte/hueco grande
    - arrugado: el carton tiene arrugas (muchos pliegues pequeños)
    - linea: el carton tiene una linea/raya recta marcada
    - normal: el carton esta en buen estado
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    brillo_promedio = np.mean(gray)

    # 1. Sin componente: muy oscuro (nada en camara) o muy claro (sobreexpuesto)
    if brillo_promedio < 35 or brillo_promedio > 230:
        return "sin_componente", "No se detecta ningun componente en la zona de escaneo.", "Sin Componente"

    edges = cv2.Canny(gray, 60, 180)
    conteo_bordes = int(np.sum(edges > 0))

    # 2. Buscar lineas rectas largas (rayas o cortes derechos)
    lineas = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60,
                              minLineLength=90, maxLineGap=8)
    linea_larga_detectada = False
    if lineas is not None:
        for l in lineas:
            x1, y1, x2, y2 = l[0]
            largo = np.hypot(x2 - x1, y2 - y1)
            if largo > 110:
                linea_larga_detectada = True
                break

    # 3. Contornos para diferenciar "roto" de "arrugado"
    contornos, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    num_contornos = len(contornos)
    area_contorno_mayor = max((cv2.contourArea(c) for c in contornos), default=0)

    if linea_larga_detectada and conteo_bordes < 6000:
        return "linea", "Se detecto una linea/raya marcada en el carton.", "Falla: Linea Detectada"

    if conteo_bordes > 6000 or area_contorno_mayor > 4000:
        return "roto", "El carton esta roto o partido.", "Falla: Carton Roto"

    if num_contornos > 35 and conteo_bordes > 1800:
        return "arrugado", "El carton presenta arrugas en su superficie.", "Falla: Carton Arrugado"

    return "normal", "No hay ninguna falla.", "Normal"

@app.route('/api/detectar_fallas', methods=['POST'])
def detectar_fallas():
    estado_resultado = "sin_componente"
    descripcion = "No se detecta ningun componente en la zona de escaneo."
    estado_texto = "Sin Componente"

    try:
        img_resp = requests.get(f"{ESP32_CAM_URL}/capture", timeout=3)
        if img_resp.status_code != 200:
            img_resp = requests.get(f"{ESP32_CAM_URL}/hi.jpg", timeout=3)
            
        if img_resp.status_code == 200:
            arr = np.frombuffer(img_resp.content, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                estado_resultado, descripcion, estado_texto = analizar_imagen_carton(frame)
        else:
            descripcion = "No se pudo capturar la imagen de la camara."
    except Exception as e:
        print(f"Error de vision: {e}")
        descripcion = "Error al escanear el componente."
        estado_texto = "Error"
        estado_resultado = "error"

    try:
        supabase.table('Alertas_Fallas').insert({
            'componente': 'Carton',
            'descripcion': descripcion,
            'estado': estado_texto
        }).execute()
    except Exception as e:
        print(f"Error al guardar en Supabase: {e}")

    return jsonify({
        "success": True,
        "estado": estado_resultado,
        "descripcion": descripcion,
        "estado_texto": estado_texto
    })

@app.route('/api/subir_video', methods=['POST'])
def subir_video():
    if session.get('rol') != 'admin':
        return jsonify({"success": False, "message": "No autorizado"})
    data = request.get_json()
    url_video = data.get('url_video', '')
    
    embed_url = url_video
    if "watch?v=" in url_video:
        video_id = url_video.split("watch?v=")[1].split("&")[0]
        embed_url = f"https://www.youtube.com/embed/{video_id}"
    elif "youtu.be/" in url_video:
        video_id = url_video.split("youtu.be/")[1].split("?")[0]
        embed_url = f"https://www.youtube.com/embed/{video_id}"

    try:
        supabase.table('Tutoriales').insert({'titulo': 'Video Tutorial', 'ruta_video': embed_url}).execute()
        return jsonify({"success": True, "message": "Video subido correctamente"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route('/eliminar_video/<int:id_video>', methods=['DELETE'])
def eliminar_video(id_video):
    if session.get('rol') != 'admin':
        return jsonify({"success": False, "message": "No autorizado"})
    try:
        supabase.table('Tutoriales').delete().eq('id', id_video).execute()
        return jsonify({"success": True, "message": "Video eliminado"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route('/eliminar_usuario/<int:id_usuario>', methods=['DELETE'])
def eliminar_usuario(id_usuario):
    if session.get('rol') != 'admin':
        return jsonify({"success": False, "message": "No autorizado"})
    try:
        supabase.table('Usuarios').delete().eq('id', id_usuario).execute()
        return jsonify({"success": True, "message": "Usuario eliminado"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)