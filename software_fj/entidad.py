"""Clase abstracta base para todas las entidades del sistema."""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar


class EntidadBase(ABC):
    """Entidad general del sistema con identificador único y fecha de creación.

    Cada subclase concreta define ``PREFIJO`` y recibe su propio contador, de
    modo que los IDs quedan como ``CLI-0001``, ``SRV-0001``, ``RES-0001``.

    Attributes:
        id: Identificador único e inmutable de la entidad.
        fecha_creacion: Momento en que se creó el objeto.
    """

    # Prefijo del identificador; las subclases concretas lo sobrescriben.
    PREFIJO: ClassVar[str] = "ENT"
    # Contador de IDs; __init_subclass__ crea uno por cada familia de entidades.
    _contador: ClassVar[itertools.count] = itertools.count(1)

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Solo las clases que declaran su propio PREFIJO reciben un contador nuevo;
        # así ReservaSala, AlquilerEquipo, etc. comparten la numeración "SRV-" de Servicio.
        if "PREFIJO" in cls.__dict__:
            cls._contador = itertools.count(1)

    def __init__(self) -> None:
        # Atributos "privados" (name mangling) para que no se modifiquen desde fuera.
        # El ID NO se asigna aquí: si la validación de la subclase falla, el objeto
        # se descarta y no debe "gastar" un número (evita huecos como RES-0001, RES-0004).
        self.__id: str | None = None
        self.__fecha_creacion = datetime.now()

    def _asignar_id(self) -> None:
        """Asigna el siguiente ID consecutivo; se llama al final de un ``__init__`` exitoso.

        Es idempotente: si el objeto ya tiene ID, no hace nada.
        """
        if self.__id is None:
            self.__id = f"{self.PREFIJO}-{next(self._contador):04d}"

    @property
    def id(self) -> str:
        """Identificador único de la entidad (solo lectura)."""
        # Respaldo: si una subclase olvidara llamar a _asignar_id(), se asigna al leerlo.
        self._asignar_id()
        return self.__id  # type: ignore[return-value]

    @property
    def fecha_creacion(self) -> datetime:
        """Fecha y hora de creación (solo lectura)."""
        return self.__fecha_creacion

    @abstractmethod
    def validar(self) -> None:
        """Verifica la consistencia interna; lanza una excepción si no es válida."""

    @abstractmethod
    def describir(self) -> str:
        """Devuelve una descripción legible de la entidad."""

    def __str__(self) -> str:
        # Polimorfismo: cada subclase aporta su propia descripción.
        return self.describir()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.id}>"
