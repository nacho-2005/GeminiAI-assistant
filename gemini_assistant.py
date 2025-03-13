import os
import json
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai

# Cargar variables de entorno
load_dotenv()

# Configurar la API de Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

# Instrucciones del sistema para el asistente
SYSTEM_INSTRUCTIONS = """
Eres un asistente personal digital que ayuda a los usuarios a organizar sus vidas mediante la gestión de tareas y finanzas.
Tu objetivo es entender las solicitudes en lenguaje natural y convertirlas en acciones concretas.
Siempre responde en español de manera amigable y concisa.

Cuando el usuario quiere:
1. Agregar una tarea: Responde con "AGREGAR_TAREA" seguido de los detalles (título, descripción, fecha límite, prioridad).
2. Listar tareas: Responde con "LISTAR_TAREAS" seguido del filtro (todas, pendientes, completadas).
3. Completar una tarea: Responde con "COMPLETAR_TAREA" seguido del ID o título de la tarea.
4. Registrar un gasto: Responde con "REGISTRAR_GASTO" seguido de los detalles (monto, categoría, descripción, fecha).
5. Registrar un ingreso: Responde con "REGISTRAR_INGRESO" seguido de los detalles (monto, categoría, descripción, fecha).
6. Ver resumen financiero: Responde con "RESUMEN_FINANCIERO" seguido del periodo (día, semana, mes, año).
7. Ver saldo actual: Responde con "SALDO_ACTUAL".

Si el usuario te saluda o hace preguntas generales, responde de manera conversacional sin usar ninguno de los comandos anteriores.
"""

def init_db():
    """Inicializa las tablas necesarias para el asistente"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    # Tabla para tareas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tareas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        descripcion TEXT,
        fecha_creacion TEXT NOT NULL,
        fecha_limite TEXT,
        prioridad TEXT,
        completada INTEGER DEFAULT 0
    )
    ''')
    
    # Tabla para finanzas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS finanzas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        monto REAL NOT NULL,
        categoria TEXT NOT NULL,
        descripcion TEXT,
        fecha TEXT NOT NULL
    )
    ''')
    
    # Tabla para historial de conversaciones
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conversaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        mensaje TEXT NOT NULL,
        respuesta TEXT,
        timestamp TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente.")

def agregar_tarea(titulo, descripcion=None, fecha_limite=None, prioridad="media"):
    """Agrega una nueva tarea a la base de datos"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    fecha_creacion = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute(
        "INSERT INTO tareas (titulo, descripcion, fecha_creacion, fecha_limite, prioridad) VALUES (?, ?, ?, ?, ?)",
        (titulo, descripcion, fecha_creacion, fecha_limite, prioridad)
    )
    
    conn.commit()
    tarea_id = cursor.lastrowid
    conn.close()
    
    return f"✅ Tarea '{titulo}' agregada correctamente."

def registrar_gasto(monto, categoria, descripcion=None, fecha=None):
    """Registra un nuevo gasto en la base de datos"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    if not fecha:
        fecha = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute(
        "INSERT INTO finanzas (tipo, monto, categoria, descripcion, fecha) VALUES (?, ?, ?, ?, ?)",
        ("gasto", monto, categoria, descripcion, fecha)
    )
    
    conn.commit()
    conn.close()
    
    return f"✅ Gasto de ${monto} en '{categoria}' registrado correctamente."

def registrar_ingreso(monto, categoria, descripcion=None, fecha=None):
    """Registra un nuevo ingreso en la base de datos"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    if not fecha:
        fecha = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute(
        "INSERT INTO finanzas (tipo, monto, categoria, descripcion, fecha) VALUES (?, ?, ?, ?, ?)",
        ("ingreso", monto, categoria, descripcion, fecha)
    )
    
    conn.commit()
    conn.close()
    
    return f"✅ Ingreso de ${monto} en '{categoria}' registrado correctamente."

def listar_tareas(filtro="pendientes", ordenar_por="fecha"):
    """Obtiene la lista de tareas según los filtros especificados"""
    conn = sqlite3.connect('assistant.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM tareas"
    params = []
    
    if filtro == "pendientes":
        query += " WHERE completada = 0"
    elif filtro == "completadas":
        query += " WHERE completada = 1"
    
    if ordenar_por == "fecha":
        query += " ORDER BY fecha_limite"
    elif ordenar_por == "prioridad":
        # Ordenar por prioridad (alta > media > baja)
        query += " ORDER BY CASE prioridad WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baja' THEN 3 END"
    
    cursor.execute(query, params)
    tareas = cursor.fetchall()
    conn.close()
    
    if not tareas:
        return "No hay tareas para mostrar."
    
    resultado = "📋 Lista de tareas:\n\n"
    for tarea in tareas:
        estado = "✅" if tarea["completada"] else "⏳"
        prioridad_emoji = {"alta": "🔴", "media": "🟠", "baja": "🟢"}.get(tarea["prioridad"], "")
        fecha = f" (Vence: {tarea['fecha_limite']})" if tarea["fecha_limite"] else ""
        
        resultado += f"{estado} {prioridad_emoji} [{tarea['id']}] {tarea['titulo']}{fecha}\n"
    
    return resultado

def completar_tarea(id_tarea=None, titulo_tarea=None):
    """Marca una tarea como completada"""
    if not id_tarea and not titulo_tarea:
        return "❌ Error: Debes proporcionar el ID o el título de la tarea."
    
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    if id_tarea:
        cursor.execute("SELECT titulo FROM tareas WHERE id = ? AND completada = 0", (id_tarea,))
        tarea = cursor.fetchone()
        
        if not tarea:
            conn.close()
            return f"❌ No se encontró una tarea pendiente con ID {id_tarea}."
        
        cursor.execute("UPDATE tareas SET completada = 1 WHERE id = ?", (id_tarea,))
        titulo = tarea[0]
    else:
        cursor.execute("SELECT id FROM tareas WHERE titulo LIKE ? AND completada = 0", (f"%{titulo_tarea}%",))
        tarea = cursor.fetchone()
        
        if not tarea:
            conn.close()
            return f"❌ No se encontró una tarea pendiente con título similar a '{titulo_tarea}'."
        
        cursor.execute("UPDATE tareas SET completada = 1 WHERE id = ?", (tarea[0],))
        titulo = titulo_tarea
    
    conn.commit()
    conn.close()
    
    return f"✅ Tarea '{titulo}' marcada como completada."

def resumen_financiero(periodo="mes"):
    """Genera un resumen financiero para el periodo especificado"""
    conn = sqlite3.connect('assistant.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    hoy = datetime.now()
    
    if periodo == "dia":
        fecha_inicio = hoy.strftime("%Y-%m-%d")
    elif periodo == "semana":
        # 7 días atrás
        fecha_inicio = (hoy - timedelta(days=7)).strftime("%Y-%m-%d")
    elif periodo == "año":
        fecha_inicio = f"{hoy.year}-01-01"
    else:  # mes por defecto
        fecha_inicio = f"{hoy.year}-{hoy.month:02d}-01"
    
    # Obtener gastos por categoría
    cursor.execute(
        "SELECT SUM(monto) as total, categoria FROM finanzas WHERE tipo = 'gasto' AND fecha >= ? GROUP BY categoria ORDER BY total DESC",
        (fecha_inicio,)
    )
    gastos_por_categoria = cursor.fetchall()
    
    # Obtener total de gastos
    cursor.execute(
        "SELECT SUM(monto) as total FROM finanzas WHERE tipo = 'gasto' AND fecha >= ?",
        (fecha_inicio,)
    )
    total_gastos = cursor.fetchone()["total"] or 0
    
    # Obtener total de ingresos
    cursor.execute(
        "SELECT SUM(monto) as total FROM finanzas WHERE tipo = 'ingreso' AND fecha >= ?",
        (fecha_inicio,)
    )
    total_ingresos = cursor.fetchone()["total"] or 0
    
    conn.close()
    
    if total_gastos == 0 and total_ingresos == 0:
        return f"No hay movimientos financieros registrados en este {periodo}."
    
    resultado = f"💰 Resumen financiero ({periodo}):\n\n"
    resultado += f"Total de ingresos: ${total_ingresos:.2f}\n"
    resultado += f"Total de gastos: ${total_gastos:.2f}\n"
    resultado += f"Balance: ${total_ingresos - total_gastos:.2f}\n\n"
    
    if gastos_por_categoria:
        resultado += "Desglose de gastos por categoría:\n"
        for gasto in gastos_por_categoria:
            porcentaje = (gasto["total"] / total_gastos) * 100
            resultado += f"- {gasto['categoria']}: ${gasto['total']:.2f} ({porcentaje:.1f}%)\n"
    
    return resultado

def saldo_actual():
    """Calcula y muestra el saldo actual"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    # Obtener total de ingresos
    cursor.execute("SELECT SUM(monto) as total FROM finanzas WHERE tipo = 'ingreso'")
    total_ingresos = cursor.fetchone()[0] or 0
    
    # Obtener total de gastos
    cursor.execute("SELECT SUM(monto) as total FROM finanzas WHERE tipo = 'gasto'")
    total_gastos = cursor.fetchone()[0] or 0
    
    saldo = total_ingresos - total_gastos
    
    # Obtener últimos 5 movimientos
    cursor.execute(
        "SELECT tipo, monto, categoria, fecha FROM finanzas ORDER BY id DESC LIMIT 5"
    )
    ultimos_movimientos = cursor.fetchall()
    
    conn.close()
    
    resultado = f"💵 Saldo actual: ${saldo:.2f}\n\n"
    
    if ultimos_movimientos:
        resultado += "Últimos movimientos:\n"
        for mov in ultimos_movimientos:
            tipo, monto, categoria, fecha = mov
            emoji = "➕" if tipo == "ingreso" else "➖"
            resultado += f"{emoji} {fecha}: {categoria} - ${monto:.2f}\n"
    
    return resultado

def guardar_conversacion(chat_id, mensaje, respuesta):
    """Guarda la conversación en la base de datos"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO conversaciones (chat_id, mensaje, respuesta, timestamp) VALUES (?, ?, ?, ?)",
        (chat_id, mensaje, respuesta, timestamp)
    )
    
    conn.commit()
    conn.close()

def procesar_mensaje(mensaje, chat_id):
    """Procesa un mensaje del usuario y devuelve la respuesta del asistente"""
    try:
        # Configurar el modelo
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"temperature": 0.2},
            system_instruction=SYSTEM_INSTRUCTIONS
        )
        
        # Obtener respuesta del modelo
        response = model.generate_content(mensaje)
        
        # Obtener el texto de la respuesta
        respuesta_texto = response.text
        
        # Procesar comandos especiales
        if respuesta_texto.startswith("AGREGAR_TAREA"):
            # Extraer detalles de la tarea
            detalles = respuesta_texto[len("AGREGAR_TAREA"):].strip()
            partes = detalles.split(",")
            
            titulo = partes[0].strip()
            descripcion = partes[1].strip() if len(partes) > 1 else None
            fecha_limite = partes[2].strip() if len(partes) > 2 else None
            prioridad = partes[3].strip().lower() if len(partes) > 3 else "media"
            
            respuesta_final = agregar_tarea(titulo, descripcion, fecha_limite, prioridad)
        
        elif respuesta_texto.startswith("LISTAR_TAREAS"):
            filtro = respuesta_texto[len("LISTAR_TAREAS"):].strip().lower() or "pendientes"
            respuesta_final = listar_tareas(filtro)
        
        elif respuesta_texto.startswith("COMPLETAR_TAREA"):
            id_o_titulo = respuesta_texto[len("COMPLETAR_TAREA"):].strip()
            try:
                id_tarea = int(id_o_titulo)
                respuesta_final = completar_tarea(id_tarea=id_tarea)
            except ValueError:
                respuesta_final = completar_tarea(titulo_tarea=id_o_titulo)
        
        elif respuesta_texto.startswith("REGISTRAR_GASTO"):
            detalles = respuesta_texto[len("REGISTRAR_GASTO"):].strip()
            partes = detalles.split(",")
            
            try:
                monto = float(partes[0].strip())
                categoria = partes[1].strip()
                descripcion = partes[2].strip() if len(partes) > 2 else None
                fecha = partes[3].strip() if len(partes) > 3 else None
                
                respuesta_final = registrar_gasto(monto, categoria, descripcion, fecha)
            except (ValueError, IndexError):
                respuesta_final = "❌ Error: Formato incorrecto para registrar gasto. Necesito al menos el monto y la categoría."
        
        elif respuesta_texto.startswith("REGISTRAR_INGRESO"):
            detalles = respuesta_texto[len("REGISTRAR_INGRESO"):].strip()
            partes = detalles.split(",")
            
            try:
                monto = float(partes[0].strip())
                categoria = partes[1].strip()
                descripcion = partes[2].strip() if len(partes) > 2 else None
                fecha = partes[3].strip() if len(partes) > 3 else None
                
                respuesta_final = registrar_ingreso(monto, categoria, descripcion, fecha)
            except (ValueError, IndexError):
                respuesta_final = "❌ Error: Formato incorrecto para registrar ingreso. Necesito al menos el monto y la categoría."
        
        elif respuesta_texto.startswith("RESUMEN_FINANCIERO"):
            periodo = respuesta_texto[len("RESUMEN_FINANCIERO"):].strip().lower() or "mes"
            respuesta_final = resumen_financiero(periodo)
        
        elif respuesta_texto.startswith("SALDO_ACTUAL"):
            respuesta_final = saldo_actual()
        
        else:
            # Si no es un comando especial, devolver la respuesta directamente
            respuesta_final = respuesta_texto
        
        # Guardar la conversación
        guardar_conversacion(chat_id, mensaje, respuesta_final)
        
        return respuesta_final
    
    except Exception as e:
        print(f"Error al procesar mensaje: {e}")
        return "Lo siento, ha ocurrido un error al procesar tu mensaje. Por favor, inténtalo de nuevo."

# Inicializar la base de datos al importar el módulo
if __name__ == "__main__":
    init_db()
    # Ejemplo de uso
    print(procesar_mensaje("Hola, ¿cómo estás?", "test_chat_id"))