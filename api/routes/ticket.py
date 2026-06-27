from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from datetime import date
from api.DAO.database import get_db
from api.ORM.models_sqlalchemy import Ticket, Cuenta, RespuestaTicket
from api.DTO.models import CrearTicketRequest, RespuestaTicketRequest, CambiarEstadoTicketRequest, CambiarNivelTicketRequest, AsignarTicketRequest
from api.AIGEN.AI_utils import clasificar_correo, generar_respuesta_correo, enviar_email, guardar_ticket_json, agregar_respuesta_a_historial

router = APIRouter()



@router.post("/CrearTicket")
def crear_ticket(data: CrearTicketRequest, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter_by(IDCUENTA=data.idcliente).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    modelo = "openai/gpt-oss-20b:free"
    categoria = clasificar_correo(data.descrip_ticket, modelo)

    nuevo_ticket = Ticket(
        IDCLIENTE=data.idcliente,
        DESCRTICKET=data.descrip_ticket,
        NIVEL=1,
        FCHCREACION=date.today(),
        ESTADOTICKET=3,
        FCHSOLUCION=None,
        IDEMPLEADO=None
    )
    db.add(nuevo_ticket)
    db.commit()
    db.refresh(nuevo_ticket)

    respuesta_ia = generar_respuesta_correo(
        correo_entrada=data.descrip_ticket,
        modelo=modelo,
        nombre_cliente=cuenta.NOMBRECUENTA,
        num_ticket=str(nuevo_ticket.IDTICKET)
    )

    enviado = enviar_email(
        destinatario=cuenta.CORREO,
        asunto=f"Confirmación de Ticket {nuevo_ticket.IDTICKET} – ChibchaWeb",
        cuerpo=respuesta_ia
    )
    if not enviado:
        raise HTTPException(status_code=500, detail="Error al enviar el correo al cliente")

    # respuesta_guardada = RespuestaTicket(
    # RESPUESTA=respuesta_ia,
    # FECHA_RESPUESTA=date.today(),  # aquí se pone la fecha manualmente
    # IDTICKET=nuevo_ticket.IDTICKET
    # )

    # db.add(respuesta_guardada)
    # db.commit()

    return {
        "mensaje": "Ticket creado correctamente",
        "ticket": {
            "id_ticket": nuevo_ticket.IDTICKET,
            "descripcion": nuevo_ticket.DESCRTICKET,
            "categoria": categoria
        }
    }

@router.post("/ticket/{codigo}/respuesta")
def agregar_respuesta_ticket(
    codigo: int =...,
    datos: RespuestaTicketRequest = ...,
    db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter_by(IDTICKET=codigo).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {codigo} no encontrado")

    respuesta = RespuestaTicket(
        RESPUESTA=datos.mensaje,
        FECHARESPUESTA=date.today(),
        IDTICKET=codigo
    )
    db.add(respuesta)
    db.commit()
    db.refresh(respuesta)

    return {
        "mensaje": f"Respuesta agregada correctamente al ticket {codigo}",
        "id_respuesta": respuesta.IDRESPUESTATICKET,
        "fecha": str(respuesta.FECHARESPUESTA),
        "contenido": respuesta.RESPUESTA
    }


@router.get("/consultarTicketporIDCUENTA")
def consultar_tickets_por_cuenta(
    idcuenta: str = Query(..., description="ID de la cuenta (cliente)"),
    db: Session = Depends(get_db)
):
    cuenta = db.query(Cuenta).filter_by(IDCUENTA=idcuenta).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail=f"Cuenta {idcuenta} no encontrada")

    tickets = db.query(Ticket).filter_by(IDCLIENTE=idcuenta).all()
    if not tickets:
        raise HTTPException(status_code=404, detail="No se encontraron tickets asociados a esta cuenta")

    resultados = []
    for t in tickets:
        empleado = db.query(Cuenta).filter_by(IDCUENTA=t.IDEMPLEADO).first() if t.IDEMPLEADO else None

        resultados.append({
            "id_ticket": t.IDTICKET,
            "descripcion": t.DESCRTICKET,
            "nivel": t.NIVEL,
            "estado": t.ESTADOTICKET,
            "fecha_creacion": t.FCHCREACION,
            "fecha_solucion": t.FCHSOLUCION,
            "empleado_asignado": {
                "id": empleado.IDCUENTA,
                "nombre": empleado.NOMBRECUENTA,
                "correo": empleado.CORREO
            } if empleado else None
        })

    return {
        "cliente": {
            "id": cuenta.IDCUENTA,
            "nombre": cuenta.NOMBRECUENTA,
            "correo": cuenta.CORREO
        },
        "tickets": resultados
    }

@router.patch("/CambiarNivelTicket/{codigo}")
def cambiar_nivel_ticket(
    codigo: int = ...,
    data: CambiarNivelTicketRequest = ...,
    db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter_by(IDTICKET=codigo).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    ticket.NIVEL = data.nivel
    db.commit()

    return {"mensaje": f"Nivel del ticket {codigo} actualizado a {data.nivel}"}

@router.patch("/CambiarEstadoTicket/{codigo}")
def cambiar_estado_ticket(
    codigo: int = ...,
    data: CambiarEstadoTicketRequest = ...,
    db: Session = Depends(get_db)
    ):
    ticket = db.query(Ticket).filter_by(IDTICKET=codigo).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    ticket.ESTADOTICKET = data.estado
    db.commit()

    return {"mensaje": f"Estado del ticket {codigo} actualizado a {data.estado}"}
            
@router.patch("/asignarTicket/{codigo}")
def asignar_ticket(
    codigo: int = ...,
    data: AsignarTicketRequest = ...,
    db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter_by(IDTICKET=codigo).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    empleado = db.query(Cuenta).filter_by(IDCUENTA=data.idempleado).first()
    if not empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    ticket.IDEMPLEADO = data.idempleado
    db.commit()

    return {"mensaje": f"Ticket {codigo} asignado correctamente al empleado {data.idempleado}"}
@router.get("/ticket/{codigo}")
def obtener_ticket_por_codigo(
    codigo: int = ...,
    db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter_by(IDTICKET=codigo).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    cliente = db.query(Cuenta).filter_by(IDCUENTA=ticket.IDCLIENTE).first()
    empleado = db.query(Cuenta).filter_by(IDCUENTA=ticket.IDEMPLEADO).first() if ticket.IDEMPLEADO else None

    respuestas = db.query(RespuestaTicket)\
        .filter_by(IDTICKET=codigo)\
        .order_by(RespuestaTicket.FECHARESPUESTA.asc())\
        .all()

    return {
        "id_ticket": ticket.IDTICKET,
        "descripcion": ticket.DESCRTICKET,
        "estado": ticket.ESTADOTICKET,
        "nivel": ticket.NIVEL,
        "fecha_creacion": ticket.FCHCREACION,
        "fecha_solucion": ticket.FCHSOLUCION,
        "cliente": {
            "id": cliente.IDCUENTA,
            "nombre": cliente.NOMBRECUENTA,
            "correo": cliente.CORREO
        },
        "empleado_asignado": {
            "id": empleado.IDCUENTA,
            "nombre": empleado.NOMBRECUENTA,
            "correo": empleado.CORREO
        } if empleado else None,
        "respuestas": [
            {
                "id_respuesta": r.IDRESPUESTATICKET,
                "fecha": r.FECHARESPUESTA,
                "contenido": r.RESPUESTA
            } for r in respuestas
        ]
    }

@router.get("/ver-tickets")
def ver_tickets_por_estado(
    estado_ticket: int = Query(..., description="Estado del ticket (1: ACTIVO, 2: INACTIVO)"),
    db: Session = Depends(get_db)
):
    tickets = db.query(Ticket).filter(Ticket.ESTADOTICKET == estado_ticket).all()
    if not tickets:
        raise HTTPException(status_code=404, detail="No se encontraron tickets con ese estado")

    resultados = []
    for t in tickets:
        cliente = db.query(Cuenta).filter_by(IDCUENTA=t.IDCLIENTE).first()
        empleado = db.query(Cuenta).filter_by(IDCUENTA=t.IDEMPLEADO).first() if t.IDEMPLEADO else None

        resultados.append({
            "id_ticket": t.IDTICKET,
            "descripcion": t.DESCRTICKET,
            "nivel": t.NIVEL,
            "estado": t.ESTADOTICKET,
            "fecha_creacion": t.FCHCREACION,
            "fecha_solucion": t.FCHSOLUCION,
            "cliente": {
                "id": cliente.IDCUENTA,
                "nombre": cliente.NOMBRECUENTA,
                "correo": cliente.CORREO
            },
            "empleado_asignado": {
                "id": empleado.IDCUENTA,
                "nombre": empleado.NOMBRECUENTA,
                "correo": empleado.CORREO
            } if empleado else None
        })

    return resultados
@router.get("/ver-tickets-niveles")
def ver_tickets_por_estado_y_nivel(
    estado_ticket: int = Query(..., description="Estado del ticket (1: ACTIVO, 2: INACTIVO)"),
    nivel_ticket: int = Query(..., description="Nivel del ticket (por ejemplo 1 a 5)"),
    db: Session = Depends(get_db)
):
    tickets = db.query(Ticket).filter(
        Ticket.ESTADOTICKET == estado_ticket,
        Ticket.NIVEL == nivel_ticket
    ).all()

    if not tickets:
        raise HTTPException(status_code=404, detail="No se encontraron tickets con ese estado y nivel")

    resultados = []
    for t in tickets:
        cliente = db.query(Cuenta).filter_by(IDCUENTA=t.IDCLIENTE).first()
        empleado = db.query(Cuenta).filter_by(IDCUENTA=t.IDEMPLEADO).first() if t.IDEMPLEADO else None

        resultados.append({
            "id_ticket": t.IDTICKET,
            "descripcion": t.DESCRTICKET,
            "nivel": t.NIVEL,
            "estado": t.ESTADOTICKET,
            "fecha_creacion": t.FCHCREACION,
            "fecha_solucion": t.FCHSOLUCION,
            "cliente": {
                "id": cliente.IDCUENTA,
                "nombre": cliente.NOMBRECUENTA,
                "correo": cliente.CORREO
            },
            "empleado_asignado": {
                "id": empleado.IDCUENTA,
                "nombre": empleado.NOMBRECUENTA,
                "correo": empleado.CORREO
            } if empleado else None
        })

    return resultados



@router.get("/mis-tickets-empleado")
def obtener_tickets_asignados(
    idempleado: str = Query(..., description="ID del empleado"),
    db: Session = Depends(get_db)
):
    empleado = db.query(Cuenta).filter_by(IDCUENTA=idempleado).first()
    if not empleado:
        raise HTTPException(status_code=404, detail=f"Empleado {idempleado} no encontrado")

    tickets = db.query(Ticket).filter_by(IDEMPLEADO=idempleado).all()
    if not tickets:
        raise HTTPException(status_code=404, detail="No se encontraron tickets asignados a este empleado")

    resultados = []
    for t in tickets:
        cliente = db.query(Cuenta).filter_by(IDCUENTA=t.IDCLIENTE).first()

        resultados.append({
            "id_ticket": t.IDTICKET,
            "descripcion": t.DESCRTICKET,
            "nivel": t.NIVEL,
            "estado": t.ESTADOTICKET,
            "fecha_creacion": t.FCHCREACION,
            "fecha_solucion": t.FCHSOLUCION,
            "cliente": {
                "id": cliente.IDCUENTA,
                "nombre": cliente.NOMBRECUENTA,
                "correo": cliente.CORREO
            }
        })

    return {
        "empleado": {
            "id": empleado.IDCUENTA,
            "nombre": empleado.NOMBRECUENTA,
            "correo": empleado.CORREO
        },
        "tickets_asignados": resultados
    }