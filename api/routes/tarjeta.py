from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.DAO.database import get_db
from api.DTO.models import MetodoPagoCuentaCreate, TarjetaCreate, TarjetaRequest
from api.ORM.models_sqlalchemy import MetodoPagoCuenta, Tarjeta
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()
FERNET_KEY = os.getenv("FERNET_KEY")
if not FERNET_KEY:
    raise RuntimeError("Falta la clave FERNET_KEY en el archivo .env")

cipher = Fernet(FERNET_KEY.encode())

router = APIRouter()



@router.post("/tarjeta")
def registrar_tarjeta(tarjeta_data: TarjetaCreate, db: Session = Depends(get_db)):
    try:
        encrypted_numero_tarjeta = cipher.encrypt(str(tarjeta_data.numerotarjeta).encode()).decode()
        encrypted_ccv = cipher.encrypt(str(tarjeta_data.ccv).encode()).decode()

        nueva_tarjeta = Tarjeta(
            IDTIPOTARJETA=tarjeta_data.idtipotarjeta,
            NUMEROTARJETA=encrypted_numero_tarjeta,
            CCV=encrypted_ccv,
            FECHAVTO=tarjeta_data.fechavto
        )

        db.add(nueva_tarjeta)
        db.commit()
        db.refresh(nueva_tarjeta)

        return {
            "mensaje": "Tarjeta registrada correctamente",
            "idtarjeta": nueva_tarjeta.IDTARJETA
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar la tarjeta: {e}")

@router.post("/metodopago")
def agregar_metodo_pago(data: MetodoPagoCuentaCreate, db: Session = Depends(get_db)):
    metodo = MetodoPagoCuenta(
        IDTARJETA=data.idtarjeta,
        IDCUENTA=data.idcuenta,
        IDTIPOMETODOPAGO=data.idtipometodopago,
        ACTIVOMETODOPAGOCUENTA=data.activometodopagocuenta
    )

    db.add(metodo)
    db.commit()
    return {"mensaje": "Método de pago registrado correctamente"}

@router.post("/validarTarjeta")
def validar_tarjeta(tarjeta_request: TarjetaRequest, db: Session = Depends(get_db)):
    try:
        tarjetas = db.query(Tarjeta).all()

        for tarjeta in tarjetas:
            try:
                decrypted_num = cipher.decrypt(tarjeta.NUMEROTARJETA.encode()).decode()
            except:
                continue

            if decrypted_num == tarjeta_request.numero_tarjeta:
                decrypted_ccv = cipher.decrypt(tarjeta.CCV.encode()).decode()
                if decrypted_ccv == tarjeta_request.ccv:
                    return {"valid": True}
                else:
                    raise HTTPException(status_code=400, detail="CCV incorrecto")

        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al validar la tarjeta: {str(e)}")
