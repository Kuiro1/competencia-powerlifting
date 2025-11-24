import pandas as pd
import json
import math
import os
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import csv
import io
from datetime import datetime

# Configuración de Flask
app = Flask(__name__, static_url_path='', static_folder='.')
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'
CORS(app, resources={r"/*": {"origins": "*"}})

# Inicializar SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Archivo donde se guardarán los datos
BACKUP_FILE = 'competencia_backup.json'

# --- CONFIGURACIÓN CON MOVIMIENTOS ---
FILES_CONFIG = {
    "damas_iniciantes": {
        "file": "damas_iniciantes.csv",
        "skiprows": 3,
        "col_nombre": 1,
        "movimientos": {
            "peso_muerto": {
                "intento1": 4, "intento2": 5, "valido": 6,
                "nombre": "Peso Muerto", "intentos": 2
            }
        }
    },
    "damas_avanzadas": {
        "file": "damas_avanzadas.csv",
        "skiprows": 4,
        "col_nombre": 1,
        "movimientos": {
            "sentadilla": {
                "intento1": 4, "intento2": 5, "valido": 6,
                "nombre": "Sentadilla", "intentos": 2
            },
            "peso_muerto": {
                "intento1": 7, "intento2": 8, "valido": 9,
                "nombre": "Peso Muerto", "intentos": 2
            }
        }
    },
    "damas_overall": {
        "file": "damas_overall.csv",
        "skiprows": 3,
        "col_nombre": 1,
        "movimientos": {
            "sentadilla": {
                "intento1": 4, "intento2": 5, "intento3": 6, "valido": 7,
                "nombre": "Sentadilla", "intentos": 3
            },
            "press_banca": {
                "intento1": 8, "intento2": 9, "intento3": 10, "valido": 11,
                "nombre": "Press Banca", "intentos": 3
            },
            "peso_muerto": {
                "intento1": 12, "intento2": 13, "intento3": 14, "valido": 15,
                "nombre": "Peso Muerto", "intentos": 3
            }
        }
    },
    "varones_iniciantes": {
        "file": "varones_iniciantes.csv",
        "skiprows": 3,
        "col_nombre": 1,
        "movimientos": {
            "peso_muerto": {
                "intento1": 4, "intento2": 5, "valido": 6,
                "nombre": "Peso Muerto", "intentos": 2
            }
        }
    },
    "varones_avanzados": {
        "file": "varones_avanzados.csv",
        "skiprows": 3,
        "col_nombre": 1,
        "movimientos": {
            "press_banca": {
                "intento1": 4, "intento2": 5, "valido": 6,
                "nombre": "Press Banca", "intentos": 2
            },
            "peso_muerto": {
                "intento1": 7, "intento2": 8, "valido": 9,
                "nombre": "Peso Muerto", "intentos": 2
            }
        }
    },
    "varones_overall": {
        "file": "varones_overall.csv",
        "skiprows": 3,
        "col_nombre": 1,
        "movimientos": {
            "sentadilla": {
                "intento1": 4, "intento2": 5, "intento3": 6, "valido": 7,
                "nombre": "Sentadilla", "intentos": 3
            },
            "press_banca": {
                "intento1": 8, "intento2": 9, "intento3": 10, "valido": 11,
                "nombre": "Press Banca", "intentos": 3
            },
            "peso_muerto": {
                "intento1": 12, "intento2": 13, "intento3": 14, "valido": 15,
                "nombre": "Peso Muerto", "intentos": 3
            }
        }
    }
}

datos_globales = {}

# ========== FUNCIONES DE PERSISTENCIA ==========

def cargar_backup():
    """Carga datos desde el archivo de backup si existe"""
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                print(f"✅ Backup cargado desde {BACKUP_FILE}")
                return datos
        except Exception as e:
            print(f"⚠️ Error al cargar backup: {e}")
            return {}
    return {}

def guardar_backup():
    """Guarda los datos actuales en el archivo de backup"""
    try:
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos_globales, f, ensure_ascii=False, indent=2)
        print("💾 Backup guardado correctamente")
    except Exception as e:
        print(f"❌ Error al guardar backup: {e}")

def notificar_cambios(cat_id):
    """Notifica a todos los clientes conectados que hubo un cambio"""
    socketio.emit('datos_actualizados', {'categoria': cat_id}, broadcast=True)

# ========== FUNCIONES AUXILIARES ==========

def convertir_a_float(valor):
    if valor is None or valor == '':
        return 0.0
    try:
        resultado = float(str(valor).strip() or 0)
        if math.isnan(resultado):
            return 0.0
        return resultado
    except (ValueError, TypeError):
        return 0.0

def cargar_csv(archivo, skiprows, col_nombre):
    try:
        df = pd.read_csv(
            archivo, skiprows=skiprows, header=None,
            delimiter=';', encoding='windows-1252'
        )
        
        if col_nombre >= len(df.columns):
            return []
        
        df_limpio = pd.DataFrame({
            'ID_Planilla': df.iloc[:, 0],
            'Nombre': df.iloc[:, col_nombre],
            'Carrera': df.iloc[:, col_nombre+1] if col_nombre+1 < len(df.columns) else None,
            'BW': df.iloc[:, col_nombre+2] if col_nombre+2 < len(df.columns) else None
        })
        
        for col in range(len(df.columns)):
            if col >= col_nombre + 3:
                df_limpio[f'col_{col}'] = df.iloc[:, col]
        
        df_limpio = df_limpio.dropna(subset=['Nombre'])
        df_limpio['Nombre'] = df_limpio['Nombre'].astype(str)
        df_limpio = df_limpio[df_limpio['Nombre'].str.strip() != '']
        df_limpio = df_limpio[df_limpio['Nombre'].str.strip() != 'nan']
        df_limpio = df_limpio[df_limpio['Nombre'].str.upper() != 'NOMBRE / APELLIDOS']
        df_limpio = df_limpio.where(pd.notnull(df_limpio), None)
        
        return df_limpio.to_dict('records')
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []

def calcular_fuerza_relativa_total(cat_id, participante):
    if cat_id not in FILES_CONFIG:
        return 0.0
    
    config = FILES_CONFIG[cat_id]
    bw = convertir_a_float(participante.get("BW"))
    
    if bw <= 0:
        return 0.0
    
    suma_pesos = 0.0
    
    for mov_id, mov_config in config["movimientos"].items():
        peso_valido = convertir_a_float(participante.get(f'col_{mov_config["valido"]}'))
        suma_pesos += peso_valido
    
    fuerza_relativa = round(suma_pesos / bw, 4)
    
    return fuerza_relativa

# ========== CARGAR ARCHIVOS ==========
print("\n" + "="*60)
print("🔄 INICIANDO CARGA DE DATOS...")
print("="*60)

backup_data = cargar_backup()

if backup_data:
    datos_globales = backup_data
    print("\n📦 Datos cargados desde backup")
    for cat_id in datos_globales:
        print(f"   ✅ {cat_id}: {len(datos_globales[cat_id])} participantes")
else:
    print("\n📂 No se encontró backup, cargando desde CSVs...")
    
    for cat_id, config in FILES_CONFIG.items():
        archivo = config["file"]
        skiprows = config["skiprows"]
        col_nombre = config["col_nombre"]
        
        print(f"\n📄 {archivo} (skiprows={skiprows})")
        
        movimientos = list(config["movimientos"].keys())
        print(f"   Movimientos: {', '.join([config['movimientos'][m]['nombre'] for m in movimientos])}")
        
        datos = cargar_csv(archivo, skiprows, col_nombre)
        datos_globales[cat_id] = datos
        
        if len(datos) > 0:
            print(f"   ✅ {len(datos)} registros | Primero: {datos[0]['Nombre']}")
        else:
            print(f"   ⚠️ 0 registros")
    
    guardar_backup()
    print("\n💾 Backup inicial creado")

print("\n" + "="*60)
print(f"📊 Total categorías: {len(datos_globales)}")
print("="*60 + "\n")

# --- RUTAS HTTP ---

@app.route("/")
def serve_index():
    return app.send_static_file('index.html')

@app.route("/ranking/<cat_id>", methods=["GET"])
def get_ranking(cat_id):
    lista = datos_globales.get(cat_id, [])
    ranking = []
    
    for c in lista:
        bw = convertir_a_float(c.get("BW"))
        fuerza_relativa_total = calcular_fuerza_relativa_total(cat_id, c)
        
        comp = {
            "Nombre": c.get("Nombre", ""),
            "Carrera": c.get("Carrera", ""),
            "BW": bw,
            "Total_Fuerza_Relativa": fuerza_relativa_total
        }
        
        ranking.append(comp)
    
    ranking.sort(key=lambda x: x.get("Total_Fuerza_Relativa", 0), reverse=True)
    
    for i, comp in enumerate(ranking):
        comp["Lugar"] = i + 1
    
    return jsonify(ranking)

@app.route("/movimientos/<cat_id>", methods=["GET"])
def get_movimientos(cat_id):
    if cat_id not in FILES_CONFIG:
        return jsonify({"error": "Categoría no encontrada"}), 404
    
    config = FILES_CONFIG[cat_id]
    movimientos = []
    
    for mov_id, mov_info in config["movimientos"].items():
        movimientos.append({
            "id": mov_id,
            "nombre": mov_info["nombre"],
            "intentos": mov_info["intentos"]
        })
    
    return jsonify(movimientos)

@app.route("/movimiento/<cat_id>/<mov_id>", methods=["GET"])
def get_movimiento(cat_id, mov_id):
    if cat_id not in FILES_CONFIG:
        return jsonify({"error": "Categoría no encontrada"}), 404
    
    if mov_id not in FILES_CONFIG[cat_id]["movimientos"]:
        return jsonify({"error": "Movimiento no encontrado"}), 404
    
    lista = datos_globales.get(cat_id, [])
    mov_config = FILES_CONFIG[cat_id]["movimientos"][mov_id]
    
    resultado = []
    
    for i, c in enumerate(lista):
        intento1 = convertir_a_float(c.get(f'col_{mov_config["intento1"]}'))
        intento2 = convertir_a_float(c.get(f'col_{mov_config["intento2"]}')) if "intento2" in mov_config else 0
        intento3 = convertir_a_float(c.get(f'col_{mov_config["intento3"]}')) if "intento3" in mov_config else 0
        valido = convertir_a_float(c.get(f'col_{mov_config["valido"]}'))
        bw = convertir_a_float(c.get("BW"))
        
        dato = {
            "Lugar": i + 1,
            "Nombre": c.get("Nombre", ""),
            "Carrera": c.get("Carrera", ""),
            "BW": bw,
            "Intento1": intento1,
            "Intento2": intento2,
            "Mejor": valido,
            "Res1": c.get(f'res_{mov_id}_1'),
            "Res2": c.get(f'res_{mov_id}_2')
        }
        
        if "intento3" in mov_config:
            dato["Intento3"] = intento3
            dato["Res3"] = c.get(f'res_{mov_id}_3')
        
        resultado.append(dato)
    
    return jsonify(resultado)

@app.route("/registrar_intento", methods=["POST"])
def registrar_intento():
    data = request.json
    cat_id = data.get("cat_id")
    mov_id = data.get("mov_id")
    nombre = data.get("nombre")
    intento = data.get("intento")
    resultado = data.get("resultado")
    
    lista = datos_globales.get(cat_id)
    if not lista:
        return jsonify({"error": "Categoría inválida"}), 400
    
    if cat_id not in FILES_CONFIG or mov_id not in FILES_CONFIG[cat_id]["movimientos"]:
        return jsonify({"error": "Movimiento inválido"}), 400
    
    mov_config = FILES_CONFIG[cat_id]["movimientos"][mov_id]
    
    for c in lista:
        if c["Nombre"] == nombre:
            c[f'res_{mov_id}_{intento}'] = resultado
            
            if resultado == "exito":
                col_intento = mov_config.get(f'intento{intento}')
                peso_intento = convertir_a_float(c.get(f'col_{col_intento}'))
                
                col_valido = mov_config["valido"]
                peso_valido_actual = convertir_a_float(c.get(f'col_{col_valido}'))
                
                if peso_intento > peso_valido_actual:
                    c[f'col_{col_valido}'] = peso_intento
            
            guardar_backup()
            notificar_cambios(cat_id)
            return jsonify({"status": "exito"})
    
    return jsonify({"error": "No encontrado"}), 404

@app.route("/actualizar_peso", methods=["POST"])
def actualizar_peso():
    data = request.json
    cat_id = data.get("cat_id")
    mov_id = data.get("mov_id")
    nombre = data.get("nombre")
    intento = data.get("intento")
    peso = convertir_a_float(data.get("peso"))
    
    lista = datos_globales.get(cat_id)
    if not lista:
        return jsonify({"error": "Categoría inválida"}), 400
    
    if cat_id not in FILES_CONFIG or mov_id not in FILES_CONFIG[cat_id]["movimientos"]:
        return jsonify({"error": "Movimiento inválido"}), 400
    
    mov_config = FILES_CONFIG[cat_id]["movimientos"][mov_id]
    col_intento = mov_config.get(f'intento{intento}')
    
    for c in lista:
        if c["Nombre"] == nombre:
            c[f'col_{col_intento}'] = peso
            guardar_backup()
            notificar_cambios(cat_id)
            return jsonify({"status": "exito"})
    
    return jsonify({"error": "No encontrado"}), 404

@app.route("/borrar_intento", methods=["POST"])
def borrar_intento():
    data = request.json
    cat_id = data.get("cat_id")
    mov_id = data.get("mov_id")
    nombre = data.get("nombre")
    intento = data.get("intento")
    
    lista = datos_globales.get(cat_id)
    if not lista:
        return jsonify({"error": "Categoría inválida"}), 400
    
    if cat_id not in FILES_CONFIG or mov_id not in FILES_CONFIG[cat_id]["movimientos"]:
        return jsonify({"error": "Movimiento inválido"}), 400
    
    mov_config = FILES_CONFIG[cat_id]["movimientos"][mov_id]
    
    for c in lista:
        if c["Nombre"] == nombre:
            c[f'res_{mov_id}_{intento}'] = None
            
            col_valido = mov_config["valido"]
            mejor = 0.0
            
            for i in range(1, mov_config["intentos"] + 1):
                if c.get(f'res_{mov_id}_{i}') == "exito":
                    col_int = mov_config.get(f'intento{i}')
                    peso = convertir_a_float(c.get(f'col_{col_int}'))
                    if peso > mejor:
                        mejor = peso
            
            c[f'col_{col_valido}'] = mejor
            
            guardar_backup()
            notificar_cambios(cat_id)
            return jsonify({"status": "exito"})
    
    return jsonify({"error": "No encontrado"}), 404

@app.route("/agregar_completo", methods=["POST"])
def agregar_completo():
    """Agregar participante con todos los intentos de todos los movimientos"""
    try:
        data = request.json
        cat_id = data.get("cat_id")
        lista = datos_globales.get(cat_id)
        
        if lista is None:
            return jsonify({"error": "Categoría inválida"}), 400
        
        config = FILES_CONFIG[cat_id]
        
        nuevo = {
            "ID_Planilla": 999,
            "Nombre": data.get("nombre"),
            "Carrera": data.get("carrera"),
            "BW": convertir_a_float(data.get("bw"))
        }
        
        intentos = data.get("intentos", {})
        
        for mov_id, mov_config in config["movimientos"].items():
            if mov_id in intentos:
                intentos_mov = intentos[mov_id]
                
                col_int1 = mov_config["intento1"]
                nuevo[f'col_{col_int1}'] = convertir_a_float(intentos_mov.get("intento1", 0))
                
                if "intento2" in mov_config and intentos_mov.get("intento2"):
                    col_int2 = mov_config["intento2"]
                    nuevo[f'col_{col_int2}'] = convertir_a_float(intentos_mov["intento2"])
                
                if "intento3" in mov_config and intentos_mov.get("intento3"):
                    col_int3 = mov_config["intento3"]
                    nuevo[f'col_{col_int3}'] = convertir_a_float(intentos_mov["intento3"])
        
        lista.append(nuevo)
        guardar_backup()
        notificar_cambios(cat_id)
        
        print(f"✅ Participante agregado: {nuevo['Nombre']}")
        return jsonify({"status": "exito"})
        
    except Exception as e:
        import traceback
        print(f"❌ Error en agregar_completo:")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/editar_bw", methods=["POST"])
def editar_bw():
    data = request.json
    cat_id = data.get("cat_id")
    nombre = data.get("nombre")
    nuevo_bw = convertir_a_float(data.get("bw"))
    
    lista = datos_globales.get(cat_id)
    if not lista:
        return jsonify({"error": "Categoría inválida"}), 400
    
    for c in lista:
        if c["Nombre"] == nombre:
            c["BW"] = nuevo_bw
            guardar_backup()
            notificar_cambios(cat_id)
            return jsonify({"status": "exito"})
    
    return jsonify({"error": "No encontrado"}), 404

@app.route("/eliminar_participante", methods=["POST"])
def eliminar_participante():
    data = request.json
    cat_id = data.get("cat_id")
    nombre = data.get("nombre")
    
    if cat_id in datos_globales:
        orig = len(datos_globales[cat_id])
        datos_globales[cat_id] = [c for c in datos_globales[cat_id] if c["Nombre"] != nombre]
        if len(datos_globales[cat_id]) < orig:
            guardar_backup()
            notificar_cambios(cat_id)
            return jsonify({"status": "exito"})
    
    return jsonify({"error": "No encontrado"}), 404

@app.route("/descargar/<cat_id>", methods=["GET"])
def descargar_categoria(cat_id):
    """Descarga el ranking de una categoría en formato CSV"""
    lista = datos_globales.get(cat_id, [])
    
    if not lista:
        return jsonify({"error": "Sin datos"}), 404
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['Lugar', 'Nombre', 'Carrera', 'BW', 'F.R._Total'])
    writer.writeheader()
    
    ranking = []
    for c in lista:
        ranking.append({
            'Nombre': c.get('Nombre', ''),
            'Carrera': c.get('Carrera', ''),
            'BW': convertir_a_float(c.get('BW')),
            'F.R._Total': calcular_fuerza_relativa_total(cat_id, c)
        })
    
    ranking.sort(key=lambda x: x['F.R._Total'], reverse=True)
    
    for i, c in enumerate(ranking):
        writer.writerow({
            'Lugar': i+1,
            'Nombre': c['Nombre'],
            'Carrera': c['Carrera'],
            'BW': round(c['BW'], 1),
            'F.R._Total': round(c['F.R._Total'], 4)
        })
    
    output.seek(0)
    fecha = datetime.now().strftime("%Y%m%d")
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'ranking_{cat_id}_{fecha}.csv'
    )

@app.route('/editar_intento1', methods=['POST'])
def editar_intento1():
    """Editar el primer intento de un participante"""
    try:
        data = request.json
        cat_id = data.get('cat_id')
        mov_id = data.get('mov_id')
        nombre = data.get('nombre')
        nuevo_peso = float(data.get('nuevo_peso'))
        
        print(f"📝 Editando Intento 1: {nombre} en {mov_id} -> {nuevo_peso} kg")
        
        if cat_id not in datos_globales:
            return jsonify({"error": "Categoría no válida"}), 400
        
        if cat_id not in FILES_CONFIG:
            return jsonify({"error": "Configuración no encontrada"}), 400
        
        lista = datos_globales[cat_id]
        config = FILES_CONFIG[cat_id]
        
        if mov_id not in config['movimientos']:
            return jsonify({"error": f"Movimiento '{mov_id}' no válido"}), 400
        
        mov_config = config['movimientos'][mov_id]
        col_intento1 = mov_config['intento1']
        
        participante_encontrado = False
        for participante in lista:
            if participante.get('Nombre') == nombre:
                participante[f'col_{col_intento1}'] = nuevo_peso
                participante_encontrado = True
                break
        
        if not participante_encontrado:
            return jsonify({"error": f"Participante '{nombre}' no encontrado"}), 404
        
        guardar_backup()
        notificar_cambios(cat_id)
        
        print(f"✅ Intento 1 actualizado exitosamente")
        
        return jsonify({
            "success": True,
            "mensaje": f"Intento 1 actualizado a {nuevo_peso} kg"
        })
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Error en editar_intento1:")
        print(error_detail)
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

# --- EVENTOS WEBSOCKET ---

@socketio.on('connect')
def handle_connect():
    print('🔌 Cliente conectado')

@socketio.on('disconnect')
def handle_disconnect():
    print('🔌 Cliente desconectado')

# --- EJECUTAR SERVIDOR ---

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, debug=False, host='0.0.0.0', port=port)
