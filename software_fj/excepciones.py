"""Jerarquía de excepciones personalizadas del sistema Software FJ.

Todas heredan de :class:`SoftwareFJError`, de modo que el programa principal
puede capturar cualquier error de negocio con un único ``except`` y seguir
funcionando, mientras que cada capa lanza el tipo más específico posible.

Jerarquía::

    SoftwareFJError
    ├── ValidacionError
    │   ├── ClienteInvalidoError
    │   └── ParametroFaltanteError
    ├── ServicioError
    │   ├── ParametroServicioError
    │   └── ServicioNoDisponibleError
    ├── ReservaError
    │   ├── ReservaInvalidaError
    │   └── OperacionNoPermitidaError
    ├── CalculoInconsistenteError
    ├── EntidadDuplicadaError
    └── EntidadNoEncontradaError
"""

from __future__ import annotations


class SoftwareFJError(Exception):
    """Excepción base de todos los errores de negocio del sistema.

    Attributes:
        mensaje: Descripción legible del error.
        codigo: Código corto que identifica el tipo de error en los logs.
    """

    # Código por defecto; cada subclase define el suyo.
    codigo: str = "FJ-000"

    def __init__(self, mensaje: str, codigo: str | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        # Permite sobrescribir el código en una instancia concreta si se necesita.
        if codigo is not None:
            self.codigo = codigo

    def __str__(self) -> str:
        return f"[{self.codigo}] {self.mensaje}"


# --- Errores de validación de datos -----------------------------------------
class ValidacionError(SoftwareFJError):
    """Datos de entrada con formato o valor inválido."""

    codigo = "FJ-100"


class ClienteInvalidoError(ValidacionError):
    """Datos personales de un cliente que no superan las validaciones."""

    codigo = "FJ-101"


class ParametroFaltanteError(ValidacionError):
    """Falta un parámetro obligatorio (None o cadena vacía)."""

    codigo = "FJ-102"


# --- Errores de servicios ---------------------------------------------------
class ServicioError(SoftwareFJError):
    """Error general relacionado con la definición o uso de un servicio."""

    codigo = "FJ-200"


class ParametroServicioError(ServicioError):
    """Parámetros de un servicio (tarifa, duración, capacidad...) inválidos."""

    codigo = "FJ-201"


class ServicioNoDisponibleError(ServicioError):
    """El servicio está deshabilitado o no tiene recursos suficientes."""

    codigo = "FJ-202"


# --- Errores de reservas ----------------------------------------------------
class ReservaError(SoftwareFJError):
    """Error general en el ciclo de vida de una reserva."""

    codigo = "FJ-300"


class ReservaInvalidaError(ReservaError):
    """La reserva no puede crearse o confirmarse con los datos dados."""

    codigo = "FJ-301"


class OperacionNoPermitidaError(ReservaError):
    """Transición de estado no permitida (p. ej. procesar una reserva cancelada)."""

    codigo = "FJ-302"


# --- Otros errores ----------------------------------------------------------
class CalculoInconsistenteError(SoftwareFJError):
    """Un cálculo de costos produjo un valor imposible (negativo, infinito...)."""

    codigo = "FJ-400"


class EntidadDuplicadaError(SoftwareFJError):
    """Se intentó registrar una entidad que ya existe."""

    codigo = "FJ-500"


class EntidadNoEncontradaError(SoftwareFJError):
    """La entidad buscada no existe en las listas internas."""

    codigo = "FJ-501"
