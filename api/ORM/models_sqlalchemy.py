from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Numeric, Date, DateTime, DECIMAL, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class TipoCuenta(Base):
    __tablename__ = "TIPOCUENTA"

    IDTIPOCUENTA = Column("IDTIPOCUENTA", Numeric(2), primary_key=True)
    NOMBRETIPO = Column("NOMBRETIPO", String(30), nullable=False)

    CUENTAS = relationship("Cuenta", back_populates="TIPOCUENTA_REL")


from sqlalchemy.orm import relationship

class Cuenta(Base):
    __tablename__ = "CUENTA"

    IDCUENTA = Column("IDCUENTA", String(15), primary_key=True)
    IDTIPOCUENTA = Column("IDTIPOCUENTA", Numeric(2), ForeignKey("TIPOCUENTA.IDTIPOCUENTA"), nullable=False)
    IDPAIS = Column("IDPAIS", Numeric(3), ForeignKey("PAIS.IDPAIS"), nullable=False)
    IDPLAN = Column("IDPLAN", Integer, ForeignKey("PLAN.IDPLAN"), nullable=True)
    TOKEN = Column("TOKEN", String(1084), nullable=False)
    PASSWORD = Column("PASSWORD", String(255), nullable=False)
    IDENTIFICACION = Column("IDENTIFICACION", String(15), nullable=False)
    NOMBRECUENTA = Column("NOMBRECUENTA", String(150), nullable=False)
    CORREO = Column("CORREO", String(50), nullable=False)
    TELEFONO = Column("TELEFONO", Integer, nullable=False)
    FECHAREGISTRO = Column("FECHAREGISTRO", Date, nullable=False)
    DIRECCION = Column("DIRECCION", String(30))

    # Relaciones
    TIPOCUENTA_REL = relationship("TipoCuenta", back_populates="CUENTAS")
    PAIS_REL = relationship("Pais", back_populates="CUENTAS")
    PLAN_REL = relationship("Plan", back_populates="CUENTAS")
    METODOSPAGO = relationship("MetodoPagoCuenta", back_populates="CUENTA_REL")

class Plan(Base):
    __tablename__ = "PLAN"

    IDPLAN = Column(Integer, primary_key=True)
    NOMBREPLAN = Column(String(15), nullable=False)
    COMISION = Column(DECIMAL(10, 2), nullable=False)
    LIMITEDOMINIOS = Column(Integer, nullable=False)
    CUENTAS = relationship("Cuenta", back_populates="PLAN_REL")
    

class Pais(Base):
    __tablename__ = "PAIS"

    IDPAIS = Column(Numeric(3), primary_key=True)
    NOMBREPAIS = Column(String(15), nullable=False)

    CUENTAS = relationship("Cuenta", back_populates="PAIS_REL")



class Tarjeta(Base):
    __tablename__ = "TARJETA"

    IDTARJETA = Column("IDTARJETA", Integer, primary_key=True, autoincrement=True)
    IDTIPOTARJETA = Column("IDTIPOTARJETA", Numeric(2), nullable=False)
    NUMEROTARJETA = Column("NUMEROTARJETA", String(255), nullable=False)
    CCV = Column("CCV", String(255), nullable=False) 
    FECHAVTO = Column("FECHAVTO", Date, nullable=False)



class MetodoPagoCuenta(Base):
    __tablename__ = "METODOPAGOCUENTA"

    IDMETODOPAGOCUENTA = Column("IDMETODOPAGOCUENTA", Integer, primary_key=True, autoincrement=True)  # Aquí está el cambio
    IDTARJETA = Column("IDTARJETA", Integer, ForeignKey("TARJETA.IDTARJETA"))
    IDCUENTA = Column("IDCUENTA", String(15), ForeignKey("CUENTA.IDCUENTA"))
    IDTIPOMETODOPAGO = Column("IDTIPOMETODOPAGO", Numeric(2), ForeignKey("TIPOMETODOPAGO.IDTIPOMETODOPAGO"))
    ACTIVOMETODOPAGOCUENTA = Column("ACTIVOMETODOPAGOCUENTA", Boolean, nullable=False)

    CUENTA_REL = relationship("Cuenta", back_populates="METODOSPAGO")
    TARJETA_REL = relationship("Tarjeta")


class TipoMetodoPago(Base):
    __tablename__ = "TIPOMETODOPAGO"

    IDTIPOMETODOPAGO = Column("IDTIPOMETODOPAGO", Numeric(2), primary_key=True)
    NOMBRETIPOMETODOPAGO = Column("NOMBRETIPOMETODOPAGO", String(15), nullable=False)


class Dominio(Base):
    __tablename__ = "DOMINIO"

    IDDOMINIO = Column("IDDOMINIO", String(150), primary_key=True)
    NOMBREPAGINA = Column("NOMBREPAGINA", String(150), nullable=False)
    PRECIODOMINIO = Column("PRECIODOMINIO", Numeric(10, 2), nullable=False)
    OCUPADO = Column("OCUPADO", Boolean, nullable=False)


class EstadoCarrito(Base):
    __tablename__ = "ESTADOCARRITO"

    IDESTADOCARRITO = Column("IDESTADOCARRITO", String(3), primary_key=True)
    NOMESTADOCARRITO = Column("NOMESTADOCARRITO", String(30), nullable=False)


class Carrito(Base):
    __tablename__ = "CARRITO"

    IDCARRITO = Column("IDCARRITO", Integer, primary_key=True, autoincrement=True)
    IDESTADOCARRITO = Column("IDESTADOCARRITO", String(3), ForeignKey("ESTADOCARRITO.IDESTADOCARRITO"), nullable=False)
    IDCUENTA = Column("IDCUENTA", String(15), ForeignKey("CUENTA.IDCUENTA"), nullable=False)
    IDMETODOPAGOCUENTA = Column("IDMETODOPAGOCUENTA", Integer, ForeignKey("METODOPAGOCUENTA.IDMETODOPAGOCUENTA"), nullable=False)

    ESTADOCARRITO_REL = relationship("EstadoCarrito", backref="carritos")
    facturas = relationship("Factura", back_populates="carrito", cascade="all, delete-orphan")

class CarritoDominio(Base):
    __tablename__ = "CARRITODOMINIO"

    IDDOMINIO = Column("IDDOMINIO", String(150), ForeignKey("DOMINIO.IDDOMINIO"), primary_key=True)
    IDCARRITO = Column("IDCARRITO", Integer, ForeignKey("CARRITO.IDCARRITO"), primary_key=True)
    IDCARRITODOMINIO = Column("IDCARRITODOMINIO", String(10), primary_key=True)

class Factura(Base):
    __tablename__ = "FACTURA"

    IDFACTURA = Column(Integer, primary_key=True, autoincrement=True)
    IDCARRITO = Column(Integer, ForeignKey("CARRITO.IDCARRITO"), nullable=False)
    PAGOFACTURA = Column(DateTime, default=datetime.utcnow)
    VIGFACTURA = Column(DateTime, nullable=False)

    # Relación con Carrito
    carrito = relationship("Carrito", back_populates="facturas")

class InfoPaqueteHosting(Base):
    __tablename__ = "INFOPAQUETEHOSTING"
    IDINFOPAQUETEHOSTING = Column(Integer, primary_key=True, autoincrement=True)
    CANTIDADSITIOS = Column(DECIMAL(4, 0))
    NOMBREPAQUETEHOSTING = Column(String(20))
    BD = Column(DECIMAL(4, 0))
    GBENSSD = Column(DECIMAL(4, 0))
    CORREOS = Column(DECIMAL(3, 0))
    CERTIFICADOSSSLHTTPS = Column(DECIMAL(3, 0))

class PaqueteHosting(Base):
    __tablename__ = "PAQUETEHOSTING"

    IDPAQUETEHOSTING = Column(Integer, primary_key=True, autoincrement=True)
    IDINFOPAQUETEHOSTING = Column(Integer, ForeignKey("INFOPAQUETEHOSTING.IDINFOPAQUETEHOSTING"), nullable=False)
    PRECIOPAQUETE = Column(Numeric(10, 0), nullable=False)
    PERIODICIDAD = Column(String(100), nullable=False)

    infopaquete = relationship("InfoPaqueteHosting", backref="paquetes", foreign_keys=[IDINFOPAQUETEHOSTING])


class FacturaPaquete(Base):
    __tablename__ = "FACTURAPAQUETE"

    IDFACTURAPAQUETE = Column(Integer, primary_key=True, autoincrement=True)
    IDMETODOPAGOCUENTA = Column(Integer, ForeignKey("METODOPAGOCUENTA.IDMETODOPAGOCUENTA"), nullable=False)
    IDPAQUETEHOSTING = Column(Integer, ForeignKey("PAQUETEHOSTING.IDPAQUETEHOSTING"), nullable=True)
    FCHPAGO = Column(Date, nullable=False)
    FCHVENCIMIENTO = Column(Date, nullable=False)
    ESTADO = Column(Integer, nullable=False)
    VALORFP = Column(Numeric(10, 0), nullable=False)

    # Relaciones
    metodopago = relationship("MetodoPagoCuenta", backref="facturas_paquete", foreign_keys=[IDMETODOPAGOCUENTA])
    paquete_hosting = relationship("PaqueteHosting", backref="facturas_paquete", foreign_keys=[IDPAQUETEHOSTING])

class ItemPaquete(Base):
    __tablename__ = "ITEMPAQUETE"

    IDREGITEMPAQUETE = Column(Integer, primary_key=True, autoincrement=True)
    IDFACTURAPAQUETE = Column(Integer, ForeignKey("FACTURAPAQUETE.IDFACTURAPAQUETE"), nullable=False)
    DESCRIPCION = Column(String(256), nullable=False)
    TAMANO = Column(String(10), nullable=False)
    NOMBREITEM = Column(String(100), nullable=True)

    factura = relationship("FacturaPaquete", backref="items_paquete", foreign_keys=[IDFACTURAPAQUETE])

class Ticket(Base):
    __tablename__ = "TICKET"

    IDTICKET = Column(Integer, primary_key=True, autoincrement=True)
    IDCLIENTE = Column(String(15), ForeignKey("CUENTA.IDCUENTA"), nullable=False)
    DESCRTICKET = Column(String(1084), nullable=False)
    NIVEL = Column(Integer, nullable=False, default=1)
    FCHCREACION = Column(Date, nullable=False)
    ESTADOTICKET = Column(Integer, nullable=False, default=1)
    FCHSOLUCION = Column(Date, nullable=True)
    IDEMPLEADO = Column(String(15), ForeignKey("CUENTA.IDCUENTA"), nullable=True)

class RespuestaTicket(Base):
    __tablename__ = "RESPUESTATICKET"

    IDRESPUESTATICKET = Column(Integer, primary_key=True, autoincrement=True)
    RESPUESTA = Column(Text, nullable=False)
    IDTICKET = Column(Integer, ForeignKey("TICKET.IDTICKET", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    FECHARESPUESTA = Column(Date, nullable=False)

    ticket = relationship("Ticket", backref="respuestas")

class Traduccion(Base):
    __tablename__ = "TRADUCCIONES"

    IDTRADUCCION = Column(Integer, primary_key=True, autoincrement=True)
    IDIOMA = Column(String(5), nullable=False)         # Ej: ES, EN, FR
    CLAVE = Column(String(100), nullable=False)         # Ej: 'Welcome_message'
    VALOR = Column(Text, nullable=False)                # Ej: '¡Bienvenidos a ChibchaWeb!'

    __table_args__ = (
        UniqueConstraint('IDIOMA', 'CLAVE', name='uq_idioma_clave'),
    )
