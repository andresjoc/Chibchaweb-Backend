from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime
import random
from sqlalchemy.orm import Session
from api.DAO.database import get_db
from api.ORM.models_sqlalchemy import Cuenta, Carrito, MetodoPagoCuenta, TipoCuenta
from api.DTO.models import CuentaCreate, LoginRequest,CuentaNombreCorreo, CorreoRequest, CuentaResponse, CuentaAdminUpdateRequest, CambiarTipoCuentaRequest, CambiarContrasenaRequest,RestablecerContrasenaRequest, SolicitarRecuperacionRequest
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

import random
import string
import os
import uuid
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import SQLAlchemyError
router = APIRouter()



@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    cuenta = (
        db.query(Cuenta)
        .filter(Cuenta.IDENTIFICACION == data.identificacion)
        .first()
    )

    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    if not verify_password(data.password, cuenta.PASSWORD):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    return {
        "message": "Inicio de sesión exitoso",
        "idcuenta": cuenta.IDCUENTA,
        "nombrecuenta": cuenta.NOMBRECUENTA,
        "identificacion": cuenta.IDENTIFICACION,
        "tipocuenta": cuenta.TIPOCUENTA_REL.NOMBRETIPO if cuenta.TIPOCUENTA_REL else None,
        "pais": cuenta.PAIS_REL.NOMBREPAIS if cuenta.PAIS_REL else None,
        "plan": cuenta.PLAN_REL.NOMBREPLAN if cuenta.PLAN_REL else None,
        "correo": cuenta.CORREO,
        "telefono": cuenta.TELEFONO,
        "fecharegistro": cuenta.FECHAREGISTRO.isoformat(),
        "direccion": cuenta.DIRECCION
    }



def generar_token_corto(longitud=6):
    caracteres = string.ascii_uppercase + string.digits  # A-Z y 0-9
    return ''.join(random.choices(caracteres, k=longitud))

@router.post("/registrar2")
def registrar_cuenta2(cuenta_data: CuentaCreate, db: Session = Depends(get_db)):
    # Inicia la transacción
    try:
        # Generación del IDCUENTA con un formato único
        now_str = datetime.now().strftime("%Y%m%d%H%M%S")
        idcuenta = f"{random.randint(1, 9)}{now_str}"
        token_verificacion = generar_token_corto()
        # Hashing de la contraseña
        hashed_password = hash_password(cuenta_data.password)

        # Creación de la cuenta en la base de datos
        cuenta = Cuenta(
            IDCUENTA=idcuenta,
            IDTIPOCUENTA=cuenta_data.idtipocuenta,
            IDPAIS=cuenta_data.idpais,
            IDPLAN=cuenta_data.idplan,
            PASSWORD=hashed_password,
            IDENTIFICACION=cuenta_data.identificacion,
            NOMBRECUENTA=cuenta_data.nombrecuenta,
            CORREO=cuenta_data.correo,
            TELEFONO=cuenta_data.telefono,
            FECHAREGISTRO=datetime.now().date(),
            DIRECCION=cuenta_data.direccion,
            TOKEN=token_verificacion  # <-- AQUÍ se guarda el token
        )

        # Insertamos la cuenta en la base de datos
        db.add(cuenta)
        db.commit()
        db.refresh(cuenta)

        # Crear el método de pago asociado al IDCUENTA
        metodo_pago = MetodoPagoCuenta(
            IDCUENTA=idcuenta,  # Ya no es necesario pasar IDMETODOPAGOCUENTA
            IDTIPOMETODOPAGO=1,  # ID para tarjeta de crédito
            ACTIVOMETODOPAGOCUENTA=True,  # Activamos el método de pago
        )

        db.add(metodo_pago)
        db.commit()
        db.refresh(metodo_pago)  # El ID se genera automáticamente

        # Crear un carrito asociado al IDCUENTA con el IDMETODOPAGOCUENTA correcto
        carrito = Carrito(
            IDESTADOCARRITO="1",  # Suponiendo que "1" es un estado válido
            IDCUENTA=idcuenta,
            IDMETODOPAGOCUENTA=metodo_pago.IDMETODOPAGOCUENTA  # Usamos el ID del método de pago recién creado
        )
        db.add(carrito)
        db.commit()
        db.refresh(carrito)

        remitente = os.getenv("EMAIL_REMITENTE")
        contrasena = os.getenv("EMAIL_CONTRASENA")
        enlace = f"https://www.chibchaweb.site/verificar?token={token_verificacion}&idcuenta={idcuenta}"

        msg = EmailMessage()
        msg["Subject"] = "Verifica tu cuenta en ChibchaWeb"
        msg["From"] = formataddr(("ChibchaWeb", remitente))
        msg["To"] = cuenta_data.correo
        msg.set_content(
    f"""Hola {cuenta_data.nombrecuenta},

Gracias por registrarte en ChibchaWeb. Para activar tu cuenta, tienes dos opciones:

1. Haz clic en el siguiente enlace para verificar automáticamente:
   {enlace}

2. O bien, copia y pega este código en la página de verificación manual:
   Código de verificación: {token_verificacion}

Este código es válido por un tiempo limitado. Si no solicitaste este registro, puedes ignorar este mensaje.

Atentamente,
El equipo de ChibchaWeb
"""
)
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as smtp:
                smtp.login(remitente, contrasena)
                smtp.send_message(msg)
        except Exception as email_err:
            print(f"Error al enviar correo de verificación (registrar2): {email_err}")

        # Devolvemos la respuesta con el IDCUENTA generado
        return {"message": "Cuenta, carrito y método de pago registrados exitosamente", "idcuenta": cuenta.IDCUENTA}
    
    except SQLAlchemyError as e:
        db.rollback()  # Si algo falla, deshacemos los cambios
        raise HTTPException(status_code=500, detail=f"Error al registrar: {str(e)}")

    except Exception as e:
        db.rollback()  # Deshacemos cualquier cambio si hay otro error
        raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")
    
@router.get("/cuentas-por-tipo", response_model=List[CuentaNombreCorreo])
def obtener_cuentas_por_tipo(idtipo: int, db: Session = Depends(get_db)):
    cuentas = db.query(Cuenta).filter(Cuenta.IDTIPOCUENTA == idtipo).all()

    if not cuentas:
        raise HTTPException(status_code=404, detail="No se encontraron cuentas con ese tipo")

    # Solo extraemos los campos requeridos
    resultado = [{"nombrecuenta": c.NOMBRECUENTA, "correo": c.CORREO} for c in cuentas]

    return resultado

@router.post("/cuenta_por_correo", response_model=CuentaResponse)
def obtener_cuenta_por_correo(data: CorreoRequest, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(Cuenta.CORREO == data.correo).first()
    
    if not cuenta:
        raise HTTPException(status_code=404, detail="No se encontró cuenta con ese correo.")
    
    return cuenta


@router.post("/solicitar-registro")
def solicitar_registro(nombre: str, correo: str, password: str, identificacion: str, telefono: str, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(Cuenta.CORREO == correo).first()

    if cuenta:
        if cuenta.TOKEN == "NA":
            raise HTTPException(status_code=400, detail="El usuario ya está verificado.")
        else:
            token = cuenta.TOKEN  # Reutilizamos
    else:
        token = str(uuid.uuid4())
        try:
            telefono_int = int(telefono)
        except ValueError:
            telefono_int = 0
            
        nueva = Cuenta(
            IDCUENTA=str(uuid.uuid4())[:15],
            IDTIPOCUENTA=1,
            IDPAIS=170,
            PASSWORD=password,
            IDENTIFICACION=identificacion,
            NOMBRECUENTA=nombre,
            CORREO=correo,
            TELEFONO=telefono_int,
            FECHAREGISTRO=datetime.today().date(),
            DIRECCION="",
            TOKEN=token
        )
        db.add(nueva)
        db.commit()

    # ENVÍO DEL CORREO

    remitente = os.getenv("EMAIL_REMITENTE")
    contrasena = os.getenv("EMAIL_CONTRASENA") 

    msg = EmailMessage()
    msg["Subject"] = "Verificación de cuenta en ChibchaWeb"
    msg["From"] = formataddr(("ChibchaWeb", remitente))
    msg["To"] = correo
    msg.set_content(
        f"Hola {nombre},\n\n"
        f"Gracias por registrarte en ChibchaWeb. Tu código de verificación es:\n\n"
        f"Código: {token}\n\n"
        f"Atentamente,\n"
        f"El equipo de ChibchaWeb"
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as smtp:
            smtp.login(remitente, contrasena)
            smtp.send_message(msg)
    except Exception as email_err:
        print(f"Error al enviar correo de verificación (solicitar-registro): {email_err}")
    return {"mensaje": "Correo enviado con verificación."}

@router.get("/confirmar-registro")
def confirmar_registro(token: str, idcuenta: str, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(
        Cuenta.IDCUENTA == idcuenta,
        Cuenta.TOKEN == token
    ).first()

    if not cuenta:
        raise HTTPException(status_code=404, detail="Token inválido o IDCUENTA no coincide.")

    if cuenta.TOKEN == "NA":
        return {"mensaje": "Esta cuenta ya fue verificada."}

    cuenta.TOKEN = "NA"
    db.commit()

    return {"mensaje": "Cuenta verificada correctamente. Ya puedes iniciar sesión."}

@router.get("/estoy-verificado")
def estoy_verificado(idcuenta: str, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(Cuenta.IDCUENTA == idcuenta).first()

    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")

    if cuenta.TOKEN == "NA":
        return {"verificado": True}
    else:
        return {"verificado": False}
    
@router.put("/admin/modificar_cuenta/{idcuenta}")
def modificar_cuenta_admin(idcuenta: str, datos_actualizados: CuentaAdminUpdateRequest, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(Cuenta.IDCUENTA == idcuenta).first()

    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    campos_actualizables = [
        "IDTIPOCUENTA", "IDPAIS", "IDPLAN", "NOMBRECUENTA",
        "CORREO", "TELEFONO", "FECHAREGISTRO", "DIRECCION"
    ]

    for campo in campos_actualizables:
        nuevo_valor = getattr(datos_actualizados, campo.lower(), None)
        if nuevo_valor is not None:
            setattr(cuenta, campo, nuevo_valor)

    db.commit()
    db.refresh(cuenta)

    return {"mensaje": "Cuenta modificada correctamente"}

@router.delete("/admin/eliminar_cuenta/{idcuenta}")
def eliminar_cuenta(idcuenta: str, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(Cuenta.IDCUENTA == idcuenta).first()

    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    try:
        db.delete(cuenta)
        db.commit()
        return {"mensaje": f"Cuenta con ID '{idcuenta}' eliminada correctamente"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar la cuenta porque tiene datos relacionados en otras tablas"
        )
    
@router.patch("/admin/cambiar_tipo_cuenta")
def cambiar_tipo_cuenta(data: CambiarTipoCuentaRequest, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(Cuenta.IDCUENTA == data.idcuenta).first()

    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    tipo_existe = db.query(TipoCuenta).filter(TipoCuenta.IDTIPOCUENTA == data.idtipocuenta).first()
    if not tipo_existe:
        raise HTTPException(status_code=400, detail=f"IDTIPOCUENTA '{data.idtipocuenta}' no es válido")

    cuenta.IDTIPOCUENTA = data.idtipocuenta
    db.commit()

    return {"mensaje": f"Tipo de cuenta actualizado correctamente a {data.idtipocuenta}"}

@router.post("/cambiar-contrasena")
def cambiar_contrasena(data: CambiarContrasenaRequest, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(Cuenta.IDCUENTA == data.idcuenta).first()

    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    if not verify_password(data.contrasena_actual, cuenta.PASSWORD):
        raise HTTPException(status_code=401, detail="La contraseña actual no es válida")

    if verify_password(data.contrasena_nueva, cuenta.PASSWORD):
        raise HTTPException(status_code=400, detail="La nueva contraseña no puede ser igual a la actual")

    cuenta.PASSWORD = hash_password(data.contrasena_nueva)
    db.commit()

    return {"mensaje": "Contraseña actualizada correctamente"}


def generar_token_recuperacion(longitud=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=longitud))

@router.post("/solicitar-recuperacion")
def solicitar_recuperacion(data: SolicitarRecuperacionRequest, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(Cuenta.CORREO == data.correo).first()

    if not cuenta:
        raise HTTPException(status_code=404, detail="No se encontró ninguna cuenta con ese correo.")

    token = generar_token_recuperacion()
    cuenta.TOKEN = token
    db.commit()

    # Enviar correo
    remitente = os.getenv("EMAIL_REMITENTE")
    contrasena = os.getenv("EMAIL_CONTRASENA")

    msg = EmailMessage()
    msg["Subject"] = "Recuperación de contraseña – ChibchaWeb"
    msg["From"] = formataddr(("ChibchaWeb", remitente))
    msg["To"] = data.correo
    msg.set_content(f"""
Hola {cuenta.NOMBRECUENTA},

Has solicitado restablecer tu contraseña en ChibchaWeb.

Tu código de recuperación es:
    {token}

Ingresa este código en la aplicación para definir tu nueva contraseña.

Si no solicitaste este cambio, ignora este correo.

— El equipo de ChibchaWeb
""")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as smtp:
            smtp.login(remitente, contrasena)
            smtp.send_message(msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo: {e}")

    return {"mensaje": "Correo de recuperación enviado correctamente"}

@router.post("/restablecer-contrasena")
def restablecer_contrasena(data: RestablecerContrasenaRequest, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter(Cuenta.CORREO == data.correo).first()

    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")

    if cuenta.TOKEN != data.token:
        raise HTTPException(status_code=400, detail="Código de recuperación inválido.")

    if verify_password(data.nueva_contrasena, cuenta.PASSWORD):
        raise HTTPException(status_code=400, detail="La nueva contraseña no puede ser igual a la actual.")

    cuenta.PASSWORD = hash_password(data.nueva_contrasena)
    cuenta.TOKEN = "NA"  # Invalidamos el token
    db.commit()

    return {"mensaje": "Contraseña restablecida correctamente"}