from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
import os
import sqlite3
import requests
from datetime import datetime
from dotenv import load_dotenv
import gemini_assistant

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'clave_secreta_predeterminada')
socketio = SocketIO(app)

# Configuración de Twilio para WhatsApp
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# URL del servicio de WhatsApp (si estás usando un servicio personalizado)
WHATSAPP_SERVICE_URL = os.getenv('WHATSAPP_SERVICE_URL', 'http://localhost:3000')

def get_db_connection():
    """Establece una conexión con la base de datos"""
    try:
        conn = sqlite3.connect('assistant.db', timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error de conexión a SQLite: {e}")
        return None

def save_and_emit_message(platform, sender, chat_id, message, timestamp, is_from_assistant=False):
    """Guarda un mensaje en la base de datos y lo emite a través de Socket.IO"""
    conn = get_db_connection()
    if conn:
        try:
            c = conn.cursor()
            c.execute('INSERT INTO mensajes (platform, sender, chat_id, message, timestamp, is_from_assistant) VALUES (?, ?, ?, ?, ?, ?)',
                      (platform, sender, chat_id, message, timestamp, is_from_assistant))
            conn.commit()

            message_data = {
                'platform': platform,
                'sender': sender,
                'chat_id': chat_id,
                'message': message,
                'timestamp': timestamp,
                'is_from_assistant': is_from_assistant
            }
            socketio.emit('new_message', message_data, broadcast=True)
        except sqlite3.Error as e:
            print(f"Error al guardar mensaje en la base de datos: {e}")
        finally:
            conn.close()

@app.route('/')
def index():
    """Ruta principal que muestra la interfaz web"""
    return render_template('index.html')

@app.route('/messages')
def get_messages():
    """Obtiene todos los mensajes almacenados"""
    conn = get_db_connection()
    if conn:
        try:
            messages = conn.execute('SELECT * FROM mensajes ORDER BY timestamp DESC').fetchall()
            return jsonify([dict(row) for row in messages])
        except sqlite3.Error as e:
            print(f"Error al obtener mensajes: {e}")
            return jsonify({'error': 'Error en la base de datos'}), 500
        finally:
            conn.close()
    return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500

@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    """Webhook para recibir mensajes de WhatsApp (Twilio)"""
    try:
        # Extraer información del mensaje de WhatsApp
        from_number = request.values.get('From', '').replace('whatsapp:', '')
        to_number = request.values.get('To', '').replace('whatsapp:', '')
        body = request.values.get('Body', '')
        
        # Procesar el mensaje con nuestro asistente
        respuesta = gemini_assistant.procesar_mensaje(body, from_number)
        
        # Guardar el mensaje recibido y la respuesta
        timestamp = datetime.now().isoformat()
        save_and_emit_message('WhatsApp', from_number, from_number, body, timestamp)
        save_and_emit_message('WhatsApp', 'Asistente', from_number, respuesta, timestamp, True)
        
        # Enviar respuesta a través de Twilio
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            
            message = client.messages.create(
                body=respuesta,
                from_=f'whatsapp:{TWILIO_PHONE_NUMBER}',
                to=f'whatsapp:{from_number}'
            )
            
            print(f"Mensaje enviado a WhatsApp: {message.sid}")
        
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error en webhook de WhatsApp: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/whatsapp_message', methods=['POST'])
def whatsapp_message():
    """Endpoint para recibir mensajes de WhatsApp (servicio personalizado)"""
    data = request.json
    if not all(key in data for key in ['platform', 'sender', 'chat_id', 'message', 'timestamp']):
        return jsonify({'error': 'Datos incompletos'}), 400

    # Guardar el mensaje recibido
    save_and_emit_message(data['platform'], data['sender'], data['chat_id'], data['message'], data['timestamp'])
    
    # Procesar el mensaje con el asistente
    if data['platform'] == 'WhatsApp':
        try:
            # Procesar el mensaje con el asistente
            respuesta = gemini_assistant.procesar_mensaje(data['message'], data['chat_id'])
            
            # Enviar la respuesta a WhatsApp (servicio personalizado)
            response = requests.post(f'{WHATSAPP_SERVICE_URL}/send', json={
                'chat_id': data['chat_id'] + '@s.whatsapp.net',
                'message': respuesta
            }, timeout=5)
            
            # Guardar la respuesta del asistente en la base de datos
            timestamp = datetime.now().isoformat()
            save_and_emit_message(
                data['platform'],
                'Asistente',
                data['chat_id'],
                respuesta,
                timestamp,
                is_from_assistant=True
            )
            
            print(f"Respuesta del asistente enviada: {respuesta}")
        except Exception as e:
            print(f"Error al procesar mensaje con el asistente: {e}")
    
    return jsonify({'status': 'ok'})

@socketio.on('send_message')
def handle_send_message(data):
    """Maneja el envío de mensajes desde la interfaz web"""
    platform = data.get('platform')
    chat_id = data.get('chat_id')
    message = data.get('message')

    if not all([platform, chat_id, message]):
        print("Error: Datos incompletos en send_message")
        return

    if platform == 'WhatsApp':
        try:
            # Enviar mensaje a través del servicio personalizado
            response = requests.post(f'{WHATSAPP_SERVICE_URL}/send', json={
                'chat_id': chat_id + '@s.whatsapp.net',  
                'message': message
            }, timeout=5)
            
            # Procesar la respuesta del asistente
            respuesta = gemini_assistant.procesar_mensaje(message, chat_id)
            
            # Guardar la respuesta
            timestamp = datetime.now().isoformat()
            save_and_emit_message(platform, 'Asistente', chat_id, respuesta, timestamp, is_from_assistant=True)
            
            print(f"Mensaje enviado a WhatsApp: {chat_id} - {message}")
            print(f"Respuesta del asistente: {respuesta}")
        except requests.RequestException as e:
            print(f"Error al enviar mensaje a WhatsApp: {e}")

def init_db():
    """Inicializa la base de datos para mensajes"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS mensajes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT,
        sender TEXT,
        chat_id TEXT,
        message TEXT,
        timestamp TEXT,
        is_from_assistant BOOLEAN DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()
    print("Base de datos de mensajes inicializada correctamente.")

if __name__ == '__main__':
    # Inicializar la base de datos
    init_db()
    gemini_assistant.init_db()
    
    # Iniciar el servidor
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    print(f"Iniciando servidor en el puerto {port}...")
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)