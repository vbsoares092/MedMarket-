from flask import Blueprint, session, redirect, render_template, request, jsonify
from App.database import db
from App.models import User, ClinicService, Disponibilidade, Appointment
from App.utils.security import login_required_patient
from datetime import datetime as _dt

anuncios = Blueprint("anuncios", __name__)


def _current_user():
    """Return the DB User for the active session, or None."""
    uid = (session.get("user") or {}).get("id")
    return User.query.get(uid) if uid else None


# Verificação de pré-requisitos → redireciona para o calendário
@anuncios.route("/iniciar-agendamento/<listing_id>")
def checkout_step(listing_id):
    # 1. Verificar login pela sessão (sem pedir senha novamente)
    if not session.get("user"):
        return redirect(f"/auth?redirect=/iniciar-agendamento/{listing_id}")

    # 2. Bloquear contas de Clínica — devolver à página do serviço com aviso
    user_type = (session.get("user") or {}).get("user_type", "")
    if user_type == "CLINICA":
        return redirect(
            f"/listing/{listing_id}?aviso=clinic_blocked"
        )

    # 3. Verificar CPF diretamente no banco — redireciona apenas se estiver vazio
    db_user = _current_user()
    if not db_user or not db_user.cpf:
        return redirect(
            f"/perfil?aviso=cpf&redirect=/iniciar-agendamento/{listing_id}"
        )

    # 4. CPF já cadastrado → vai direto ao calendário
    return redirect(f"/calendario/{listing_id}")


# Página do calendário de agendamento
@anuncios.route("/calendario/<int:listing_id>")
@login_required_patient
def calendario(listing_id):
    listing = ClinicService.query.filter_by(id=listing_id, active=True).first()
    if not listing:
        return render_template("404.html"), 404

    # Build a set of ISO dates that have at least one available slot
    rows = (
        Disponibilidade.query
        .filter_by(service_id=listing_id, status=True)
        .with_entities(Disponibilidade.data)
        .distinct()
        .all()
    )
    available_dates = sorted({r.data.isoformat() for r in rows})

    return render_template(
        "calendar.html",
        anuncio=listing,
        is_logged_in=True,
        available_dates=available_dates,
    )


# API — slots disponíveis para uma data específica (consumida pelo calendar.html)
@anuncios.route("/api/disponibilidade/<int:service_id>")
def api_disponibilidade(service_id):
    """Return available time slots from the Disponibilidade table.

    Query param: ?date=YYYY-MM-DD
    Returns JSON:
      {
        "slots": [
          {"horario": "08:00", "preco_efetivo": 150.0, "turno": "manha"},
          ...
        ]
      }
    """
    data_str = request.args.get("date", "")
    try:
        data = _dt.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"slots": []})

    service = ClinicService.query.get(service_id)
    base_price = service.price if service else 0.0

    slots = (
        Disponibilidade.query
        .filter_by(service_id=service_id, data=data, status=True)
        .order_by(Disponibilidade.horario)
        .all()
    )

    def _turno(horario: str) -> str:
        h = int(horario[:2])
        if 6 <= h < 12:  return "manha"
        if 12 <= h < 18: return "tarde"
        if 18 <= h < 22: return "noite"
        return "madrugada"          # 22-06

    return jsonify({
        "slots": [
            {
                "horario":       s.horario,
                "preco_padrao":  base_price,
                "valor_ajuste":  s.valor_ajuste,
                "preco_efetivo": s.preco if s.preco is not None else base_price,
                "turno":         _turno(s.horario),
            }
            for s in slots
        ]
    })


# Recebe data/hora e processa o agendamento
@anuncios.route("/pagamento", methods=["POST"])
def pagamento():
    # Block clinic accounts — they must never execute bookings
    user_type = (session.get("user") or {}).get("user_type", "")
    if user_type == "CLINICA":
        return jsonify({
            "ok": False,
            "msg": "Contas de Clínica não podem realizar agendamentos. Por favor, use uma conta de Paciente."
        }), 403

    listing_id = request.form.get("listing_id", type=int)
    data_str   = request.form.get("data")
    horario    = request.form.get("horario")

    listing = ClinicService.query.filter_by(id=listing_id, active=True).first() if listing_id else None
    if not listing or not data_str or not horario:
        return jsonify({"ok": False, "msg": "Dados inválidos"}), 400

    # Validate and reserve the slot atomically
    try:
        data = _dt.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"ok": False, "msg": "Data inválida"}), 400

    slot = Disponibilidade.query.filter_by(
        service_id=listing_id, data=data, horario=horario, status=True
    ).first()
    if not slot:
        return jsonify({"ok": False, "msg": "Este horário não está mais disponível. Por favor, escolha outro."}), 409

    # Identify the patient making the booking
    patient = _current_user()
    patient_id = patient.id if patient else None

    # Mark slot as reserved and attach the patient
    slot.status     = False
    slot.patient_id = patient_id

    # Create an Appointment record for full traceability
    appointment = Appointment(
        service_id       = listing.id,
        clinic_id        = listing.clinic_id,
        user_id          = patient_id,
        date             = data_str,
        time_slot        = horario,
        status           = Appointment.STATUS_CONFIRMED,
        status_pagamento = 'aprovado',
    )
    db.session.add(appointment)
    db.session.commit()

    return jsonify({
        "ok": True,
        "msg": "Agendamento confirmado! Você será redirecionado.",
        "redirect": f"/listing/{listing_id}",
    })

