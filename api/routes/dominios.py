from fastapi import APIRouter, Depends, HTTPException, Query
from api.DTO.models import DomainRequest, DomainStatus, AlternativesResponse, DominioCreate, DominioEnCarrito, ActualizarOcupadoDominioRequestList, AgregarDominioRequest,TransferenciaDominioRequest,GenerarDominiosRequest
from api.ORM.models_sqlalchemy import Dominio, CarritoDominio, Cuenta, MetodoPagoCuenta, Carrito, Factura
from sqlalchemy.orm import Session
from ..DAO.database import SessionLocal
import requests
from typing import List
from bs4 import BeautifulSoup
from xml.etree.ElementTree import Element, SubElement, ElementTree
import smtplib
from email.message import EmailMessage
import os
from io import BytesIO
import uuid
from datetime import timedelta, date
from api.AIGEN.AI_utils import generar_dominios_desde_descripcion
from sqlalchemy import func
router = APIRouter()


HEADERS = { "User-Agent": "Mozilla/5.0" }
BASE_URL = "https://who.is/whois/"
EXTENSIONS = ["com", "net", "org", "co", "io", "app", "info", "dev", "online", "store"]
def enviar_xml_por_correo(nombre_archivo: str, contenido_bytes: bytes, destinatario: str):
    remitente = os.getenv("EMAIL_REMITENTE")
    password = os.getenv("EMAIL_CONTRASENA")

    msg = EmailMessage()
    msg["Subject"] = "Solicitud de Dominio CHIBCHAWEB"
    msg["From"] = remitente
    msg["To"] = destinatario  # Usamos el correo de la cuenta
    msg.set_content("Se adjunta la solicitud del dominio registrado. GRACIAS POR CONFIAR")

    msg.add_attachment(
        contenido_bytes,
        maintype="application",
        subtype="xml",
        filename=nombre_archivo
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(remitente, password)
        smtp.send_message(msg)


# Dependency para obtener una sesión DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Web Scraping para WHOIS
def get_html(domain: str) -> str:
    url = BASE_URL + domain
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.text

def parse_data(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()

    result = {
        "registered": None,
        "expires": None
    }

    if "No WHOIS data was found for" in text:
        result["registered"] = False
        return result

    if "The domain" in text and "is registered" in text:
        result["registered"] = True

    expires_label = soup.find("dt", string="Expires")
    if expires_label:
        expires_value = expires_label.find_next_sibling("dd")
        if expires_value:
            result["expires"] = expires_value.text.strip()

    return result

@router.post("/DominiosDisponible", response_model=AlternativesResponse)
def verificar_extensiones(data: DomainRequest, db: Session = Depends(get_db)):
    base = data.domain.strip().lower()
    alternativas = []

    # Verificar si el dominio ya está en la base de datos y si está ocupado
    for ext in EXTENSIONS:
        dominio = f"{base}.{ext}"

        # Comprobar si el dominio está ocupado en la base de datos (OCUPADO = 1)
        dominio_db = db.query(Dominio).filter_by(IDDOMINIO=dominio, OCUPADO=True).first()

        if dominio_db:
            # Si el dominio está ocupado, no agregarlo a las alternativas
            continue
        else:
            try:
                # Si el dominio no está ocupado, verificamos disponibilidad en línea
                html = get_html(dominio)
                info = parse_data(html)
                alternativas.append(DomainStatus(
                    domain=dominio,
                    registered=info["registered"],
                    expires=info["expires"]
                ))
            except:
                # Si la verificación en línea falla, lo marcamos como no disponible
                alternativas.append(DomainStatus(
                    domain=dominio,
                    registered=False,
                    expires=None
                ))

    return AlternativesResponse(domain=base, alternativas=alternativas)




@router.post("/agregarDominio")
def agregar_dominio(dominio_data: DominioCreate, db: Session = Depends(get_db)):
    if db.query(Dominio).filter_by(IDDOMINIO=dominio_data.iddominio).first():
        raise HTTPException(status_code=400, detail="ID de dominio ya registrado.")

    nuevo_dominio = Dominio(
        IDDOMINIO=dominio_data.iddominio,
        NOMBREPAGINA=dominio_data.nombrepagina,
        PRECIODOMINIO=dominio_data.preciodominio,
        OCUPADO=dominio_data.ocupado
    )

    db.add(nuevo_dominio)
    db.commit()
    db.refresh(nuevo_dominio)

    return {"message": "Dominio registrado exitosamente", "id": nuevo_dominio.IDDOMINIO}

@router.put("/ActualizarOcupadoDominio")
def actualizar_ocupado_dominio(data: ActualizarOcupadoDominioRequestList, db: Session = Depends(get_db)):
    dominios_pagados = []
    cuenta = None
    carrito = None
    carrito_pagado = False

    for item in data.dominios:
        dominio = db.query(Dominio).filter_by(IDDOMINIO=item.iddominio).first()
        if not dominio:
            continue

        car_dominio = db.query(CarritoDominio).filter_by(IDDOMINIO=item.iddominio).first()
        if not car_dominio:
            continue

        carrito = db.query(Carrito).filter_by(IDCARRITO=car_dominio.IDCARRITO).first()
        if not carrito:
            continue

        if not cuenta:
            cuenta = db.query(Cuenta).filter_by(IDCUENTA=carrito.IDCUENTA).first()
            if not cuenta:
                continue

        if dominio.OCUPADO != True:
            dominio.OCUPADO = True
            db.commit()
            db.refresh(dominio)

            if dominio.OCUPADO:
                if carrito.IDESTADOCARRITO != '2':
                    carrito_pagado = True
                    dominios_pagados.append(dominio.NOMBREPAGINA)
    
    if carrito_pagado and carrito:
        carrito.IDESTADOCARRITO = '2'
        db.commit()

        carrito_existente = db.query(Carrito).filter_by(IDCUENTA=cuenta.IDCUENTA, IDESTADOCARRITO='1').first()
        if not carrito_existente:
            nuevo_carrito = Carrito(
                IDESTADOCARRITO='1',
                IDCUENTA=cuenta.IDCUENTA,
                IDMETODOPAGOCUENTA=carrito.IDMETODOPAGOCUENTA
            )
            db.add(nuevo_carrito)
            db.commit()
            db.refresh(nuevo_carrito)

        # Crear la factura
        factura = Factura(
            IDCARRITO=carrito.IDCARRITO,  # Asociar la factura con el carrito
            PAGOFACTURA=date.today(),  # Usamos `date.today()` para la fecha actual
            VIGFACTURA=date.today() + timedelta(days=365)
        )
        db.add(factura)
        db.commit()
        db.refresh(factura)  # Para obtener el ID de la factura

        # Crear XML y enviarlo por correo
        root = Element("SolicitudDominios")
        SubElement(root, "Identificacion").text = cuenta.IDENTIFICACION

        for dominio in dominios_pagados:
            precio_dominio = db.query(Dominio.PRECIODOMINIO).filter_by(IDDOMINIO=dominio).first()
            if precio_dominio:
                sub_element = SubElement(root, "Dominio")
                SubElement(sub_element, "NombrePagina").text = dominio
                SubElement(sub_element, "PrecioDominio").text = str(precio_dominio.PRECIODOMINIO)

        buffer = BytesIO()
        tree = ElementTree(root)
        tree.write(buffer, encoding="utf-8", xml_declaration=True)
        xml_bytes = buffer.getvalue()

        enviar_xml_por_correo("solicitud_dominios.xml", xml_bytes, cuenta.CORREO)
        
        return {
            "identificacion": cuenta.IDENTIFICACION,
            "dominios_pagados": dominios_pagados,
            "factura_id": factura.IDFACTURA,  # Devuelvo el ID de la factura generada
            "fecha_pago": factura.PAGOFACTURA,
            "fecha_vencimiento": factura.VIGFACTURA
        }











@router.get("/carrito/dominios", response_model=List[DominioEnCarrito])
def obtener_dominios_facturados(idcuenta: str = Query(...), db: Session = Depends(get_db)):
    resultados = (
        db.query(
            Cuenta.IDCUENTA.label("cuenta"),
            Carrito.IDCARRITO.label("carrito"),
            Dominio.IDDOMINIO.label("iddominio"),
            Dominio.NOMBREPAGINA.label("dominio"),
            Dominio.PRECIODOMINIO.label("precio")
        )
        .join(MetodoPagoCuenta, MetodoPagoCuenta.IDCUENTA == Cuenta.IDCUENTA)
        .join(Carrito, Carrito.IDMETODOPAGOCUENTA == MetodoPagoCuenta.IDMETODOPAGOCUENTA)
        .join(CarritoDominio, CarritoDominio.IDCARRITO == Carrito.IDCARRITO)
        .join(Dominio, Dominio.IDDOMINIO == CarritoDominio.IDDOMINIO)
        .filter(Carrito.IDESTADOCARRITO == "1", Cuenta.IDCUENTA == idcuenta)
        .all()
    )

    if not resultados:
        raise HTTPException(status_code=404, detail="No se encontraron dominios para el carrito facturado")

    return resultados

@router.post("/dominios/agregar-a-carrito-existente")
def agregar_dominio_a_carrito(data: AgregarDominioRequest, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter_by(IDCUENTA=data.idcuenta).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    dominio = db.query(Dominio).filter_by(IDDOMINIO=data.iddominio).first()
    if not dominio:
        raise HTTPException(status_code=404, detail="Dominio no encontrado")
    if dominio.OCUPADO:
        raise HTTPException(status_code=400, detail="Dominio ya está ocupado")

    carrito = db.query(Carrito).filter_by(IDCUENTA=data.idcuenta, IDESTADOCARRITO='1').first()
    if not carrito:
        raise HTTPException(status_code=404, detail="No hay carrito activo para esta cuenta")


    ya_existe = db.query(CarritoDominio).filter_by(IDDOMINIO=data.iddominio, IDCARRITO=carrito.IDCARRITO).first()
    if ya_existe:
        raise HTTPException(status_code=400, detail="Este dominio ya está en el carrito")

    nuevo_item = CarritoDominio(
        IDDOMINIO=data.iddominio,
        IDCARRITO=carrito.IDCARRITO,
        IDCARRITODOMINIO=str(uuid.uuid4())[:10]
    )
    db.add(nuevo_item)
    db.commit()

    return {
        "message": "Dominio agregado exitosamente al carrito activo",
        "idcarrito": carrito.IDCARRITO,
        "iddominio": data.iddominio
    }


@router.put("/TransferenciaDominio")
def transferencia_dominio(data: TransferenciaDominioRequest, db: Session = Depends(get_db)):
    # Buscar dominio
    dominio = db.query(Dominio).filter_by(IDDOMINIO=data.iddominio).first()
    if not dominio:
        raise HTTPException(status_code=404, detail="Dominio no encontrado")

    # Cuenta origen y destino
    cuenta_origen = db.query(Cuenta).filter_by(IDCUENTA=data.idcuenta_origen).first()
    if not cuenta_origen:
        raise HTTPException(status_code=404, detail="Cuenta de origen no encontrada")

    cuenta_destino = db.query(Cuenta).filter_by(CORREO=data.correo_destino).first()
    if not cuenta_destino:
        raise HTTPException(status_code=404, detail="Cuenta de destino no encontrada")

    # Método pago destino
    metodo_pago_destino = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=cuenta_destino.IDCUENTA).first()
    if not metodo_pago_destino:
        raise HTTPException(status_code=404, detail="Método de pago para la cuenta de destino no encontrado")

    # Relación dominio-carrito ORIGINAL (guardamos el carrito original antes de mover)
    car_dominio = db.query(CarritoDominio).join(Carrito).filter(
        CarritoDominio.IDDOMINIO == data.iddominio,
        Carrito.IDCUENTA == data.idcuenta_origen
    ).first()
    if not car_dominio:
        raise HTTPException(status_code=404, detail="Relación dominio-carrito no encontrada en cuenta de origen")

    carrito_original_id = car_dominio.IDCARRITO

    # Crear carrito destino (estado "3" = TRANSFERIDO)
    nuevo_carrito = Carrito(
        IDESTADOCARRITO='3',
        IDCUENTA=cuenta_destino.IDCUENTA,
        IDMETODOPAGOCUENTA=metodo_pago_destino.IDMETODOPAGOCUENTA
    )
    db.add(nuevo_carrito)
    db.commit()
    db.refresh(nuevo_carrito)

    # Mover relación al nuevo carrito
    car_dominio.IDCARRITO = nuevo_carrito.IDCARRITO
    db.commit()

    # Marcar estado (por si acaso)
    if nuevo_carrito.IDESTADOCARRITO != '3':
        nuevo_carrito.IDESTADOCARRITO = '3'
        db.commit()

    # ===== Clonar la VIGENCIA (Factura) =====
    # Tomamos la última factura del carrito original (por fecha de pago más reciente)
    factura_origen = db.query(Factura).filter(
        Factura.IDCARRITO == carrito_original_id
    ).order_by(Factura.PAGOFACTURA.desc()).first()

    if factura_origen:
        factura_nueva = Factura(
            IDCARRITO=nuevo_carrito.IDCARRITO,
            PAGOFACTURA=date.today(),
            VIGFACTURA=factura_origen.VIGFACTURA  # preservamos la vigencia
        )
        db.add(factura_nueva)
        db.commit()
    # Si no hay factura de origen, no creamos nada (el endpoint de vigencia hará LEFT JOIN y no fallará)

    return {
        "message": f"Dominio {dominio.NOMBREPAGINA} transferido de {cuenta_origen.NOMBRECUENTA} a {cuenta_destino.NOMBRECUENTA}",
        "iddominio": dominio.IDDOMINIO,
        "cuenta_origen": cuenta_origen.NOMBRECUENTA,
        "cuenta_destino": cuenta_destino.NOMBRECUENTA,
        "nuevo_carrito": nuevo_carrito.IDCARRITO
    }


@router.get("/DominiosAdquiridos")
def dominios_adquiridos(idcuenta: str, db: Session = Depends(get_db)):
    try:
        # Consultar los dominios con OCUPADO = 1 y el idcuenta proporcionado
        dominios = db.query(Dominio).join(
            CarritoDominio, CarritoDominio.IDDOMINIO == Dominio.IDDOMINIO
        ).join(
            Carrito, Carrito.IDCARRITO == CarritoDominio.IDCARRITO
        ).filter(
            Dominio.OCUPADO == True,  # Filtrar solo dominios ocupados
            Carrito.IDCUENTA == idcuenta  # Filtrar por el IDCUENTA proporcionado
        ).all()

        if not dominios:
            raise HTTPException(status_code=404, detail="No se encontraron dominios adquiridos para esta cuenta")

        # Preparar la lista de dominios
        dominios_lista = [dominio.IDDOMINIO for dominio in dominios]

        # Incluir un encabezado "Páginas adquiridas:"
        return {
            "mensaje": "Páginas adquiridas:",
            "dominios_adquiridos": dominios_lista
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener los dominios adquiridos: {str(e)}")

@router.get("/dominios/vigencia")
def obtener_vigencia_dominios(idcuenta: str = Query(...), db: Session = Depends(get_db)):
    sub = (
        db.query(
            Dominio.NOMBREPAGINA.label("nombre"),
            func.max(Factura.VIGFACTURA).label("vigencia_max")
        )
        .join(CarritoDominio, CarritoDominio.IDDOMINIO == Dominio.IDDOMINIO)
        .join(Carrito, Carrito.IDCARRITO == CarritoDominio.IDCARRITO)
        .outerjoin(Factura, Factura.IDCARRITO == Carrito.IDCARRITO)  # LEFT JOIN
        .filter(Carrito.IDCUENTA == idcuenta, Dominio.OCUPADO == True)
        .group_by(Dominio.NOMBREPAGINA)
        .subquery()
    )

    resultados = db.query(sub.c.nombre, sub.c.vigencia_max).all()
    if not resultados:
        raise HTTPException(status_code=404, detail="No se encontraron dominios con vigencia para esta cuenta")

    hoy = date.today()
    dominios_con_vigencia = []

    for nombre, vigencia in resultados:
        if vigencia is None:
            dias_restantes = None  # o 0 si prefieres: 0
        else:
            dias_restantes = (vigencia.date() - hoy).days

        dominios_con_vigencia.append({
            "nombre_dominio": nombre,
            "vigencia": vigencia,
            "dias_restantes": dias_restantes
        })

    return dominios_con_vigencia


@router.post("/generar-dominiosIA")
def generar_dominios_con_IA(data: GenerarDominiosRequest):
    if not data.descripcion or len(data.descripcion) < 5:
        raise HTTPException(status_code=400, detail="Descripción demasiado corta")

    dominios = generar_dominios_desde_descripcion(data.descripcion)

    if not dominios:
        raise HTTPException(status_code=500, detail="No se pudieron generar dominios")

    return {
        "descripcion": data.descripcion,
        "dominios_generados": dominios
    }