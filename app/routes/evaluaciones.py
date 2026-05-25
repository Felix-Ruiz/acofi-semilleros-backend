from flask import Blueprint, request, jsonify
from app.models import db, Ponencia, Evaluador, Evaluacion

evaluaciones_bp = Blueprint('evaluaciones', __name__)

@evaluaciones_bp.route('/calificar', methods=['POST'])
def calificar_ponencia():
    data = request.get_json()

    # Validamos los nuevos datos que envía el frontend
    if not data or 'documento_evaluador' not in data or 'ponencia_codigo' not in data or 'respuestas' not in data:
        return jsonify({"error": "Faltan datos requeridos"}), 400

    try:
        # 1. Buscar al evaluador por su documento para confirmar que está registrado
        evaluador = Evaluador.query.filter_by(documento_identidad=data['documento_evaluador']).first()
        if not evaluador:
            return jsonify({"error": "Evaluador no encontrado. Por favor, regístrese primero en el sistema."}), 404

        # 2. Buscar la ponencia usando el código
        ponencia = Ponencia.query.filter_by(codigo=data['ponencia_codigo']).first()
        if not ponencia:
            return jsonify({"error": "El código de la ponencia no existe"}), 404

        if ponencia.estado != 'aceptada':
            return jsonify({"error": "Esta ponencia no está habilitada para evaluación"}), 400

        # REGLA 1: Validar máximo de evaluaciones
        if len(ponencia.evaluaciones) >= 2:
            return jsonify({"error": "Esta ponencia ya alcanzó el límite máximo de 2 evaluaciones"}), 400

        # REGLA 2: Validar que este evaluador no la haya calificado antes
        evaluacion_previa = Evaluacion.query.filter_by(
            ponencia_id=ponencia.id, 
            evaluador_id=evaluador.id
        ).first()
        
        if evaluacion_previa:
            return jsonify({"error": "Ya has evaluado esta ponencia anteriormente"}), 400

        # 3. Guardar la evaluación
        nueva_evaluacion = Evaluacion(
            ponencia_id=ponencia.id,
            evaluador_id=evaluador.id,
            respuestas_rubrica=data['respuestas']
        )
        
        db.session.add(nueva_evaluacion)
        db.session.commit()

        return jsonify({"mensaje": "¡Evaluación guardada con éxito!"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al guardar la evaluación: {str(e)}"}), 500