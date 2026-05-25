from flask import Blueprint, request, jsonify
from app.models import db, Evento
from datetime import datetime

# Creamos el Blueprint para eventos
eventos_bp = Blueprint('eventos', __name__)

@eventos_bp.route('/', methods=['GET'])
def obtener_eventos():
    # Consulta todos los eventos en la base de datos
    eventos = Evento.query.all()
    # Los formateamos para enviarlos al Frontend
    resultado = [
        {
            "id": e.id, 
            "nombre": e.nombre, 
            "fecha": e.fecha.strftime('%Y-%m-%d')
        } for e in eventos
    ]
    return jsonify(resultado), 200

@eventos_bp.route('/crear', methods=['POST'])
def crear_evento():
    data = request.get_json()
    
    if not data or 'nombre' not in data or 'fecha' not in data:
        return jsonify({"error": "Faltan datos (nombre, fecha)"}), 400
    
    try:
        # Convertimos el texto de la fecha (Ej: "2026-05-15") a un objeto de fecha real para la BD
        fecha_obj = datetime.strptime(data['fecha'], '%Y-%m-%d').date()
        
        nuevo_evento = Evento(
            nombre=data['nombre'], 
            fecha=fecha_obj
        )
        db.session.add(nuevo_evento)
        db.session.commit()
        
        return jsonify({"mensaje": f"Evento '{data['nombre']}' creado exitosamente"}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al crear evento: {str(e)}"}), 500