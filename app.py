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
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Calcular brillo promedio para saber si hay algo enfocado
                brillo_promedio = np.mean(gray)
                
                # Calcular la cantidad de bordes (para ver si el cartón está roto/partido o entero)
                edges = cv2.Canny(gray, 100, 200)
                conteo_bordes = np.sum(edges > 0)

                # 1. Si el brillo es muy bajo o muy alto sin forma, no hay componente
                if brillo_promedio < 35 or brillo_promedio > 230:
                    estado_resultado = "sin_componente"
                    descripcion = "No se detecta ningun componente."
                    estado_texto = "Sin Componente"
                # 2. Si hay demasiados bordes fragmentados o huecos (Cartón partido a la mitad)
                elif conteo_bordes > 3500:
                    estado_resultado = "partido"
                    descripcion = "Papel partido casi a la mitad."
                    estado_texto = "Falla: Papel Partido"
                # 3. Si el cartón está completo y estable
                else:
                    estado_resultado = "normal"
                    descripcion = "No hay ninguna falla."
                    estado_texto = "Normal"
        else:
            descripcion = "No se pudo capturar la imagen de la camara."
    except Exception as e:
        print(f"Error de vision: {e}")
        descripcion = "Error al escanear el componente."
        estado_texto = "Error"

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