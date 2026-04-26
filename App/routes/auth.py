from flask import Blueprint, session, redirect, render_template, request, jsonify
from App.database import db
from App.models import User, Appointment, ClinicService, DocumentoPaciente, PostAtendimento, Review
from App.utils.security import sanitize_cpf

auth = Blueprint("auth", __name__)


def _render_perfil(user, aviso, redirect_to, erro, appointments=None, documentos=None,
                   historico_saude=None, unread_cuidados=0):
    return render_template(
        "perfil.html",
        user={"email": user.email, "name": user.name,
              "cpf": user.cpf or "", "telefone": user.telefone or ""},
        aviso=aviso,
        redirect_to=redirect_to,
        erro=erro,
        appointments=appointments or [],
        documentos=documentos or [],
        historico_saude=historico_saude or [],
        unread_cuidados=unread_cuidados,
        chat_messages=[],
        query="",
        selected_category="",
        is_logged_in=True,
    )


@auth.route("/perfil", methods=["GET", "POST"])
def perfil():
    if not session.get("user"):
        return redirect("/auth?redirect=/perfil")

    aviso      = request.args.get("aviso", "")
    redirect_to = request.args.get("redirect", "/")

    db_user = User.query.get(session["user"]["id"])
    if not db_user:
        session.pop("user", None)
        return redirect("/auth?redirect=/perfil")

    if request.method == "POST":
        name_raw = request.form.get("nome", "").strip()
        cpf_raw  = request.form.get("cpf",  "").strip()
        tel_raw  = request.form.get("telefone", "").strip()

        if not name_raw or len(name_raw) < 2:
            return _render_perfil(db_user, aviso, redirect_to,
                                  "Nome inválido. Informe ao menos 2 caracteres.")

        cpf = sanitize_cpf(cpf_raw)
        if not cpf:
            return _render_perfil(db_user, aviso, redirect_to,
                                  "CPF inválido. Informe 11 dígitos numéricos.")

        # Ensure CPF is not taken by another account
        conflict = User.query.filter(
            User.cpf == cpf, User.id != db_user.id
        ).first()
        if conflict:
            return _render_perfil(db_user, aviso, redirect_to,
                                  "Este CPF já está cadastrado em outra conta.")

        db_user.name     = name_raw
        db_user.cpf      = cpf
        if tel_raw:
            db_user.telefone = tel_raw
        db.session.commit()

        # Keep session in sync
        session["user"]["name"]      = name_raw
        session["user"]["user_type"] = db_user.user_type
        session.modified = True

        return redirect(redirect_to)

    appointments = (
        Appointment.query
        .filter_by(user_id=db_user.id)
        .order_by(Appointment.date.desc(), Appointment.time_slot.desc())
        .all()
    )
    documentos = (
        DocumentoPaciente.query
        .filter_by(paciente_id=db_user.id)
        .order_by(DocumentoPaciente.data_upload.desc())
        .all()
    )

    # Build Histórico de Saúde: finalized appointments with post-care records
    finalized_appts = (
        Appointment.query
        .filter_by(user_id=db_user.id, status=Appointment.STATUS_FINALIZED)
        .order_by(Appointment.date.desc(), Appointment.time_slot.desc())
        .all()
    )
    reviewed_appt_ids = {
        r.appointment_id for r in Review.query.filter_by(user_id=db_user.id).all()
        if r.appointment_id
    }
    historico_saude = []
    for appt in finalized_appts:
        post = PostAtendimento.query.filter_by(appointment_id=appt.id).first()
        historico_saude.append({
            "appt":     appt,
            "post":     post,
            "reviewed": appt.id in reviewed_appt_ids,
        })

    unread_cuidados = sum(
        1 for h in historico_saude
        if h["post"] and not h["post"].notificacao_lida
    )

    return _render_perfil(db_user, aviso, redirect_to, None, appointments, documentos,
                          historico_saude, unread_cuidados)


@auth.route("/avaliar/<int:appt_id>", methods=["POST"])
def avaliar_atendimento(appt_id):
    """Submit a star review for a finalized appointment."""
    if not session.get("user"):
        return jsonify({"ok": False, "msg": "Não autenticado."}), 401

    uid    = session["user"]["id"]
    appt   = Appointment.query.filter_by(id=appt_id, user_id=uid).first()
    if not appt:
        return jsonify({"ok": False, "msg": "Agendamento não encontrado."}), 404
    if appt.status != Appointment.STATUS_FINALIZED:
        return jsonify({"ok": False, "msg": "Só é possível avaliar após o atendimento ser finalizado."}), 400

    # Prevent duplicate reviews per appointment
    existing = Review.query.filter_by(appointment_id=appt_id, user_id=uid).first()
    if existing:
        return jsonify({"ok": False, "msg": "Você já avaliou este atendimento."}), 400

    data = request.get_json(force=True, silent=True) or {}
    try:
        rating = float(data.get("rating", 0))
    except (ValueError, TypeError):
        rating = 0.0
    if not (1 <= rating <= 5):
        return jsonify({"ok": False, "msg": "Nota inválida. Use de 1 a 5."}), 400

    comentario = (data.get("comentario") or "").strip() or None

    review = Review(
        service_id     = appt.service_id,
        user_id        = uid,
        appointment_id = appt_id,
        rating         = rating,
        comentario     = comentario,
    )
    db.session.add(review)

    # Mark notification as read when the patient submits a review
    post = PostAtendimento.query.filter_by(appointment_id=appt_id).first()
    if post:
        post.notificacao_lida = True

    db.session.commit()
    return jsonify({"ok": True, "msg": "Avaliação enviada com sucesso!"})


@auth.route("/cuidados/<int:appt_id>/marcar-lido", methods=["POST"])
def marcar_cuidado_lido(appt_id):
    """Mark a PostAtendimento notification as read for the current patient."""
    if not session.get("user"):
        return jsonify({"ok": False}), 401
    uid  = session["user"]["id"]
    appt = Appointment.query.filter_by(id=appt_id, user_id=uid).first()
    if not appt:
        return jsonify({"ok": False}), 404
    post = PostAtendimento.query.filter_by(appointment_id=appt_id).first()
    if post and not post.notificacao_lida:
        post.notificacao_lida = True
        db.session.commit()
    return jsonify({"ok": True})
