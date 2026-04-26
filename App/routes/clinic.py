import os
from datetime import datetime, date, timedelta
from calendar import monthrange
from sqlalchemy.orm import joinedload
from flask import (
    Blueprint, session, redirect, render_template,
    request, jsonify, current_app,
)
from werkzeug.utils import secure_filename
from App.database import db
from App.models import User, ClinicProfile, ClinicService, ClinicSchedule, Appointment, Disponibilidade, Mensagem, ChatConversa, PostAtendimento
from App.utils.security import (
    hash_password, verify_password, sanitize_cnpj, login_required_clinic,
)

clinic_bp = Blueprint("clinic", __name__, url_prefix="/clinica")

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _upload_dir() -> str:
    path = os.path.join(current_app.instance_path, "uploads", "clinics")
    os.makedirs(path, exist_ok=True)
    return path


ALLOWED_IMG = {"png", "jpg", "jpeg", "gif", "webp"}


def _service_img_dir() -> str:
    """Absolute path to static/uploads/anuncios (public-facing)."""
    path = os.path.join(current_app.root_path, "static", "uploads", "anuncios")
    os.makedirs(path, exist_ok=True)
    return path


def _save_service_image(file_storage) -> str | None:
    """Validate, sanitize and save an uploaded service image.
    Returns the relative URL (for use in <img src>) or None on failure.
    """
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMG:
        return None
    filename = secure_filename(file_storage.filename)
    # Use a unique prefix so filenames never collide
    import uuid
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    file_storage.save(os.path.join(_service_img_dir(), unique_name))
    return f"uploads/anuncios/{unique_name}"


def _session_clinic() -> User | None:
    """Return the logged-in User if they are a CLINICA, otherwise None."""
    uid = (session.get("user") or {}).get("id")
    if not uid:
        return None
    user = User.query.get(uid)
    if not user or not user.is_clinic:
        return None
    return user


def _set_clinic_session(user: User) -> None:
    """Write unified session dict for a clinic user."""
    razao = user.clinic_profile.razao_social if user.clinic_profile else user.name
    session["user"] = {
        "id":        user.id,
        "email":     user.email,
        "name":      razao,
        "user_type": User.USER_TYPE_CLINIC,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  AUTH
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@clinic_bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    if (session.get("user") or {}).get("user_type") == User.USER_TYPE_CLINIC:
        return redirect("/clinica/dashboard")

    erro = None
    if request.method == "POST":
        razao_social = (request.form.get("razao_social") or "").strip()
        cnpj_raw     = request.form.get("cnpj", "")
        email        = (request.form.get("email") or "").strip().lower()
        password     = request.form.get("password", "")
        crm_cro      = (request.form.get("crm_cro") or "").strip()

        cnpj = sanitize_cnpj(cnpj_raw)
        if not cnpj:
            erro = "CNPJ invÃ¡lido. Informe 14 dÃ­gitos numÃ©ricos."
        elif not razao_social or len(razao_social) < 3:
            erro = "RazÃ£o Social invÃ¡lida."
        elif not email or len(password) < 6:
            erro = "E-mail e senha (mÃ­n. 6 caracteres) sÃ£o obrigatÃ³rios."
        elif User.query.filter_by(email=email).first():
            erro = "Este e-mail jÃ¡ estÃ¡ cadastrado."
        elif ClinicProfile.query.filter_by(cnpj=cnpj).first():
            erro = "Este CNPJ jÃ¡ estÃ¡ cadastrado."
        else:
            doc_filename = None
            doc = request.files.get("document")
            if doc and doc.filename and _allowed_file(doc.filename):
                safe_name = secure_filename(doc.filename)
                doc.save(os.path.join(_upload_dir(), safe_name))
                doc_filename = safe_name

            user = User(
                email=email,
                name=razao_social,
                password_hash=hash_password(password),
                user_type=User.USER_TYPE_CLINIC,
            )
            db.session.add(user)
            db.session.flush()  # populate user.id before creating profile

            profile = ClinicProfile(
                user_id=user.id,
                razao_social=razao_social,
                cnpj=cnpj,
                crm_cro=crm_cro or None,
                document_filename=doc_filename,
            )
            db.session.add(profile)
            db.session.commit()

            _set_clinic_session(user)
            return redirect("/clinica/dashboard")

    return render_template("clinic/auth.html", action="registrar", erro=erro)


@clinic_bp.route("/login", methods=["GET", "POST"])
def login():
    if (session.get("user") or {}).get("user_type") == User.USER_TYPE_CLINIC:
        return redirect("/clinica/dashboard")

    erro = None
    if request.method == "POST":
        email    = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email, user_type=User.USER_TYPE_CLINIC).first()
        if not user or not verify_password(password, user.password_hash):
            erro = "E-mail ou senha incorretos."
        else:
            _set_clinic_session(user)
            return redirect("/clinica/dashboard")

    return render_template("clinic/auth.html", action="login", erro=erro)


@clinic_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/clinica/login")


def _build_conversations(clinic_user_id: int):
    """Return conversations for the dashboard Mensagens tab.

    Each entry:
      { 'other': User, 'last_msg': Mensagem, 'unread': int,
        'status_chat': str, 'chat_id': int|None, 'ultimo_servico': str|None }
    Ordered by latest message descending.
    Two lists are returned: ativas + encerradas (filtered in template).
    """
    from sqlalchemy import or_
    all_msgs = (
        Mensagem.query
        .filter(
            or_(
                Mensagem.receiver_id == clinic_user_id,
                Mensagem.sender_id   == clinic_user_id,
            )
        )
        .order_by(Mensagem.timestamp.desc())
        .all()
    )
    seen: dict = {}
    for m in all_msgs:
        other_id = m.sender_id if m.receiver_id == clinic_user_id else m.receiver_id
        if other_id not in seen:
            other  = m.sender if m.receiver_id == clinic_user_id else m.receiver
            unread = sum(
                1 for x in all_msgs
                if x.sender_id == other_id and x.receiver_id == clinic_user_id and not x.lido
            )
            conversa = ChatConversa.query.filter_by(
                clinic_id=clinic_user_id, patient_id=other_id
            ).first()
            ultimo_appt = (
                Appointment.query
                .filter_by(clinic_id=clinic_user_id, user_id=other_id)
                .order_by(Appointment.created_at.desc())
                .first()
            )
            ultimo_servico = (
                ultimo_appt.service.title
                if ultimo_appt and ultimo_appt.service else None
            )
            seen[other_id] = {
                "other":          other,
                "last_msg":       m,
                "unread":         unread,
                "status_chat":    conversa.status if conversa else "ativa",
                "chat_id":        conversa.id     if conversa else None,
                "ultimo_servico": ultimo_servico,
            }
    return list(seen.values())


@clinic_bp.route("/dashboard")
@login_required_clinic
def dashboard():
    user = _session_clinic()
    if not user:
        session.pop("user", None)
        return redirect("/clinica/login")

    # â”€â”€ BI indicators â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    today       = date.today()
    month_start = today.replace(day=1).isoformat()
    month_end   = today.replace(day=monthrange(today.year, today.month)[1]).isoformat()

    monthly_apps = Appointment.query.filter(
        Appointment.clinic_id == user.id,
        Appointment.date >= month_start,
        Appointment.date <= month_end,
        Appointment.status != Appointment.STATUS_CANCELLED,
    ).all()

    total_this_month  = len(monthly_apps)
    estimated_revenue = sum(
        (a.service.price if a.service else 0) for a in monthly_apps
    )
    status_counts = {
        "pending":   sum(1 for a in monthly_apps if a.status == Appointment.STATUS_PENDING),
        "confirmed": sum(1 for a in monthly_apps if a.status == Appointment.STATUS_CONFIRMED),
        "completed": sum(1 for a in monthly_apps if a.status == Appointment.STATUS_COMPLETED),
    }

    all_services = ClinicService.query.filter_by(clinic_id=user.id).all()
    service_ids  = [s.id for s in all_services]

    # ── Agenda slots (upcoming + today) ─────────────────────
    agenda_slots = (
        Disponibilidade.query
        .options(
            joinedload(Disponibilidade.patient),
            joinedload(Disponibilidade.anuncio),
        )
        .filter(
            Disponibilidade.service_id.in_(service_ids),
            Disponibilidade.data >= today,
        )
        .order_by(Disponibilidade.data, Disponibilidade.horario)
        .all()
    ) if service_ids else []

    # Pre-build a service lookup for the template
    service_map  = {s.id: s for s in all_services}
    specialties  = sorted({s.specialty for s in all_services if s.specialty})

    # Build a payment-status lookup keyed by (service_id, date_str, horario)
    # Appointment.date is stored as "YYYY-MM-DD" string; slot.data.isoformat() matches.
    appt_map: dict = {}
    if service_ids:
        appointments = (
            Appointment.query
            .filter(Appointment.service_id.in_(service_ids))
            .all()
        )
        for a in appointments:
            appt_map[(a.service_id, a.date, a.time_slot)] = a

    # ── Analytics (last 30 days covers both 7-day and 30-day views) ──────────
    thirty_ago = today - timedelta(days=29)

    # Completed appointments in the last 30 days
    completed_appts = (
        Appointment.query
        .filter(
            Appointment.clinic_id == user.id,
            Appointment.status == Appointment.STATUS_COMPLETED,
            Appointment.date >= thirty_ago.isoformat(),
            Appointment.date <= today.isoformat(),
        )
        .all()
    )

    # Build disponibilidade price lookup to get adjusted price per slot
    disp_price_map: dict = {}
    if service_ids:
        disps = (
            Disponibilidade.query
            .filter(
                Disponibilidade.service_id.in_(service_ids),
                Disponibilidade.data >= thirty_ago,
                Disponibilidade.data <= today,
            )
            .all()
        )
        for d in disps:
            disp_price_map[(d.service_id, d.data.isoformat(), d.horario)] = (
                d.preco if d.preco is not None else None
            )

    # Accumulate daily revenue and shift counts over last 30 days
    daily_revenue: dict = {}
    shift_counts = {"Madrugada": 0, "Manhã": 0, "Tarde": 0, "Noite": 0}
    for a in completed_appts:
        base_price = a.service.price if a.service else 0.0
        adj_price = disp_price_map.get((a.service_id, a.date, a.time_slot))
        price = adj_price if adj_price is not None else base_price
        daily_revenue[a.date] = daily_revenue.get(a.date, 0.0) + price
        hour = int(a.time_slot[:2]) if a.time_slot and len(a.time_slot) >= 2 else 0
        if hour < 6:
            shift_counts["Madrugada"] += 1
        elif hour < 12:
            shift_counts["Manhã"] += 1
        elif hour < 18:
            shift_counts["Tarde"] += 1
        else:
            shift_counts["Noite"] += 1

    # Build labelled day arrays for Chart.js
    seven_ago = today - timedelta(days=6)
    days_7  = [(seven_ago  + timedelta(days=i)) for i in range(7)]
    days_30 = [(thirty_ago + timedelta(days=i)) for i in range(30)]

    rev_7d  = [round(daily_revenue.get(d.isoformat(), 0.0), 2) for d in days_7]
    rev_30d = [round(daily_revenue.get(d.isoformat(), 0.0), 2) for d in days_30]
    lbl_7d  = [d.strftime("%d/%m") for d in days_7]
    lbl_30d = [d.strftime("%d/%m") for d in days_30]

    consults_7d  = sum(1 for a in completed_appts if a.date in {d.isoformat() for d in days_7})
    consults_30d = len(completed_appts)

    total_rev_7d  = round(sum(rev_7d),  2)
    total_rev_30d = round(sum(rev_30d), 2)
    ticket_7d  = round(total_rev_7d  / consults_7d,  2) if consults_7d  else 0.0
    ticket_30d = round(total_rev_30d / consults_30d, 2) if consults_30d else 0.0

    import json as _json
    analytics_json = _json.dumps({
        "revenue_7d":   rev_7d,
        "labels_7d":    lbl_7d,
        "revenue_30d":  rev_30d,
        "labels_30d":   lbl_30d,
        "shift_counts": shift_counts,
        "total_rev_7d":  total_rev_7d,
        "total_rev_30d": total_rev_30d,
        "ticket_7d":    ticket_7d,
        "ticket_30d":   ticket_30d,
        "consults_7d":  consults_7d,
        "consults_30d": consults_30d,
    })

    return render_template(
        "clinic/dashboard.html",
        clinic=user,
        services=all_services,
        total_this_month=total_this_month,
        estimated_revenue=estimated_revenue,
        status_counts=status_counts,
        agenda_slots=agenda_slots,
        service_map=service_map,
        specialties=specialties,
        appt_map=appt_map,
        conversations=_build_conversations(user.id),
        analytics_json=analytics_json,
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  SERVICES (ANÃšNCIOS)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


# ─────────────────────────────────────────────────────────────
#  EDIT VITRINE (personalizar vitrine pública)
# ─────────────────────────────────────────────────────────────

ALLOWED_PROFILE_IMG = {"png", "jpg", "jpeg", "gif", "webp"}


def _profile_img_dir() -> str:
    path = os.path.join(current_app.root_path, "static", "uploads", "profiles")
    os.makedirs(path, exist_ok=True)
    return path


def _save_profile_image(file_storage, prefix: str):
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_PROFILE_IMG:
        return None
    import uuid
    filename = f"{prefix}_{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(_profile_img_dir(), filename))
    return f"uploads/profiles/{filename}"


@clinic_bp.route("/vitrine/editar", methods=["GET", "POST"])
@login_required_clinic
def editar_vitrine():
    user = _session_clinic()
    if not user:
        session.pop("user", None)
        return redirect("/clinica/login")

    profile     = user.clinic_profile
    services    = ClinicService.query.filter_by(clinic_id=user.id, active=True).all()
    specialties = list({s.specialty for s in services if s.specialty})

    ok   = False
    erro = None

    if request.method == "POST":
        razao = (request.form.get("razao_social") or "").strip()
        if len(razao) < 2:
            erro = "Nome da clínica muito curto (mín. 2 caracteres)."
        else:
            profile.razao_social   = razao
            profile.cnpj           = (request.form.get("cnpj") or "").replace(".", "").replace("/", "").replace("-", "")
            profile.crm_cro        = (request.form.get("crm_cro") or "").strip() or None
            profile.endereco       = (request.form.get("endereco") or "").strip() or None
            profile.cep            = (request.form.get("cep") or "").strip() or None
            profile.bio            = (request.form.get("bio") or "").strip()[:600] or None
            profile.especialidades = (request.form.get("especialidades") or "").strip()[:500] or None

            fone = (request.form.get("telefone") or "").replace("(", "").replace(")", "").replace(" ", "").replace("-", "")
            user.telefone = fone[:20] if fone else None

            avatar_url = _save_profile_image(request.files.get("avatar"), f"avatar_{user.id}")
            if avatar_url:
                profile.avatar_url = avatar_url

            banner_url = _save_profile_image(request.files.get("banner"), f"banner_{user.id}")
            if banner_url:
                profile.banner_url = banner_url

            _set_clinic_session(user)
            db.session.commit()
            ok = True

    return render_template(
        "clinic/edit_profile.html",
        user=user,
        profile=profile,
        services=services,
        specialties=specialties,
        ok=ok,
        erro=erro,
    )

@clinic_bp.route("/novo-anuncio", methods=["GET", "POST"])
@login_required_clinic
def novo_anuncio():
    user = _session_clinic()
    erro = None

    if request.method == "POST":
        title       = (request.form.get("title") or "").strip()
        doctor_name = (request.form.get("doctor_name") or "").strip()
        specialty   = (request.form.get("specialty") or "").strip()
        description      = (request.form.get("description") or "").strip()
        logradouro       = (request.form.get("logradouro") or "").strip() or None
        numero           = (request.form.get("numero") or "").strip() or None
        complemento      = (request.form.get("complemento") or "").strip() or None
        bairro           = (request.form.get("bairro") or "").strip() or None
        cidade           = (request.form.get("cidade") or "").strip() or None
        estado           = ((request.form.get("estado") or "").strip()[:2].upper()) or None
        cep              = (request.form.get("cep") or "").strip() or None
        google_maps_link = (request.form.get("google_maps_link") or "").strip() or None
        # Hybrid fields
        service_category  = (request.form.get("service_category") or "consulta").strip()
        if service_category not in ('consulta', 'exame', 'pacote'):
            service_category = 'consulta'
        exam_type         = (request.form.get("exam_type") or "").strip() or None
        exam_orientations = (request.form.get("exam_orientations") or "").strip() or None
        try:
            price = float(request.form.get("price", "0").replace(",", "."))
        except ValueError:
            price = 0.0

        if not title or not doctor_name or not specialty or price <= 0:
            erro = "Preencha todos os campos obrigatórios e um preço válido."
        else:
            imagem_url = _save_service_image(request.files.get("imagem"))
            service = ClinicService(
                clinic_id=user.id,
                title=title,
                doctor_name=doctor_name,
                specialty=specialty,
                description=description,
                price=price,
                imagem_url=imagem_url,
                logradouro=logradouro,
                numero=numero,
                complemento=complemento,
                bairro=bairro,
                cidade=cidade,
                estado=estado,
                cep=cep,
                google_maps_link=google_maps_link,
                service_category=service_category,
                exam_type=exam_type,
                exam_orientations=exam_orientations,
                active=True,
            )
            db.session.add(service)
            db.session.commit()
            return redirect("/clinica/dashboard")

    return render_template("clinic/new_service.html", clinic=user, erro=erro)


@clinic_bp.route("/anuncio/<int:service_id>/editar", methods=["GET", "POST"])
@login_required_clinic
def editar_anuncio(service_id):
    user    = _session_clinic()
    service = ClinicService.query.filter_by(id=service_id, clinic_id=user.id).first_or_404()
    erro    = None

    if request.method == "POST":
        title       = (request.form.get("title") or "").strip()
        doctor_name = (request.form.get("doctor_name") or "").strip()
        specialty   = (request.form.get("specialty") or "").strip()
        description      = (request.form.get("description") or "").strip()
        logradouro       = (request.form.get("logradouro") or "").strip() or None
        numero           = (request.form.get("numero") or "").strip() or None
        complemento      = (request.form.get("complemento") or "").strip() or None
        bairro           = (request.form.get("bairro") or "").strip() or None
        cidade           = (request.form.get("cidade") or "").strip() or None
        estado           = ((request.form.get("estado") or "").strip()[:2].upper()) or None
        cep              = (request.form.get("cep") or "").strip() or None
        google_maps_link = (request.form.get("google_maps_link") or "").strip() or None
        try:
            price = float(request.form.get("price", "0").replace(",", "."))
        except ValueError:
            price = 0.0

        if not title or not doctor_name or not specialty or price <= 0:
            erro = "Preencha todos os campos obrigatórios e um preço válido."
        else:
            service_category  = (request.form.get("service_category") or "consulta").strip()
            if service_category not in ('consulta', 'exame', 'pacote'):
                service_category = 'consulta'
            exam_type         = (request.form.get("exam_type") or "").strip() or None
            exam_orientations = (request.form.get("exam_orientations") or "").strip() or None
            service.title             = title
            service.doctor_name       = doctor_name
            service.specialty         = specialty
            service.description       = description
            service.price             = price
            service.logradouro        = logradouro
            service.numero            = numero
            service.complemento       = complemento
            service.bairro            = bairro
            service.cidade            = cidade
            service.estado            = estado
            service.cep               = cep
            service.google_maps_link  = google_maps_link
            service.service_category  = service_category
            service.exam_type         = exam_type
            service.exam_orientations = exam_orientations
            new_img = _save_service_image(request.files.get("imagem"))
            if new_img:
                if service.imagem_url:
                    old_path = os.path.join(current_app.root_path, "static", service.imagem_url)
                    if os.path.isfile(old_path):
                        os.remove(old_path)
                service.imagem_url = new_img
            db.session.commit()
            return redirect("/clinica/dashboard")

    return render_template("clinic/edit_service.html", clinic=user, service=service, erro=erro)


@clinic_bp.route("/anuncio/<int:service_id>/deletar", methods=["POST"])
@login_required_clinic
def deletar_anuncio(service_id):
    user    = _session_clinic()
    service = ClinicService.query.filter_by(id=service_id, clinic_id=user.id).first_or_404()
    if service.imagem_url:
        img_path = os.path.join(current_app.root_path, "static", service.imagem_url)
        if os.path.isfile(img_path):
            os.remove(img_path)
    db.session.delete(service)
    db.session.commit()
    return jsonify({"ok": True})


@clinic_bp.route("/anuncio/<int:service_id>/toggle", methods=["POST"])
@login_required_clinic
def toggle_service(service_id):
    user    = _session_clinic()
    service = ClinicService.query.filter_by(id=service_id, clinic_id=user.id).first_or_404()
    service.active = not service.active
    db.session.commit()
    return jsonify({"ok": True, "active": service.active})

# ───────────────────────────────────────────────────────────────
#  SCHEDULES (HORÁRIOS) — LEGADO
#  Substituído pela Gestão de Disponibilidade Médica (Agenda).
#  Qualquer acesso a /clinica/horarios/* é redirecionado para /clinica/agenda.
# ───────────────────────────────────────────────────────────────

@clinic_bp.route("/horarios", methods=["GET", "POST"])
@clinic_bp.route("/horarios/salvar", methods=["GET", "POST"])
@clinic_bp.route("/horarios/<int:schedule_id>/deletar", methods=["GET", "POST"])
def horarios_redirect(**kwargs):
    """Redirect legacy /horarios/* URLs to the Gestao de Disponibilidade Medica page."""
    return redirect("/clinica/agenda")


# ─────────────────────────────────────────────
#  AGENDA — specific date/time slots
# ─────────────────────────────────────────────

def _is_night_slot(horario: str, inicio: str, fim: str) -> bool:
    """Return True if *horario* falls in the overnight band [inicio .. fim].

    Handles both intra-day ranges (22:00-23:00) and overnight ranges that
    cross midnight (22:00-06:00). All strings must be "HH:MM".
    """
    def _mins(t: str) -> int:
        return int(t[:2]) * 60 + int(t[3:])
    h, s, e = _mins(horario), _mins(inicio), _mins(fim)
    if s >= e:          # overnight — e.g. 22:00 → 06:00
        return h >= s or h < e
    return s <= h < e   # intra-day — e.g. 18:00 → 22:00


@clinic_bp.route("/agenda", methods=["GET"])
@login_required_clinic
def agenda():
    """Page for the clinic to manage specific availability slots."""
    user     = _session_clinic()
    services = ClinicService.query.filter_by(clinic_id=user.id, active=True).all()
    return render_template(
        "clinic/agenda.html",
        clinic=user,
        services=services,
        now_date=date.today().isoformat(),
    )


@clinic_bp.route("/cadastrar-disponibilidade", methods=["GET"])
@login_required_clinic
def cadastrar_disponibilidade():
    """Dedicated full-page form to register new availability slots."""
    user     = _session_clinic()
    services = ClinicService.query.filter_by(clinic_id=user.id, active=True).all()
    return render_template(
        "clinic/cadastrar_disponibilidade.html",
        clinic=user,
        services=services,
        now_date=date.today().isoformat(),
    )


@clinic_bp.route("/agenda/salvar", methods=["POST"])
@login_required_clinic
def salvar_disponibilidade():
    """Save time slots for one or more dates with optional price adjustment.

    Form fields:
      service_id       — int
      datas            — comma-separated ISO dates "2026-04-05,2026-04-08,…"
      horarios[]       — list of "HH:MM" strings
      preco_tipo       — "padrao" | "ajuste"
      valor_ajuste     — signed float when preco_tipo=="ajuste"
                         (e.g. +50.00 to add, -20.00 to discount)
      ajuste_scope     — "todos" | "madrugada" | "comercial"
                         quickly pre-fills for the quick-preset buttons
                         (when scope != "todos", ajuste only applies to
                          matching hours; others get preco=None)
    """
    user       = _session_clinic()
    service_id = request.form.get("service_id", type=int)
    datas_str  = (request.form.get("datas") or "").strip()
    horarios   = request.form.getlist("horarios")

    service = ClinicService.query.filter_by(id=service_id, clinic_id=user.id).first_or_404()

    # ── Pricing parameters ────────────────────────────────────
    preco_tipo     = request.form.get("preco_tipo", "padrao")
    ajuste_raw     = (request.form.get("valor_ajuste") or "").strip()
    ajuste_scope   = request.form.get("ajuste_scope", "todos")   # "todos"|"madrugada"|"comercial"

    valor_ajuste: float | None = None
    if preco_tipo == "ajuste" and ajuste_raw:
        try:
            valor_ajuste = float(ajuste_raw.replace(",", "."))
        except ValueError:
            return jsonify({"ok": False, "msg": "Ajuste de preço inválido."}), 400

    def _in_scope(horario: str) -> bool:
        """Return True if this slot falls within the chosen quick-preset scope."""
        if ajuste_scope == "todos":
            return True
        h = int(horario[:2])
        if ajuste_scope == "madrugada":
            return h >= 22 or h < 6
        if ajuste_scope == "comercial":
            return 8 <= h < 18
        return True

    def _calc(horario: str):
        """Return (preco_final, valor_ajuste_registrado) for this slot."""
        if valor_ajuste is None or not _in_scope(horario):
            return None, None           # use service.price, no adjustment
        base  = service.price
        final = round(base + valor_ajuste, 2)
        if final < 0:
            final = 0.0
        return final, valor_ajuste

    # ── Parse date list ───────────────────────────────────────
    date_tokens = [d.strip() for d in datas_str.split(",") if d.strip()]
    if not date_tokens:
        return jsonify({"ok": False, "msg": "Selecione ao menos uma data."}), 400

    datas = []
    for token in date_tokens:
        try:
            datas.append(datetime.strptime(token, "%Y-%m-%d").date())
        except ValueError:
            return jsonify({"ok": False, "msg": f"Data inválida: {token}"}), 400

    horarios = [h.strip() for h in horarios if h.strip()]
    if not horarios:
        return jsonify({"ok": False, "msg": "Informe ao menos um horário."}), 400

    # ── Bulk-fetch existing slots to skip duplicates ──────────
    existing = {
        (r.data, r.horario)
        for r in Disponibilidade.query.filter(
            Disponibilidade.service_id == service.id,
            Disponibilidade.data.in_(datas),
        ).with_entities(Disponibilidade.data, Disponibilidade.horario).all()
    }

    saved = 0
    for data in datas:
        for h in horarios:
            if (data, h) not in existing:
                preco_final, ajuste = _calc(h)
                db.session.add(Disponibilidade(
                    service_id=service.id,
                    data=data,
                    horario=h,
                    status=True,
                    preco=preco_final,
                    valor_ajuste=ajuste,
                ))
                saved += 1

    db.session.commit()
    ndatas     = len(datas)
    total_req  = len(datas) * len(horarios)
    duplicados = total_req - saved

    if saved == 0:
        return jsonify({
            "ok":        False,
            "salvos":    0,
            "duplicados": duplicados,
            "msg":       "Este horário já está cadastrado em sua agenda.",
        }), 409

    if duplicados > 0:
        msg = (
            f"{saved} horário(s) criado(s) em {ndatas} data(s). "
            f"{duplicados} já existia(m) e foram ignorados."
        )
    else:
        msg = f"{saved} horário(s) criado(s) com sucesso em {ndatas} data(s)."

    return jsonify({"ok": True, "salvos": saved, "duplicados": duplicados, "msg": msg})


@clinic_bp.route("/agenda/slots", methods=["GET"])
@login_required_clinic
def listar_disponibilidade():
    """Return slots for a service on a given date (for the clinic's own agenda view)."""
    user       = _session_clinic()
    service_id = request.args.get("service_id", type=int)
    data_str   = request.args.get("data", "")

    service = ClinicService.query.filter_by(id=service_id, clinic_id=user.id).first_or_404()

    try:
        data = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"slots": []})

    rows = (
        Disponibilidade.query
        .filter_by(service_id=service.id, data=data)
        .order_by(Disponibilidade.horario)
        .all()
    )
    return jsonify({
        "slots": [
            {
                "id":            r.id,
                "horario":       r.horario,
                "status":        r.status,
                "preco_padrao":  service.price,
                "preco":         r.preco,
                "valor_ajuste":  r.valor_ajuste,
                "preco_efetivo": r.preco if r.preco is not None else service.price,
                "patient_name":  r.patient.name if r.patient else None,
            }
            for r in rows
        ]
    })


@clinic_bp.route("/agenda/slot/<int:slot_id>/preco", methods=["POST"])
@login_required_clinic
def atualizar_preco_slot(slot_id):
    """Update the price adjustment of a single availability slot (inline edit).

    POST body:
      valor_ajuste — signed float string (e.g. "+50", "-20", "0"),
                     or empty string to reset the slot to service default.
    """
    user = _session_clinic()
    slot = Disponibilidade.query.join(ClinicService).filter(
        Disponibilidade.id == slot_id,
        ClinicService.clinic_id == user.id,
    ).first_or_404()

    service    = slot.anuncio
    ajuste_raw = (request.form.get("valor_ajuste") or "").strip()

    if ajuste_raw == "" or ajuste_raw == "0":
        slot.preco        = None
        slot.valor_ajuste = None
    else:
        try:
            ajuste = float(ajuste_raw.replace(",", "."))
        except ValueError:
            return jsonify({"ok": False, "msg": "Valor de ajuste inválido."}), 400
        final = round(service.price + ajuste, 2)
        if final < 0:
            final = 0.0
        slot.preco        = final
        slot.valor_ajuste = ajuste

    db.session.commit()
    preco_efetivo = slot.preco if slot.preco is not None else service.price
    return jsonify({
        "ok":            True,
        "preco_padrao":  service.price,
        "preco":         slot.preco,
        "valor_ajuste":  slot.valor_ajuste,
        "preco_efetivo": preco_efetivo,
    })


@clinic_bp.route("/agenda/excluir/<int:slot_id>", methods=["POST"])
@login_required_clinic
def excluir_disponibilidade(slot_id):
    """Delete a specific availability slot owned by this clinic."""
    user = _session_clinic()
    slot = Disponibilidade.query.join(ClinicService).filter(
        Disponibilidade.id == slot_id,
        ClinicService.clinic_id == user.id,
    ).first_or_404()
    db.session.delete(slot)
    db.session.commit()
    return jsonify({"ok": True})


@clinic_bp.route("/agenda/horarios-ocupados", methods=["GET"])
@login_required_clinic
def horarios_ocupados():
    """Return already-registered horários for a service across given dates.

    Query params:
      service_id — int
      datas      — comma-separated ISO dates "2026-04-05,2026-04-08,…"

    Returns:
      {
        "taken": {
          "2026-04-05": ["09:00", "10:00"],
          "2026-04-08": ["14:00"]
        }
      }
    """
    user       = _session_clinic()
    service_id = request.args.get("service_id", type=int)
    datas_str  = (request.args.get("datas") or "").strip()

    if not service_id:
        return jsonify({"taken": {}})

    service = ClinicService.query.filter_by(id=service_id, clinic_id=user.id).first_or_404()

    datas = []
    for token in datas_str.split(","):
        token = token.strip()
        if token:
            try:
                datas.append(datetime.strptime(token, "%Y-%m-%d").date())
            except ValueError:
                pass

    if not datas:
        return jsonify({"taken": {}})

    rows = (
        Disponibilidade.query
        .filter(
            Disponibilidade.service_id == service.id,
            Disponibilidade.data.in_(datas),
        )
        .with_entities(Disponibilidade.data, Disponibilidade.horario)
        .all()
    )

    taken: dict = {}
    for r in rows:
        key = r.data.isoformat()
        taken.setdefault(key, []).append(r.horario)

    return jsonify({"taken": taken})


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  PUBLIC API â€” consumed by calendar.html
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@clinic_bp.route("/api/disponibilidade/<int:service_id>")
def disponibilidade(service_id):
    """Return available time slots for a service on a given date.

    Query param: ?date=YYYY-MM-DD
    Returns JSON: { "slots": ["08:00", "08:30", ...] }
    """
    date_str = request.args.get("date", "")
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"slots": []})

    weekday = target.weekday()  # 0=Monday â€¦ 6=Sunday

    schedules = ClinicSchedule.query.filter_by(
        service_id=service_id, weekday=weekday
    ).all()

    if not schedules:
        return jsonify({"slots": []})

    # Generate all slots from schedule bands
    all_slots = []
    for sched in schedules:
        try:
            start = datetime.strptime(sched.start_time, "%H:%M")
            end   = datetime.strptime(sched.end_time,   "%H:%M")
        except ValueError:
            continue
        current = start
        while current < end:
            all_slots.append(current.strftime("%H:%M"))
            current += timedelta(minutes=sched.slot_minutes or 30)

    # Subtract already-booked slots
    booked = {
        a.time_slot for a in Appointment.query.filter_by(
            service_id=service_id,
            date=date_str,
        ).filter(Appointment.status != Appointment.STATUS_CANCELLED).all()
    }

    available = [s for s in all_slots if s not in booked]
    return jsonify({"slots": sorted(set(available))})


# ─────────────────────────────────────────────────────────────
#  APPOINTMENT WORKFLOW  (clinic-initiated state transitions)
# ─────────────────────────────────────────────────────────────

@clinic_bp.route("/agenda/slot/<int:slot_id>/aceitar", methods=["POST"])
@login_required_clinic
def aceitar_agendamento(slot_id):
    """Accept a reservation: Reservado → Agendado (confirmed).

    If an Appointment already exists with status=pending, it is confirmed.
    If no Appointment exists yet (direct Disponibilidade booking), one is created.
    """
    user = _session_clinic()
    slot = Disponibilidade.query.join(ClinicService).filter(
        Disponibilidade.id == slot_id,
        ClinicService.clinic_id == user.id,
    ).first_or_404()

    if slot.status:
        return jsonify({"ok": False, "msg": "Horário ainda disponível — nenhum paciente reservou."}), 400
    if not slot.patient_id:
        return jsonify({"ok": False, "msg": "Nenhum paciente associado a este horário."}), 400

    appt = Appointment.query.filter_by(
        service_id=slot.service_id,
        date=slot.data.isoformat(),
        time_slot=slot.horario,
        clinic_id=user.id,
    ).first()

    if appt and appt.status == Appointment.STATUS_CONFIRMED:
        return jsonify({"ok": False, "msg": "Agendamento já está confirmado."}), 400

    if appt:
        appt.status = Appointment.STATUS_CONFIRMED
    else:
        appt = Appointment(
            service_id=slot.service_id,
            clinic_id=user.id,
            user_id=slot.patient_id,
            date=slot.data.isoformat(),
            time_slot=slot.horario,
            status=Appointment.STATUS_CONFIRMED,
            status_pagamento="pendente",
        )
        db.session.add(appt)

    db.session.commit()
    return jsonify({"ok": True, "msg": "Agendamento confirmado."})


@clinic_bp.route("/agenda/appointment/<int:appt_id>/confirmar-chegada", methods=["POST"])
@login_required_clinic
def confirmar_chegada(appt_id):
    """Patient arrived: Agendado (confirmed) → Em Atendimento (in_progress)."""
    user = _session_clinic()
    appt = Appointment.query.filter_by(id=appt_id, clinic_id=user.id).first_or_404()

    if appt.status != Appointment.STATUS_CONFIRMED:
        return jsonify({"ok": False, "msg": "Agendamento não está no status 'Agendado'."}), 400

    appt.status = Appointment.STATUS_IN_PROGRESS
    db.session.commit()
    return jsonify({"ok": True, "msg": "Chegada confirmada. Consulta em andamento."})


@clinic_bp.route("/agenda/appointment/<int:appt_id>/iniciar", methods=["POST"])
@login_required_clinic
def iniciar_atendimento(appt_id):
    """Start consultation in one click: pending or confirmed → in_progress."""
    user = _session_clinic()
    appt = Appointment.query.filter_by(id=appt_id, clinic_id=user.id).first_or_404()

    allowed = {Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED}
    # Idempotent: already in_progress is fine (doctor may have re-clicked)
    if appt.status == Appointment.STATUS_IN_PROGRESS:
        return jsonify({"ok": True, "msg": "Consulta já está em andamento."})
    if appt.status not in allowed:
        return jsonify({"ok": False, "msg": "Consulta não pode ser iniciada neste estado."}), 400

    appt.status = Appointment.STATUS_IN_PROGRESS
    db.session.commit()
    return jsonify({"ok": True, "msg": "Consulta iniciada."})


@clinic_bp.route("/agenda/appointment/<int:appt_id>/encerrar", methods=["POST"])
@login_required_clinic
def encerrar_consulta(appt_id):
    """Close consultation: Em Atendimento (in_progress) → Realizada (completed)."""
    user = _session_clinic()
    appt = Appointment.query.filter_by(id=appt_id, clinic_id=user.id).first_or_404()

    if appt.status != Appointment.STATUS_IN_PROGRESS:
        return jsonify({"ok": False, "msg": "Consulta não está em andamento."}), 400

    appt.status = Appointment.STATUS_COMPLETED
    db.session.commit()
    return jsonify({"ok": True, "msg": "Consulta encerrada e marcada como Realizada."})


@clinic_bp.route("/agenda/appointment/<int:appt_id>/finalizar", methods=["POST"])
@login_required_clinic
def finalizar_atendimento(appt_id):
    """Finalize with post-care: in_progress|completed → finalized + PostAtendimento record."""
    user = _session_clinic()
    appt = Appointment.query.filter_by(id=appt_id, clinic_id=user.id).first_or_404()

    allowed = {Appointment.STATUS_IN_PROGRESS, Appointment.STATUS_COMPLETED}
    if appt.status not in allowed:
        return jsonify({"ok": False, "msg": "Agendamento não pode ser finalizado neste estado."}), 400

    # Prevent duplicate post-atendimento
    existing = PostAtendimento.query.filter_by(appointment_id=appt_id).first()
    if existing:
        return jsonify({"ok": False, "msg": "Este atendimento já foi finalizado."}), 400

    data = request.get_json(force=True, silent=True) or {}
    recomendacoes   = (data.get("recomendacoes")   or "").strip() or None
    proximos_passos = (data.get("proximos_passos") or "").strip() or None
    retorno_tipo    = (data.get("retorno_tipo")    or "").strip() or None
    retorno_meses_raw = data.get("retorno_meses")
    try:
        retorno_meses = int(retorno_meses_raw) if retorno_meses_raw not in (None, "") else None
    except (ValueError, TypeError):
        retorno_meses = None
    retorno_sugerido = bool(data.get("retorno_sugerido")) and retorno_tipo is not None

    post = PostAtendimento(
        appointment_id   = appt_id,
        recomendacoes    = recomendacoes,
        proximos_passos  = proximos_passos,
        retorno_sugerido = retorno_sugerido,
        retorno_tipo     = retorno_tipo if retorno_sugerido else None,
        retorno_meses    = retorno_meses if retorno_sugerido else None,
        notificacao_lida = False,
    )
    appt.status = Appointment.STATUS_FINALIZED
    db.session.add(post)
    db.session.commit()
    return jsonify({"ok": True, "msg": "Atendimento finalizado com sucesso."})

