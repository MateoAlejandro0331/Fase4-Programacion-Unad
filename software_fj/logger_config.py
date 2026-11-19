"""Configuración centralizada del módulo ``logging`` de Python para Software FJ.

Todos los módulos del paquete obtienen su logger con
``logging.getLogger(__name__)``; como sus nombres empiezan por ``software_fj``,
heredan los handlers configurados aquí sobre el logger raíz del paquete.

Se configuran dos destinos:

* **Archivo** (``logs/software_fj.log``): nivel DEBUG, con rotación por tamaño,
  donde quedan registrados TODOS los eventos y errores (requisito del Anexo 3).
* **Consola**: nivel INFO (configurable), para seguir la simulación en vivo.
"""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

# Nombre del logger raíz del paquete: todos los loggers hijos ("software_fj.cliente",
# "software_fj.reserva", etc.) propagan sus mensajes hacia él.
NOMBRE_LOGGER_RAIZ = "software_fj"

# Ruta por defecto del archivo de logs, relativa a la raíz del proyecto.
RUTA_LOG_POR_DEFECTO = Path(__file__).resolve().parent.parent / "logs" / "software_fj.log"

# Formato detallado para el archivo: fecha, nivel, módulo, función y línea de origen.
FORMATO_ARCHIVO = (
    "%(asctime)s | %(levelname)-8s | %(name)-22s | "
    "%(funcName)s:%(lineno)d | %(message)s"
)
# Formato compacto para la consola: solo hora, nivel y mensaje.
FORMATO_CONSOLA = "%(asctime)s | %(levelname)-8s | %(message)s"

# Bandera de módulo para que la configuración se aplique una sola vez aunque
# configurar_logging() se invoque desde varios puntos (main, tests, etc.).
_configurado = False


def configurar_logging(
    ruta_archivo: Path | str = RUTA_LOG_POR_DEFECTO,
    nivel_consola: int = logging.INFO,
    max_bytes: int = 1_000_000,
    respaldos: int = 3,
    forzar: bool = False,
) -> logging.Logger:
    """Configura los handlers de archivo y consola del logger del paquete.

    Usa ``logging.config.dictConfig`` para declarar formatters y handlers. El
    archivo rota al superar ``max_bytes`` y conserva ``respaldos`` copias.

    Args:
        ruta_archivo: Ruta del archivo de logs; su carpeta se crea si no existe.
        nivel_consola: Nivel mínimo mostrado en consola (el archivo siempre es DEBUG).
        max_bytes: Tamaño máximo del archivo antes de rotar.
        respaldos: Número de archivos rotados que se conservan.
        forzar: Si es True, reconfigura aunque ya se hubiera configurado antes.

    Returns:
        El logger raíz del paquete (``software_fj``) ya configurado.
    """
    global _configurado
    # Si ya se configuró y no se pide forzar, se reutiliza la configuración existente.
    if _configurado and not forzar:
        return logging.getLogger(NOMBRE_LOGGER_RAIZ)

    ruta = Path(ruta_archivo)
    # Se crea la carpeta logs/ si no existe para evitar FileNotFoundError.
    ruta.parent.mkdir(parents=True, exist_ok=True)

    configuracion = {
        "version": 1,
        # No se desactivan los loggers creados antes de configurar (p. ej. al importar módulos).
        "disable_existing_loggers": False,
        "formatters": {
            "detallado": {"format": FORMATO_ARCHIVO, "datefmt": "%Y-%m-%d %H:%M:%S"},
            "compacto": {"format": FORMATO_CONSOLA, "datefmt": "%H:%M:%S"},
        },
        "handlers": {
            "archivo": {
                # RotatingFileHandler evita que el archivo crezca indefinidamente.
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detallado",
                "filename": str(ruta),
                "maxBytes": max_bytes,
                "backupCount": respaldos,
                # UTF-8 para conservar tildes y eñes en los mensajes.
                "encoding": "utf-8",
            },
            "consola": {
                "class": "logging.StreamHandler",
                "level": logging.getLevelName(nivel_consola),
                "formatter": "compacto",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            NOMBRE_LOGGER_RAIZ: {
                "level": "DEBUG",
                "handlers": ["archivo", "consola"],
                # No se propaga al logger raíz de Python para no duplicar mensajes.
                "propagate": False,
            }
        },
    }

    logging.config.dictConfig(configuracion)
    _configurado = True

    logger = logging.getLogger(NOMBRE_LOGGER_RAIZ)
    logger.debug("Logging configurado. Archivo de registro: %s", ruta)
    return logger
