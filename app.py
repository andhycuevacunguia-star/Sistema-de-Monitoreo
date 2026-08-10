import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = "clave_secreta_mano_robotica_123"

SUPABASE_URL = "https://mdekqtmpttchanmllzus.supabase.co"
SUPABASE_KEY = "sb_publishable_A7yLQoU_B6spnL1NPCARVg_htc3C39n"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Conexión con Supabase configurada exitosamente.")
except Exception as e:
    supabase = None
    print(f"Error al conectar con Supabase: {e}")

@app.route('/')
def index():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not supabase:
            return jsonify({'success': False, 'message': 'Error de configuración en la base de datos.'})

        data = request.get_json()
        usuario = data.get('usuario')
        password = data.get('password')

        try:
            res = supabase.table('Usuarios').select('*').eq('usuario', usuario).eq('password', password).execute()
            if len(res.data) > 0:
                user_info = res.data[0]
                session['user_id'] = user_info['id']
                session['usuario'] = user_info['usuario']
                session['rol'] = user_info.get('rol', 'estudiante')
                return jsonify({'success': True, 'redirect': '/dashboard'})
            else:
                return jsonify({'success': False, 'message': 'Usuario o contraseña incorrectos'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error de base de datos: {str(e)}'})

    return render_template('login.html')

@app.route('/registro', methods=['POST'])
def registro():
    if not supabase:
        return jsonify({'success': False, 'message': 'Error de configuración en la base de datos.'})

    data = request.get_json()
    usuario = data.get('usuario')
    password = data.get('password')
    rol = data.get('rol', 'estudiante')

    try:
        existe = supabase.table('Usuarios').select('*').eq('usuario', usuario).execute()
        if len(existe.data) > 0:
            return jsonify({'success': False, 'message': 'El nombre de usuario ya está registrado'})

        supabase.table('Usuarios').insert({
            'usuario': usuario,
            'password': password,
            'rol': rol
        }).execute()

        return jsonify({'success': True, 'message': 'Usuario registrado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al registrar: {str(e)}'})

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    lista_usuarios = []
    lista_sensores = []
    lista_fallas = []
    lista_videos = []

    if supabase:
        try:
            if session.get('rol') == 'admin':
                res_u = supabase.table('Usuarios').select('id, usuario, rol, created_at').execute()
                lista_usuarios = res_u.data
        except Exception as e:
            print(f"Error cargando usuarios: {e}")

        try:
            res_s = supabase.table('sensores').select('*').order('created_at', desc=True).limit(5).execute()
            lista_sensores = res_s.data
        except Exception as e:
            print(f"Error cargando sensores: {e}")

        try:
            res_f = supabase.table('fallas').select('*').order('created_at', desc=True).execute()
            lista_fallas = res_f.data
        except Exception as e:
            print(f"Error cargando fallas: {e}")

        try:
            res_v = supabase.table('Tutoriales').select('*').execute()
            lista_videos = res_v.data
        except Exception as e:
            print(f"Error cargando tutoriales: {e}")
            lista_videos = []

    return render_template(
        'dashboard.html', 
        usuario=session['usuario'], 
        rol=session.get('rol', 'estudiante'),
        usuarios=lista_usuarios,
        sensores=lista_sensores,
        fallas=lista_fallas,
        videos=lista_videos
    )

@app.route('/api/guardar_sensor', methods=['POST'])
def guardar_sensor():
    data = request.get_json()
    try:
        supabase.table('sensores').insert({
            'sensor_nombre': data.get('sensor_nombre'),
            'valor': data.get('valor'),
            'estado': data.get('estado', 'Normal')
        }).execute()
        return jsonify({'success': True, 'message': 'Sensor guardado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/guardar_falla', methods=['POST'])
def guardar_falla():
    data = request.get_json()
    try:
        supabase.table('fallas').insert({
            'componente': data.get('componente'),
            'descripcion': data.get('descripcion'),
            'estado': data.get('estado', 'Pendiente')
        }).execute()
        return jsonify({'success': True, 'message': 'Falla registrada'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/subir_video', methods=['POST'])
def subir_video():
    if session.get('rol') != 'admin':
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403
    
    data = request.get_json()
    titulo = data.get('titulo')
    url_video = data.get('url_video')

    try:
        supabase.table('Tutoriales').insert({
            'titulo': titulo,
            'ruta_video': url_video
        }).execute()
        return jsonify({'success': True, 'message': 'Video registrado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/eliminar_video/<int:video_id>', methods=['DELETE', 'POST'])
def eliminar_video(video_id):
    if 'usuario' not in session or session.get('rol') != 'admin':
        return jsonify({'success': False, 'message': 'Acceso denegado.'}), 403

    try:
        supabase.table('Tutoriales').delete().eq('id', video_id).execute()
        return jsonify({'success': True, 'message': 'Video eliminado correctamente.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al eliminar: {str(e)}'})

@app.route('/eliminar_usuario/<int:user_id>', methods=['DELETE', 'POST'])
def eliminar_usuario(user_id):
    if 'usuario' not in session or session.get('rol') != 'admin':
        return jsonify({'success': False, 'message': 'Acceso denegado.'}), 403

    if session.get('user_id') == user_id:
        return jsonify({'success': False, 'message': 'No puedes eliminar tu propia cuenta en uso.'})

    try:
        supabase.table('Usuarios').delete().eq('id', user_id).execute()
        return jsonify({'success': True, 'message': 'Usuario eliminado correctamente.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al eliminar: {str(e)}'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)