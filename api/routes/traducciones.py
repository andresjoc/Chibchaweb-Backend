from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from api.DAO.database import get_db
from api.DTO.models import TraduccionRequest
from api.ORM.models_sqlalchemy import Traduccion

router = APIRouter()



@router.get("/traduccion")
def obtener_traduccion(
    idioma: str = Query(...),
    clave: str = Query(...),
    db: Session = Depends(get_db)
):
    traduccion = db.query(Traduccion).filter_by(IDIOMA=idioma, CLAVE=clave).first()
    if not traduccion:
        raise HTTPException(status_code=404, detail="Traducción no encontrada")

    return {
        "idioma": traduccion.IDIOMA,
        "clave": traduccion.CLAVE,
        "valor": traduccion.VALOR
    }

@router.post("/traduccion")
def crear_o_actualizar_traduccion(
    datos: TraduccionRequest,
    db: Session = Depends(get_db)
):
    traduccion = db.query(Traduccion).filter_by(IDIOMA=datos.idioma, CLAVE=datos.clave).first()

    if traduccion:
        traduccion.VALOR = datos.valor
        mensaje = "Traducción actualizada"
    else:
        traduccion = Traduccion(
            IDIOMA=datos.idioma,
            CLAVE=datos.clave,
            VALOR=datos.valor
        )
        db.add(traduccion)
        mensaje = "Traducción creada"

    db.commit()
    return {
        "mensaje": mensaje,
        "idioma": traduccion.IDIOMA,
        "clave": traduccion.CLAVE,
        "valor": traduccion.VALOR
    }