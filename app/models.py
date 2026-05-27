from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Administrador(db.Model):
    __tablename__ = 'administradores'
    id = db.Column(db.Integer, primary_key=True)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class Evento(db.Model):
    __tablename__ = 'eventos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False) # Ej: Barranquilla, Atlántico
    fecha = db.Column(db.Date, nullable=False)
    evaluadores = db.relationship('Evaluador', backref='evento', lazy=True)

class Estudiante(db.Model):
    __tablename__ = 'estudiantes'
    id = db.Column(db.Integer, primary_key=True)
    nombres_apellidos = db.Column(db.String(200), nullable=False)
    documento_identidad = db.Column(db.String(50), unique=True, nullable=False)
    institucion = db.Column(db.String(200), nullable=False)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    ciudad = db.Column(db.String(100), nullable=False)
    cargo = db.Column(db.String(50), nullable=False)
    nombre_trabajo = db.Column(db.String(300), nullable=False)
    pin_acceso = db.Column(db.String(20), nullable=True)
    
    # ⚠️ NUEVA COLUMNA DE ASISTENCIA AÑADIDA
    asistencia = db.Column(db.Boolean, default=False)
    
    ponencia = db.relationship('Ponencia', backref='estudiante', uselist=False)

class Evaluador(db.Model):
    __tablename__ = 'evaluadores'
    id = db.Column(db.Integer, primary_key=True)
    nombres_apellidos = db.Column(db.String(200), nullable=False)
    documento_identidad = db.Column(db.String(50), unique=True, nullable=False)
    institucion = db.Column(db.String(200), nullable=False)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    cargo = db.Column(db.String(100), nullable=False)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=False)
    pin_acceso = db.Column(db.String(20), nullable=True)
    evaluaciones = db.relationship('Evaluacion', backref='evaluador', lazy=True)

class Ponencia(db.Model):
    __tablename__ = 'ponencias'
    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    titulo = db.Column(db.String(300), nullable=False)
    estado = db.Column(db.String(20), default='pendiente') # pendiente, aceptada, rechazada
    codigo = db.Column(db.String(3), unique=True, nullable=True) # Los 3 números automáticos
    url_qr = db.Column(db.String(300), nullable=True) # Ruta de la imagen del QR
    evaluaciones = db.relationship('Evaluacion', backref='ponencia', lazy=True)

class Evaluacion(db.Model):
    __tablename__ = 'evaluaciones'
    id = db.Column(db.Integer, primary_key=True)
    ponencia_id = db.Column(db.Integer, db.ForeignKey('ponencias.id'), nullable=False)
    evaluador_id = db.Column(db.Integer, db.ForeignKey('evaluadores.id'), nullable=False)
    respuestas_rubrica = db.Column(db.JSON, nullable=False)
    fecha_evaluacion = db.Column(db.DateTime, default=datetime.utcnow)

class Configuracion(db.Model):
    __tablename__ = 'configuraciones'
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.String(100), nullable=False)