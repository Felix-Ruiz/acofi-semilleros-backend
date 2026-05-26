from flask import Blueprint, request, jsonify
from app.models import db, Evaluador
import random
import string

evaluadores_bp = Blueprint('evaluadores', __name__)

def generar_pin():
    return ''.join(random.choices(string.digits, k=4))

@evaluadores_bp.route('/registro', methods=['POST'])
def registrar_evaluador():
    data = request.get_json()
    
    # Validar si ya existe el evaluador
    existente = Evaluador.query.filter_by(documento_identidad=data['documento_identidad']).first()
    if existente:
        return jsonify({"error": "El documento ingresado ya se encuentra registrado."}), 400

    try:
        nuevo_evaluador = Evaluador(
            nombres_apellidos=data['nombres_apellidos'],
            documento_identidad=data['documento_identidad'],
            institucion=data['institucion'],
            correo=data['correo'],
            cargo=data['cargo'],
            evento_id=data['evento_id'],
            pin_acceso=generar_pin()
        )
        db.session.add(nuevo_evaluador)
        db.session.commit()

        return jsonify({
            "mensaje": f"Registro exitoso. IMPORTANTE: Su PIN de acceso es {nuevo_evaluador.pin_acceso}. Guárdelo para ingresar al sistema."
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al registrar: {str(e)}"}), 500