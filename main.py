"""Punto de entrada de Software FJ.

Uso::

    python main.py            # abre la aplicación de escritorio (Tkinter)
    python main.py --consola  # ejecuta la simulación de 25 operaciones en consola

Si la interfaz gráfica no puede iniciarse (Tkinter no instalado o sin pantalla),
el error se registra en el log y se ejecuta la simulación en consola, de modo
que el programa nunca termina de forma abrupta.
"""

from __future__ import annotations

import argparse
import logging

from software_fj import configurar_logging
from software_fj.simulacion import ejecutar_simulacion

logger = logging.getLogger("software_fj.main")


def iniciar_interfaz() -> bool:
    """Abre la ventana principal; devuelve False si la interfaz no pudo iniciarse."""
    try:
        import tkinter as tk

        from software_fj.gui import App
    except ImportError as error:
        logger.critical("Tkinter no está disponible: %s", error)
        return False

    try:
        app = App()
    except tk.TclError as error:
        # Típico en servidores sin entorno gráfico ("no display name").
        logger.critical("No se pudo crear la ventana: %s", error)
        return False
    else:
        app.mainloop()
        return True


def main(argumentos: list[str] | None = None) -> None:
    """Configura el logging y lanza la interfaz gráfica o la simulación en consola."""
    parser = argparse.ArgumentParser(description="Sistema de gestión Software FJ")
    parser.add_argument("--consola", action="store_true",
                        help="ejecuta la simulación en consola sin abrir la ventana")
    opciones = parser.parse_args(argumentos)

    configurar_logging()
    if opciones.consola:
        ejecutar_simulacion()
    elif not iniciar_interfaz():
        logger.warning("Se ejecuta la simulación en consola como alternativa.")
        ejecutar_simulacion()


if __name__ == "__main__":
    main()
