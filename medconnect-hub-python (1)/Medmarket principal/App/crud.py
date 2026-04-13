from sqlalchemy.orm import Session
import models, schemas

def criar_anuncio(db: Session, anuncio: schemas.AnuncioCreate):
    db_anuncio = models.Anuncio(**anuncio.dict())
    db.add(db_anuncio)
    db.commit()
    db.refresh(db_anuncio)
    return db_anuncio
def criar_reserva(db: Session, reserva: schemas.ReservaCreate, user_id: int, anuncio_id: int):
    nova_reserva = models.Reserva(
        user_id=user_id,
        anuncio_id=anuncio_id,
        data=reserva.data,
        horario=reserva.horario,
        status="pendente"  # só confirma após pagamento
    )
    db.add(nova_reserva)
    db.commit()
    db.refresh(nova_reserva)
    return nova_reserva