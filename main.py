from flask import Flask, jsonify
from flask_cors import CORS
from app.models import db, Evento
from datetime import datetime
import os

def create_app():
    app = Flask(__name__)
    CORS(app) # Permite que el Frontend (React) se comunique con este Backend
    
    # Configuración de la base de datos (Conexión a Supabase / PostgreSQL)
    # Nota: El símbolo '#' en la contraseña se codifica como '%23' para evitar errores de lectura en la URL
    database_url = os.environ.get(
        'DATABASE_URL', 
        'postgresql+psycopg2://postgres:AcofiSemilleros%23@db.zobctsmkhuzibnlgmfqr.supabase.co:5432/postgres'
    )
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    # Crea las tablas en la base de datos si no existen y siembra datos iniciales
    with app.app_context():
        db.create_all() # ¡Esto creará las tablas directamente en Supabase!
        
        # Validación para crear los 3 eventos iniciales automáticamente si la tabla está vacía
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
        
    # --- Registro de Rutas (Blueprints) ---
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
        
    return app

if __name__ == '__main__':
    app = create_app()
    # Inicia el servidor en el puerto 5000
    app.run(debug=True, port=5000)