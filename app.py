from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import requests
import cv2
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_super_segura'

# Configuración de Supabase con tus credenciales reales
SUPABASE_URL = "https://mdekqtmpttchanmllzus.supabase.co"
SUPABASE_KEY = "sb_publishable_A7yLQoU_B6spnL1NPCARVg_htc3C39n"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
            response = supabase.table('usuarios').select('*').eq('usuario', usuario).eq('password', password).execute()
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
        rol = 'usuario' # Por defecto se registran como usuarios normales
        
        try:
            supabase.table('usuarios').insert({
                'usuario': usuario,
                'password': password,
                'rol': rol
            }).execute()
            return redirect(url_for('login'))
        except Exception as e:
            return render_template('registro.html', error="El usuario ya existe o hubo un error.")
            
    return render_template('registro.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    try:
        # Obtener datos de sensores
        sensores_res = supabase.table('sensores').select('*').order('created_at', desc=True).limit(5).execute()
        sensores = sensores_res.data
        
        # Obtener fallas registradas
        fallas_res = supabase.table('fallas').select('*').order('created_at', desc=True).execute()
        fallas = fallas_res.data
        
        # Obtener videos tutoriales
        videos_res = supabase.table('videos').select('*').order('created_at', desc=True).execute()
        videos = videos_res.data
        
        # Obtener usuarios si es admin
        usuarios = []
        if session.get('rol') == 'admin':
            usuarios_res = supabase.table('usuarios').select('*').execute()
            usuarios = usuarios_res.data
            
    except Exception as e:
        sensores, fallas, videos, usuarios = [], [], [], []

    return render_template('dashboard.html', 
                           usuario=session['usuario'], 
                           rol=session['rol'],
                           sensores=sensores,
                           fallas=fallas,
                           videos=videos,
                           usuarios=usuarios)

# Ruta para guardar las fallas desde el navegador al congelar y escanear
@app.route('/api/detectar_fallas', methods=['POST'])
def detectar_fallas():
    data = request.get_json()
    estado = data.get('estado', 'arrugado')
    
    componente = "Cartón de Prueba"
    descripcion = "El cartón presenta arrugas o irregularidades superficiales detectadas en la captura."
    estado_texto = "Detectado (ARRUGADO)"
    
    try:
        supabase.table('fallas').insert({
            'componente': componente,
            'descripcion': descripcion,
            'estado': estado_texto
        }).execute()
    except Exception as e:
        print(f"Error al guardar en Supabase: {e}")

    return jsonify({
        "success": True,
        "estado": estado,
        "descripcion": descripcion
    })

@app.route('/api/subir_video', methods=['POST'])
def subir_video():
    if session.get('rol') != 'admin':
        return jsonify({"success": False, "message": "No autorizado"})
        
    data = request.get_json()
    titulo = data.get('titulo')
    url_video = data.get('url_video')
    
    # Convertir URL normal de YouTube a embed si es necesario
    if "watch?v=" in url_video:
        url_video = url_video.replace("watch?v=", "embed/")
    elif "youtu.be/" in url_video:
        url_video = url_video.replace("youtu.be/", "www.youtube.com/embed/")

    try:
        supabase.table('videos').insert({
            'titulo': titulo,
            'ruta_video': url_video
        }).execute()
        return jsonify({"success": True, "message": "Video subido correctamente"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error al subir: {e}"})

@app.route('/eliminar_video/<int:id_video>', methods=['DELETE'])
def eliminar_video(id_video):
    if session.get('rol') != 'admin':
        return jsonify({"success": False, "message": "No autorizado"})
    try:
        supabase.table('videos').delete().eq('id', id_video).execute()
        return jsonify({"success": True, "message": "Video eliminado"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route('/eliminar_usuario/<int:id_usuario>', methods=['DELETE'])
def eliminar_usuario(id_usuario):
    if session.get('rol') != 'admin':
        return jsonify({"success": False, "message": "No autorizado"})
    try:
        supabase.table('usuarios').delete().eq('id', id_usuario).execute()
        return jsonify({"success": True, "message": "Usuario eliminado"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)