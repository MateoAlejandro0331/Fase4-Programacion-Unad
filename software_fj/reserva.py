"""Clase Reserva: integra cliente, servicio, duración y estado.

Ciclo de vida permitido::

    PENDIENTE ──confirmar()──► CONFIRMADA ──procesar()──► PROCESADA
        │                          │
        └──────cancelar()──────────┴──────► CANCELADA

Cualquier otra transición lanza :class:`OperacionNoPermitidaError`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum

from .cliente import Cliente
from .entidad import EntidadBase
from .excepciones import (
    CalculoInconsistenteError,
    OperacionNoPermitidaError,
    ParametroFaltanteError,
    ParametroServicioError,
    ReservaError,
    ReservaInvalidaError,
    ServicioNoDisponibleError,
)
from .servicios import Servicio

logger = logging.getLogger(__name__)

# IVA colombiano aplicado por defecto al confirmar una reserva.
IVA_POR_DEFECTO = 0.19


class EstadoReserva(Enum):
    """Estados posibles de una reserva."""

    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    PROCESADA = "procesada"


class Reserva(EntidadBase):
    """Reserva de un servicio por parte de un cliente.

    Attributes:
        cliente: Cliente que realiza la reserva.
        servicio: Servicio reservado.
        duracion: Duración en horas.
        opciones: Parámetros específicos del servicio (asistentes, cantidad...).
        estado: Estado actual (:class:`EstadoReserva`).
        costo: Costo total calculado al confirmar, o None si aún no se confirma.
        historial: Lista de cambios de estado con su marca de tiempo.
    """

    PREFIJO = "RES"

    def __init__(
        self, cliente: Cliente, servicio: Servicio, duracion: float, **opciones: object
    ) -> None:
        super().__init__()
        # Validación de tipos: la reserva solo integra objetos del dominio.
        if cliente is None or servicio is None:
            raise ParametroFaltanteError("La reserva requiere un cliente y un servicio.")
        if not isinstance(cliente, Cliente):
            raise ReservaInvalidaError(f"'{cliente!r}' no es un Cliente válido.")
        if not isinstance(servicio, Servicio):
            raise ReservaInvalidaError(f"'{servicio!r}' no es un Servicio válido.")

        self._cliente = cliente
        self._servicio = servicio
        self._duracion = duracion
        self._opciones = dict(opciones)
        self._estado = EstadoReserva.PENDIENTE
        self._costo: float | None = None
        self._historial: list[tuple[datetime, EstadoReserva, str]] = []

        self.validar()
        # Tras validar, la duración se guarda normalizada como float.
        self._duracion = float(duracion)
        self._asignar_id()  # Solo una reserva válida recibe ID.
        self._registrar_cambio(EstadoReserva.PENDIENTE, "Reserva creada")

    # --- Propiedades de solo lectura ------------------------------------------
    @property
    def cliente(self) -> Cliente:
        """Cliente que realizó la reserva."""
        return self._cliente

    @property
    def servicio(self) -> Servicio:
        """Servicio reservado."""
        return self._servicio

    @property
    def duracion(self) -> float:
        """Duración en horas."""
        return self._duracion

    @property
    def opciones(self) -> dict[str, object]:
        """Copia de las opciones para que no se alteren desde fuera."""
        return dict(self._opciones)

    @property
    def estado(self) -> EstadoReserva:
        """Estado actual de la reserva."""
        return self._estado

    @property
    def costo(self) -> float | None:
        """Costo total calculado al confirmar."""
        return self._costo

    @property
    def historial(self) -> list[tuple[datetime, EstadoReserva, str]]:
        """Copia del historial de cambios de estado."""
        return list(self._historial)

    # --- Métodos de EntidadBase ---------------------------------------------
    def validar(self) -> None:
        """Valida duración y opciones contra las reglas del servicio.

        Raises:
            ReservaInvalidaError: Encadenada con el error del servicio que la originó.
        """
        try:
            self._servicio.validar_parametros(self._duracion, **self._opciones)
        except (ParametroServicioError, ParametroFaltanteError) as error:
            # Encadenamiento: se traduce el error del servicio a uno de reserva,
            # conservando el original en __cause__ para el diagnóstico en los logs.
            raise ReservaInvalidaError(
                f"Datos de reserva inválidos para '{self._servicio.nombre}': {error.mensaje}"
            ) from error

    def describir(self) -> str:
        """Resumen de la reserva."""
        costo = f"${self._costo:,.2f}" if self._costo is not None else "sin calcular"
        return (
            f"Reserva {self.id}: {self._cliente.nombre} → {self._servicio.nombre} "
            f"({self._duracion:g} h) | estado: {self._estado.value} | costo: {costo}"
        )

    # --- Ciclo de vida --------------------------------------------------------
    def _registrar_cambio(self, estado: EstadoReserva, detalle: str) -> None:
        """Cambia el estado, lo agrega al historial y lo registra en el log."""
        self._estado = estado
        self._historial.append((datetime.now(), estado, detalle))
        logger.info("%s → %s (%s)", self.id, estado.value.upper(), detalle)

    def _exigir_estado(self, *permitidos: EstadoReserva, accion: str) -> None:
        """Lanza OperacionNoPermitidaError si el estado actual no está en ``permitidos``."""
        if self._estado not in permitidos:
            raise OperacionNoPermitidaError(
                f"No se puede {accion} la reserva {self.id} en estado "
                f"'{self._estado.value}'."
            )

    def confirmar(self, impuesto: float = IVA_POR_DEFECTO, descuento: float = 0.0) -> float:
        """Calcula el costo, aparta los recursos y pasa la reserva a CONFIRMADA.

        Args:
            impuesto: Fracción de impuesto (por defecto IVA 19 %).
            descuento: Fracción de descuento entre 0 y 1.

        Returns:
            Costo total de la reserva.

        Raises:
            OperacionNoPermitidaError: Si la reserva no está PENDIENTE.
            ServicioNoDisponibleError: Si el servicio está deshabilitado o sin recursos.
            ReservaInvalidaError: Si el cálculo de costo es inconsistente (encadenada).
        """
        self._exigir_estado(EstadoReserva.PENDIENTE, accion="confirmar")
        if not self._servicio.disponible:
            raise ServicioNoDisponibleError(
                f"El servicio '{self._servicio.nombre}' no está disponible actualmente."
            )

        # try / except / else: el bloque else solo se ejecuta si no hubo excepción,
        # así el estado cambia únicamente cuando costo y recursos quedaron asegurados.
        try:
            costo = self._servicio.calcular_costo(
                self._duracion, impuesto, descuento, **self._opciones
            )
            self._servicio.reservar_recursos(**self._opciones)
        except CalculoInconsistenteError as error:
            raise ReservaInvalidaError(
                f"No se pudo confirmar {self.id}: cálculo de costo inconsistente."
            ) from error
        else:
            self._costo = costo
            self._registrar_cambio(EstadoReserva.CONFIRMADA, f"Costo total ${costo:,.2f}")
            return costo

    def cancelar(self, motivo: str = "Solicitud del cliente") -> None:
        """Cancela la reserva y libera los recursos si ya estaba confirmada.

        Raises:
            OperacionNoPermitidaError: Si ya estaba cancelada o procesada.
        """
        self._exigir_estado(
            EstadoReserva.PENDIENTE, EstadoReserva.CONFIRMADA, accion="cancelar"
        )
        estaba_confirmada = self._estado is EstadoReserva.CONFIRMADA
        # try / finally: aunque liberar recursos fallara, la reserva queda cancelada
        # para no dejarla en un estado intermedio inconsistente.
        try:
            if estaba_confirmada:
                self._servicio.liberar_recursos(**self._opciones)
        finally:
            self._registrar_cambio(EstadoReserva.CANCELADA, motivo)

    def procesar(self) -> dict[str, object]:
        """Procesa (factura) una reserva confirmada y devuelve su comprobante.

        Returns:
            Diccionario con los datos del comprobante.

        Raises:
            OperacionNoPermitidaError: Si la reserva no está CONFIRMADA.
            ReservaError: Si el comprobante no puede generarse (encadenada).
        """
        self._exigir_estado(EstadoReserva.CONFIRMADA, accion="procesar")
        # try / except / else / finally completo.
        try:
            comprobante = self._generar_comprobante()
        except CalculoInconsistenteError as error:
            raise ReservaError(f"Fallo al procesar {self.id}.") from error
        else:
            self._registrar_cambio(EstadoReserva.PROCESADA, "Pago registrado")
            return comprobante
        finally:
            # Se ejecuta siempre, haya éxito o error: deja traza del intento.
            logger.debug("Intento de procesamiento de %s finalizado (estado: %s).",
                         self.id, self._estado.value)

    def _generar_comprobante(self) -> dict[str, object]:
        """Construye el comprobante verificando que el costo almacenado sea coherente."""
        if self._costo is None or self._costo <= 0:
            raise CalculoInconsistenteError(
                f"La reserva {self.id} tiene un costo inválido: {self._costo!r}."
            )
        return {
            "reserva": self.id,
            "cliente": self._cliente.nombre,
            "documento": self._cliente.documento_enmascarado,
            "servicio": self._servicio.nombre,
            "duracion_horas": self._duracion,
            "total": self._costo,
            "fecha": datetime.now().isoformat(timespec="seconds"),
        }
