from flask import Blueprint, session, redirect, render_template, request
from App.database import db
from App.models import User, Appointment, ClinicService, DocumentoPaciente
from App.utils.security import sanitize_cpf

auth = Blueprint("auth", __name__)


def _render_perfil(user, aviso, redirect_to, erro, appointments=None, documentos=None):
    return render_template(
        "perfil.html",
        user={"email": user.email, "name": user.name,
              "cpf": user.cpf or "", "telefone": user.telefone or ""},
        aviso=aviso,
        redirect_to=redirect_to,
        erro=erro,
        appointments=appointments or [],
        documentos=documentos or [],
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
    return _render_perfil(db_user, aviso, redirect_to, None, appointments, documentos)
