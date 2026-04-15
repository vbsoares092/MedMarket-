import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from sqlalchemy import func, or_, and_
from datetime import datetime
from App.routes.anuncios import anuncios
from App.routes.auth import auth as auth_bp
from App.routes.clinic import clinic_bp
from App.routes.prontuario import prontuario_bp
from App.database import db
from App.models import User, ClinicProfile, ClinicService, Mensagem, ChatConversa, Appointment, Prontuario, DocumentoPaciente, Disponibilidade, Review
from App.utils.security import hash_password, verify_password, sanitize_cpf

# ── Static reference data ──────────────────────────────────────────────────────
categories = [
    {"name": "Clínica Geral",        "icon": "stethoscope"},
    {"name": "Cardiologia",          "icon": "heart"},
    {"name": "Neurologia",           "icon": "brain"},
    {"name": "Ortopedia",            "icon": "bone"},
    {"name": "Pediatria",            "icon": "baby"},
    {"name": "Oftalmologia",         "icon": "eye"},
    {"name": "Exames",               "icon": "microscope"},
    {"name": "Exame de Sangue",      "icon": "droplets"},
    {"name": "Ressonância Magnética","icon": "scan"},
    {"name": "Raio-X",               "icon": "unfold-horizontal"},
    {"name": "Farmácia",             "icon": "pill"},
    {"name": "Laboratório",          "icon": "flask-conical"},
    {"name": "Equipamentos",         "icon": "monitor"},
    {"name": "Emergência",           "icon": "siren"},
    {"name": "Diagnóstico",          "icon": "scan-line"},
    {"name": "Outros",               "icon": "more-horizontal"},
]

chat_messages = [
    {"id": "1", "user": "Dr. Carlos",  "avatar": "C", "message": "Alguém tem experiência com o novo Butterfly iQ3?",            "time": "14:32"},
    {"id": "2", "user": "Dra. Ana",    "avatar": "A", "message": "Sim! Uso há 3 meses, excelente para cardiologia.",            "time": "14:35"},
    {"id": "3", "user": "MedEquip",    "avatar": "M", "message": "Temos unidades disponíveis com desconto para compra em grupo.", "time": "14:38"},
    {"id": "4", "user": "Dr. Ricardo", "avatar": "R", "message": "Procurando plantão para o próximo feriado. Alguém precisa?",   "time": "14:42"},
    {"id": "5", "user": "LabVida",     "avatar": "L", "message": "Novo pacote de exames com coleta domiciliar disponível!",      "time": "14:45"},
    {"id": "6", "user": "Dra. Fernanda","avatar": "F", "message": "Vendo cadeira odontológica Gnatus, ótimo estado. Aceito proposta!", "time": "14:50"},
]
# ── App factory ───────────────────────────────────────────────────────────────
_basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "medmarket-secret-key-change-me")

_default_db = "sqlite:///" + os.path.join(_basedir, "instance", "medmarket.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", _default_db)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit

db.init_app(app)

with app.app_context():
    from App import models  # noqa: ensure table metadata is loaded
    from sqlalchemy import text

    # Create any brand-new tables
    db.create_all()

    # Auto-add columns that may be missing in an existing DB (safe ALTER TABLE)
    _migrations = [
        ("users", "user_type",        "ALTER TABLE users ADD COLUMN user_type VARCHAR(20) NOT NULL DEFAULT 'CLIENTE'"),
        ("users", "telefone",         "ALTER TABLE users ADD COLUMN telefone VARCHAR(20)"),
        ("clinic_services", "imagem_url",         "ALTER TABLE clinic_services ADD COLUMN imagem_url VARCHAR(255)"),
        ("clinic_services", "logradouro",          "ALTER TABLE clinic_services ADD COLUMN logradouro VARCHAR(200)"),
        ("clinic_services", "numero",              "ALTER TABLE clinic_services ADD COLUMN numero VARCHAR(20)"),
        ("clinic_services", "bairro",              "ALTER TABLE clinic_services ADD COLUMN bairro VARCHAR(100)"),
        ("clinic_services", "cidade",              "ALTER TABLE clinic_services ADD COLUMN cidade VARCHAR(100)"),
        ("appointments", "status_pagamento",       "ALTER TABLE appointments ADD COLUMN status_pagamento VARCHAR(20) NOT NULL DEFAULT 'pendente'"),
        ("prontuarios",  "observacoes",             "ALTER TABLE prontuarios ADD COLUMN observacoes TEXT"),
        ("clinic_profiles", "bio",            "ALTER TABLE clinic_profiles ADD COLUMN bio TEXT"),
        ("clinic_profiles", "avatar_url",     "ALTER TABLE clinic_profiles ADD COLUMN avatar_url VARCHAR(255)"),
        ("clinic_profiles", "banner_url",     "ALTER TABLE clinic_profiles ADD COLUMN banner_url VARCHAR(255)"),
        ("clinic_profiles", "cep",            "ALTER TABLE clinic_profiles ADD COLUMN cep VARCHAR(9)"),
        ("clinic_profiles", "especialidades", "ALTER TABLE clinic_profiles ADD COLUMN especialidades VARCHAR(500)"),
        ("clinic_services", "rating",           "ALTER TABLE clinic_services ADD COLUMN rating FLOAT DEFAULT 0"),
        ("clinic_services", "review_count",     "ALTER TABLE clinic_services ADD COLUMN review_count INTEGER DEFAULT 0"),
        ("clinic_services", "tempo_resultado",  "ALTER TABLE clinic_services ADD COLUMN tempo_resultado VARCHAR(50)"),
        ("clinic_services", "preparacao",       "ALTER TABLE clinic_services ADD COLUMN preparacao TEXT"),
    ]
    with db.engine.connect() as _conn:
        for _table, _col, _sql in _migrations:
            _cols = [r[1] for r in _conn.execute(text(f"PRAGMA table_info({_table})")).fetchall()]
            if _col not in _cols:
                _conn.execute(text(_sql))
                _conn.commit()

        # Ensure reviews table exists (created by db.create_all above, this is a safety check)
        _tables = [r[0] for r in _conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
        if 'reviews' not in _tables:
            _conn.execute(text("""
                CREATE TABLE reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    clinic_id INTEGER NOT NULL REFERENCES users(id),
                    rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            _conn.commit()

    # Ensure upload directory exists
    os.makedirs(os.path.join(app.instance_path, "uploads", "clinics"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "static", "uploads", "anuncios"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "static", "uploads", "prontuarios"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "static", "uploads", "documentos"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "static", "uploads", "profiles"), exist_ok=True)

app.register_blueprint(anuncios)
app.register_blueprint(auth_bp)
app.register_blueprint(clinic_bp)
app.register_blueprint(prontuario_bp)


def _to_float_or_none(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


CITY_COORDS = {
    ("salvador", "ba"): (-12.9714, -38.5014),
    ("sao paulo", "sp"): (-23.5505, -46.6333),
    ("rio de janeiro", "rj"): (-22.9068, -43.1729),
    ("belo horizonte", "mg"): (-19.9245, -43.9352),
    ("recife", "pe"): (-8.0476, -34.8770),
    ("fortaleza", "ce"): (-3.7319, -38.5267),
    ("curitiba", "pr"): (-25.4284, -49.2733),
    ("brasilia", "df"): (-15.7939, -47.8828),
    ("goiania", "go"): (-16.6869, -49.2648),
    ("porto alegre", "rs"): (-30.0346, -51.2177),
}

CITIES_DISPLAY = [
    "Salvador, BA", "São Paulo, SP", "Rio de Janeiro, RJ",
    "Belo Horizonte, MG", "Recife, PE", "Fortaleza, CE",
    "Curitiba, PR", "Brasília, DF", "Goiânia, GO", "Porto Alegre, RS",
]


def _effective_listing_price(listing, start_date_obj=None, end_date_obj=None):
    q_slots = listing.disponibilidades.filter_by(status=True)
    if start_date_obj:
        q_slots = q_slots.filter(Disponibilidade.data >= start_date_obj)
    if end_date_obj:
        q_slots = q_slots.filter(Disponibilidade.data <= end_date_obj)
    slots = q_slots.all()

    if not slots:
        return float(listing.price or 0), 0

    prices = [(s.preco if s.preco is not None else listing.price) for s in slots]
    return float(min(prices or [listing.price or 0])), len(slots)


def _listing_center_coords(listing):
    city = (listing.cidade or "").strip().lower()
    state = (listing.estado or "").strip().lower()
    center = CITY_COORDS.get((city, state), CITY_COORDS[("salvador", "ba")])

    # deterministic small offset so cards from same city do not overlap exactly.
    seed = (listing.id or 1) * 37
    lat_jitter = ((seed % 7) - 3) * 0.008
    lng_jitter = (((seed // 7) % 7) - 3) * 0.008
    return round(center[0] + lat_jitter, 6), round(center[1] + lng_jitter, 6)


def filter_listings(query="", category=None, location="", start_date="", end_date="", fair_price=None):
    start_date_obj = None
    end_date_obj = None
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            start_date_obj = None
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            end_date_obj = None

    if start_date_obj and end_date_obj and end_date_obj < start_date_obj:
        start_date_obj, end_date_obj = end_date_obj, start_date_obj

    q_obj = ClinicService.query.filter_by(active=True)
    if query:
        q_obj = q_obj.filter(
            (ClinicService.title.ilike(f"%{query}%")) |
            (ClinicService.description.ilike(f"%{query}%")) |
            (ClinicService.specialty.ilike(f"%{query}%"))
        )
    if category:
        q_obj = q_obj.filter(ClinicService.specialty.ilike(category))
    if location:
        loc = location.strip()
        # Handle "City, ST" format produced by the city-chip selector
        parts = [p.strip() for p in loc.split(',')]
        city_part = parts[0]
        state_part = parts[1].strip() if len(parts) > 1 else None
        if state_part and len(state_part) <= 3:
            # Exact city+state match (e.g. "Salvador, BA")
            q_obj = q_obj.filter(
                ClinicService.cidade.ilike(f"%{city_part}%"),
                ClinicService.estado.ilike(f"%{state_part}%"),
            )
        else:
            # Free-form text – try city or state
            q_obj = q_obj.filter(
                (ClinicService.cidade.ilike(f"%{loc}%")) |
                (ClinicService.estado.ilike(f"%{loc}%"))
            )

    if start_date_obj or end_date_obj:
        q_obj = (
            q_obj
            .join(Disponibilidade, Disponibilidade.service_id == ClinicService.id)
            .filter(Disponibilidade.status == True)
            .distinct()
        )
        if start_date_obj:
            q_obj = q_obj.filter(Disponibilidade.data >= start_date_obj)
        if end_date_obj:
            q_obj = q_obj.filter(Disponibilidade.data <= end_date_obj)

    listings = q_obj.order_by(ClinicService.created_at.desc()).all()

    # Pre-fetch real average ratings per clinic
    _clinic_ids = list({l.clinic_id for l in listings})
    _rating_map = {}
    if _clinic_ids:
        _rating_rows = (
            db.session.query(
                Review.clinic_id,
                func.avg(Review.rating),
                func.count(Review.id),
            )
            .filter(Review.clinic_id.in_(_clinic_ids))
            .group_by(Review.clinic_id)
            .all()
        )
        for cid, avg_r, cnt in _rating_rows:
            _rating_map[cid] = (round(float(avg_r), 1), cnt)

    fair_price_value = _to_float_or_none(fair_price)
    for listing in listings:
        effective_price, slots_count = _effective_listing_price(listing, start_date_obj, end_date_obj)
        listing.display_price = effective_price
        listing.available_slots_count = slots_count
        listing.reco_score = 0.0
        listing.is_recommended = False
        listing.map_lat, listing.map_lng = _listing_center_coords(listing)

        # Use real avg rating from reviews; fall back to 0 if no reviews
        real_avg, real_count = _rating_map.get(listing.clinic_id, (0.0, 0))
        listing.real_avg_rating = real_avg
        listing.real_review_count = real_count

        if fair_price_value and fair_price_value > 0:
            closeness = max(0.0, 1.0 - (abs(effective_price - fair_price_value) / fair_price_value))
            value_bonus = min(1.0, fair_price_value / max(effective_price, 1.0))
            slot_bonus = min(1.0, slots_count / 6.0)
            score = (0.65 * closeness) + (0.25 * value_bonus) + (0.10 * slot_bonus)
            listing.reco_score = score
            listing.is_recommended = score >= 0.68
        else:
            pass

    if fair_price_value and fair_price_value > 0:
        # Hard-filter: only keep listings at or below the requested budget
        listings = [l for l in listings if (l.display_price or 0) <= fair_price_value]
        listings.sort(key=lambda l: (-(l.reco_score or 0), abs((l.display_price or 0) - fair_price_value), l.display_price or 0))

    return listings


@app.route("/")
def index():
    query = request.args.get("q", "")
    category = request.args.get("category", "")
    specialty = request.args.get("specialty", "") or category
    location = request.args.get("location", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    fair_price = request.args.get("fair_price", "")

    filtered = filter_listings(
        query=query,
        category=specialty if specialty else None,
        location=location,
        start_date=start_date,
        end_date=end_date,
        fair_price=fair_price,
    )

    map_points = [
        {
            "id": l.id,
            "title": l.title,
            "price": int(l.display_price if hasattr(l, "display_price") else l.price),
            "lat": l.map_lat,
            "lng": l.map_lng,
            "url": f"/listing/{l.id}",
            "clinic": (
                l.clinic.clinic_profile.razao_social
                if l.clinic and l.clinic.clinic_profile
                else (l.clinic.name if l.clinic else "Clinica")
            ),
        }
        for l in filtered
    ]

    # Top-6 clinics by number of active services for the Showcase section
    partners = (
        db.session.query(User, func.count(ClinicService.id).label('svc_count'))
        .join(ClinicService, ClinicService.clinic_id == User.id)
        .filter(ClinicService.active == True, User.user_type == 'CLINICA')
        .group_by(User.id)
        .order_by(func.count(ClinicService.id).desc())
        .limit(6)
        .all()
    )

    # Carousel: prefer services with uploaded images, fall back to most recent
    _with_img = (
        ClinicService.query
        .filter(ClinicService.active == True, ClinicService.imagem_url.isnot(None))
        .order_by(ClinicService.created_at.desc())
        .limit(6)
        .all()
    )
    if len(_with_img) >= 3:
        banner_listings = _with_img
    else:
        banner_listings = (
            ClinicService.query
            .filter_by(active=True)
            .order_by(ClinicService.created_at.desc())
            .limit(6)
            .all()
        )

    has_filters = bool(query or specialty or location or start_date or end_date or fair_price)

    return render_template(
        "index.html",
        listings=filtered,
        categories=categories,
        query=query,
        selected_category=specialty,
        location=location,
        start_date=start_date,
        end_date=end_date,
        fair_price=fair_price,
        map_points=map_points,
        has_filters=has_filters,
        chat_messages=chat_messages,
        cities=CITIES_DISPLAY,
        is_logged_in=session.get("user") is not None,
        partners=partners,
        banner_listings=banner_listings,
    )


@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    listing = ClinicService.query.filter_by(id=listing_id, active=True).first()
    if not listing:
        return render_template("404.html"), 404

    # Build min_price from slots with explicit per-slot pricing; fall back to base price.
    base_price = listing.price or 0.0
    slot_precos = [
        d.preco for d in listing.disponibilidades.filter_by(status=True).all()
        if d.preco is not None
    ]
    min_price = min(slot_precos) if slot_precos else base_price
    has_discount = min_price < base_price

    _sess = session.get("user") or {}
    return render_template(
        "listing_detail.html",
        listing=listing,
        is_logged_in=bool(_sess),
        current_user_id=_sess.get("id"),
        current_user_type=_sess.get("user_type", ""),
        min_price=min_price,
        has_discount=has_discount,
    )


@app.route("/chat/<int:clinic_id>")
def chat_with_clinic(clinic_id):
    """Direct chat page between logged-in user and a clinic."""
    if not session.get("user"):
        return redirect(url_for("auth", redirect=f"/chat/{clinic_id}"))
    clinic = User.query.filter_by(id=clinic_id, user_type="CLINICA").first()
    if not clinic:
        return render_template("404.html"), 404
    clinic_name = (
        clinic.clinic_profile.razao_social
        if clinic.clinic_profile
        else clinic.name
    )
    user_id = session["user"]["id"]
    return render_template(
        "chat.html",
        clinic=clinic,
        clinic_name=clinic_name,
        user_id=user_id,
        is_logged_in=True,
        query="",
        selected_category="",
        chat_messages=chat_messages,
    )


@app.route("/auth", methods=["GET", "POST"])
def auth():
    redirect_to = request.args.get("redirect", "/")
    if request.method == "POST":
        action   = request.form.get("action", "login")
        email    = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password", "")

        if action == "register":
            name    = (request.form.get("name") or email.split("@")[0]).strip()
            cpf_raw = request.form.get("cpf", "")
            cpf     = sanitize_cpf(cpf_raw)
            if not cpf:
                return render_template(
                    "auth.html", redirect_to=redirect_to,
                    erro="CPF inválido. Informe 11 dígitos numéricos.",
                    is_logged_in=False, query="", selected_category="",
                    chat_messages=chat_messages,
                )
            if not email or len(password) < 6:
                return render_template(
                    "auth.html", redirect_to=redirect_to,
                    erro="Email e senha (mín. 6 caracteres) são obrigatórios.",
                    is_logged_in=False, query="", selected_category="",
                    chat_messages=chat_messages,
                )
            if User.query.filter_by(email=email).first():
                return render_template(
                    "auth.html", redirect_to=redirect_to,
                    erro="Este e-mail já está cadastrado.",
                    is_logged_in=False, query="", selected_category="",
                    chat_messages=chat_messages,
                )
            if User.query.filter_by(cpf=cpf).first():
                return render_template(
                    "auth.html", redirect_to=redirect_to,
                    erro="Este CPF já está cadastrado.",
                    is_logged_in=False, query="", selected_category="",
                    chat_messages=chat_messages,
                )
            user = User(
                email=email, name=name,
                password_hash=hash_password(password),
                cpf=cpf,
                telefone=(request.form.get("telefone") or "").strip() or None,
                user_type=User.USER_TYPE_CLIENT,
            )
            db.session.add(user)
            db.session.commit()
        else:  # login
            # Block clinic accounts from logging in via the client form
            user = User.query.filter_by(
                email=email, user_type=User.USER_TYPE_CLIENT
            ).first()
            if not user or not verify_password(password, user.password_hash):   
                return render_template(
                    "auth.html", redirect_to=redirect_to,
                    erro="E-mail ou senha incorretos.",
                    is_logged_in=False, query="", selected_category="",
                    chat_messages=chat_messages,
                )

        session["user"] = {
            "id":        user.id,
            "email":     user.email,
            "name":      user.name,
            "user_type": user.user_type,
        }
        return redirect(redirect_to)

    return render_template(
        "auth.html", redirect_to=redirect_to,
        erro=None, is_logged_in=session.get("user") is not None,
        query="", selected_category="", chat_messages=chat_messages,
    )


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    msg = data.get("message", "").strip()
    if not msg:
        return jsonify({"ok": False})
    user = session.get("user", {"name": "Visitante", "email": "?"})
    new_msg = {
        "id": str(len(chat_messages) + 1),
        "user": user["name"],
        "avatar": user["name"][0].upper(),
        "message": msg,
        "time": __import__("datetime").datetime.now().strftime("%H:%M"),
    }
    chat_messages.append(new_msg)
    return jsonify({"ok": True, "message": new_msg})


@app.route("/submit_review", methods=["POST"])
def submit_review():
    """Save a patient review for a clinic."""
    user_sess = session.get("user")
    if not user_sess:
        return jsonify({"ok": False, "error": "Você precisa estar logado para avaliar."}), 401

    data = request.get_json(silent=True) or {}
    clinic_id = data.get("clinic_id")
    rating = data.get("rating")
    comment = (data.get("comment") or "").strip()

    # Validate
    if not clinic_id or not rating:
        return jsonify({"ok": False, "error": "Dados incompletos."}), 400
    try:
        rating = int(rating)
        clinic_id = int(clinic_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Dados inválidos."}), 400

    if rating < 1 or rating > 5:
        return jsonify({"ok": False, "error": "Nota deve ser de 1 a 5."}), 400

    clinic = User.query.filter_by(id=clinic_id, user_type="CLINICA").first()
    if not clinic:
        return jsonify({"ok": False, "error": "Clínica não encontrada."}), 404

    if user_sess["id"] == clinic_id:
        return jsonify({"ok": False, "error": "Você não pode avaliar sua própria clínica."}), 403

    # Limit comment length
    if len(comment) > 1000:
        comment = comment[:1000]

    review = Review(
        user_id=user_sess["id"],
        clinic_id=clinic_id,
        rating=rating,
        comment=comment if comment else None,
    )
    db.session.add(review)
    db.session.commit()

    avg, count = Review.avg_rating_for_clinic(clinic_id)

    return jsonify({
        "ok": True,
        "review": {
            "id": review.id,
            "user_name": user_sess.get("name", "Paciente"),
            "rating": review.rating,
            "comment": review.comment or "",
            "created_at": review.created_at.strftime("%d/%m/%Y") if review.created_at else "",
        },
        "avg_rating": avg,
        "review_count": count,
    })


@app.route("/perfil/clinica/<int:clinic_id>")
def clinic_profile_view(clinic_id):
    clinic = User.query.filter_by(id=clinic_id, user_type="CLINICA").first()
    if not clinic:
        return render_template("404.html"), 404
    services    = ClinicService.query.filter_by(clinic_id=clinic_id, active=True).order_by(ClinicService.created_at.desc()).all()
    specialties = sorted({s.specialty for s in services if s.specialty})
    doctors     = sorted({s.doctor_name for s in services if s.doctor_name})
    avg_rating, review_count = Review.avg_rating_for_clinic(clinic_id)
    reviews = Review.query.filter_by(clinic_id=clinic_id).order_by(Review.created_at.desc()).limit(20).all()
    return render_template(
        "clinic_profile_view.html",
        clinic=clinic,
        services=services,
        specialties=specialties,
        doctors=doctors,
        avg_rating=avg_rating,
        review_count=review_count,
        reviews=reviews,
        is_logged_in=session.get("user") is not None,
        query="",
        selected_category="",
        chat_messages=chat_messages,
    )


@app.route("/api/mensagens/<int:other_user_id>", methods=["GET"])
def api_mensagens_get(other_user_id):
    """Returns all messages between the current logged-in user and other_user_id."""
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    user_id = session["user"]["id"]
    msgs = (
        Mensagem.query
        .filter(
            or_(
                and_(Mensagem.sender_id == user_id,      Mensagem.receiver_id == other_user_id),
                and_(Mensagem.sender_id == other_user_id, Mensagem.receiver_id == user_id),
            )
        )
        .order_by(Mensagem.timestamp)
        .all()
    )
    # Mark incoming unread messages as read
    unread = [m for m in msgs if m.receiver_id == user_id and not m.lido]
    if unread:
        for m in unread:
            m.lido = True
        db.session.commit()
    return jsonify([
        {
            "id":        m.id,
            "sender_id": m.sender_id,
            "conteudo":  m.conteudo,
            "timestamp": m.timestamp.strftime("%H:%M") if m.timestamp else "",
            "from_self": m.sender_id == user_id,
        }
        for m in msgs
    ])


@app.route("/api/mensagens/<int:other_user_id>", methods=["POST"])
def api_mensagens_post(other_user_id):
    """Saves a message from the current user to other_user_id."""
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    data     = request.get_json(silent=True) or {}
    conteudo = (data.get("conteudo") or "").strip()
    if not conteudo or len(conteudo) > 1000:
        return jsonify({"error": "Invalid message"}), 400
    user_id  = session["user"]["id"]
    other    = User.query.get(other_user_id)
    if not other:
        return jsonify({"error": "User not found"}), 404

    # Determine clinic/patient sides and check if conversation is encerrada
    user_obj = User.query.get(user_id)
    if user_obj and other:
        if user_obj.is_clinic and other.user_type == User.USER_TYPE_CLIENT:
            clinic_id_c, patient_id_c = user_id, other_user_id
        elif other.is_clinic and user_obj.user_type == User.USER_TYPE_CLIENT:
            clinic_id_c, patient_id_c = other_user_id, user_id
        else:
            clinic_id_c = patient_id_c = None
        if clinic_id_c:
            conv = ChatConversa.query.filter_by(
                clinic_id=clinic_id_c, patient_id=patient_id_c
            ).first()
            if conv and conv.status == ChatConversa.STATUS_ENCERRADA:
                return jsonify({"error": "Chat encerrado"}), 403

    msg = Mensagem(sender_id=user_id, receiver_id=other_user_id, conteudo=conteudo)
    db.session.add(msg)
    db.session.commit()
    return jsonify({"ok": True, "id": msg.id, "timestamp": msg.timestamp.strftime("%H:%M") if msg.timestamp else ""})


@app.route("/api/chat/with/<int:patient_id>", methods=["GET"])
def api_chat_with_patient(patient_id):
    """Clinic-only: open / initialise a conversation with a patient.

    Returns the ChatConversa id, status, full message history,
    the patient's last booked service and marks incoming messages as read.
    """
    user = session.get("user")
    if not user or user.get("user_type") != User.USER_TYPE_CLINIC:
        return jsonify({"error": "Unauthorized"}), 403

    clinic_id = user["id"]
    patient   = User.query.filter_by(id=patient_id, user_type=User.USER_TYPE_CLIENT).first()
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    # Get-or-create conversation record
    conversa = ChatConversa.query.filter_by(
        clinic_id=clinic_id, patient_id=patient_id
    ).first()
    if not conversa:
        conversa = ChatConversa(
            clinic_id=clinic_id, patient_id=patient_id,
            status=ChatConversa.STATUS_ATIVA,
        )
        db.session.add(conversa)
        db.session.commit()

    # Fetch full message history
    msgs = (
        Mensagem.query
        .filter(
            or_(
                and_(Mensagem.sender_id == clinic_id,  Mensagem.receiver_id == patient_id),
                and_(Mensagem.sender_id == patient_id, Mensagem.receiver_id == clinic_id),
            )
        )
        .order_by(Mensagem.timestamp)
        .all()
    )

    # Mark patient messages as read
    unread = [m for m in msgs if m.sender_id == patient_id and not m.lido]
    if unread:
        for m in unread:
            m.lido = True
        db.session.commit()

    # Last service the patient booked with this clinic
    ultimo_appt = (
        Appointment.query
        .filter_by(clinic_id=clinic_id, user_id=patient_id)
        .order_by(Appointment.created_at.desc())
        .first()
    )
    ultimo_servico = (
        ultimo_appt.service.title if ultimo_appt and ultimo_appt.service else None
    )

    return jsonify({
        "chat_id":        conversa.id,
        "status":         conversa.status,
        "patient_name":   patient.name,
        "ultimo_servico": ultimo_servico,
        "messages": [
            {
                "id":        m.id,
                "conteudo":  m.conteudo,
                "from_self": m.sender_id == clinic_id,
                "timestamp": m.timestamp.strftime("%d/%m %H:%M") if m.timestamp else "",
            }
            for m in msgs
        ],
    })


@app.route("/chat/encerrar/<int:chat_id>", methods=["POST"])
def encerrar_chat(chat_id):
    """Clinic-only: close (encerrar) an active conversation."""
    user = session.get("user")
    if not user or user.get("user_type") != User.USER_TYPE_CLINIC:
        return jsonify({"error": "Unauthorized"}), 403

    conversa = ChatConversa.query.filter_by(
        id=chat_id, clinic_id=user["id"]
    ).first()
    if not conversa:
        return jsonify({"error": "Not found"}), 404

    if conversa.status != ChatConversa.STATUS_ENCERRADA:
        import datetime as _dt
        conversa.status       = ChatConversa.STATUS_ENCERRADA
        conversa.encerrada_em = _dt.datetime.utcnow()
        db.session.commit()

    return jsonify({"ok": True, "status": "encerrada"})


@app.route("/api/listings")
def api_listings():
    query = request.args.get("q", "")
    category = request.args.get("category", "")
    services = filter_listings(query, category if category else None)
    return jsonify([
        {
            "id":          s.id,
            "title":       s.title,
            "specialty":   s.specialty,
            "doctor_name": s.doctor_name,
            "price":       s.price,
            "description": s.description,
            "active":      s.active,
        }
        for s in services
    ])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
