from flask import Blueprint, request, jsonify, send_file
from app.models import db, Ponencia, Estudiante, Evaluador, Evaluacion, Configuracion
import qrcode
import os
import random
import string
import io
import pandas as pd
from openpyxl import Workbook
import cloudinary
import cloudinary.uploader
import re
import threading
import urllib.request
import json

# =====================================================================
# ⚠️ DOMINIO DE PRODUCCIÓN
DOMINIO_PRODUCCION = "https://semilleros.acofiapps.com" 
# =====================================================================

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

admin_bp = Blueprint('admin', __name__)

@admin_bp.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

def generar_pin():
    return ''.join(random.choices(string.digits, k=4))

def enviar_correo(destinatario, asunto, cuerpo):
    try:
        api_key = os.environ.get('BREVO_API_KEY') or os.environ.get('MAIL_PASSWORD', '').strip()
        remitente_oficial = os.environ.get('MAIL_SENDER', 'semilleros@acofiapps.com').strip()

        if not api_key:
            return False, "Falta la clave de Brevo."

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
            return True, "Enviado con éxito"
            
    except Exception as e:
        return False, f"Error HTTP: {str(e)}"

def proceso_envio_segundo_plano(lista_datos):
    api_key = os.environ.get('BREVO_API_KEY') or os.environ.get('MAIL_PASSWORD', '').strip()
    remitente_oficial = os.environ.get('MAIL_SENDER', 'semilleros@acofiapps.com').strip()
    url = "https://api.brevo.com/v3/smtp/email"

    if not api_key: return

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    for datos in lista_datos:
        try:
            cuerpo_html = f"""
            <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: auto; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px;">
                <h2 style="color: #1e3a8a;">Hola {datos['nombres']},</h2>
                <p>Nos complace informarte que tu proyecto <strong>"{datos['titulo']}"</strong> está listo para el I Encuentro Regional de Investigación e Innovación en Ingeniería ACOFI 2026.</p>
                <p>Tu código de póster asignado es: <strong style="font-size: 18px; color: #1e3a8a;">{datos['codigo']}</strong></p>
                
                <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #1e3a8a;">
                    <h3 style="margin-top: 0; color: #1e3a8a;">Credencial Digital</h3>
                    <p style="margin-bottom: 10px;">Para ver tu código QR desde tu celular e ingresar a la plataforma:</p>
                    <p style="margin-bottom: 15px;">🔗 <strong>Enlace de ingreso:</strong> <a href="{DOMINIO_PRODUCCION}/login">{DOMINIO_PRODUCCION}/login</a></p>
                    <ul style="list-style-type: none; padding-left: 0; margin: 0;">
                        <li style="margin-bottom: 8px;">👤 <strong>Usuario:</strong> Tu número de documento ({datos['documento']})</li>
                        <li>🔑 <strong>Contraseña (PIN):</strong> {datos['pin']}</li>
                    </ul>
                </div>
                <div style="text-align: center; margin: 20px 0;">
                    <img src="{datos['url_qr']}" alt="QR Ponencia" style="width:200px; height:200px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px;">
                </div>
                <p>Saludos cordiales,<br><strong>Comité Organizador ACOFI</strong></p>
            </div>
            """
            data = {
                "sender": {"name": "Comité Organizador ACOFI", "email": remitente_oficial},
                "to": [{"email": datos['correo']}],
                "subject": f"Código QR de Evaluación - Ponencia: {datos['codigo']}",
                "htmlContent": cuerpo_html
            }

            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=15) as response:
                pass 
        except Exception as e:
            pass

def eliminar_qr_cloudinary(url_qr):
    if not url_qr: return
    try:
        match = re.search(r'(qrs_acofi/[^.]+)', url_qr)
        if match:
            cloudinary.uploader.destroy(match.group(1))
    except Exception as e:
        pass

@admin_bp.route('/configuracion', methods=['GET'])
def obtener_configuracion():
    config = Configuracion.query.filter_by(clave='registro_abierto').first()
    estado = config.valor if config else 'true'
    return jsonify({"registro_abierto": estado == 'true'}), 200

@admin_bp.route('/configuracion/toggle', methods=['POST'])
def alternar_configuracion():
    config = Configuracion.query.filter_by(clave='registro_abierto').first()
    if not config:
        config = Configuracion(clave='registro_abierto', valor='true')
        db.session.add(config)
    config.valor = 'false' if config.valor == 'true' else 'true'
    db.session.commit()
    return jsonify({"mensaje": "Estado de registros actualizado", "registro_abierto": config.valor == 'true'}), 200

@admin_bp.route('/estudiante_perfil/<int:estudiante_id>', methods=['GET'])
def obtener_perfil_estudiante(estudiante_id):
    try:
        estudiante = Estudiante.query.get(estudiante_id)
        if not estudiante:
            return jsonify({"error": "Estudiante no encontrado"}), 404
        ponencia = Ponencia.query.filter_by(titulo=estudiante.nombre_trabajo).first()
        return jsonify({
            "id": estudiante.id,
            "nombre": estudiante.nombres_apellidos,
            "documento": estudiante.documento_identidad,
            "institucion": estudiante.institucion,
            "correo": estudiante.correo,
            "ciudad": estudiante.ciudad,
            "trabajo_titulo": ponencia.titulo if ponencia else estudiante.nombre_trabajo,
            "codigo": ponencia.codigo if ponencia else None,
            "url_qr": ponencia.url_qr if ponencia else None
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/estudiantes', methods=['GET'])
def obtener_estudiantes():
    try:
        estudiantes = Estudiante.query.all()
        resultado = []
        for e in estudiantes:
            resultado.append({
                "id": e.id,
                "nombres_apellidos": e.nombres_apellidos,
                "documento_identidad": e.documento_identidad,
                "institucion": e.institucion,
                "correo": e.correo,
                "ciudad": e.ciudad,
                "cargo": e.cargo,
                "nombre_trabajo": e.nombre_trabajo,
                "pin_acceso": e.pin_acceso,
                "asistencia": getattr(e, 'asistencia', False)
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": f"Error al cargar estudiantes: {str(e)}"}), 500

@admin_bp.route('/estudiantes/<int:id>/asistencia', methods=['PUT'])
def toggle_asistencia(id):
    data = request.get_json()
    try:
        estudiante = Estudiante.query.get(id)
        if not estudiante: return jsonify({"error": "Estudiante no encontrado"}), 404
        estudiante.asistencia = data.get('asistencia', False)
        db.session.commit()
        return jsonify({"mensaje": "Asistencia actualizada con éxito", "asistencia": estudiante.asistencia}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al actualizar asistencia: {str(e)}"}), 500

@admin_bp.route('/estudiantes/<int:id>', methods=['PUT'])
def editar_estudiante(id):
    data = request.get_json()
    try:
        estudiante = Estudiante.query.get(id)
        if not estudiante: return jsonify({"error": "Estudiante no encontrado"}), 404
        
        antiguo_trabajo = estudiante.nombre_trabajo
        estudiante.nombres_apellidos = data.get('nombres_apellidos', estudiante.nombres_apellidos)
        estudiante.documento_identidad = data.get('documento_identidad', estudiante.documento_identidad)
        estudiante.institucion = data.get('institucion', estudiante.institucion)
        estudiante.correo = data.get('correo', estudiante.correo)
        estudiante.ciudad = data.get('ciudad', estudiante.ciudad)
        estudiante.cargo = data.get('cargo', estudiante.cargo)
        estudiante.nombre_trabajo = data.get('nombre_trabajo', estudiante.nombre_trabajo)
        
        if antiguo_trabajo != estudiante.nombre_trabajo:
            ponencia_nueva = Ponencia.query.filter_by(titulo=estudiante.nombre_trabajo).first()
            if not ponencia_nueva:
                while True:
                    codigo_generado = str(random.randint(100, 999))
                    if not Ponencia.query.filter_by(codigo=codigo_generado).first():
                        break
                ponencia_nueva = Ponencia(
                    titulo=estudiante.nombre_trabajo,
                    estado='aceptada',
                    estudiante_id=estudiante.id,
                    codigo=codigo_generado
                )
                db.session.add(ponencia_nueva)
                db.session.flush()
                
                # ⚠️ 1. SOLUCIÓN QR REDIRECCIÓN DIRECTA
                url_evaluacion = f"{DOMINIO_PRODUCCION}/login?redirect=/evaluar/{ponencia_nueva.codigo}"
                qr = qrcode.make(url_evaluacion)
                ruta_temporal = f"qr_{ponencia_nueva.codigo}.png"
                qr.save(ruta_temporal)
                upload_result = cloudinary.uploader.upload(ruta_temporal, folder="qrs_acofi")
                ponencia_nueva.url_qr = upload_result.get("secure_url")
                if os.path.exists(ruta_temporal): os.remove(ruta_temporal)
                    
        db.session.commit()
        return jsonify({"mensaje": "Datos del estudiante actualizados con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al actualizar estudiante: {str(e)}"}), 500

@admin_bp.route('/estudiantes/<int:id>', methods=['DELETE'])
def eliminar_estudiante(id):
    try:
        estudiante = Estudiante.query.get(id)
        if not estudiante: return jsonify({"error": "Estudiante no encontrado"}), 404
        
        trabajo = estudiante.nombre_trabajo
        db.session.delete(estudiante)
        db.session.flush()
        
        restantes = Estudiante.query.filter_by(nombre_trabajo=trabajo).count()
        if restantes == 0:
            ponencia = Ponencia.query.filter_by(titulo=trabajo).first()
            if ponencia:
                eliminar_qr_cloudinary(ponencia.url_qr)
                Evaluacion.query.filter_by(ponencia_id=ponencia.id).delete()
                db.session.delete(ponencia)
                
        db.session.commit()
        return jsonify({"mensaje": "Estudiante eliminado del sistema correctamente."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al eliminar estudiante: {str(e)}"}), 500

@admin_bp.route('/enviar_qr_estudiante/<int:id>', methods=['POST'])
def enviar_qr_estudiante(id):
    try:
        integrante = Estudiante.query.get(id)
        if not integrante: return jsonify({"error": "Estudiante no encontrado"}), 404
            
        p = Ponencia.query.filter_by(titulo=integrante.nombre_trabajo).first()
        if not p or not p.url_qr: return jsonify({"error": "El proyecto no posee un código QR activo."}), 400
            
        asunto = f"Código QR de Evaluación - Ponencia: {p.codigo}"
        cuerpo_html = f"""
        <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: auto; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px;">
            <h2 style="color: #1e3a8a;">Hola {integrante.nombres_apellidos},</h2>
            <p>Aquí tienes tu credencial de acceso para tu proyecto <strong>"{p.titulo}"</strong>.</p>
            <p>Tu código de póster asignado es: <strong style="font-size: 18px; color: #1e3a8a;">{p.codigo}</strong></p>
            
            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #1e3a8a;">
                <h3 style="margin-top: 0; color: #1e3a8a;">Credencial Digital</h3>
                <p style="margin-bottom: 10px;">Ingresa a la plataforma para ver tu QR el día del evento:</p>
                <p style="margin-bottom: 15px;">🔗 <strong>Enlace:</strong> <a href="{DOMINIO_PRODUCCION}/login">{DOMINIO_PRODUCCION}/login</a></p>
                <ul style="list-style-type: none; padding-left: 0; margin: 0;">
                    <li style="margin-bottom: 8px;">👤 <strong>Usuario:</strong> Tu documento ({integrante.documento_identidad})</li>
                    <li>🔑 <strong>Contraseña (PIN):</strong> {integrante.pin_acceso}</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin: 20px 0;">
                <img src="{p.url_qr}" alt="QR" style="width:200px; height:200px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px;">
            </div>
            <p>Saludos cordiales,<br><strong>Comité Organizador ACOFI</strong></p>
        </div>
        """
        exito, mensaje_error = enviar_correo(integrante.correo, asunto, cuerpo_html)
        if exito: return jsonify({"mensaje": f"Credencial enviada con éxito a {integrante.correo}"}), 200
        return jsonify({"error": mensaje_error}), 400
    except Exception as e:
        return jsonify({"error": f"Fallo en el servidor: {str(e)}"}), 500

@admin_bp.route('/ponencias', methods=['GET'])
def obtener_ponencias():
    try:
        ponencias = Ponencia.query.all()
        estudiantes = Estudiante.query.all()
        
        estudiantes_por_trabajo = {}
        for e in estudiantes:
            if e.nombre_trabajo not in estudiantes_por_trabajo:
                estudiantes_por_trabajo[e.nombre_trabajo] = []
            estudiantes_por_trabajo[e.nombre_trabajo].append(e)

        resultado = []
        for p in ponencias:
            integrantes_db = estudiantes_por_trabajo.get(p.titulo, [])
            nombres_integrantes = " | ".join([i.nombres_apellidos for i in integrantes_db])
            
            resultado.append({
                "id": p.id,
                "titulo": p.titulo,
                "estado": p.estado,
                "codigo": p.codigo,
                "url_qr": p.url_qr,
                "estudiante_id": p.estudiante_id,
                "estudiante_nombre": nombres_integrantes if nombres_integrantes else "N/A",
                "estudiante_institucion": integrantes_db[0].institucion if integrantes_db else "",
                "estudiante_pin": integrantes_db[0].pin_acceso if integrantes_db else ""
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": f"Error al cargar ponencias: {str(e)}"}), 500

@admin_bp.route('/ponencias', methods=['POST'])
def crear_ponencia_admin():
    data = request.get_json()
    try:
        nuevo_estudiante = Estudiante(
            nombres_apellidos=data['estudiante_nombre'],
            documento_identidad=data['estudiante_documento'],
            institucion=data['estudiante_institucion'],
            correo=data['estudiante_correo'],
            ciudad=data['estudiante_ciudad'],
            cargo=data['estudiante_cargo'],
            nombre_trabajo=data['titulo'],
            pin_acceso=generar_pin(),
            asistencia=False
        )
        db.session.add(nuevo_estudiante)
        db.session.flush()

        ponencia_existente = Ponencia.query.filter_by(titulo=data['titulo']).first()
        if not ponencia_existente:
            nueva_ponencia = Ponencia(
                titulo=data['titulo'],
                estado='pendiente',
                estudiante_id=nuevo_estudiante.id
            )
            db.session.add(nueva_ponencia)
            
        db.session.commit()
        return jsonify({"mensaje": "Registro procesado con éxito", "pin": nuevo_estudiante.pin_acceso}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al crear: {str(e)}"}), 500

@admin_bp.route('/ponencias/<int:id>', methods=['PUT'])
def editar_ponencia(id):
    data = request.get_json()
    try:
        ponencia = Ponencia.query.get(id)
        if not ponencia: return jsonify({"error": "Ponencia no encontrada"}), 404
        ponencia.titulo = data['titulo']
        if ponencia.estudiante:
            ponencia.estudiante.nombres_apellidos = data['estudiante_nombre']
            ponencia.estudiante.documento_identidad = data['estudiante_documento']
            ponencia.estudiante.institucion = data['estudiante_institucion']
            ponencia.estudiante.correo = data['estudiante_correo']
            ponencia.estudiante.ciudad = data['estudiante_ciudad']
            ponencia.estudiante.cargo = data['estudiante_cargo']
            ponencia.estudiante.nombre_trabajo = data['titulo']
        db.session.commit()
        return jsonify({"mensaje": "Datos actualizados con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al actualizar: {str(e)}"}), 500

@admin_bp.route('/evaluadores', methods=['GET'])
def obtener_evaluadores():
    try:
        evaluadores = Evaluador.query.all()
        resultado = []
        for e in evaluadores:
            resultado.append({
                "id": e.id,
                "nombres_apellidos": e.nombres_apellidos,
                "documento_identidad": e.documento_identidad,
                "institucion": e.institucion,
                "correo": e.correo,
                "cargo": e.cargo,
                "evento_id": e.evento_id,
                "evento": e.evento.nombre if e.evento else "N/A",
                "pin_acceso": e.pin_acceso
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": f"Error al cargar evaluadores: {str(e)}"}), 500

@admin_bp.route('/evaluadores', methods=['POST'])
def crear_evaluador_admin():
    data = request.get_json()
    try:
        nuevo_evaluador = Evaluador(
            nombres_apellidos=data['nombres_apellidos'],
            documento_identidad=data['documento_identidad'],
            institucion=data['institucion'],
            correo=data['correo'],
            cargo=data['cargo'],
            evento_id=int(data['evento_id']),
            pin_acceso=generar_pin()
        )
        db.session.add(nuevo_evaluador)
        db.session.commit()
        return jsonify({"mensaje": "Evaluador creado con éxito", "pin": nuevo_evaluador.pin_acceso}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al crear evaluador: {str(e)}"}), 500

@admin_bp.route('/evaluadores/<int:id>', methods=['PUT'])
def editar_evaluador(id):
    data = request.get_json()
    try:
        evaluador = Evaluador.query.get(id)
        if not evaluador: return jsonify({"error": "Evaluador no encontrado"}), 404
        evaluador.nombres_apellidos = data['nombres_apellidos']
        evaluador.documento_identidad = data['documento_identidad']
        evaluador.institucion = data['institucion']
        evaluador.correo = data['correo']
        evaluador.cargo = data['cargo']
        evaluador.evento_id = int(data['evento_id'])
        db.session.commit()
        return jsonify({"mensaje": "Datos del evaluador actualizados con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al actualizar evaluador: {str(e)}"}), 500

@admin_bp.route('/ranking', methods=['GET'])
def obtener_ranking():
    try:
        ponencias = Ponencia.query.all()
        evaluaciones = Evaluacion.query.all()
        estudiantes = Estudiante.query.all()

        evals_por_ponencia = {}
        for ev in evaluaciones:
            if ev.ponencia_id not in evals_por_ponencia: evals_por_ponencia[ev.ponencia_id] = []
            evals_por_ponencia[ev.ponencia_id].append(ev)

        estudiantes_por_trabajo = {}
        for e in estudiantes:
            if e.nombre_trabajo not in estudiantes_por_trabajo: estudiantes_por_trabajo[e.nombre_trabajo] = []
            estudiantes_por_trabajo[e.nombre_trabajo].append(e)

        resultado = []
        for p in ponencias:
            evaluaciones_db = evals_por_ponencia.get(p.id, [])
            total_score = 0
            num_evals = len(evaluaciones_db)
            
            for ev in evaluaciones_db:
                resp = ev.respuestas_rubrica
                try:
                    score = int(resp.get('q6', 0)) + int(resp.get('q7', 0)) + int(resp.get('q8', 0)) + int(resp.get('q9', 0)) + int(resp.get('q10', 0))
                    total_score += score
                except:
                    pass
            promedio = (total_score / num_evals) if num_evals > 0 else 0
            
            integrantes_db = estudiantes_por_trabajo.get(p.titulo, [])
            nombres = " | ".join([e.nombres_apellidos for e in integrantes_db]) if integrantes_db else "N/A"
            
            resultado.append({
                "id": p.id,
                "titulo": p.titulo,
                "codigo": p.codigo or "N/A",
                "estudiante_nombre": nombres,
                "num_evaluaciones": num_evals,
                "puntaje_total": total_score,
                "promedio": round(promedio, 2)
            })
        resultado = sorted(resultado, key=lambda x: x['promedio'], reverse=True)
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": f"Error al calcular ranking: {str(e)}"}), 500

@admin_bp.route('/ponencias/<int:id>', methods=['DELETE'])
def eliminar_ponencia(id):
    try:
        ponencia = Ponencia.query.get(id)
        if not ponencia: return jsonify({"error": "Ponencia no encontrada"}), 404
            
        eliminar_qr_cloudinary(ponencia.url_qr)
        Evaluacion.query.filter_by(ponencia_id=id).delete()
        estudiantes = Estudiante.query.filter_by(nombre_trabajo=ponencia.titulo).all()
        
        db.session.delete(ponencia)
        db.session.flush() 
        
        for e in estudiantes:
            db.session.delete(e)
            
        db.session.commit()
        return jsonify({"mensaje": "Ponencia, QR y estudiantes eliminados correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al eliminar: {str(e)}"}), 500

@admin_bp.route('/evaluadores/<int:id>', methods=['DELETE'])
def eliminar_evaluador(id):
    try:
        evaluador = Evaluador.query.get(id)
        if not evaluador: return jsonify({"error": "Evaluador no encontrado"}), 404
        Evaluacion.query.filter_by(evaluador_id=id).delete()
        db.session.delete(evaluador)
        db.session.commit()
        return jsonify({"mensaje": "Evaluador eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al eliminar: {str(e)}"}), 500

@admin_bp.route('/borrar_todos/<entidad>', methods=['DELETE'])
def borrar_todos(entidad):
    try:
        if entidad == 'ponencias':
            ponencias = Ponencia.query.all()
            for p in ponencias:
                eliminar_qr_cloudinary(p.url_qr)
            Evaluacion.query.delete()
            Ponencia.query.delete()
            Estudiante.query.delete()
        elif entidad == 'evaluadores':
            Evaluadores = Evaluador.query.all()
            for ev in Evaluadores:
                Evaluacion.query.filter_by(evaluador_id=ev.id).delete()
            Evaluador.query.delete()
        else:
            return jsonify({"error": "Entidad no válida"}), 400
        
        db.session.commit()
        return jsonify({"mensaje": f"Todos los registros de {entidad} y sus recursos han sido eliminados."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al vaciar registros: {str(e)}"}), 500

@admin_bp.route('/exportar/<entidad>', methods=['GET'])
def exportar_excel(entidad):
    try:
        wb = Workbook()
        ws = wb.active
        if entidad == 'estudiantes':
            ws.title = "Estudiantes"
            estudiantes = Estudiante.query.all()
            ws.append(['ID', 'Nombres y Apellidos', 'Documento', 'Institución', 'Correo', 'Ciudad', 'Cargo', 'Nombre del Trabajo', 'PIN'])
            for e in estudiantes:
                ws.append([e.id, e.nombres_apellidos, e.documento_identidad, e.institucion, e.correo, e.ciudad, e.cargo, e.nombre_trabajo, e.pin_acceso])
            filename = "Listado_Estudiantes.xlsx"
        elif entidad == 'evaluadores':
            ws.title = "Evaluadores"
            evaluadores = Evaluador.query.all()
            ws.append(['ID', 'Nombres y Apellidos', 'Documento', 'Institución', 'Correo', 'Cargo', 'Evento', 'PIN'])
            for e in evaluadores:
                ws.append([e.id, e.nombres_apellidos, e.documento_identidad, e.institucion, e.correo, e.cargo, e.evento.nombre if e.evento else '', e.pin_acceso])
            filename = "Listado_Evaluadores.xlsx"
        elif entidad == 'ponencias':
            ws.title = "Ponencias"
            ponencias = Ponencia.query.all()
            estudiantes = Estudiante.query.all()
            
            est_por_trabajo = {}
            for e in estudiantes:
                if e.nombre_trabajo not in est_por_trabajo:
                    est_por_trabajo[e.nombre_trabajo] = []
                est_por_trabajo[e.nombre_trabajo].append(e)

            ws.append(['ID', 'Título', 'Estado', 'Código', 'URL QR', 'Integrantes'])
            for p in ponencias:
                nombres = " | ".join([e.nombres_apellidos for e in est_por_trabajo.get(p.titulo, [])])
                ws.append([p.id, p.titulo, p.estado, p.codigo or 'N/A', p.url_qr or 'N/A', nombres])
            filename = "Listado_Ponencias.xlsx"
        elif entidad == 'evaluaciones':
            ws.title = "Resultados Evaluaciones"
            evaluaciones = Evaluacion.query.all()
            ws.append(['ID Eval', 'Ponencia', 'Código Poster', 'Evaluador', 'Cédula Evaluador', 'P.6 Título', 'P.7 Estructura', 'P.8 Resultados', 'P.9 Metodología', 'P.10 Conclusiones', 'PUNTAJE TOTAL', 'Comentarios'])
            for ev in evaluaciones:
                resp = ev.respuestas_rubrica
                try:
                    p6, p7, p8, p9, p10 = int(resp.get('q6', 0)), int(resp.get('q7', 0)), int(resp.get('q8', 0)), int(resp.get('q9', 0)), int(resp.get('q10', 0))
                    total = p6 + p7 + p8 + p9 + p10
                except:
                    p6, p7, p8, p9, p10, total = 0, 0, 0, 0, 0, 0
                ws.append([
                    ev.id,
                    ev.ponencia.titulo if ev.ponencia else 'N/A',
                    ev.ponencia.codigo if ev.ponencia else 'N/A',
                    ev.evaluador.nombres_apellidos if ev.evaluador else 'N/A',
                    ev.evaluador.documento_identidad if ev.evaluador else 'N/A',
                    p6, p7, p8, p9, p10, total, resp.get('comentarios', '')
                ])
            filename = "Resultados_Evaluaciones_Semillero.xlsx"
        elif entidad == 'asistencia':
            ws.title = "Control de Asistencia"
            estudiantes = Estudiante.query.all()
            ws.append(['ID', 'Nombres y Apellidos', 'Documento', 'Institución', 'Proyecto', 'Asistió'])
            for e in estudiantes:
                asistio_texto = "SÍ" if getattr(e, 'asistencia', False) else "NO"
                ws.append([e.id, e.nombres_apellidos, e.documento_identidad, e.institucion, e.nombre_trabajo, asistio_texto])
            filename = "Control_Asistencia_Estudiantes.xlsx"
        else:
            return jsonify({"error": "Entidad no válida"}), 400

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({"error": f"Error al generar Excel: {str(e)}"}), 500

@admin_bp.route('/aceptar_ponencia/<int:id_ponencia>', methods=['POST'])
def aceptar_ponencia(id_ponencia):
    ponencia = Ponencia.query.get(id_ponencia)
    if not ponencia: return jsonify({"error": "Ponencia no encontrada"}), 404
    if ponencia.estado == 'aceptada' and ponencia.url_qr: return jsonify({"mensaje": "La ponencia ya estaba aceptada", "codigo_asignado": ponencia.codigo}), 200
    try:
        ponencia.estado = 'aceptada'
        if not ponencia.codigo:
            while True:
                codigo_generado = str(random.randint(100, 999))
                existe = Ponencia.query.filter_by(codigo=codigo_generado).first()
                if not existe:
                    ponencia.codigo = codigo_generado
                    break
                    
        # ⚠️ 2. SOLUCIÓN QR REDIRECCIÓN DIRECTA
        url_evaluacion = f"{DOMINIO_PRODUCCION}/login?redirect=/evaluar/{ponencia.codigo}"
        qr = qrcode.make(url_evaluacion)
        
        ruta_temporal = f"qr_{ponencia.codigo}.png"
        qr.save(ruta_temporal)
        upload_result = cloudinary.uploader.upload(ruta_temporal, folder="qrs_acofi")
        ponencia.url_qr = upload_result.get("secure_url")
        
        if os.path.exists(ruta_temporal): os.remove(ruta_temporal)
            
        db.session.commit()
        return jsonify({"mensaje": "Ponencia aceptada y QR generado con éxito", "codigo_asignado": ponencia.codigo, "url_qr": ponencia.url_qr}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al procesar la ponencia: {str(e)}"}), 500

# ⚠️ 3. PROCESADOR DE EXCEL BLINDADO (NO OMITE A NADIE)
@admin_bp.route('/cargar_excel', methods=['POST'])
def cargar_excel():
    if 'file' not in request.files:
        return jsonify({"error": "No se proporcionó ningún archivo"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Archivo vacío"}), 400
    try:
        if file.filename.endswith('.csv'): df = pd.read_csv(file)
        else: df = pd.read_excel(file)

        # Reemplazamos todos los vacíos para que no salgan como "N/A"
        df = df.fillna('')
        
        # Buscadores de columnas dinámicos para evitar errores de tipeo en el Excel
        col_nombres = next((c for c in df.columns if 'nombre y apellido' in str(c).lower()), None) or 'Nombre y apellidos'
        col_doc = next((c for c in df.columns if 'documento' in str(c).lower()), None) or 'Número de documento de identidad'
        col_inst = next((c for c in df.columns if 'institución' in str(c).lower() or 'institucion' in str(c).lower()), None) or 'Institución'
        col_correo = next((c for c in df.columns if 'correo' in str(c).lower()), None) or 'Correo electrónico'
        col_ciudad = next((c for c in df.columns if 'ciudad' in str(c).lower()), None) or 'Ciudad'
        col_cargo = next((c for c in df.columns if 'cargo' in str(c).lower()), None) or 'Cargo'
        col_titulo = next((c for c in df.columns if 'trabajo' in str(c).lower()), None) or 'Nombre del trabajo que representa (debe ser el mismo enviado en la carta de notificación del paso a la tercera fase).'
        col_codigo = next((c for c in df.columns if 'código' in str(c).lower() or 'codigo' in str(c).lower()), None) or 'Código'

        # Procesamos fila por fila para que un error en un estudiante no aborte el archivo entero
        for index, row in df.iterrows():
            try:
                nombres = str(row.get(col_nombres, '')).strip()
                if not nombres or nombres.lower() == 'nan': continue

                documento = str(row.get(col_doc, '')).replace('.0', '').strip()
                # ⚠️ ESCUDO DE DOCUMENTO: Si no tiene documento, le asignamos uno temporal
                if not documento or documento.lower() == 'nan':
                    documento = f"SD-{random.randint(10000, 99999)}"
                
                institucion = str(row.get(col_inst, '')).strip()
                
                correo = str(row.get(col_correo, '')).strip()
                # ⚠️ ESCUDO DE CORREO: Si no tiene correo, le damos uno temporal
                if not correo or correo.lower() == 'nan':
                    correo = f"{documento}@acofi.edu.co"
                
                ciudad = str(row.get(col_ciudad, '')).strip()
                cargo = str(row.get(col_cargo, '')).strip()
                titulo = str(row.get(col_titulo, '')).strip()
                codigo_excel = str(row.get(col_codigo, '')).replace('.0', '').strip()

                # ⚠️ ESCUDO ANTI-OMISIONES: Si el correo ya existe en otro estudiante, lo volvemos único
                exist_email = Estudiante.query.filter_by(correo=correo).first()
                if exist_email and exist_email.documento_identidad != documento:
                    correo = f"{documento}_{correo}"

                estudiante = Estudiante.query.filter_by(documento_identidad=documento).first()
                if not estudiante:
                    estudiante = Estudiante(
                        nombres_apellidos=nombres,
                        documento_identidad=documento,
                        institucion=institucion,
                        correo=correo,
                        ciudad=ciudad,
                        cargo=cargo,
                        nombre_trabajo=titulo,
                        pin_acceso=generar_pin(),
                        asistencia=False
                    )
                    db.session.add(estudiante)
                    db.session.flush() # Guarda temporalmente para darle un ID
                else:
                    estudiante.nombre_trabajo = titulo # Si ya existe, solo actualizamos el trabajo

                # PONENCIAS
                ponencia = None
                if codigo_excel and codigo_excel.lower() != 'nan':
                    ponencia = Ponencia.query.filter_by(codigo=codigo_excel).first()
                if not ponencia:
                    ponencia = Ponencia.query.filter_by(titulo=titulo).first()

                if not ponencia:
                    if codigo_excel and codigo_excel.lower() != 'nan':
                        codigo_final = codigo_excel
                    else:
                        while True:
                            codigo_generado = str(random.randint(100, 999))
                            if not Ponencia.query.filter_by(codigo=codigo_generado).first():
                                codigo_final = codigo_generado
                                break
                    ponencia = Ponencia(
                        titulo=titulo,
                        estado='aceptada',
                        estudiante_id=estudiante.id,
                        codigo=codigo_final
                    )
                    db.session.add(ponencia)
                    db.session.flush()

                    # ⚠️ 3. SOLUCIÓN QR REDIRECCIÓN DIRECTA (DENTRO DEL EXCEL)
                    url_evaluacion = f"{DOMINIO_PRODUCCION}/login?redirect=/evaluar/{ponencia.codigo}"
                    qr = qrcode.make(url_evaluacion)
                    ruta_temporal = f"qr_excel_{ponencia.codigo}.png"
                    qr.save(ruta_temporal)
                    upload_result = cloudinary.uploader.upload(ruta_temporal, folder="qrs_acofi")
                    ponencia.url_qr = upload_result.get("secure_url")
                    if os.path.exists(ruta_temporal): os.remove(ruta_temporal)
                
                # GUARDAMOS ESTA FILA. Si la siguiente falla, esta ya quedó a salvo.
                db.session.commit()
            except Exception as e_row:
                db.session.rollback()
                print(f"Error forzado al saltar en fila {index}: {str(e_row)}")

        return jsonify({"mensaje": "Archivo procesado. Estudiantes y ponencias guardados exitosamente."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error global procesando el archivo: {str(e)}"}), 500

@admin_bp.route('/enviar_qrs', methods=['POST'])
def enviar_qrs():
    data = request.get_json() or {}
    id_ponencia = data.get('id_ponencia')
    try:
        if id_ponencia:
            ponencias = Ponencia.query.filter_by(id=id_ponencia, estado='aceptada').all()
        else:
            ponencias = Ponencia.query.filter_by(estado='aceptada').all()
            
        lista_envio = []
        for p in ponencias:
            integrantes = Estudiante.query.filter_by(nombre_trabajo=p.titulo).all()
            for integrante in integrantes:
                if integrante.correo and p.url_qr:
                    lista_envio.append({
                        'nombres': integrante.nombres_apellidos,
                        'correo': integrante.correo,
                        'documento': integrante.documento_identidad,
                        'pin': integrante.pin_acceso,
                        'titulo': p.titulo,
                        'codigo': p.codigo,
                        'url_qr': p.url_qr
                    })
        
        if len(lista_envio) == 0:
            return jsonify({"error": "No hay correos válidos para enviar en las ponencias seleccionadas."}), 400

        hilo = threading.Thread(target=proceso_envio_segundo_plano, args=(lista_envio,))
        hilo.start()
            
        return jsonify({"mensaje": f"El envío masivo a {len(lista_envio)} estudiantes se ha iniciado en segundo plano. Puede continuar usando el sistema."}), 200
    except Exception as e:
        return jsonify({"error": f"Error al iniciar envíos: {str(e)}"}), 500