from fastapi import FastAPI
from routes import anuncios

app = FastAPI()
app.include_router(anuncios.router)