from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from api.DAO.database import get_db
from api.DTO.models import FacturaCreate, CarritoEstadoUpdate, ComisionUpdateRequest
from api.ORM.models_sqlalchemy import Factura, Carrito, Plan, CarritoDominio, Dominio, MetodoPagoCuenta, Cuenta

router = APIRouter()



@router.post("/realizarPago")
def realizar_pago(data: FacturaCreate, db: Session = Depends(get_db)):
    carrito = db.query(Carrito).filter_by(IDCARRITO=data.idcarrito).first()
    if not carrito:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")

    nueva_factura = Factura(
        IDCARRITO=data.idcarrito,
        PAGOFACTURA=datetime.now().date(),
        VIGFACTURA=(datetime.now() + timedelta(days=365*2)).date()
    )

    db.add(nueva_factura)
    db.commit()
    db.refresh(nueva_factura)

    return {
        "message": "Pago realizado con éxito",
        "idfactura": nueva_factura.IDFACTURA,
        "idcarrito": nueva_factura.IDCARRITO,
        "fecha_pago": nueva_factura.PAGOFACTURA,
        "vigencia_hasta": nueva_factura.VIGFACTURA
    }

@router.put("/confirmarPagoCarrito")
def confirmar_pago_carrito(data: CarritoEstadoUpdate, db: Session = Depends(get_db)):
    carrito = db.query(Carrito).filter_by(IDCARRITO=data.idcarrito).first()

    if not carrito:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")

    carrito.IDESTADOCARRITO = "2"  # Estado "facturado"
    db.commit()
    db.refresh(carrito)

    return {
        "message": "Estado del carrito actualizado a facturado",
        "idcarrito": carrito.IDCARRITO,
        "nuevo_estado": carrito.IDESTADOCARRITO
    }

@router.put("/modificar-comision")
def modificar_comision(data: ComisionUpdateRequest, db: Session = Depends(get_db)):
    plan = db.query(Plan).filter_by(IDPLAN=data.idplan).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    plan.COMISION = data.comision
    plan.LIMITEDOMINIOS = data.limitedominios
    db.commit()
    db.refresh(plan)

    return {
        "message": f"Comisión actualizada correctamente para el plan {plan.NOMBREPLAN}",
        "idplan": plan.IDPLAN,
        "nueva_comision": plan.COMISION,
        "nuevo limite" : plan.LIMITEDOMINIOS
    }



        
@router.get("/ahorro-distribuidor")
def calcular_ahorro_distribuidor(
    idcuenta: str = Query(..., description="ID del distribuidor"),
    db: Session = Depends(get_db)
):
    cuenta = db.query(Cuenta).filter_by(IDCUENTA=idcuenta, IDTIPOCUENTA=2).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Distribuidor no encontrado o no válido")

    plan = db.query(Plan).filter_by(IDPLAN=cuenta.IDPLAN).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan del distribuidor no encontrado")

    comision = float(plan.COMISION)

    metodos_pago = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=idcuenta).all()
    if not metodos_pago:
        raise HTTPException(status_code=404, detail="No hay métodos de pago asociados a la cuenta")

    dominios_info = []
    total_ahorrado = 0.0

    for metodo in metodos_pago:
        carritos = db.query(Carrito).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA).all()
        for carrito in carritos:
            carritos_dominios = db.query(CarritoDominio).filter_by(IDCARRITO=carrito.IDCARRITO).all()
            for item in carritos_dominios:
                dominio = db.query(Dominio).filter_by(IDDOMINIO=item.IDDOMINIO).first()
                if dominio:
                    precio = float(dominio.PRECIODOMINIO)
                    ahorro = round(precio * (comision / 100), 2)
                    total_ahorrado += ahorro

                    dominios_info.append({
                        "nombre_dominio": dominio.NOMBREPAGINA,
                        "precio_original": precio,
                        "ahorro_por_comision": ahorro
                    })

    return {
        "distribuidor": {
            "id": cuenta.IDCUENTA,
            "nombre": cuenta.NOMBRECUENTA,
            "plan": plan.NOMBREPLAN,
            "comision": comision,
            "limite_dominio": plan.LIMITEDOMINIOS
        },
        "dominios": dominios_info,
        "total_dominios_comprados": len(dominios_info),
        "total_ahorrado": round(total_ahorrado, 2)
    }