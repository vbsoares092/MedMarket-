import os
import json
import math
from dotenv import load_dotenv
load_dotenv()  # Load .env before any os.environ.get calls
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from sqlalchemy import func, or_, and_
from App.routes.anuncios import anuncios
from App.routes.auth import auth as auth_bp
from App.routes.clinic import clinic_bp
from App.routes.prontuario import prontuario_bp
from App.database import db
from App.models import User, ClinicProfile, ClinicService, Mensagem, ChatConversa, Appointment, Prontuario, DocumentoPaciente, Review, GlobalMensagem, PostAtendimento, SPECIALTY_EXAM_MAP
from App.utils.security import hash_password, verify_password, sanitize_cpf

# ── Static category icon map (specialties come from DB; icons are a UI hint) ──
_CATEGORY_ICONS = {
    "Clínica Geral":  "stethoscope",
    "Cardiologia":    "heart",
    "Neurologia":     "brain",
    "Ortopedia":      "bone",
    "Pediatria":      "baby",
    "Oftalmologia":   "eye",
    "Farmácia":       "pill",
    "Laboratório":    "flask-conical",
    "Equipamentos":   "monitor",
    "Emergência":     "siren",
    "Diagnóstico":    "scan-line",
}
_DEFAULT_ICON = "more-horizontal"

# ── Precomputed lat/lng for major Brazilian cities (used as fallback for map) ─
_CITY_COORDS: dict[str, tuple[float, float]] = {
    # State capitals
    "salvador":             (-12.9714, -38.5014),
    "são paulo":            (-23.5558, -46.6396),
    "sao paulo":            (-23.5558, -46.6396),
    "rio de janeiro":       (-22.9068, -43.1729),
    "brasília":             (-15.7942, -47.8825),
    "brasilia":             (-15.7942, -47.8825),
    "manaus":               (-3.1190,  -60.0217),
    "belém":                (-1.4558,  -48.5039),
    "belem":                (-1.4558,  -48.5039),
    "fortaleza":            (-3.7172,  -38.5433),
    "recife":               (-8.0476,  -34.8770),
    "porto alegre":         (-30.0346, -51.2177),
    "curitiba":             (-25.4290, -49.2671),
    "goiânia":              (-16.6869, -49.2648),
    "goiania":              (-16.6869, -49.2648),
    "belo horizonte":       (-19.9191, -43.9386),
    "maceió":               (-9.6498,  -35.7089),
    "maceio":               (-9.6498,  -35.7089),
    "natal":                (-5.7945,  -35.2110),
    "teresina":             (-5.0892,  -42.8019),
    "campo grande":         (-20.4697, -54.6201),
    "cuiabá":               (-15.6014, -56.0979),
    "cuiaba":               (-15.6014, -56.0979),
    "porto velho":          (-8.7612,  -63.9004),
    "rio branco":           (-9.9754,  -67.8249),
    "macapá":               (0.0349,   -51.0694),
    "macapa":               (0.0349,   -51.0694),
    "boa vista":            (2.8235,   -60.6758),
    "palmas":               (-10.1689, -48.3317),
    "são luís":             (-2.5387,  -44.2829),
    "sao luis":             (-2.5387,  -44.2829),
    "florianópolis":        (-27.5954, -48.5480),
    "florianopolis":        (-27.5954, -48.5480),
    "aracaju":              (-10.9472, -37.0731),
    "joão pessoa":          (-7.1195,  -34.8450),
    "joao pessoa":          (-7.1195,  -34.8450),
    "vitória":              (-20.3155, -40.3128),
    "vitoria":              (-20.3155, -40.3128),
    # Major non-capital cities
    "campinas":             (-22.9056, -47.0608),
    "guarulhos":            (-23.4543, -46.5333),
    "osasco":               (-23.5329, -46.7917),
    "santo andré":          (-23.6638, -46.5340),
    "santo andre":          (-23.6638, -46.5340),
    "sorocaba":             (-23.5015, -47.4526),
    "ribeirão preto":       (-21.1699, -47.8099),
    "ribeirao preto":       (-21.1699, -47.8099),
    "são josé dos campos":  (-23.1791, -45.8869),
    "sao jose dos campos":  (-23.1791, -45.8869),
    "niterói":              (-22.8833, -43.1036),
    "niteroi":              (-22.8833, -43.1036),
    "duque de caxias":      (-22.7892, -43.3134),
    "nova iguaçu":          (-22.7594, -43.4511),
    "nova iguacu":          (-22.7594, -43.4511),
    "contagem":             (-19.9319, -44.0533),
    "uberlândia":           (-18.9186, -48.2772),
    "uberlandia":           (-18.9186, -48.2772),
    "feira de santana":     (-12.2664, -38.9663),
    "camaçari":             (-12.6998, -38.3238),
    "camacari":             (-12.6998, -38.3238),
    "juazeiro do norte":    (-7.2133,  -39.3153),
    "caucaia":              (-3.7376,  -38.6530),
    "aparecida de goiânia": (-16.8234, -49.2459),
    "aparecida de goiania": (-16.8234, -49.2459),
    "anápolis":             (-16.3281, -48.9529),
    "anapolis":             (-16.3281, -48.9529),
    "joinville":            (-26.3044, -48.8485),
    "blumenau":             (-26.9194, -49.0661),
    "londrina":             (-23.3045, -51.1696),
    "maringá":              (-23.4205, -51.9331),
    "maringa":              (-23.4205, -51.9331),
    "foz do iguaçu":        (-25.5469, -54.5882),
    "foz do iguacu":        (-25.5469, -54.5882),
    "caxias do sul":        (-29.1681, -51.1793),
    "pelotas":              (-31.7724, -52.3434),
    "santarém":             (-2.4446,  -54.7083),
    "santarem":             (-2.4446,  -54.7083),
    "sobral":               (-3.6880,  -40.3494),
    "mossoró":              (-5.1877,  -37.3446),
    "mossoro":              (-5.1877,  -37.3446),
    "petrolina":            (-9.3986,  -40.5083),
    "caruaru":              (-8.2761,  -35.9753),
    "montes claros":        (-16.7282, -43.8618),
    "juiz de fora":         (-21.7642, -43.3503),
    "imperatriz":           (-5.5260,  -47.4841),
    "bauru":                (-22.3246, -49.0691),
    "piracicaba":           (-22.7253, -47.6492),
    "taubaté":              (-23.0260, -45.5558),
    "taubate":              (-23.0260, -45.5558),
    "são bernardo do campo":(-23.6939, -46.5650),
    "sao bernardo do campo":(-23.6939, -46.5650),
    "são josé":             (-27.5944, -48.6353),
    "sao jose":             (-27.5944, -48.6353),
    "belford roxo":         (-22.7644, -43.3995),
    "diadema":              (-23.6859, -46.6215),
    "mauá":                 (-23.6678, -46.4609),
    "maua":                 (-23.6678, -46.4609),
    "betim":                (-19.9681, -44.1983),
    "cascavel":             (-24.9555, -53.4552),
    "vila velha":           (-20.3297, -40.2922),
    "canoas":               (-29.9170, -51.1839),
    "santos":               (-23.9618, -46.3322),
    "mogi das cruzes":      (-23.5222, -46.1875),
    "jundiaí":              (-23.1864, -46.8964),
    "jundiai":              (-23.1864, -46.8964),
}



def _load_categories():
    """Return category list built from distinct specialties in the DB.

    Known specialties get a specific icon; any specialty not in the map
    uses the default icon.  The list is deduplicated and sorted.
    """
    rows = (
        db.session.query(ClinicService.specialty)
        .filter(ClinicService.active == True, ClinicService.specialty.isnot(None))
        .distinct()
        .all()
    )
    specialties = sorted({r[0].strip() for r in rows if r[0] and r[0].strip()})
    return [
        {"name": s, "icon": _CATEGORY_ICONS.get(s, _DEFAULT_ICON)}
        for s in specialties
    ]


def _load_locations():
    """Return sorted list of distinct 'Cidade, UF' strings from active services."""
    rows = (
        db.session.query(ClinicService.cidade, ClinicService.estado)
        .filter(
            ClinicService.active == True,
            ClinicService.cidade.isnot(None),
            ClinicService.cidade != "",
        )
        .distinct()
        .all()
    )
    locs = set()
    for cidade, estado in rows:
        c = cidade.strip() if cidade else ""
        e = estado.strip().upper() if estado else ""
        if c:
            locs.add(f"{c}, {e}" if e else c)
    return sorted(locs)


def _load_global_chat(limit: int = 50):
    """Return the most recent global chat messages from the DB."""
    msgs = (
        GlobalMensagem.query
        .order_by(GlobalMensagem.timestamp.desc())
        .limit(limit)
        .all()
    )
    msgs.reverse()   # oldest first for display
    return [
        {
            "id":      m.id,
            "user":    m.user_name,
            "avatar":  m.avatar,
            "message": m.conteudo,
            "time":    m.timestamp.strftime("%H:%M") if m.timestamp else "",
        }
        for m in msgs
    ]

# ── App factory ───────────────────────────────────────────────────────────────
_basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "medmarket-secret-key-change-me")

_default_db = "sqlite:///" + os.path.join(_basedir, "instance", "medmarket.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", _default_db)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit
app.config["GOOGLE_MAPS_KEY"] = os.environ.get("Maps_API_KEY", "")

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
        ("clinic_services", "lat",                 "ALTER TABLE clinic_services ADD COLUMN lat FLOAT"),
        ("clinic_services", "lng",                 "ALTER TABLE clinic_services ADD COLUMN lng FLOAT"),
        ("appointments", "status_pagamento",       "ALTER TABLE appointments ADD COLUMN status_pagamento VARCHAR(20) NOT NULL DEFAULT 'pendente'"),
        ("prontuarios",  "observacoes",             "ALTER TABLE prontuarios ADD COLUMN observacoes TEXT"),
        ("clinic_profiles", "bio",            "ALTER TABLE clinic_profiles ADD COLUMN bio TEXT"),
        ("clinic_profiles", "avatar_url",     "ALTER TABLE clinic_profiles ADD COLUMN avatar_url VARCHAR(255)"),
        ("clinic_profiles", "banner_url",     "ALTER TABLE clinic_profiles ADD COLUMN banner_url VARCHAR(255)"),
        ("clinic_profiles", "cep",            "ALTER TABLE clinic_profiles ADD COLUMN cep VARCHAR(9)"),
        ("clinic_profiles", "especialidades", "ALTER TABLE clinic_profiles ADD COLUMN especialidades VARCHAR(500)"),
        ("clinic_services", "service_category", "ALTER TABLE clinic_services ADD COLUMN service_category VARCHAR(20) NOT NULL DEFAULT 'consulta'"),
        ("clinic_services", "exam_type",          "ALTER TABLE clinic_services ADD COLUMN exam_type VARCHAR(30)"),
        ("clinic_services", "exam_orientations",   "ALTER TABLE clinic_services ADD COLUMN exam_orientations TEXT"),
    ]
    with db.engine.connect() as _conn:
        for _table, _col, _sql in _migrations:
            _cols = [r[1] for r in _conn.execute(text(f"PRAGMA table_info({_table})")).fetchall()]
            if _col not in _cols:
                _conn.execute(text(_sql))
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


# ── Well-known exam keyword list for smart search boost ─────────────────────
_EXAM_KEYWORDS: set[str] = {
    "hemograma", "glicemia", "colesterol", "triglicerides", "tsh", "t4",
    "urina", "fezes", "vitamina", "ferritina", "psa", "ca125", "cea",
    "raio-x", "raio x", "rx", "ultrassom", "ultrassonografia", "eco",
    "ecocardiograma", "eletrocardiograma", "ecg", "eletroencefalograma",
    "tomografia", "ressonância", "ressonancia", "pet scan", "cintilografia",
    "mamografia", "densitometria", "espirometria", "audiometria",
    "papanicolau", "biopsia", "biópsia", "endoscopia", "colonoscopia",
    "exame", "exames", "laboratorial", "laboratorio", "laboratório",
    "sangue", "check-up", "checkup", "hba1c", "pcr", "vhs",
    "eletroneuromiografia", "holter", "mapa",
}


def _is_exam_query(q: str) -> bool:
    """Return True if the search term is likely an exam name."""
    return any(kw in q.lower() for kw in _EXAM_KEYWORDS)


def filter_listings(query="", category=None, max_price=None,
                    date_from=None, date_to=None, location=None,
                    service_type=None):
    q_obj = ClinicService.query.filter_by(active=True)
    if query:
        q_obj = q_obj.filter(
            (ClinicService.title.ilike(f"%{query}%")) |
            (ClinicService.description.ilike(f"%{query}%")) |
            (ClinicService.specialty.ilike(f"%{query}%"))
        )
    if category:
        q_obj = q_obj.filter(ClinicService.specialty.ilike(category.strip()))
    if service_type in ('consulta', 'exame', 'pacote'):
        q_obj = q_obj.filter(ClinicService.service_category == service_type)
    if location:
        # location comes as "Cidade, UF" or just "Cidade"
        parts = [p.strip() for p in location.split(",", 1)]
        cidade = parts[0]
        estado = parts[1] if len(parts) > 1 else None
        q_obj = q_obj.filter(ClinicService.cidade.ilike(f"%{cidade}%"))
        if estado:
            # Only exclude services that have an estado set AND it doesn't match;
            # services with no estado set are kept (they may not have state data)
            from sqlalchemy import or_ as _or
            q_obj = q_obj.filter(
                _or(
                    ClinicService.estado.ilike(f"%{estado}%"),
                    ClinicService.estado.is_(None),
                    ClinicService.estado == ""
                )
            )
    if max_price is not None:
        q_obj = q_obj.filter(ClinicService.price <= max_price)
    if date_from or date_to:
        from App.models import Disponibilidade
        q_obj = q_obj.filter(
            ClinicService.id.in_(
                db.session.query(Disponibilidade.service_id)
                .filter(Disponibilidade.status == True)
                .filter(
                    *([Disponibilidade.data >= date_from] if date_from else []),
                    *([Disponibilidade.data <= date_to]   if date_to   else []),
                )
            )
        )
    results = q_obj.order_by(ClinicService.created_at.desc()).all()
    # Smart boost: if query looks like an exam term and no explicit type filter,
    # float exam/pacote results to the top.
    if query and _is_exam_query(query) and not service_type:
        exams  = [s for s in results if s.service_category in ('exame', 'pacote')]
        others = [s for s in results if s.service_category not in ('exame', 'pacote')]
        return exams + others
    return results


def _build_map_points(listings: list) -> str:
    """Return a JSON string with lat/lng + metadata for each mappable listing."""
    points = []
    for svc in listings:
        lat, lng = svc.lat, svc.lng
        if not (lat and lng) and svc.cidade:
            city_key = svc.cidade.strip().lower().split(",")[0].strip()
            coords = _CITY_COORDS.get(city_key)
            if coords:
                lat, lng = coords
        if lat and lng:
            cname = (
                svc.clinic.clinic_profile.razao_social
                if svc.clinic and svc.clinic.clinic_profile
                else (svc.clinic.name if svc.clinic else svc.title)
            )
            points.append({
                "id":          svc.id,
                "lat":         lat,
                "lng":         lng,
                "nome":        cname or svc.title,
                "title":       svc.title,
                "preco":       int(svc.price or 0),
                "especialidade": svc.specialty or "",
                "img_url":     url_for("static", filename=svc.imagem_url) if svc.imagem_url else "",
                "tipo":        svc.service_category or "consulta",
            })
    return json.dumps(points)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km (Haversine formula)."""
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _sort_by_proximity_and_price(listings: list, center: tuple) -> list:
    """Sort listings nearest-first; ties broken by cheapest price.

    Listings whose coordinates cannot be resolved are pushed to the end.
    The center argument is (lat, lng) of the searched city.
    """
    clat, clng = center

    def _key(svc):
        lat, lng = svc.lat, svc.lng
        if not (lat and lng) and svc.cidade:
            city_key = svc.cidade.strip().lower().split(",")[0].strip()
            coords = _CITY_COORDS.get(city_key)
            if coords:
                lat, lng = coords
        dist  = _haversine_km(clat, clng, lat, lng) if (lat and lng) else float("inf")
        price = svc.price if svc.price is not None else float("inf")
        return (dist, price)

    return sorted(listings, key=_key)


def _resolve_location_center(location_raw: str, query: str = "") -> str:
    """Return JSON {lat, lng} for the searched city/query term, or 'null'."""
    raw = location_raw or query
    if not raw:
        return "null"
    key = raw.split(",")[0].strip().lower()
    coords = _CITY_COORDS.get(key)
    if coords:
        return json.dumps({"lat": coords[0], "lng": coords[1]})
    return "null"


@app.route("/")
def index():
    query = request.args.get("q", "")
    category = request.args.get("category", "")
    location_raw = request.args.get("location", "").strip()
    max_price_raw = request.args.get("max_price", "").strip()
    date_from = request.args.get("date_from", "").strip() or None
    date_to   = request.args.get("date_to", "").strip()   or None

    # ── GPS user coordinates (validated) ─────────────────────────────────────
    user_lat: float | None = None
    user_lng: float | None = None
    _ulat_raw = request.args.get("user_lat", "").strip()
    _ulng_raw = request.args.get("user_lng", "").strip()
    if _ulat_raw and _ulng_raw:
        try:
            _lat = float(_ulat_raw)
            _lng = float(_ulng_raw)
            if -90.0 <= _lat <= 90.0 and -180.0 <= _lng <= 180.0:
                user_lat, user_lng = _lat, _lng
        except ValueError:
            pass

    has_filters = bool(location_raw or category or query or max_price_raw or date_from or date_to or user_lat is not None)

    # ── Session-based filter persistence ──────────────────────────────────────
    # ?home=1 → explicit "go home" intent; clear saved search
    if request.args.get("home") == "1":
        session.pop("search_last_url", None)
    elif has_filters:
        # Save current search URL so the listing detail can link back to it
        qs = request.query_string.decode("utf-8")
        session["search_last_url"] = "/?" + qs
    elif not request.args:
        # No params at all and no explicit home flag → restore last search
        saved = session.get("search_last_url")
        if saved:
            return redirect(saved)

    max_price = None
    if max_price_raw:
        try:
            max_price = float(max_price_raw)
        except ValueError:
            pass

    service_type = request.args.get("tipo", "").strip() or None

    # When GPS coords are active, skip city-text filter (proximity sort handles it)
    _location_filter = None if user_lat is not None else (location_raw or None)

    filtered = filter_listings(
        query,
        category if category else None,
        max_price=max_price,
        date_from=date_from,
        date_to=date_to,
        location=_location_filter,
        service_type=service_type,
    )

    # ── Proximity + price sort — GPS coords take precedence over city center ──
    if user_lat is not None and user_lng is not None:
        _center: tuple | None = (user_lat, user_lng)
    else:
        _loc_key = location_raw.split(",")[0].strip().lower() if location_raw else ""
        _center  = _CITY_COORDS.get(_loc_key) if _loc_key else None
    if _center and filtered:
        filtered = _sort_by_proximity_and_price(filtered, _center)

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

    # Map is shown whenever the user has any active search term or GPS is active
    search_performed = bool(location_raw or category or query or user_lat is not None)

    # Map center: prefer GPS coords, then city lookup
    if user_lat is not None and user_lng is not None:
        _loc_center_json = json.dumps({"lat": user_lat, "lng": user_lng})
    else:
        _loc_center_json = _resolve_location_center(location_raw, query)

    return render_template(
        "index.html",
        listings=filtered,
        categories=_load_categories(),
        locations=_load_locations(),
        query=query,
        selected_category=category,
        chat_messages=_load_global_chat(),
        is_logged_in=session.get("user") is not None,
        partners=partners,
        banner_listings=banner_listings,
        map_points_json=_build_map_points(filtered),
        location_center_json=_loc_center_json,
        search_performed=search_performed,
        google_maps_key=app.config.get("GOOGLE_MAPS_KEY", ""),
        user_lat=user_lat,
        user_lng=user_lng,
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
    back_url = session.get("search_last_url", "/")
    return render_template(
        "listing_detail.html",
        listing=listing,
        is_logged_in=bool(_sess),
        current_user_id=_sess.get("id"),
        current_user_type=_sess.get("user_type", ""),
        min_price=min_price,
        has_discount=has_discount,
        back_url=back_url,
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
        chat_messages=_load_global_chat(),
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
                    chat_messages=_load_global_chat(),
                )
            if not email or len(password) < 6:
                return render_template(
                    "auth.html", redirect_to=redirect_to,
                    erro="Email e senha (mín. 6 caracteres) são obrigatórios.",
                    is_logged_in=False, query="", selected_category="",
                    chat_messages=_load_global_chat(),
                )
            if User.query.filter_by(email=email).first():
                return render_template(
                    "auth.html", redirect_to=redirect_to,
                    erro="Este e-mail já está cadastrado.",
                    is_logged_in=False, query="", selected_category="",
                    chat_messages=_load_global_chat(),
                )
            if User.query.filter_by(cpf=cpf).first():
                return render_template(
                    "auth.html", redirect_to=redirect_to,
                    erro="Este CPF já está cadastrado.",
                    is_logged_in=False, query="", selected_category="",
                    chat_messages=_load_global_chat(),
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
                    chat_messages=_load_global_chat(),
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
        query="", selected_category="", chat_messages=_load_global_chat(),
    )


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    msg = (data.get("message") or "").strip()
    if not msg or len(msg) > 500:
        return jsonify({"ok": False})
    user = session.get("user", {})
    user_name = (user.get("name") or "Visitante")
    avatar    = user_name[0].upper() if user_name else "?"
    user_id   = user.get("id")
    new_entry = GlobalMensagem(
        user_id   = user_id,
        user_name = user_name,
        avatar    = avatar,
        conteudo  = msg,
    )
    db.session.add(new_entry)
    db.session.commit()
    return jsonify({
        "ok": True,
        "message": {
            "id":      new_entry.id,
            "user":    user_name,
            "avatar":  avatar,
            "message": msg,
            "time":    new_entry.timestamp.strftime("%H:%M"),
        },
    })


@app.route("/perfil/clinica/<int:clinic_id>")
def clinic_profile_view(clinic_id):
    clinic = User.query.filter_by(id=clinic_id, user_type="CLINICA").first()
    if not clinic:
        return render_template("404.html"), 404
    services    = ClinicService.query.filter_by(clinic_id=clinic_id, active=True).order_by(ClinicService.created_at.desc()).all()
    consultas   = [s for s in services if (s.service_category or 'consulta') == 'consulta']
    exames      = [s for s in services if s.service_category == 'exame']
    specialties = sorted({s.specialty for s in services if s.specialty})
    doctors     = sorted({s.doctor_name for s in services if s.doctor_name})
    # Build complementary exam suggestions from specialty map
    _seen: set[str] = set()
    suggested_exams: list[str] = []
    for spec in specialties:
        for exam in SPECIALTY_EXAM_MAP.get(spec, []):
            if exam not in _seen:
                _seen.add(exam)
                suggested_exams.append(exam)
    return render_template(
        "clinic_profile_view.html",
        clinic=clinic,
        services=services,
        consultas=consultas,
        exames=exames,
        specialties=specialties,
        doctors=doctors,
        suggested_exams=suggested_exams[:10],
        is_logged_in=session.get("user") is not None,
        query="",
        selected_category="",
        chat_messages=_load_global_chat(),
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

@app.route("/api/review", methods=["POST"])
def api_review():
    """Submit a rating review for a service.

    Only authenticated patients who have had a *completed* appointment
    for the service may leave a review. Duplicate reviews are rejected.
    """
    user_sess = session.get("user")
    if not user_sess:
        return jsonify({"ok": False, "msg": "Faça login para avaliar."}), 401

    if user_sess.get("user_type") == "CLINICA":
        return jsonify({"ok": False, "msg": "Clínicas não podem deixar avaliações."}), 403

    data       = request.get_json(silent=True) or {}
    service_id = data.get("service_id")
    try:
        rating = float(data.get("rating", 0))
    except (ValueError, TypeError):
        rating = 0.0

    if not service_id or not (1.0 <= rating <= 5.0):
        return jsonify({"ok": False, "msg": "Dados inválidos."}), 400

    service = ClinicService.query.filter_by(id=service_id, active=True).first()
    if not service:
        return jsonify({"ok": False, "msg": "Serviço não encontrado."}), 404

    patient_id = user_sess["id"]

    # Ensure the patient has completed at least one appointment for this service
    completed = Appointment.query.filter_by(
        service_id=service_id,
        user_id=patient_id,
        status=Appointment.STATUS_COMPLETED,
    ).first()
    if not completed:
        return jsonify({
            "ok": False,
            "msg": "Você só pode avaliar serviços após uma consulta concluída.",
        }), 403

    # Prevent duplicate reviews
    existing = Review.query.filter_by(service_id=service_id, user_id=patient_id).first()
    if existing:
        return jsonify({"ok": False, "msg": "Você já avaliou este serviço."}), 409

    comentario = (data.get("comentario") or "").strip()[:500] or None
    review = Review(
        service_id=service_id,
        user_id=patient_id,
        rating=round(rating, 1),
        comentario=comentario,
    )
    db.session.add(review)
    db.session.commit()

    return jsonify({
        "ok":           True,
        "avg_rating":   service.avg_rating,
        "review_count": service.review_count,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
