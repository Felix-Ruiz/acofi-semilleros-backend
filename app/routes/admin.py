from flask import Blueprint, request, jsonify, send_file
from app.models import db, Ponencia, Estudiante, Evaluador, Evaluacion
import qrcode
import os
import random
import io
from openpyxl import Workbook

admin_bp = Blueprint('admin', __name__)

# --- LEER PONENCIAS ---
@admin_bp.route('/ponencias', methods=['GET'])
def obtener_ponencias():
    try:
        ponencias = Ponencia.query.join(Estudiante).all()
        resultado = []
        for p in ponencias:
            resultado.append({
                "id": p.id,
                "titulo": p.titulo,
                "estado": p.estado,
                "codigo": p.codigo,
                "url_qr": p.url_qr,
                "estudiante_id": p.estudiante.id if p.estudiante else None,
                "estudiante_nombre": p.estudiante.nombres_apellidos if p.estudiante else "N/A",
                "estudiante_documento": p.estudiante.documento_identidad if p.estudiante else "",
                "estudiante_institucion": p.estudiante.institucion if p.estudiante else "",
                "estudiante_correo": p.estudiante.correo if p.estudiante else "",
                "estudiante_ciudad": p.estudiante.ciudad if p.estudiante else "",
                "estudiante_cargo": p.estudiante.cargo if p.estudiante else ""
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": f"Error al cargar ponencias: {str(e)}"}), 500

# --- CREAR PONENCIA + ESTUDIANTE DESDE EL ADMIN ---
@admin_bp.route('/ponencias', methods=['POST'])
def crear_ponencia_admin():
    data = request.get_json()
    try:
        # Primero creamos al estudiante asociado
        nuevo_estudiante = Estudiante(
            nombres_apellidos=data['estudiante_nombre'],
            documento_identidad=data['estudiante_documento'],
            institucion=data['estudiante_institucion'],
            correo=data['estudiante_correo'],
            ciudad=data['estudiante_ciudad'],
            cargo=data['estudiante_cargo'],
            nombre_trabajo=data['titulo'] # El trabajo representa el título
        )
        db.session.add(nuevo_estudiante)
        db.session.flush() # Para obtener el ID del estudiante inmediatamente

        nueva_ponencia = Ponencia(
            titulo=data['titulo'],
            estado='pendiente',
            estudiante_id=nuevo_estudiante.id
        )
        db.session.add(nueva_ponencia)
        db.session.commit()
        return jsonify({"mensaje": "Ponencia y ponente creados con éxito desde administración"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al crear: {str(e)}"}), 500

# --- ACTUALIZAR/EDITAR PONENCIA + ESTUDIANTE ---
@admin_bp.route('/ponencias/<int:id>', methods=['PUT'])
def editar_ponencia(id):
    data = request.get_json()
    try:
        ponencia = Ponencia.query.get(id)
        if not ponencia:
            return jsonify({"error": "Ponencia no encontrada"}), 404

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
        return jsonify({"mensaje": "Ponencia y datos del ponente actualizados con éxito"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al actualizar: {str(e)}"}), 500

# --- LEER EVALUADORES ---
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
                "evento": e.evento.nombre if e.evento else "N/A"
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": f"Error al cargar evaluadores: {str(e)}"}), 500

# --- CREAR EVALUADOR DESDE EL ADMIN ---
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
            evento_id=int(data['evento_id'])
        )
        db.session.add(nuevo_evaluador)
        db.session.commit()
        return jsonify({"mensaje": "Evaluador creado con éxito"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al crear evaluador: {str(e)}"}), 500

# --- ACTUALIZAR/EDITAR EVALUADOR ---
@admin_bp.route('/evaluadores/<int:id>', methods=['PUT'])
def editar_evaluador(id):
    data = request.get_json()
    try:
        evaluador = Evaluador.query.get(id)
        if not evaluador:
            return jsonify({"error": "Evaluador no encontrado"}), 404

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

# --- RANKING Y RESULTADOS ---
@admin_bp.route('/ranking', methods=['GET'])
def obtener_ranking():
    try:
        ponencias = Ponencia.query.all()
        resultado = []
        for p in ponencias:
            evaluaciones = Evaluacion.query.filter_by(ponencia_id=p.id).all()
            total_score = 0
            num_evals = len(evaluaciones)

            for ev in evaluaciones:
                resp = ev.respuestas_rubrica
                try:
                    score = int(resp.get('q6', 0)) + int(resp.get('q7', 0)) + int(resp.get('q8', 0)) + int(resp.get('q9', 0)) + int(resp.get('q10', 0))
                    total_score += score
                except:
                    pass

            promedio = (total_score / num_evals) if num_evals > 0 else 0

            resultado.append({
                "id": p.id,
                "titulo": p.titulo,
                "codigo": p.codigo or "N/A",
                "estudiante_nombre": p.estudiante.nombres_apellidos if p.estudiante else "N/A",
                "num_evaluaciones": num_evals,
                "puntaje_total": total_score,
                "promedio": round(promedio, 2)
            })

        resultado = sorted(resultado, key=lambda x: x['promedio'], reverse=True)
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": f"Error al calcular ranking: {str(e)}"}), 500

# --- ELIMINAR PONENCIAS Y EVALUADORES ---
@admin_bp.route('/ponencias/<int:id>', methods=['DELETE'])
def eliminar_ponencia(id):
    try:
        ponencia = Ponencia.query.get(id)
        if not ponencia:
            return jsonify({"error": "Ponencia no encontrada"}), 404

        Evaluacion.query.filter_by(ponencia_id=id).delete()
        if ponencia.estudiante:
            db.session.delete(ponencia.estudiante)
            
        db.session.delete(ponencia)
        db.session.commit()
        return jsonify({"mensaje": "Ponencia y estudiante eliminados correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al eliminar: {str(e)}"}), 500

@admin_bp.route('/evaluadores/<int:id>', methods=['DELETE'])
def eliminar_evaluador(id):
    try:
        evaluador = Evaluador.query.get(id)
        if not evaluador:
            return jsonify({"error": "Evaluador no encontrado"}), 404

        Evaluacion.query.filter_by(evaluador_id=id).delete()
        db.session.delete(evaluador)
        db.session.commit()
        return jsonify({"mensaje": "Evaluador eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al eliminar: {str(e)}"}), 500

# --- EXPORTAR A EXCEL ---
@admin_bp.route('/exportar/<entidad>', methods=['GET'])
def exportar_excel(entidad):
    try:
        wb = Workbook()
        ws = wb.active
        
        if entidad == 'estudiantes':
            ws.title = "Estudiantes"
            estudiantes = Estudiante.query.all()
            ws.append(['ID', 'Nombres y Apellidos', 'Documento', 'Institución', 'Correo', 'Ciudad', 'Cargo', 'Nombre del Trabajo'])
            for e in estudiantes:
                ws.append([e.id, e.nombres_apellidos, e.documento_identidad, e.institucion, e.correo, e.ciudad, e.cargo, e.nombre_trabajo])
            filename = "Listado_Estudiantes.xlsx"
            
        elif entidad == 'evaluadores':
            ws.title = "Evaluadores"
            evaluadores = Evaluador.query.all()
            ws.append(['ID', 'Nombres y Apellidos', 'Documento', 'Institución', 'Correo', 'Cargo', 'Evento'])
            for e in evaluadores:
                ws.append([e.id, e.nombres_apellidos, e.documento_identidad, e.institucion, e.correo, e.cargo, e.evento.nombre if e.evento else ''])
            filename = "Listado_Evaluadores.xlsx"
            
        elif entidad == 'ponencias':
            ws.title = "Ponencias"
            ponencias = Ponencia.query.all()
            ws.append(['ID', 'Título', 'Estudiante', 'Estado', 'Código', 'URL QR'])
            for p in ponencias:
                ws.append([p.id, p.titulo, p.estudiante.nombres_apellidos if p.estudiante else '', p.estado, p.codigo or 'N/A', p.url_qr or 'N/A'])
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
        else:
            return jsonify({"error": "Entidad no válida"}), 400

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({"error": f"Error al generar Excel: {str(e)}"}), 500

# --- ACEPTAR PONENCIA Y GENERAR QR ---
@admin_bp.route('/aceptar_ponencia/<int:id_ponencia>', methods=['POST'])
def aceptar_ponencia(id_ponencia):
    ponencia = Ponencia.query.get(id_ponencia)
    if not ponencia:
        return jsonify({"error": "Ponencia no encontrada"}), 404
    if ponencia.estado == 'aceptada':
        return jsonify({"mensaje": "La ponencia ya estaba aceptada"}), 400

    try:
        ponencia.estado = 'aceptada'
        while True:
            codigo_generado = str(random.randint(100, 999))
            existe = Ponencia.query.filter_by(codigo=codigo_generado).first()
            if not existe:
                ponencia.codigo = codigo_generado
                break
        
        url_evaluacion = f"https://subdominio.acofiapps.com/evaluar/{ponencia.codigo}"
        qr = qrcode.make(url_evaluacion)
        ruta_qrs = os.path.join(os.getcwd(), 'static', 'qrs')
        os.makedirs(ruta_qrs, exist_ok=True)
        nombre_archivo_qr = f"qr_ponencia_{ponencia.codigo}.png"
        ruta_completa_qr = os.path.join(ruta_qrs, nombre_archivo_qr)
        qr.save(ruta_completa_qr)
        
        ponencia.url_qr = f"/static/qrs/{nombre_archivo_qr}"
        db.session.commit()
        return jsonify({"mensaje": "Ponencia aceptada con éxito", "codigo_asignado": ponencia.codigo, "url_qr": ponencia.url_qr}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al procesar la ponencia: {str(e)}"}), 500