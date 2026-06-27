from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from api.DAO.database import get_db
from api.DTO.models import CrearPaqueteRequest, PaqueteResponse, InfoPaqueteResponse, MiPaqueteResponse, ComprarPaqueteRequest, ModificarPaqueteRequest, EliminarPaqueteRequest, ItemFacturaResponse, ActualizarItemFacturaRequest
from api.ORM.models_sqlalchemy import InfoPaqueteHosting, PaqueteHosting, MetodoPagoCuenta, FacturaPaquete, ItemPaquete
from typing import List, Optional
from datetime import datetime, timedelta, date 
import re
import random 

router = APIRouter()



@router.post("/CrearPaquete")
def crear_paquete(data: CrearPaqueteRequest, db: Session = Depends(get_db)):
    try:
        # Paso 1: Crear InfoPaqueteHosting
        nuevo_info = InfoPaqueteHosting(
            CANTIDADSITIOS=data.cantidadsitios,
            NOMBREPAQUETEHOSTING=data.nombrepaquetehosting,
            BD=data.bd,
            GBENSSD=data.gbenssd,
            CORREOS=data.correos,
            CERTIFICADOSSSLHTTPS=data.certificadosslhttps
        )
        db.add(nuevo_info)
        db.commit()
        db.refresh(nuevo_info)

        # Paso 2: Crear el PaqueteHosting con periodicidad directa (sin tabla intermedia)
        nuevo_paquete = PaqueteHosting(
            IDINFOPAQUETEHOSTING=nuevo_info.IDINFOPAQUETEHOSTING,
            PRECIOPAQUETE=data.preciopaquete,
            PERIODICIDAD=data.periodicidad  # varchar(100)
        )
        db.add(nuevo_paquete)
        db.commit()
        db.refresh(nuevo_paquete)

        return {
            "message": "Paquete creado exitosamente",
            "idpaquete": nuevo_paquete.IDPAQUETEHOSTING
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/Paquetes", response_model=List[PaqueteResponse])
def obtener_paquetes(db: Session = Depends(get_db)):
    paquetes = db.query(PaqueteHosting).options(joinedload(PaqueteHosting.infopaquete)).all()
    if not paquetes:
        raise HTTPException(status_code=404, detail="No hay paquetes disponibles")

    return [
        PaqueteResponse(
            idpaquetehosting=p.IDPAQUETEHOSTING,
            preciopaquete=p.PRECIOPAQUETE,
            periodicidad=p.PERIODICIDAD,
            info=InfoPaqueteResponse(
                cantidadsitios=p.infopaquete.CANTIDADSITIOS,
                nombrepaquetehosting=p.infopaquete.NOMBREPAQUETEHOSTING,
                bd=p.infopaquete.BD,
                gbenssd=p.infopaquete.GBENSSD,
                correos=p.infopaquete.CORREOS,
                certificadosslhttps=p.infopaquete.CERTIFICADOSSSLHTTPS
            )
        )
        for p in paquetes
    ]

@router.get("/MiPaquete", response_model=MiPaqueteResponse)
def obtener_paquete_por_cuenta(idcuenta: str = Query(...), db: Session = Depends(get_db)):
    # Buscar método de pago activo de la cuenta
    metodo = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=idcuenta, ACTIVOMETODOPAGOCUENTA=True).first()
    if not metodo:
        raise HTTPException(status_code=404, detail="Método de pago no encontrado para la cuenta")

    # Buscar factura activa (estado = 1)
    factura = db.query(FacturaPaquete).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA, ESTADO=1).first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura de paquete activa no encontrada")

    # Verificar vencimiento
    if factura.FCHVENCIMIENTO < date.today():
        factura.ESTADO = 2  # Cambiar a vencido
        db.commit()
        raise HTTPException(status_code=400, detail="El paquete ha vencido. Estado actualizado a vencido.")

    # Verificar existencia de paquete y su info
    paquete = factura.paquete_hosting
    if not paquete or not paquete.infopaquete:
        raise HTTPException(status_code=404, detail="Información del paquete incompleta")

    info = paquete.infopaquete

    return MiPaqueteResponse(
        idfacturapaquete=factura.IDFACTURAPAQUETE,
        idinfopaquetehosting=info.IDINFOPAQUETEHOSTING,
        idpaquetehosting=paquete.IDPAQUETEHOSTING,
        fchpago=factura.FCHPAGO,
        fchvencimiento=factura.FCHVENCIMIENTO,
        estado=factura.ESTADO,
        valorfp=float(factura.VALORFP),
        preciopaquete=float(paquete.PRECIOPAQUETE),
        periodicidad=paquete.PERIODICIDAD,
        info=InfoPaqueteResponse(
            cantidadsitios=int(info.CANTIDADSITIOS),
            nombrepaquetehosting=info.NOMBREPAQUETEHOSTING,
            bd=int(info.BD),
            gbenssd=int(info.GBENSSD),
            correos=int(info.CORREOS),
            certificadosslhttps=int(info.CERTIFICADOSSSLHTTPS)
        )
    )



def generar_items_para_factura(idfacturapaquete: int, db: Session):
    factura = db.query(FacturaPaquete).filter_by(IDFACTURAPAQUETE=idfacturapaquete).first()

    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    paquete = factura.paquete_hosting
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado para la factura")

    info = paquete.infopaquete
    if not info:
        raise HTTPException(status_code=404, detail="Info del paquete no encontrada")

    items = []

    # 1. Sitios Web (DESCRIPCION="Web")
    for i in range(int(info.CANTIDADSITIOS)):
        items.append(ItemPaquete(
            IDFACTURAPAQUETE=factura.IDFACTURAPAQUETE,
            DESCRIPCION="Web",
            TAMANO="NA",
            NOMBREITEM=f"Sitio Web {i+1}"
        ))

    # 2. Bases de Datos (DESCRIPCION="BD")
    for i in range(int(info.BD)):
        items.append(ItemPaquete(
            IDFACTURAPAQUETE=factura.IDFACTURAPAQUETE,
            DESCRIPCION="BD",
            TAMANO="NA",
            NOMBREITEM=f"BASE {i+1}"
        ))

    # 3. GB en SSD (DESCRIPCION="GBenSSD", solo uno, TAMAÑO=0)
    items.append(ItemPaquete(
        IDFACTURAPAQUETE=factura.IDFACTURAPAQUETE,
        DESCRIPCION="GBenSSD",
        TAMANO="0",  # para que el usuario indique hasta cuántos GB usar
        NOMBREITEM="Nube 1"
    ))

    # 4. Correos electrónicos (DESCRIPCION="CORREO")
    for i in range(int(info.CORREOS)):
        correo_simulado = f"correo{i+1}@chibchaweb.com"
        items.append(ItemPaquete(
            IDFACTURAPAQUETE=factura.IDFACTURAPAQUETE,
            DESCRIPCION="CORREO",
            TAMANO="NA",
            NOMBREITEM=correo_simulado
        ))

    # 5. Certificados SSL (DESCRIPCION="SSL")
    for i in range(int(info.CERTIFICADOSSSLHTTPS)):
        ssl_simulado = f"SSL-{i+1:02d}-{random.randint(1000,9999)}"
        items.append(ItemPaquete(
            IDFACTURAPAQUETE=factura.IDFACTURAPAQUETE,
            DESCRIPCION="SSL",
            TAMANO="NA",
            NOMBREITEM=ssl_simulado
        ))

    db.add_all(items)
    db.commit()




@router.post("/ComprarPaquete")
def comprar_paquete(data: ComprarPaqueteRequest, db: Session = Depends(get_db)):
    try:
        # Paso 1: Obtener método de pago activo
        metodo = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=data.idcuenta, ACTIVOMETODOPAGOCUENTA=True).first()
        if not metodo:
            raise HTTPException(status_code=404, detail="No se encontró método de pago activo para esta cuenta")

        # Paso 2: Verificar paquete
        paquete = db.query(PaqueteHosting).filter_by(IDPAQUETEHOSTING=data.idpaquetehosting).first()
        if not paquete:
            raise HTTPException(status_code=404, detail="Paquete no encontrado")

        # Paso 3: Calcular fechas
        hoy = datetime.now().date()

        # Extraer número de días desde el campo PERIODICIDAD (ej. "30 días", "90 días")
        match = re.search(r"(\d+)", paquete.PERIODICIDAD)
        if not match:
            raise HTTPException(status_code=400, detail="Periodicidad del paquete no válida")
        dias = int(match.group(1))
        vencimiento = hoy + timedelta(days=dias)

        # Paso 4: Crear factura
        nueva_factura = FacturaPaquete(
            IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA,
            IDPAQUETEHOSTING=paquete.IDPAQUETEHOSTING,
            FCHPAGO=hoy,
            FCHVENCIMIENTO=vencimiento,
            ESTADO=data.estado,
            VALORFP=paquete.PRECIOPAQUETE
        )

        db.add(nueva_factura)
        db.commit()
        db.refresh(nueva_factura)

        generar_items_para_factura(nueva_factura.IDFACTURAPAQUETE, db)

        return {
            "message": "Paquete comprado exitosamente",
            "idfactura": nueva_factura.IDFACTURAPAQUETE,
            "fchpago": hoy.isoformat(),
            "fchvencimiento": vencimiento.isoformat()
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/ModificarPaquete")
def modificar_paquete(data: ModificarPaqueteRequest, db: Session = Depends(get_db)):
    # Buscar el paquete
    paquete = db.query(PaqueteHosting).filter_by(IDPAQUETEHOSTING=data.idpaquetehosting).first()
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado")

    # Buscar la información del paquete
    info = db.query(InfoPaqueteHosting).filter_by(IDINFOPAQUETEHOSTING=data.idinfopaquetehosting).first()
    if not info:
        raise HTTPException(status_code=404, detail="InfoPaquete no encontrada")

    # Actualizar solo los campos que fueron enviados
    if data.preciopaquete is not None:
        paquete.PRECIOPAQUETE = data.preciopaquete
    if data.periodicidad is not None:
        paquete.PERIODICIDAD = data.periodicidad

    if data.cantidadsitios is not None:
        info.CANTIDADSITIOS = data.cantidadsitios
    if data.nombrepaquetehosting is not None:
        info.NOMBREPAQUETEHOSTING = data.nombrepaquetehosting
    if data.bd is not None:
        info.BD = data.bd
    if data.gbenssd is not None:
        info.GBENSSD = data.gbenssd
    if data.correos is not None:
        info.CORREOS = data.correos
    if data.certificadosslhttps is not None:
        info.CERTIFICADOSSSLHTTPS = data.certificadosslhttps

    db.commit()

    return {"mensaje": "Paquete modificado correctamente"}

@router.delete("/EliminarPaquete")
def eliminar_paquete(data: EliminarPaqueteRequest, db: Session = Depends(get_db)):
    info = db.query(InfoPaqueteHosting).filter_by(IDINFOPAQUETEHOSTING=data.idinfopaquetehosting).first()
    if not info:
        raise HTTPException(status_code=404, detail="InfoPaquete no encontrado")

    paquetes = db.query(PaqueteHosting).filter_by(IDINFOPAQUETEHOSTING=data.idinfopaquetehosting).all()

    # Desvincular facturas (poner NULL en IDPAQUETEHOSTING)
    for paquete in paquetes:
        for factura in paquete.facturas_paquete:
            factura.IDPAQUETEHOSTING = None

    # Eliminar paquetes
    for paquete in paquetes:
        db.delete(paquete)

    # Eliminar info
    db.delete(info)

    db.commit()

    return {"mensaje": f"InfoPaquete {data.idinfopaquetehosting} y {len(paquetes)} paquete(s) eliminados correctamente, manteniendo historial de facturas."}

@router.get("/ItemsFactura", response_model=List[ItemFacturaResponse])
def obtener_items_factura(
    idfacturapaquete: int = Query(..., description="ID de la factura del paquete"),
    db: Session = Depends(get_db)
):
    items = db.query(ItemPaquete).filter_by(IDFACTURAPAQUETE=idfacturapaquete).all()

    if not items:
        raise HTTPException(status_code=404, detail="No se encontraron ítems para esta factura")

    return items

@router.put("/EditarItemFactura")
def actualizar_item_factura(data: ActualizarItemFacturaRequest, db: Session = Depends(get_db)):
    item = db.query(ItemPaquete).filter_by(IDREGITEMPAQUETE=data.idregitempaquete).first()

    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")

    if data.tamano is not None:
        item.TAMANO = data.tamano

    if data.nombreitem is not None:
        item.NOMBREITEM = data.nombreitem

    db.commit()

    return {"mensaje": "Ítem actualizado correctamente"}

@router.get("/InfoDePaqueteHosting")
def obtener_idinfopaquetehosting(idpaquetehosting: int = Query(...), db: Session = Depends(get_db)):
    paquete = db.query(PaqueteHosting).filter_by(IDPAQUETEHOSTING=idpaquetehosting).first()

    if not paquete:
        raise HTTPException(status_code=404, detail="PaqueteHosting no encontrado")

    return {"idinfopaquetehosting": paquete.IDINFOPAQUETEHOSTING}