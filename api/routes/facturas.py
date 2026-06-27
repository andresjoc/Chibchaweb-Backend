from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from api.DAO.database import get_db
from api.ORM.models_sqlalchemy import Factura, Cuenta, Carrito, CarritoDominio, Dominio, MetodoPagoCuenta, FacturaPaquete, Plan
import smtplib
from email.message import EmailMessage
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from decimal import Decimal
import os
from reportlab.lib.utils import ImageReader
from sqlalchemy import func
from datetime import date, timedelta

router = APIRouter()

@router.get("/ObtenerFacturas")
def obtener_facturas(idcuenta: str, db: Session = Depends(get_db)):
    try:
        # Consultar todos los carritos asociados a la cuenta
        carritos = db.query(Carrito).filter_by(IDCUENTA=idcuenta).all()

        if not carritos:
            raise HTTPException(status_code=404, detail="No se encontraron carritos para esta cuenta")

        # Consultar las facturas asociadas a esos carritos
        facturas = db.query(Factura).filter(Factura.IDCARRITO.in_([carrito.IDCARRITO for carrito in carritos])).all()

        if not facturas:
            raise HTTPException(status_code=404, detail="No se encontraron facturas para esta cuenta")

        # Preparar el diccionario con las facturas
        facturas_dict = [
            {
                "idfactura": factura.IDFACTURA,
                "pago_factura": factura.PAGOFACTURA,
                "vig_factura": factura.VIGFACTURA
            }
            for factura in facturas
        ]

        return {"facturas": facturas_dict}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener las facturas: {str(e)}")




def generar_factura_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    try:
        logo_path = os.path.join("resources", "logo.png")
        logo = ImageReader(logo_path)

        # Calcular dimensiones conservando proporción
        iw, ih = logo.getSize()
        logo_width = 100  # ancho fijo en puntos
        logo_height = int((ih / iw) * logo_width)

        x = width - logo_width - 50  # margen derecho
        y = height - logo_height - 40  # margen superior

        c.drawImage(logo, x, y, width=logo_width, height=logo_height, mask='auto')
    except Exception as e:
        print(f"[!] Error cargando el logo: {e}")

    c.setFont("Helvetica-Bold", 16)
    c.drawString(180, 750, "Factura de Venta - CHIBCHAWEB")
    c.setFont("Helvetica", 12)
    c.drawString(50, 710, f"Cliente: {data['nombre_cliente']} ({data['identificacion_cliente']})")
    c.drawString(50, 690, f"Correo: {data['correo_cliente']}")
    c.drawString(50, 670, f"Fecha de pago: {data['fecha_pago']}")
    c.drawString(50, 650, f"Vigencia hasta: {data['vigencia']}")

    c.drawString(50, 620, "Dominios comprados:")
    y = 600
    for dom in data["dominios"]:
        c.drawString(70, y, f"- {dom['dominio']} | ${dom['precio']:.2f}")
        y -= 20

    c.drawString(50, y-10, f"Subtotal: ${data['total_sin_descuento']:.2f}")
    c.drawString(50, y-30, f"Comisión aplicada: {data['comision_aplicada']}%")
    c.drawString(50, y-50, f"Descuento por comisión: ${data['descuento_comision']:.2f}")
    c.drawString(50, y-70, f"Total pagado: ${data['total_pagado']:.2f}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()




@router.get("/EnviarFactura/{idfactura}")
def enviar_factura(idfactura: int, db: Session = Depends(get_db)):
    factura = db.query(Factura).filter(Factura.IDFACTURA == idfactura).first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    carrito = factura.carrito
    cuenta = db.query(Cuenta).filter(Cuenta.IDCUENTA == carrito.IDCUENTA).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    dominios_carrito = db.query(CarritoDominio).filter(CarritoDominio.IDCARRITO == carrito.IDCARRITO).all()
    dominios = []
    total = Decimal(0)

    for cd in dominios_carrito:
        dominio = db.query(Dominio).filter(Dominio.IDDOMINIO == cd.IDDOMINIO).first()
        if dominio:
            dominios.append({
                "dominio": dominio.NOMBREPAGINA,
                "precio": float(dominio.PRECIODOMINIO)
            })
            total += dominio.PRECIODOMINIO

    plan = cuenta.PLAN_REL
    comision = plan.COMISION if plan else Decimal(0)
    descuento = (total * comision / Decimal(100)).quantize(Decimal("0.01"))
    total_final = (total - descuento).quantize(Decimal("0.01"))

    data = {
        "nombre_cliente": cuenta.NOMBRECUENTA,
        "correo_cliente": cuenta.CORREO,
        "identificacion_cliente": cuenta.IDENTIFICACION,
        "fecha_pago": factura.PAGOFACTURA.strftime("%Y-%m-%d"),
        "vigencia": factura.VIGFACTURA.strftime("%Y-%m-%d"),
        "dominios": dominios,
        "total_sin_descuento": float(total),
        "comision_aplicada": float(comision),
        "descuento_comision": float(descuento),
        "total_pagado": float(total_final)
    }

    # Generar PDF
    pdf_content = generar_factura_pdf(data)

    # Configuración del correo
    remitente = os.getenv("EMAIL_REMITENTE")
    destinatario = cuenta.CORREO
    contraseña = os.getenv("EMAIL_CONTRASENA")  # usa un .env o variable de entorno real

    msg = EmailMessage()
    msg["Subject"] = "Factura de Venta CHIBCHAWEB"
    msg["From"] = remitente
    msg["To"] = destinatario
    msg.set_content(f"""
Hola {cuenta.NOMBRECUENTA},

Adjunto encontrarás tu factura por la compra de dominios en ChibchaWeb.

Gracias por tu preferencia.

— Equipo ChibchaWeb
""")
    msg.add_attachment(pdf_content, maintype="application", subtype="pdf", filename="Factura_ChibchaWeb.pdf")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(remitente, contraseña)
            smtp.send_message(msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo: {str(e)}")

    return {"mensaje": f"Factura enviada exitosamente a {cuenta.CORREO}"}


@router.get("/facturas-por-cuenta")
def obtener_facturas_por_cuenta(
    idcuenta: str = Query(..., description="ID de la cuenta del cliente"),
    db: Session = Depends(get_db)
):
    cuenta = db.query(Cuenta).filter_by(IDCUENTA=idcuenta).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail=f"Cuenta {idcuenta} no encontrada")

    metodos = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=idcuenta).all()
    if not metodos:
        raise HTTPException(status_code=404, detail="No se encontraron métodos de pago para esta cuenta")

    facturas = []
    for metodo in metodos:
        facturas_metodo = db.query(FacturaPaquete).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA).all()
        for f in facturas_metodo:
            paquete = f.paquete_hosting
            facturas.append({
                "idfacturapaquete": f.IDFACTURAPAQUETE,
                "fchpago": f.FCHPAGO,
                "fchvencimiento": f.FCHVENCIMIENTO,
                "estado": f.ESTADO,
                "valor": float(f.VALORFP),
                "paquete": {
                    "idpaquetehosting": paquete.IDPAQUETEHOSTING if paquete else None,
                    "preciopaquete": float(paquete.PRECIOPAQUETE) if paquete else None,
                    "periodicidad": paquete.PERIODICIDAD if paquete else None
                } if paquete else None
            })

    if not facturas:
        raise HTTPException(status_code=404, detail="No se encontraron facturas para esta cuenta")

    return {
        "idcuenta": idcuenta,
        "facturas": facturas
    }


@router.get("/reporte/admin/comisiones-distribuidores")
def comisiones_distribuidores(db: Session = Depends(get_db)):
    distribuidores = db.query(Cuenta).filter_by(IDTIPOCUENTA=2).all()
    total = 0.0

    for dist in distribuidores:
        plan = db.query(Plan).filter_by(IDPLAN=dist.IDPLAN).first()
        if not plan:
            continue
        comision = float(plan.COMISION)

        metodos = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=dist.IDCUENTA).all()
        for metodo in metodos:
            carrito_ids = db.query(Carrito.IDCARRITO).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA).all()
            carrito_ids = [c[0] for c in carrito_ids]
            dominios = db.query(Dominio.PRECIODOMINIO).join(CarritoDominio)\
                        .filter(CarritoDominio.IDCARRITO.in_(carrito_ids)).all()
            for d in dominios:
                total += float(d[0]) * (comision / 100)

    return {"comisiones_distribuidores": round(total, 2)}


@router.get("/reporte/admin/ventas")
def ventas_admin(db: Session = Depends(get_db)):
    total_paquetes = db.query(FacturaPaquete).count()

    clientes = db.query(Cuenta).filter_by(IDTIPOCUENTA=1).all()
    distros = db.query(Cuenta).filter_by(IDTIPOCUENTA=2).all()

    dom_clientes = 0
    dom_distribuidores = 0

    for grupo, counter in [(clientes, 'cliente'), (distros, 'distribuidor')]:
        for cuenta in grupo:
            metodos = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=cuenta.IDCUENTA).all()
            for metodo in metodos:
                carrito_ids = db.query(Carrito.IDCARRITO).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA).all()
                carrito_ids = [c[0] for c in carrito_ids]
                cantidad = db.query(CarritoDominio).filter(CarritoDominio.IDCARRITO.in_(carrito_ids)).count()
                if counter == 'cliente':
                    dom_clientes += cantidad
                else:
                    dom_distribuidores += cantidad

    return {
        "paquetes_vendidos": total_paquetes,
        "dominios_a_clientes": dom_clientes,
        "dominios_a_distribuidores": dom_distribuidores,
        "total_dominios_vendidos": dom_clientes + dom_distribuidores
    }


@router.get("/reporte/admin/ingresos")
def ingresos_admin(db: Session = Depends(get_db)):
    from datetime import date, timedelta
    hoy = date.today()
    hace_un_mes = hoy - timedelta(days=30)

    dom_clientes = 0.0
    dom_distros = 0.0

    for tipo, filtro in [("cliente", 1), ("distribuidor", 2)]:
        cuentas = db.query(Cuenta).filter_by(IDTIPOCUENTA=filtro).all()
        for cuenta in cuentas:
            metodos = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=cuenta.IDCUENTA).all()
            for metodo in metodos:
                carrito_ids = db.query(Carrito.IDCARRITO).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA).all()
                carrito_ids = [c[0] for c in carrito_ids]
                dominios = db.query(Dominio.PRECIODOMINIO).join(CarritoDominio)\
                             .filter(CarritoDominio.IDCARRITO.in_(carrito_ids)).all()
                suma = sum(float(d[0]) for d in dominios)
                if tipo == "cliente":
                    dom_clientes += suma
                else:
                    dom_distros += suma

    total_dominios = dom_clientes + dom_distros
    total_paquetes = db.query(func.sum(FacturaPaquete.VALORFP)).scalar() or 0.0
    ult_mes = db.query(func.sum(FacturaPaquete.VALORFP))\
        .filter(FacturaPaquete.FCHPAGO >= hace_un_mes).scalar() or 0.0

    return {
        "por_dominios_distribuidores": round(dom_distros, 2),
        "por_dominios_clientes": round(dom_clientes, 2),
        "por_venta_paquetes": float(total_paquetes),
        "total_ultimo_mes": float(ult_mes),
        "total_general": round(float(total_paquetes) + float(total_dominios), 2)

    }

@router.get("/reporte/admin/usuarios")
def usuarios_admin(db: Session = Depends(get_db)):
    total = db.query(Cuenta).filter_by(IDTIPOCUENTA=1).count()

    con_compras = db.query(Cuenta.IDCUENTA)\
        .filter_by(IDTIPOCUENTA=1)\
        .join(MetodoPagoCuenta, MetodoPagoCuenta.IDCUENTA == Cuenta.IDCUENTA)\
        .join(Carrito, Carrito.IDMETODOPAGOCUENTA == MetodoPagoCuenta.IDMETODOPAGOCUENTA)\
        .join(CarritoDominio, CarritoDominio.IDCARRITO == Carrito.IDCARRITO)\
        .distinct().count()

    distros = db.query(Cuenta).filter_by(IDTIPOCUENTA=2).all()
    compra_valores = {}

    for d in distros:
        metodos = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=d.IDCUENTA).all()
        for metodo in metodos:
            carrito_ids = db.query(Carrito.IDCARRITO).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA).all()
            carrito_ids = [c[0] for c in carrito_ids]
            dominios = db.query(Dominio.PRECIODOMINIO).join(CarritoDominio)\
                         .filter(CarritoDominio.IDCARRITO.in_(carrito_ids)).all()
            total_compras = sum(float(d[0]) for d in dominios)
            compra_valores[d.NOMBRECUENTA] = compra_valores.get(d.NOMBRECUENTA, 0.0) + total_compras

    if len(compra_valores) >= 2:
        mas = max(compra_valores, key=compra_valores.get)
        menos = min(compra_valores, key=compra_valores.get)
    elif len(compra_valores) == 1:
        mas = menos = next(iter(compra_valores))
    else:
        mas = menos = None

    return {
        "total_clientes_registrados": total,
        "total_clientes_con_compras": con_compras,
        "distribuidor_mas_compro": mas,
        "distribuidor_menos_compro": menos
    }

# `@router.get("/reporte-admin")
# def reporte_admin(db: Session = Depends(get_db)):
#     hoy = date.today()
#     hace_un_mes = hoy - timedelta(days=30)

#     # 1. Comisiones entregadas a distribuidores
#     distribuidores = db.query(Cuenta).filter_by(IDTIPOCUENTA=2).all()
#     total_comisiones = 0.0
#     compras_distribuidor = {}

#     for dist in distribuidores:
#         plan = db.query(Plan).filter_by(IDPLAN=dist.IDPLAN).first()
#         comision = float(plan.COMISION) if plan else 0.0
#         ahorro = 0.0

#         metodos = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=dist.IDCUENTA).all()
#         for metodo in metodos:
#             carritos = db.query(Carrito).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA).all()
#             for carrito in carritos:
#                 dominios = db.query(CarritoDominio).filter_by(IDCARRITO=carrito.IDCARRITO).all()
#                 for d in dominios:
#                     dom = db.query(Dominio).filter_by(IDDOMINIO=d.IDDOMINIO).first()
#                     if dom:
#                         ahorro += float(dom.PRECIODOMINIO) * (comision / 100)

#         total_comisiones += ahorro
#         compras_distribuidor[dist.NOMBRECUENTA] = compras_distribuidor.get(dist.NOMBRECUENTA, 0) + ahorro

#     # 2. Paquetes vendidos a clientes
#     total_paquetes_vendidos = db.query(FacturaPaquete).count()

#     # 3. Dominios vendidos a clientes (TIPOCUENTA = 1)
#     clientes = db.query(Cuenta).filter_by(IDTIPOCUENTA=1).all()
#     dominios_clientes = 0
#     dominios_distribuidores = 0
#     dinero_dom_clientes = 0.0
#     dinero_dom_distribuidores = 0.0

#     for c in clientes:
#         metodos = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=c.IDCUENTA).all()
#         for metodo in metodos:
#             carritos = db.query(Carrito).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA).all()
#             for carrito in carritos:
#                 items = db.query(CarritoDominio).filter_by(IDCARRITO=carrito.IDCARRITO).all()
#                 for item in items:
#                     dom = db.query(Dominio).filter_by(IDDOMINIO=item.IDDOMINIO).first()
#                     if dom:
#                         dominios_clientes += 1
#                         dinero_dom_clientes += float(dom.PRECIODOMINIO)

#     for d in distribuidores:
#         metodos = db.query(MetodoPagoCuenta).filter_by(IDCUENTA=d.IDCUENTA).all()
#         for metodo in metodos:
#             carritos = db.query(Carrito).filter_by(IDMETODOPAGOCUENTA=metodo.IDMETODOPAGOCUENTA).all()
#             for carrito in carritos:
#                 items = db.query(CarritoDominio).filter_by(IDCARRITO=carrito.IDCARRITO).all()
#                 for item in items:
#                     dom = db.query(Dominio).filter_by(IDDOMINIO=item.IDDOMINIO).first()
#                     if dom:
#                         dominios_distribuidores += 1
#                         dinero_dom_distribuidores += float(dom.PRECIODOMINIO)

#     total_dominios = dominios_clientes + dominios_distribuidores
#     total_dinero_dominios = dinero_dom_clientes + dinero_dom_distribuidores

#     # 4. Dinero adquirido por paquetes
#     dinero_paquetes = db.query(func.sum(FacturaPaquete.VALORFP)).scalar() or 0.0

#     # 5. Dinero adquirido en el último mes
#     dinero_ultimo_mes = db.query(func.sum(FacturaPaquete.VALORFP))\
#         .filter(FacturaPaquete.FCHPAGO >= hace_un_mes)\
#         .scalar() or 0.0

#     # 6. Dinero total
#     dinero_total = float(total_dinero_dominios) + float(dinero_paquetes)

#     # 7. Total clientes registrados
#     total_clientes = db.query(Cuenta).filter_by(IDTIPOCUENTA=1).count()

#     # 8. Clientes que han comprado algo
#     clientes_con_compras = db.query(Cuenta.IDCUENTA).filter_by(IDTIPOCUENTA=1)\
#         .join(MetodoPagoCuenta, MetodoPagoCuenta.IDCUENTA == Cuenta.IDCUENTA)\
#         .join(Carrito, Carrito.IDMETODOPAGOCUENTA == MetodoPagoCuenta.IDMETODOPAGOCUENTA)\
#         .join(CarritoDominio, CarritoDominio.IDCARRITO == Carrito.IDCARRITO)\
#         .distinct().count()

#     # 9. Distribuidor que más y menos ha comprado (por valor)
#     if len(compras_distribuidor) >= 2:
#         distribuidor_mas = max(compras_distribuidor, key=compras_distribuidor.get)
#         distribuidor_menos = min(compras_distribuidor, key=compras_distribuidor.get)
#     elif len(compras_distribuidor) == 1:
#         distribuidor_mas = distribuidor_menos = next(iter(compras_distribuidor))
#     else:
#         distribuidor_mas = distribuidor_menos = None


#     return {
#         "comisiones_distribuidores": round(total_comisiones, 2),
#         "ventas": {
#             "paquetes_vendidos": total_paquetes_vendidos,
#             "dominios_a_clientes": dominios_clientes,
#             "dominios_a_distribuidores": dominios_distribuidores,
#             "total_dominios_vendidos": total_dominios
#         },
#         "ingresos": {
#             "por_dominios_distribuidores": round(dinero_dom_distribuidores, 2),
#             "por_dominios_clientes": round(dinero_dom_clientes, 2),
#             "por_venta_paquetes": round(dinero_paquetes, 2),
#             "total_ultimo_mes": round(dinero_ultimo_mes, 2),
#             "total_general": round(dinero_total, 2)
#         },
#         "clientes": {
#             "total_registrados": total_clientes,
#             "total_que_compraron": clientes_con_compras
#         },
#         "distribuidores": {
#             "mas_compro": distribuidor_mas,
#             "menos_compro": distribuidor_menos
#         }
#     }`