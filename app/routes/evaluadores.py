from flask import Blueprint, request, jsonify
from app.models import db, Evaluador

# Creamos el Blueprint para evaluadores
evaluadores_bp = Blueprint('evaluadores', __name__)

@evaluadores_bp.route('/registro', methods=['POST'])
def registrar_evaluador():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se recibieron datos"}), 400

    try:
        nuevo_evaluador = Evaluador(
            nombres_apellidos=data['nombres_apellidos'],
            documento_identidad=data['documento_identidad'],
            institucion=data['institucion'],
            correo=data['correo'],
            cargo=data['cargo'],
            evento_id=data['evento_id'] # Aquí llegará el ID de la ciudad seleccionada en el formulario
        )
        db.session.add(nuevo_evaluador)
        db.session.commit()

        return jsonify({
            "mensaje": "Evaluador registrado exitosamente. Ya puede iniciar sesión para escanear ponencias."
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al registrar evaluador: {str(e)}"}), 500