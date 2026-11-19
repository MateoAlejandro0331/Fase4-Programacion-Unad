"""Fachada del sistema: gestiona clientes, servicios y reservas en listas internas.

No se usa ninguna base de datos: todo vive en listas de objetos en memoria y
solo el archivo de logs se escribe en disco. Cada operación pública queda
envuelta por :func:`registrar_operacion`, que registra en el log los errores
de negocio y traduce cualquier error inesperado a :class:`SoftwareFJError`.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from functools import singledispatchmethod
from typing import ParamSpec, TypeVar

from .cliente import Cliente
from .excepciones import (
    EntidadDuplicadaError,
    EntidadNoEncontradaError,
    ServicioError,
    SoftwareFJError,
)
from .reserva import IVA_POR_DEFECTO, EstadoReserva, Reserva
from .servicios import AlquilerEquipo, AsesoriaEspecializada, ReservaSala, Servicio

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def _cadena_de_causas(error: BaseException) -> str:
    """Recorre ``__cause__`` y devuelve la cadena de excepciones encadenadas como texto."""
    eslabones: list[str] = []
    causa = error.__cause__
    while causa is not None:
        eslabones.append(f"{type(causa).__name__}: {causa}")
        causa = causa.__cause__
    return " ← ".join(eslabones)


def _ultimos_digitos(documento: object) -> str:
    """Devuelve los últimos 4 caracteres del documento, sin espacios, para los mensajes."""
    return str(documento).strip()[-4:]


def registrar_operacion(descripcion: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorador que registra en el log el resultado de una operación del sistema.

    * Errores de negocio (``SoftwareFJError``): se registran como ERROR, junto con
      su causa encadenada si existe, y se vuelven a lanzar.
    * Errores inesperados (cualquier otra ``Exception``): se registran con el
      traceback completo y se relanzan como ``SoftwareFJError`` encadenado.

    Args:
        descripcion: Nombre legible de la operación para los mensajes de log.

    Returns:
        El decorador que envuelve el método.
    """

    def decorador(funcion: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(funcion)
        def envoltura(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return funcion(*args, **kwargs)
            except SoftwareFJError as error:
                cadena = _cadena_de_causas(error)
                if cadena:
                    logger.error("%s falló: %s | causa: %s", descripcion, error, cadena)
                else:
                    logger.error("%s falló: %s", descripcion, error)
                raise
            except Exception as error:
                # Error no previsto: se guarda el traceback completo en el log.
                logger.exception("Error inesperado en '%s'", descripcion)
                raise SoftwareFJError(
                    f"Error inesperado en '{descripcion}': {type(error).__name__}", "FJ-999"
                ) from error

        return envoltura

    return decorador


class SistemaGestion:
    """Sistema integral de gestión de Software FJ.

    Attributes:
        clientes: Copia de la lista de clientes registrados.
        servicios: Copia de la lista de servicios del catálogo.
        reservas: Copia de la lista de reservas creadas.
    """

    # Fábrica de servicios: asocia un nombre de tipo con su clase concreta.
    # Agregar un servicio nuevo solo requiere añadir una entrada aquí (extensibilidad).
    TIPOS_SERVICIO: dict[str, type[Servicio]] = {
        "sala": ReservaSala,
        "equipo": AlquilerEquipo,
        "asesoria": AsesoriaEspecializada,
    }

    def __init__(self) -> None:
        # Listas internas: el "almacenamiento" del sistema, sin base de datos.
        self._clientes: list[Cliente] = []
        self._servicios: list[Servicio] = []
        self._reservas: list[Reserva] = []
        logger.info("Sistema Software FJ iniciado.")

    @property
    def clientes(self) -> list[Cliente]:
        """Copia de la lista de clientes."""
        return list(self._clientes)

    @property
    def servicios(self) -> list[Servicio]:
        """Copia de la lista de servicios."""
        return list(self._servicios)

    @property
    def reservas(self) -> list[Reserva]:
        """Copia de la lista de reservas."""
        return list(self._reservas)

    # --- Clientes --------------------------------------------------------------
    @registrar_operacion("Registro de cliente")
    def registrar_cliente(
        self, nombre: str, documento: str, email: str, telefono: str | None = None
    ) -> Cliente:
        """Crea un cliente validado y lo agrega a la lista, evitando duplicados."""
        if any(c.documento == str(documento).strip() for c in self._clientes):
            raise EntidadDuplicadaError(
                f"Ya existe un cliente con documento terminado en {_ultimos_digitos(documento)}."
            )
        cliente = Cliente(nombre, documento, email, telefono)
        self._clientes.append(cliente)
        logger.info("Cliente registrado: %s", cliente)
        return cliente

    def buscar_cliente(self, documento: str) -> Cliente:
        """Devuelve el cliente con ese documento o lanza EntidadNoEncontradaError."""
        for cliente in self._clientes:
            if cliente.documento == str(documento).strip():
                return cliente
        raise EntidadNoEncontradaError(
            f"No existe un cliente con documento terminado en {_ultimos_digitos(documento)}."
        )

    # --- Servicios -------------------------------------------------------------
    @registrar_operacion("Creación de servicio")
    def crear_servicio(self, tipo: str, **datos: object) -> Servicio:
        """Crea un servicio del tipo indicado ("sala", "equipo" o "asesoria").

        Args:
            tipo: Clave de ``TIPOS_SERVICIO``.
            **datos: Argumentos del constructor de la clase concreta.

        Returns:
            El servicio creado y agregado al catálogo.
        """
        clase = self.TIPOS_SERVICIO.get(str(tipo).lower())
        if clase is None:
            raise ServicioError(
                f"Tipo de servicio '{tipo}' no existe; use {list(self.TIPOS_SERVICIO)}."
            )
        nombre = str(datos.get("nombre") or "").strip().lower()
        if nombre and any(s.nombre.lower() == nombre for s in self._servicios):
            raise EntidadDuplicadaError(f"Ya existe un servicio llamado '{datos['nombre']}'.")
        try:
            servicio = clase(**datos)  # type: ignore[arg-type]
        except TypeError as error:
            # TypeError aquí significa argumentos faltantes o sobrantes en el constructor.
            raise ServicioError(f"Datos incompletos para crear '{tipo}': {error}") from error
        self._servicios.append(servicio)
        logger.info("Servicio creado: %s", servicio)
        return servicio

    # singledispatchmethod permite "sobrecargar" buscar_servicio según el tipo
    # del argumento: str busca por ID o nombre, int por número consecutivo.
    @singledispatchmethod
    def buscar_servicio(self, criterio: object) -> Servicio:
        """Busca un servicio; la variante depende del tipo de ``criterio``."""
        raise EntidadNoEncontradaError(
            f"Criterio de búsqueda no soportado: {type(criterio).__name__}."
        )

    @buscar_servicio.register
    def _(self, criterio: str) -> Servicio:
        texto = criterio.strip().lower()
        for servicio in self._servicios:
            if servicio.id.lower() == texto or servicio.nombre.lower() == texto:
                return servicio
        raise EntidadNoEncontradaError(f"No existe el servicio '{criterio}'.")

    @buscar_servicio.register
    def _(self, criterio: int) -> Servicio:
        return self.buscar_servicio(f"{Servicio.PREFIJO}-{criterio:04d}")

    @registrar_operacion("Cambio de disponibilidad de servicio")
    def deshabilitar_servicio(self, criterio: str | int) -> Servicio:
        """Marca un servicio como no disponible."""
        servicio = self.buscar_servicio(criterio)
        servicio.deshabilitar()
        return servicio

    @registrar_operacion("Cambio de disponibilidad de servicio")
    def habilitar_servicio(self, criterio: str | int) -> Servicio:
        """Marca un servicio como disponible."""
        servicio = self.buscar_servicio(criterio)
        servicio.habilitar()
        return servicio

    # --- Reservas --------------------------------------------------------------
    @registrar_operacion("Creación de reserva")
    def crear_reserva(
        self, documento_cliente: str, servicio: str | int, duracion: float, **opciones: object
    ) -> Reserva:
        """Crea una reserva PENDIENTE para un cliente y servicio existentes."""
        cliente = self.buscar_cliente(documento_cliente)
        srv = self.buscar_servicio(servicio)
        reserva = Reserva(cliente, srv, duracion, **opciones)
        self._reservas.append(reserva)
        logger.info("Reserva creada: %s", reserva)
        return reserva

    def buscar_reserva(self, id_reserva: str) -> Reserva:
        """Devuelve la reserva con ese ID o lanza EntidadNoEncontradaError."""
        for reserva in self._reservas:
            if reserva.id == id_reserva:
                return reserva
        raise EntidadNoEncontradaError(f"No existe la reserva '{id_reserva}'.")

    @registrar_operacion("Confirmación de reserva")
    def confirmar_reserva(
        self, id_reserva: str, impuesto: float = IVA_POR_DEFECTO, descuento: float = 0.0
    ) -> Reserva:
        """Confirma una reserva aplicando impuesto y descuento."""
        reserva = self.buscar_reserva(id_reserva)
        reserva.confirmar(impuesto, descuento)
        return reserva

    @registrar_operacion("Cancelación de reserva")
    def cancelar_reserva(self, id_reserva: str, motivo: str = "Solicitud del cliente") -> Reserva:
        """Cancela una reserva pendiente o confirmada."""
        reserva = self.buscar_reserva(id_reserva)
        reserva.cancelar(motivo)
        return reserva

    @registrar_operacion("Procesamiento de reserva")
    def procesar_reserva(self, id_reserva: str) -> dict[str, object]:
        """Procesa una reserva confirmada y devuelve su comprobante."""
        reserva = self.buscar_reserva(id_reserva)
        comprobante = reserva.procesar()
        logger.info("Comprobante emitido: %s", comprobante)
        return comprobante

    # --- Reportes --------------------------------------------------------------
    def resumen(self) -> dict[str, object]:
        """Totales de clientes, servicios, reservas por estado e ingresos procesados."""
        por_estado = {estado.value: 0 for estado in EstadoReserva}
        for reserva in self._reservas:
            por_estado[reserva.estado.value] += 1
        ingresos = sum(
            r.costo or 0.0 for r in self._reservas if r.estado is EstadoReserva.PROCESADA
        )
        return {
            "clientes": len(self._clientes),
            "servicios": len(self._servicios),
            "reservas": len(self._reservas),
            "reservas_por_estado": por_estado,
            "ingresos_procesados": round(ingresos, 2),
        }
