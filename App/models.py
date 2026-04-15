from App.database import db


class User(db.Model):
    """Unified user model for both clients (CLIENTE) and clinics (CLINICA)."""
    __tablename__ = 'users'

    USER_TYPE_CLIENT = 'CLIENTE'
    USER_TYPE_CLINIC = 'CLINICA'

    id            = db.Column(db.Integer,     primary_key=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name          = db.Column(db.String(80),  nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    # CPF: clients only (11 raw digits)
    cpf           = db.Column(db.String(11),  unique=True, nullable=True)
    telefone      = db.Column(db.String(20),  nullable=True)   # e.g. "(11) 99999-9999"
    user_type     = db.Column(db.String(10),  nullable=False, default='CLIENTE')

    # 1:1 extended profile for CLINICA users
    clinic_profile = db.relationship(
        'ClinicProfile', back_populates='user',
        uselist=False, cascade='all, delete-orphan',
    )
    # Services owned by this clinic user
    services = db.relationship(
        'ClinicService',
        foreign_keys='ClinicService.clinic_id',
        backref='clinic',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )
    # Appointments booked *by* this user as a patient
    patient_appointments = db.relationship(
        'Appointment',
        foreign_keys='Appointment.user_id',
        backref='patient',
        lazy='dynamic',
    )
    # Documents uploaded by this user (patient)
    documentos = db.relationship(
        'DocumentoPaciente',
        foreign_keys='DocumentoPaciente.paciente_id',
        back_populates='paciente',
        lazy=True,
    )

    @property
    def is_clinic(self):
        return self.user_type == self.USER_TYPE_CLINIC

    def __repr__(self):
        return f'<User {self.email} [{self.user_type}]>'


class ClinicProfile(db.Model):
    """Company-specific data stored only for User with user_type='CLINICA'."""
    __tablename__ = 'clinic_profiles'

    id                = db.Column(db.Integer,     primary_key=True)
    user_id           = db.Column(db.Integer,     db.ForeignKey('users.id'), unique=True, nullable=False)
    razao_social      = db.Column(db.String(150), nullable=False)
    cnpj              = db.Column(db.String(14),  unique=True, nullable=False, index=True)
    crm_cro           = db.Column(db.String(30),  nullable=True)
    endereco          = db.Column(db.String(300),  nullable=True)
    cep               = db.Column(db.String(9),   nullable=True)
    document_filename = db.Column(db.String(255), nullable=True)
    bio               = db.Column(db.Text,        nullable=True)
    avatar_url        = db.Column(db.String(255), nullable=True)
    banner_url        = db.Column(db.String(255), nullable=True)
    especialidades    = db.Column(db.String(500), nullable=True)
    created_at        = db.Column(db.DateTime,    server_default=db.func.now())

    user = db.relationship('User', back_populates='clinic_profile')

    def __repr__(self):
        return f'<ClinicProfile {self.razao_social}>'


class ClinicService(db.Model):
    """Service/consultation listing created by a clinic user."""
    __tablename__ = 'clinic_services'

    id          = db.Column(db.Integer,     primary_key=True)
    clinic_id   = db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=False)
    title       = db.Column(db.String(150), nullable=False)
    doctor_name = db.Column(db.String(100), nullable=False)
    specialty   = db.Column(db.String(80),  nullable=False)
    price       = db.Column(db.Float,       nullable=False)
    description = db.Column(db.Text,        nullable=True)
    active      = db.Column(db.Boolean,     default=True)
    imagem_url  = db.Column(db.String(255),  nullable=True)   # relative path under static/
    logradouro       = db.Column(db.String(200),  nullable=True)
    numero           = db.Column(db.String(20),   nullable=True)
    complemento      = db.Column(db.String(100),  nullable=True)
    bairro           = db.Column(db.String(100),  nullable=True)
    cidade           = db.Column(db.String(100),  nullable=True)
    estado           = db.Column(db.String(2),    nullable=True)
    cep              = db.Column(db.String(9),    nullable=True)   # "00000-000"
    google_maps_link = db.Column(db.String(500),  nullable=True)
    rating           = db.Column(db.Float,        default=0)
    review_count     = db.Column(db.Integer,      default=0)
    tempo_resultado  = db.Column(db.String(50),   nullable=True)   # e.g. "24h", "Imediato"
    preparacao       = db.Column(db.Text,         nullable=True)   # e.g. "Jejum de 8h"
    created_at       = db.Column(db.DateTime,    server_default=db.func.now())

    @property
    def endereco_formatado(self) -> str:
        """Returns a clean, Google Maps-searchable address string."""
        parts = []
        if self.logradouro:
            linha = self.logradouro
            if self.numero:
                linha += ', ' + self.numero
            if self.complemento:
                linha += ', ' + self.complemento
            parts.append(linha)
        if self.bairro:
            parts.append(self.bairro)
        if self.cidade:
            linha = self.cidade
            if self.estado:
                linha += ' - ' + self.estado.upper()
            parts.append(linha)
        if self.cep:
            parts.append('CEP ' + self.cep)
        return ', '.join(parts)

    schedules        = db.relationship('ClinicSchedule', backref='service', lazy='dynamic',
                                       cascade='all, delete-orphan')
    appointments     = db.relationship('Appointment', backref='service', lazy='dynamic',
                                       foreign_keys='Appointment.service_id',
                                       cascade='all, delete-orphan')
    disponibilidades = db.relationship('Disponibilidade', backref='anuncio', lazy='dynamic',
                                       cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ClinicService {self.title}>'


class ClinicSchedule(db.Model):
    """Availability slot for a service on a given weekday.
    weekday: 0=Segunda … 6=Domingo (Python/ISO convention).
    """
    __tablename__ = 'clinic_schedules'

    id           = db.Column(db.Integer,   primary_key=True)
    service_id   = db.Column(db.Integer,   db.ForeignKey('clinic_services.id'), nullable=False)
    clinic_id    = db.Column(db.Integer,   db.ForeignKey('users.id'),           nullable=False)
    weekday      = db.Column(db.Integer,   nullable=False)   # 0–6
    start_time   = db.Column(db.String(5), nullable=False)   # "HH:MM"
    end_time     = db.Column(db.String(5), nullable=False)   # "HH:MM"
    slot_minutes = db.Column(db.Integer,   default=30)

    def __repr__(self):
        days = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
        return f'<ClinicSchedule {days[self.weekday]} {self.start_time}-{self.end_time}>'


class Appointment(db.Model):
    """A patient booking a clinic service."""
    __tablename__ = 'appointments'

    STATUS_PENDING     = 'pending'
    STATUS_CONFIRMED   = 'confirmed'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED   = 'completed'
    STATUS_CANCELLED   = 'cancelled'

    id         = db.Column(db.Integer,    primary_key=True)
    service_id = db.Column(db.Integer,    db.ForeignKey('clinic_services.id'), nullable=False)
    # clinic_id → users.id where user_type='CLINICA'
    clinic_id  = db.Column(db.Integer,    db.ForeignKey('users.id'), nullable=False)
    # user_id   → users.id where user_type='CLIENTE'
    user_id    = db.Column(db.Integer,    db.ForeignKey('users.id'), nullable=True)
    date       = db.Column(db.String(10), nullable=False)   # "YYYY-MM-DD"
    time_slot  = db.Column(db.String(5),  nullable=False)   # "HH:MM"
    status     = db.Column(db.String(20), nullable=False, default='pending')
    status_pagamento = db.Column(db.String(20), nullable=False, default='pendente')  # pendente | aprovado | cancelado
    created_at = db.Column(db.DateTime,   server_default=db.func.now())

    def __repr__(self):
        return f'<Appointment {self.date} {self.time_slot} [{self.status}]>'


class Disponibilidade(db.Model):
    """Specific date + time slot offered by a clinic for a given service.

    status=True  → slot is available for booking
    status=False → slot was already reserved by a patient
    patient_id   → FK to users.id (filled when a patient reserves the slot)
    """
    __tablename__ = 'disponibilidades'

    id         = db.Column(db.Integer,  primary_key=True)
    service_id = db.Column(db.Integer,  db.ForeignKey('clinic_services.id'), nullable=False)
    data       = db.Column(db.Date,     nullable=False)
    horario    = db.Column(db.String(5), nullable=False)   # "HH:MM"
    status       = db.Column(db.Boolean, nullable=False, default=True)
    preco        = db.Column(db.Float,   nullable=True)   # final price; None → use anuncio.price
    valor_ajuste = db.Column(db.Float,   nullable=True)   # delta applied (+/−); None → no adjustment
    patient_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    patient = db.relationship('User', foreign_keys=[patient_id])

    __table_args__ = (
        db.UniqueConstraint('service_id', 'data', 'horario', name='uq_disp_service_data_hora'),
    )

    def __repr__(self):
        state = 'livre' if self.status else 'reservado'
        return f'<Disponibilidade {self.data} {self.horario} [{state}]>'


class Mensagem(db.Model):
    """Chat message between a patient (CLIENTE) and a clinic (CLINICA)."""
    __tablename__ = 'mensagens'

    id          = db.Column(db.Integer,  primary_key=True)
    sender_id   = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=False)
    conteudo    = db.Column(db.Text,     nullable=False)
    timestamp   = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    lido        = db.Column(db.Boolean,  default=False, nullable=False)

    sender   = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

    def __repr__(self):
        return f'<Mensagem {self.sender_id}→{self.receiver_id}>'


class ChatConversa(db.Model):
    """Tracks the lifecycle of a direct conversation between a clinic and a patient."""
    __tablename__ = 'chat_conversas'

    STATUS_ATIVA     = 'ativa'
    STATUS_ENCERRADA = 'encerrada'

    id           = db.Column(db.Integer,  primary_key=True)
    clinic_id    = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=False)
    patient_id   = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=False)
    status       = db.Column(db.String(20), nullable=False, default='ativa')
    encerrada_em = db.Column(db.DateTime, nullable=True)
    created_at   = db.Column(db.DateTime, server_default=db.func.now())

    clinic   = db.relationship('User', foreign_keys=[clinic_id])
    patient  = db.relationship('User', foreign_keys=[patient_id])

    __table_args__ = (
        db.UniqueConstraint('clinic_id', 'patient_id', name='uq_conversa_clinic_patient'),
    )

    def __repr__(self):
        return f'<ChatConversa clinic={self.clinic_id} patient={self.patient_id} [{self.status}]>'


class Prontuario(db.Model):
    """Clinical record written by a clinic/doctor for a specific appointment."""
    __tablename__ = 'prontuarios'

    id             = db.Column(db.Integer,  primary_key=True)
    paciente_id    = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=False)
    medico_id      = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=False)
    appointment_id = db.Column(db.Integer,  db.ForeignKey('appointments.id'), nullable=True, unique=True)
    data_consulta  = db.Column(db.String(10), nullable=False)   # "YYYY-MM-DD"
    diagnostico    = db.Column(db.Text,     nullable=True)
    prescricao     = db.Column(db.Text,     nullable=True)
    observacoes    = db.Column(db.Text,     nullable=True)
    created_at     = db.Column(db.DateTime, server_default=db.func.now())

    paciente    = db.relationship('User', foreign_keys=[paciente_id])
    medico      = db.relationship('User', foreign_keys=[medico_id])
    appointment = db.relationship('Appointment', foreign_keys=[appointment_id])

    def __repr__(self):
        return f'<Prontuario paciente={self.paciente_id} data={self.data_consulta}>'


class DocumentoPaciente(db.Model):
    """File (PDF/image) uploaded by a patient for their own records."""
    __tablename__ = 'documentos_paciente'

    id          = db.Column(db.Integer,     primary_key=True)
    paciente_id = db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=False)
    titulo      = db.Column(db.String(200), nullable=False)
    arquivo_url = db.Column(db.String(400), nullable=False)   # path relative to static/
    data_upload = db.Column(db.DateTime,    server_default=db.func.now())

    paciente = db.relationship('User', foreign_keys=[paciente_id], back_populates='documentos')

    def __repr__(self):
        return f'<DocumentoPaciente {self.titulo} paciente={self.paciente_id}>'


class Review(db.Model):
    """Patient review/rating for a clinic."""
    __tablename__ = 'reviews'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    clinic_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating     = db.Column(db.Integer, nullable=False)   # 1–5
    comment    = db.Column(db.Text,    nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user   = db.relationship('User', foreign_keys=[user_id])
    clinic = db.relationship('User', foreign_keys=[clinic_id])

    __table_args__ = (
        db.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_rating_range'),
    )

    @staticmethod
    def avg_rating_for_clinic(clinic_id):
        """Return (average, count) for a given clinic."""
        from sqlalchemy import func as sa_func
        result = db.session.query(
            sa_func.avg(Review.rating),
            sa_func.count(Review.id),
        ).filter(Review.clinic_id == clinic_id).first()
        avg = round(float(result[0]), 1) if result[0] else 0.0
        count = result[1] or 0
        return avg, count

    def __repr__(self):
        return f'<Review user={self.user_id} clinic={self.clinic_id} rating={self.rating}>'