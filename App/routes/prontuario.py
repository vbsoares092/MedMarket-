"""
Documentos do Paciente
======================
Routes:
  GET  /prontuario/appointment/<id>/documentos-paciente  — Clinic views patient docs (read-only)
  GET  /prontuario/<prontuario_id>/ver                   — View a prontuário (patient or owning clinic)
  GET  /meu-historico                                    — Patient timeline
  POST /documentos/upload                                — Patient uploads a document
  POST /documentos/<doc_id>/remover                      — Patient removes their own document
"""
import os
import uuid

from flask import (
    Blueprint, session, redirect, render_template,
    request, jsonify, current_app, abort,
)
from werkzeug.utils import secure_filename

from App.database import db
from App.models import User, Appointment, Prontuario, DocumentoPaciente

prontuario_bp = Blueprint("prontuario", __name__)

ALLOWED_DOC_EXT = {"pdf", "png", "jpg", "jpeg"}


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _current_user() -> User | None:
    uid = (session.get("user") or {}).get("id")
    return User.query.get(uid) if uid else None


def _prontuarios_upload_dir() -> str:
    path = os.path.join(current_app.root_path, "static", "uploads", "prontuarios")
    os.makedirs(path, exist_ok=True)
    return path


def _documentos_upload_dir() -> str:
    path = os.path.join(current_app.root_path, "static", "uploads", "documentos")
    os.makedirs(path, exist_ok=True)
    return path


def _save_file(file_storage, upload_dir: str) -> str | None:
    """Validate extension, sanitize filename, save and return relative URL."""
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_DOC_EXT:
        return None
    safe = secure_filename(file_storage.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe}"
    file_storage.save(os.path.join(upload_dir, unique_name))
    # Return path relative to static/ so url_for('static', filename=...) works
    rel = os.path.relpath(
        os.path.join(upload_dir, unique_name),
        os.path.join(current_app.root_path, "static"),
    ).replace("\\", "/")
    return rel


def _clinic_owns_appointment(clinic_user: User, appointment: Appointment) -> bool:
    """True if the clinic user owns the service that was booked."""
    return appointment.clinic_id == clinic_user.id


def _patient_has_appointment_with_clinic(patient_id: int, clinic_id: int) -> bool:
    """True if there is at least one appointment between this patient and clinic."""
    return (
        Appointment.query
        .filter_by(clinic_id=clinic_id, user_id=patient_id)
        .first()
    ) is not None


# ──────────────────────────────────────────────
#  CLINIC: List patient documents for an appointment (read-only)
# ──────────────────────────────────────────────

@prontuario_bp.route("/prontuario/appointment/<int:appointment_id>/documentos-paciente")
def documentos_paciente_clinica(appointment_id: int):
    """Return the patient's uploaded documents to the owning clinic only."""
    user = _current_user()
    if not user or user.user_type != User.USER_TYPE_CLINIC:
        abort(403)

    appointment = Appointment.query.get_or_404(appointment_id)

    # Security: only the clinic that owns the service may access patient documents
    if not _clinic_owns_appointment(user, appointment):
        abort(403)

    if not appointment.user_id:
        return jsonify({"documentos": []})

    docs = (
        DocumentoPaciente.query
        .filter_by(paciente_id=appointment.user_id)
        .order_by(DocumentoPaciente.data_upload.desc())
        .all()
    )

    result = [
        {
            "id":          doc.id,
            "titulo":      doc.titulo,
            "arquivo_url": doc.arquivo_url,
            "data_upload": doc.data_upload.strftime("%d/%m/%Y %H:%M") if doc.data_upload else "",
        }
        for doc in docs
    ]
    return jsonify({"documentos": result})


# ──────────────────────────────────────────────
#  SHARED: View a prontuário
# ──────────────────────────────────────────────

@prontuario_bp.route("/prontuario/<int:prontuario_id>/ver")
def ver_prontuario(prontuario_id: int):
    user = _current_user()
    if not user:
        return redirect("/auth")

    pront = Prontuario.query.get_or_404(prontuario_id)

    # Access control: only the patient themselves or the clinic that created it
    allowed = (
        user.id == pront.paciente_id
        or user.id == pront.medico_id
    )
    if not allowed:
        abort(403)

    return render_template(
        "prontuario_detalhe.html",
        pront=pront,
        is_logged_in=True,
        query="",
        selected_category="",
    )


# ──────────────────────────────────────────────
#  PATIENT: Timeline (historical consultations)
# ──────────────────────────────────────────────

@prontuario_bp.route("/meu-historico")
def meu_historico():
    user = _current_user()
    if not user or user.user_type != User.USER_TYPE_CLIENT:
        return redirect("/auth")

    prontuarios = (
        Prontuario.query
        .filter_by(paciente_id=user.id)
        .order_by(Prontuario.data_consulta.desc())
        .all()
    )
    documentos = (
        DocumentoPaciente.query
        .filter_by(paciente_id=user.id)
        .order_by(DocumentoPaciente.data_upload.desc())
        .all()
    )

    return render_template(
        "timeline.html",
        user=user,
        prontuarios=prontuarios,
        documentos=documentos,
        is_logged_in=True,
        query="",
        selected_category="",
    )


# ──────────────────────────────────────────────
#  PATIENT: Upload a document
# ──────────────────────────────────────────────

@prontuario_bp.route("/documentos/upload", methods=["POST"])
def upload_documento():
    user = _current_user()
    if not user or user.user_type != User.USER_TYPE_CLIENT:
        abort(403)

    titulo = (request.form.get("titulo") or "").strip()
    if not titulo or len(titulo) > 200:
        return jsonify({"ok": False, "erro": "Título inválido (máx 200 caracteres)"}), 400

    f = request.files.get("arquivo")
    if not f or not f.filename:
        return jsonify({"ok": False, "erro": "Nenhum arquivo enviado"}), 400

    rel_url = _save_file(f, _documentos_upload_dir())
    if not rel_url:
        return jsonify({"ok": False, "erro": "Apenas PDF, PNG, JPG ou JPEG são permitidos"}), 400

    doc = DocumentoPaciente(
        paciente_id=user.id,
        titulo=titulo,
        arquivo_url=rel_url,
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify({"ok": True, "doc_id": doc.id})


# ──────────────────────────────────────────────
#  PATIENT: Remove a document
# ──────────────────────────────────────────────

@prontuario_bp.route("/documentos/<int:doc_id>/remover", methods=["POST"])
def remover_documento(doc_id: int):
    user = _current_user()
    if not user or user.user_type != User.USER_TYPE_CLIENT:
        abort(403)

    doc = DocumentoPaciente.query.filter_by(id=doc_id, paciente_id=user.id).first_or_404()

    # Remove the physical file
    full_path = os.path.join(current_app.root_path, "static", doc.arquivo_url)
    if os.path.isfile(full_path):
        os.remove(full_path)

    db.session.delete(doc)
    db.session.commit()
    return jsonify({"ok": True})
