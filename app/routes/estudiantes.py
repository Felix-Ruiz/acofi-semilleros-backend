from flask import Blueprint, request, jsonify
from app.models import db, Estudiante, Ponencia

# Creamos un "Blueprint" para agrupar todas las rutas de estudiantes
estudiantes_bp = Blueprint('estudiantes', __name__)

@estudiantes_bp.route('/registro', methods=['POST'])
def registrar_estudiante():
    # Recibimos los datos enviados desde el Frontend
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se recibieron datos"}), 400

    try:
        # 1. Crear el registro del estudiante
        nuevo_estudiante = Estudiante(
            nombres_apellidos=data['nombres_apellidos'],
            documento_identidad=data['documento_identidad'],
            institucion=data['institucion'],
            correo=data['correo'],
            ciudad=data['ciudad'],
            cargo=data['cargo'],
            nombre_trabajo=data['nombre_trabajo']
        )
        db.session.add(nuevo_estudiante)
        db.session.flush() # Hace un guardado temporal para obtener el ID del estudiante

        # 2. Crear la ponencia vinculada (estado pendiente, sin código ni QR)
        nueva_ponencia = Ponencia(
            estudiante_id=nuevo_estudiante.id,
            titulo=data['nombre_trabajo']
        )
        db.session.add(nueva_ponencia)
        
        # 3. Guardar todo permanentemente en la base de datos
        db.session.commit()

        return jsonify({
            "mensaje": "Estudiante y ponencia registrados exitosamente. En espera de revisión del admin."
        }), 201

    except Exception as e:
        db.session.rollback() # Si hay un error, deshacemos los cambios para no dañar la BD
        return jsonify({"error": f"Error al registrar: {str(e)}"}), 500