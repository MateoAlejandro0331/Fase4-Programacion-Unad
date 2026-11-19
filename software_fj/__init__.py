"""Sistema Integral de Gestión de Clientes, Servicios y Reservas — Software FJ."""

import logging

from .cliente import Cliente
from .entidad import EntidadBase
from .logger_config import configurar_logging
from .reserva import EstadoReserva, Reserva
from .servicios import AlquilerEquipo, AsesoriaEspecializada, ReservaSala, Servicio
from .sistema import SistemaGestion

# Si quien use el paquete no llama a configurar_logging(), el NullHandler evita
# que los mensajes salgan por el handler de último recurso de Python.
logging.getLogger("software_fj").addHandler(logging.NullHandler())

__all__ = [
    "AlquilerEquipo",
    "AsesoriaEspecializada",
    "Cliente",
    "EntidadBase",
    "EstadoReserva",
    "Reserva",
    "ReservaSala",
    "Servicio",
    "SistemaGestion",
    "configurar_logging",
]
