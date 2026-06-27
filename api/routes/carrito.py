from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from api.DTO.models import CarritoCreate, CarritoDominioCreate, CarritoUpdate, CarritoDominioDelete
from api.ORM.models_sqlalchemy import Carrito, CarritoDominio, Dominio
from api.DAO.database import get_db

router = APIRouter()


@router.post("/agregarCarrito")
def agregar_carrito(data: CarritoCreate, db: Session = Depends(get_db)):
    nuevo_carrito = Carrito(
        IDESTADOCARRITO=data.idestadocarrito,
        IDCUENTA=data.idcuenta,
        IDMETODOPAGOCUENTA=data.idmetodopagocuenta
    )

    db.add(nuevo_carrito)
    db.commit()
    db.refresh(nuevo_carrito)

    return {
        "message": "Carrito agregado",
        "idcarrito": nuevo_carrito.IDCARRITO
    }


@router.post("/agregarDominioACarrito")
def agregar_dominio_a_carrito(data: CarritoDominioCreate, db: Session = Depends(get_db)):
    # Verificación opcional: evitar duplicados
    existente = db.query(CarritoDominio).filter_by(
        IDDOMINIO=data.iddominio,
        IDCARRITO=data.idcarrito,
        IDCARRITODOMINIO=data.idcarritodominio
    ).first()

    if existente:
        raise HTTPException(status_code=400, detail="Este dominio ya está en el carrito con ese ID.")

    nuevo = CarritoDominio(
        IDDOMINIO=data.iddominio,
        IDCARRITO=data.idcarrito,
        IDCARRITODOMINIO=data.idcarritodominio
    )

    db.add(nuevo)
    db.commit()

    return {
        "message": "Dominio agregado al carrito",
        "iddominio": nuevo.IDDOMINIO,
        "idcarrito": nuevo.IDCARRITO
    }

@router.put("/updateCarrito")
def actualizar_carrito(data: CarritoUpdate, db: Session = Depends(get_db)):
    carrito = db.query(Carrito).filter_by(IDCARRITO=data.idcarrito).first()

    if not carrito:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")

    carrito.IDESTADOCARRITO = data.idestadocarrito

    db.commit()
    db.refresh(carrito)

    return {
        "message": "Carrito actualizado correctamente",
        "idcarrito": carrito.IDCARRITO,
        "nuevo_estado": carrito.IDESTADOCARRITO
    }

@router.get("/carrito/obtener-por-cuenta")
def obtener_carritos_por_cuenta(idcuenta: str, db: Session = Depends(get_db)):
    carritos = (
        db.query(Carrito)
        .options(joinedload(Carrito.ESTADOCARRITO_REL))
        .filter_by(IDCUENTA=idcuenta)
        .all()
    )

    if not carritos:
        raise HTTPException(status_code=404, detail="No se encontraron carritos para esta cuenta.")

    resultado = []
    for c in carritos:
        resultado.append({
            "idcarrito": c.IDCARRITO,
            "estadocarrito": c.ESTADOCARRITO_REL.NOMESTADOCARRITO
        })

    return resultado

@router.delete("/EliminarDominioCarrito")
def eliminar_dominio_carrito(idcuenta: str, iddominio: str, db: Session = Depends(get_db)):
    # Buscar la relación entre el carrito y el dominio
    car_dominio = db.query(CarritoDominio).join(Carrito).filter(
        Carrito.IDCUENTA == idcuenta, 
        CarritoDominio.IDDOMINIO == iddominio
    ).first()

    if not car_dominio:
        raise HTTPException(status_code=404, detail="Relación dominio-carrito no encontrada")

    # Eliminar la relación dominio-carrito
    db.delete(car_dominio)
    db.commit()

    # Verificar si el dominio tiene otras relaciones en la tabla CarritoDominio
    dominio_relacionado = db.query(CarritoDominio).filter(CarritoDominio.IDDOMINIO == iddominio).first()

    # Si no hay otras relaciones, eliminar el dominio de la tabla DOMINIO
    if not dominio_relacionado:
        dominio = db.query(Dominio).filter_by(IDDOMINIO=iddominio).first()
        if dominio:
            db.delete(dominio)
            db.commit()
    return {"message": f"Dominio {iddominio} eliminado del carrito de la cuenta {idcuenta} exitosamente."}
