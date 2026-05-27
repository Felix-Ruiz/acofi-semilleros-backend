from flask import Blueprint, request, jsonify
from app.models import db, Evaluador
import random
import string
import os
import urllib.request
import json
import threading

evaluadores_bp = Blueprint('evaluadores', __name__)

DOMINIO_PRODUCCION = "https://semilleros.acofiapps.com"

@evaluadores_bp.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

def generar_pin():
    return ''.join(random.choices(string.digits, k=4))

# --- FUNCIÓN DE ENVÍO INDIVIDUAL POR API REST (ARQUITECTURA INSIGNIAS) ---
def enviar_correo_evaluador(destinatario, asunto, cuerpo):
    try:
        api_key = os.environ.get('BREVO_API_KEY') or os.environ.get('MAIL_PASSWORD', '').strip()
        remitente_oficial = os.environ.get('MAIL_SENDER', 'semilleros@acofiapps.com').strip()

        if not api_key:
            return

        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        }
        
        data = {
            "sender": {"name": "Comité Organizador ACOFI", "email": remitente_oficial},
            "to": [{"email": destinatario}],
            "subject": asunto,
            "htmlContent": cuerpo
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=15) as response:
            pass
    except Exception as e:
        print(f"Error enviando correo a evaluador: {str(e)}")

@evaluadores_bp.route('/registro', methods=['POST'])
def registrar_evaluador():
    data = request.get_json()
    
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

        # ENVIAR CORREO DE BIENVENIDA EN SEGUNDO PLANO
        asunto = "Registro Exitoso - Evaluador ACOFI 2026"
        cuerpo_html = f"""
        <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: auto; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px;">
            <h2 style="color: #1e3a8a;">Hola {nuevo_evaluador.nombres_apellidos},</h2>
            <p>Tu registro como Evaluador para el I Encuentro Regional de Investigación e Innovación en Ingeniería ACOFI 2026 ha sido exitoso.</p>
            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #1e3a8a;">
                <h3 style="margin-top: 0; color: #1e3a8a;">Tus credenciales de acceso:</h3>
                <p style="margin-bottom: 15px;">🔗 <strong>Plataforma:</strong> <a href="{DOMINIO_PRODUCCION}/login">{DOMINIO_PRODUCCION}/login</a></p>
                <ul style="list-style-type: none; padding-left: 0; margin: 0;">
                    <li style="margin-bottom: 8px;">👤 <strong>Documento:</strong> {nuevo_evaluador.documento_identidad}</li>
                    <li>🔑 <strong>PIN de Acceso:</strong> {nuevo_evaluador.pin_acceso}</li>
                </ul>
            </div>
            <p>El día del evento, ingresa a la plataforma para acceder al escáner de códigos QR y evaluar los proyectos.</p>
            <p>Saludos cordiales,<br><strong>Comité Organizador ACOFI</strong></p>
        </div>
        """
        threading.Thread(target=enviar_correo_evaluador, args=(nuevo_evaluador.correo, asunto, cuerpo_html)).start()

        return jsonify({
            "mensaje": f"Registro exitoso. IMPORTANTE: Su PIN de acceso es {nuevo_evaluador.pin_acceso}. Guárdelo para ingresar al sistema."
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al registrar: {str(e)}"}), 500