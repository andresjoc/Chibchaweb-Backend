from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from api.DAO.database import SessionLocal
from api.ORM.models_sqlalchemy import Cuenta, MetodoPagoCuenta, Tarjeta
from api.DTO.models import ListaMetodoPagoResponse, MetodoPagoUsuario
import os
from cryptography.fernet import Fernet
FERNET_KEY = os.getenv("FERNET_KEY")
if not FERNET_KEY:
    raise RuntimeError("Falta la clave FERNET_KEY en el archivo .env")

cipher = Fernet(FERNET_KEY.encode())

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/metodosPagoUsuario", response_model=ListaMetodoPagoResponse)
def obtener_metodos_pago_usuario(identificacion: str, db: Session = Depends(get_db)):
    cuenta = (
        db.query(Cuenta)
        .options(joinedload(Cuenta.METODOSPAGO).joinedload(MetodoPagoCuenta.TARJETA_REL))
        .filter(Cuenta.IDENTIFICACION == identificacion)
        .first()
    )

    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")

    metodos = []
    for metodo in cuenta.METODOSPAGO:
        if metodo.TARJETA_REL:
            try:
                decrypted_numero = cipher.decrypt(metodo.TARJETA_REL.NUMEROTARJETA.encode()).decode()
            except Exception as e:
                decrypted_numero = "ERROR"
            metodos.append(MetodoPagoUsuario(
                identificacion=cuenta.IDENTIFICACION,
                numerotarjeta=decrypted_numero,
                tipotarjeta=metodo.TARJETA_REL.IDTIPOTARJETA
            ))

    return ListaMetodoPagoResponse(metodos_pago=metodos)