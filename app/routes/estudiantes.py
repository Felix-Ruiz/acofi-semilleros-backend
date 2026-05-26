from flask import Blueprint, request, jsonify
from app.models import db, Estudiante, Ponencia, Configuracion
import random
import string

# Creamos un "Blueprint" para agrupar todas las rutas de estudiantes
estudiantes_bp = Blueprint('estudiantes', __name__)

def generar_pin():
    """Genera un PIN aleatorio de 4 dígitos para el acceso del estudiante"""
    return ''.join(random.choices(string.digits, k=4))

@estudiantes_bp.route('/registro', methods=['POST'])
def registrar_estudiante():
    # --- BLOQUEO DE SEGURIDAD: Verificar si las inscripciones están abiertas ---
    config = Configuracion.query.filter_by(clave='registro_abierto').first()
    if config and config.valor == 'false':
        return jsonify({"error": "Las inscripciones se encuentran cerradas por el administrador."}), 403

    # Recibimos los datos enviados desde el Frontend
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se recibieron datos"}), 400

    try:
        # Validar si el estudiante ya está registrado (para evitar duplicados por recarga rápida)
        estudiante_existente = Estudiante.query.filter_by(documento_identidad=data['documento_identidad']).first()
        if estudiante_existente:
            return jsonify({"error": "Este documento de identidad ya se encuentra registrado."}), 400

        # 1. Crear el registro del estudiante
        nuevo_estudiante = Estudiante(
            nombres_apellidos=data['nombres_apellidos'],
            documento_identidad=data['documento_identidad'],
            institucion=data['institucion'],
            correo=data['correo'],
            ciudad=data['ciudad'],
            cargo=data['cargo'],
            nombre_trabajo=data['nombre_trabajo'],
            pin_acceso=generar_pin()  # Se asigna el PIN automático
        )
        db.session.add(nuevo_estudiante)
        db.session.flush() # Hace un guardado temporal para obtener el ID del estudiante

        # 2. LÓGICA DE GRUPOS: Verificar si ya existe una ponencia con este título
        ponencia_existente = Ponencia.query.filter_by(titulo=data['nombre_trabajo']).first()
        
        if not ponencia_existente:
            # Si no existe, creamos la ponencia vinculada (estado pendiente)
            nueva_ponencia = Ponencia(
                estudiante_id=nuevo_estudiante.id,
                titulo=data['nombre_trabajo']
            )
            db.session.add(nueva_ponencia)
        
        # 3. Guardar todo permanentemente en la base de datos
        db.session.commit()

        # Enviamos el mensaje de éxito junto con el PIN generado
        return jsonify({
            "mensaje": f"Registro exitoso. Su PIN de acceso es {nuevo_estudiante.pin_acceso}. En espera de revisión del comité."
        }), 201

    except Exception as e:
        db.session.rollback() # Si hay un error, deshacemos los cambios para no dañar la BD
        return jsonify({"error": f"Error al registrar: {str(e)}"}), 500