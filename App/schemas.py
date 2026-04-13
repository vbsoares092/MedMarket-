from pydantic import BaseModel

class AnuncioBase(BaseModel):
    titulo: str
    descricao: str
    tipo: str

class AnuncioCreate(AnuncioBase):
    pass

class Anuncio(AnuncioBase):
    id: int
    class Config:
        orm_mode = True

class ReservaCreate(BaseModel):
    data: str
    horario: str