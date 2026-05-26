from flask import Flask, jsonify, request
from flask_cors import CORS
from app.models import db, Evento, Estudiante, Evaluador, Administrador, Configuracion
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    database_url = os.environ.get(
        'DATABASE_URL', 
        'postgresql+psycopg2://postgres:AcofiSemilleros%23@db.zobctsmkhuzibnlgmfqr.supabase.co:6543/postgres'
    )
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        
        if Evento.query.count() == 0:
            eventos_predeterminados = [
                {"nombre": "Barranquilla, Atlántico", "fecha": "2026-05-15"},
                {"nombre": "Bogotá, Distrito Capital", "fecha": "2026-05-22"},
                {"nombre": "Pereira, Risaralda", "fecha": "2026-05-29"}
            ]
            for ev in eventos_predeterminados:
                nuevo_evento = Evento(
                    nombre=ev["nombre"],
                    fecha=datetime.strptime(ev["fecha"], "%Y-%m-%d").date()
                )
                db.session.add(nuevo_evento)
            db.session.commit()

        if Administrador.query.count() == 0:
            admin_defecto = Administrador(
                correo="admin@acofi.com",
                password_hash=generate_password_hash("AcofiAdmin2026#")
            )
            db.session.add(admin_defecto)
            db.session.commit()

        # Siembra de la configuración de inscripciones
        if Configuracion.query.filter_by(clave='registro_abierto').first() is None:
            config_registro = Configuracion(clave='registro_abierto', valor='true')
            db.session.add(config_registro)
            db.session.commit()
        
    from app.routes.estudiantes import estudiantes_bp
    from app.routes.eventos import eventos_bp
    from app.routes.evaluadores import evaluadores_bp
    from app.routes.admin import admin_bp
    from app.routes.evaluaciones import evaluaciones_bp
    
    app.register_blueprint(estudiantes_bp, url_prefix='/api/estudiantes')
    app.register_blueprint(eventos_bp, url_prefix='/api/eventos')
    app.register_blueprint(evaluadores_bp, url_prefix='/api/evaluadores')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(evaluaciones_bp, url_prefix='/api/evaluaciones')
        
    @app.route('/')
    def index():
        return jsonify({"mensaje": "¡Backend del Encuentro de Semilleros funcionando correctamente!"})

    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json()
        correo = data.get('correo')
        password = data.get('password')
        documento = data.get('documento')
        pin = data.get('pin')

        if correo and password:
            admin = Administrador.query.filter_by(correo=correo).first()
            if admin and check_password_hash(admin.password_hash, password):
                return jsonify({
                    "mensaje": "Inicio de sesión de administrador exitoso",
                    "tipo_usuario": "admin",
                    "id": admin.id,
                    "nombre": "Administrador General"
                }), 200
            return jsonify({"error": "Correo electrónico o contraseña incorrectos."}), 401

        if not documento or not pin:
            return jsonify({"error": "Credenciales incompletas."}), 400

        evaluador = Evaluador.query.filter_by(documento_identidad=documento, pin_acceso=pin).first()
        if evaluador:
            return jsonify({
                "mensaje": "Inicio de sesión exitoso",
                "tipo_usuario": "evaluador",
                "id": evaluador.id,
                "nombre": evaluador.nombres_apellidos
            }), 200

        estudiante = Estudiante.query.filter_by(documento_identidad=documento, pin_acceso=pin).first()
        if estudiante:
            return jsonify({
                "mensaje": "Inicio de sesión exitoso",
                "tipo_usuario": "estudiante",
                "id": estudiante.id,
                "nombre": estudiante.nombres_apellidos
            }), 200

        return jsonify({"error": "Número de documento o PIN incorrectos."}), 401
        
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)