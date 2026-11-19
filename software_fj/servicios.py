"""Servicios ofrecidos por Software FJ: clase abstracta y tres especializaciones.

* :class:`ReservaSala`: alquiler de salas por horas, con límite de capacidad.
* :class:`AlquilerEquipo`: alquiler de equipos con inventario de unidades.
* :class:`AsesoriaEspecializada`: asesorías con nivel del asesor y modalidad.

Todas comparten la plantilla :meth:`Servicio.calcular_costo`, que admite varias
"sobrecargas" (solo duración; duración + impuesto; duración + impuesto +
descuento) y delega en cada subclase la parte específica del cálculo.
"""

from __future__ import annotations

import logging
import math
from abc import abstractmethod
from typing import ClassVar, overload

from .entidad import EntidadBase
from .excepciones import (
    CalculoInconsistenteError,
    ParametroFaltanteError,
    ParametroServicioError,
    ServicioNoDisponibleError,
)

logger = logging.getLogger(__name__)


def _a_numero(valor: object, campo: str) -> float:
    """Convierte ``valor`` a float encadenando el error original si falla."""
    # bool es subclase de int en Python; se rechaza explícitamente (True no es "1 hora").
    if isinstance(valor, bool):
        raise ParametroServicioError(f"'{campo}' debe ser numérico, no booleano.")
    try:
        numero = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        # Encadenamiento: la causa técnica (ValueError/TypeError) queda en __cause__.
        raise ParametroServicioError(
            f"'{campo}' debe ser numérico, se recibió {valor!r}."
        ) from error
    if not math.isfinite(numero):
        raise ParametroServicioError(f"'{campo}' debe ser un número finito.")
    return numero


class Servicio(EntidadBase):
    """Clase abstracta para todos los servicios de Software FJ.

    Attributes:
        nombre: Nombre comercial del servicio.
        tarifa_base: Tarifa por hora en pesos colombianos.
        disponible: Indica si el servicio acepta nuevas reservas.
    """

    PREFIJO = "SRV"
    # Límites de duración (horas) que cada subclase ajusta a su naturaleza.
    DURACION_MINIMA: ClassVar[float] = 1
    DURACION_MAXIMA: ClassVar[float] = 24

    def __init__(self, nombre: str, tarifa_base: float, disponible: bool = True) -> None:
        super().__init__()
        if nombre is None or not str(nombre).strip():
            raise ParametroFaltanteError("El servicio requiere un nombre.")
        self._nombre = str(nombre).strip()
        self._tarifa_base = _a_numero(tarifa_base, "tarifa_base")
        self._disponible = bool(disponible)
        # La validación se hace al final, cuando la subclase ya asignó sus atributos.

    # --- Propiedades ----------------------------------------------------------
    @property
    def nombre(self) -> str:
        """Nombre comercial del servicio."""
        return self._nombre

    @property
    def tarifa_base(self) -> float:
        """Tarifa por hora del servicio."""
        return self._tarifa_base

    @property
    def disponible(self) -> bool:
        """True si el servicio acepta reservas."""
        return self._disponible

    def habilitar(self) -> None:
        """Permite nuevamente reservar el servicio."""
        self._disponible = True
        logger.info("Servicio %s habilitado.", self.id)

    def deshabilitar(self) -> None:
        """Bloquea nuevas reservas del servicio (p. ej. por mantenimiento)."""
        self._disponible = False
        logger.info("Servicio %s deshabilitado.", self.id)

    # --- Validaciones -----------------------------------------------------------
    def validar(self) -> None:
        """Valida los atributos comunes de cualquier servicio."""
        if self._tarifa_base <= 0:
            raise ParametroServicioError(
                f"La tarifa base debe ser positiva (se recibió {self._tarifa_base})."
            )

    def validar_duracion(self, duracion: object) -> float:
        """Convierte y verifica que la duración esté en el rango del servicio.

        Args:
            duracion: Duración solicitada en horas (número o texto numérico).

        Returns:
            La duración convertida a float.
        """
        horas = _a_numero(duracion, "duracion")
        if not self.DURACION_MINIMA <= horas <= self.DURACION_MAXIMA:
            raise ParametroServicioError(
                f"Duración de {horas:g} h fuera del rango permitido para "
                f"{type(self).__name__} ({self.DURACION_MINIMA:g}-{self.DURACION_MAXIMA:g} h)."
            )
        return horas

    @abstractmethod
    def validar_parametros(self, duracion: object, **opciones: object) -> None:
        """Valida duración y opciones específicas de una solicitud de reserva."""

    # --- Recursos (ganchos que las subclases pueden sobrescribir) --------------
    def reservar_recursos(self, **opciones: object) -> None:
        """Aparta los recursos de una reserva confirmada; por defecto no hace nada."""

    def liberar_recursos(self, **opciones: object) -> None:
        """Devuelve los recursos de una reserva cancelada; por defecto no hace nada."""

    # --- Cálculo de costos ------------------------------------------------------
    @abstractmethod
    def _costo_base(self, horas: float, **opciones: object) -> float:
        """Costo antes de descuentos e impuestos; lo define cada subclase."""

    # Python no tiene sobrecarga real de métodos: @overload documenta las variantes
    # admitidas para herramientas de tipado, y una única implementación con
    # parámetros opcionales atiende todas las combinaciones.
    @overload
    def calcular_costo(self, duracion: float) -> float: ...
    @overload
    def calcular_costo(self, duracion: float, impuesto: float) -> float: ...
    @overload
    def calcular_costo(
        self, duracion: float, impuesto: float, descuento: float, **opciones: object
    ) -> float: ...

    def calcular_costo(
        self,
        duracion: float,
        impuesto: float = 0.0,
        descuento: float = 0.0,
        **opciones: object,
    ) -> float:
        """Calcula el costo total de usar el servicio durante ``duracion`` horas.

        Aplica primero el descuento sobre el costo base y luego el impuesto sobre
        el subtotal. Ambos se expresan como fracción (0.19 = 19 %).

        Args:
            duracion: Horas de uso.
            impuesto: Fracción de impuesto entre 0 y 1 (opcional).
            descuento: Fracción de descuento entre 0 y 1 (opcional).
            **opciones: Parámetros específicos del servicio (asistentes, cantidad...).

        Returns:
            Costo total redondeado a dos decimales.

        Raises:
            ParametroServicioError: Si la duración u opciones no son válidas.
            CalculoInconsistenteError: Si impuesto/descuento están fuera de rango
                o el resultado no es un número positivo y finito.

        Example:
            >>> sala.calcular_costo(2)                    # solo duración
            >>> sala.calcular_costo(2, 0.19)              # con IVA
            >>> sala.calcular_costo(2, 0.19, 0.1, asistentes=5)
        """
        self.validar_parametros(duracion, **opciones)
        horas = float(duracion)
        tasa_impuesto = _a_numero(impuesto, "impuesto")
        tasa_descuento = _a_numero(descuento, "descuento")
        # Un porcentaje fuera de [0, 1] produciría costos absurdos o negativos.
        for nombre_tasa, tasa in (("impuesto", tasa_impuesto), ("descuento", tasa_descuento)):
            if not 0 <= tasa <= 1:
                raise CalculoInconsistenteError(
                    f"El {nombre_tasa} debe estar entre 0 y 1 (se recibió {tasa:g})."
                )

        base = self._costo_base(horas, **opciones)  # Polimorfismo: cada subclase calcula a su modo.
        subtotal = base * (1 - tasa_descuento)
        total = subtotal * (1 + tasa_impuesto)

        # Verificación de consistencia del resultado antes de devolverlo.
        if not math.isfinite(total) or total <= 0:
            raise CalculoInconsistenteError(
                f"Costo inconsistente ({total!r}) para {self.nombre}."
            )
        logger.debug(
            "Costo %s: base=%.2f desc=%.0f%% imp=%.0f%% total=%.2f",
            self.id, base, tasa_descuento * 100, tasa_impuesto * 100, total,
        )
        return round(total, 2)


class ReservaSala(Servicio):
    """Alquiler de salas de reunión o capacitación por horas.

    Attributes:
        capacidad: Número máximo de asistentes de la sala.
    """

    DURACION_MINIMA = 1
    DURACION_MAXIMA = 12
    # Recargo por ocupación alta (más del 80 % de la capacidad).
    RECARGO_OCUPACION = 0.10

    def __init__(
        self, nombre: str, tarifa_base: float, capacidad: int, disponible: bool = True
    ) -> None:
        super().__init__(nombre, tarifa_base, disponible)
        self._capacidad = _a_numero(capacidad, "capacidad")
        self.validar()
        self._asignar_id()  # Solo un servicio válido recibe ID.

    @property
    def capacidad(self) -> int:
        """Número máximo de asistentes."""
        return int(self._capacidad)

    def validar(self) -> None:
        """Valida la tarifa y que la capacidad sea un entero positivo."""
        super().validar()
        if self._capacidad <= 0 or not float(self._capacidad).is_integer():
            raise ParametroServicioError("La capacidad de la sala debe ser un entero positivo.")

    def validar_parametros(self, duracion: object, **opciones: object) -> None:
        """Valida duración y número de asistentes (obligatorio, ≤ capacidad)."""
        self.validar_duracion(duracion)
        if "asistentes" not in opciones:
            raise ParametroFaltanteError("La reserva de sala requiere 'asistentes'.")
        asistentes = _a_numero(opciones["asistentes"], "asistentes")
        if asistentes < 1 or asistentes > self.capacidad:
            raise ParametroServicioError(
                f"{asistentes:g} asistentes no caben en '{self.nombre}' "
                f"(capacidad {self.capacidad})."
            )

    def _costo_base(self, horas: float, **opciones: object) -> float:
        costo = self.tarifa_base * horas
        # Ocupación alta implica más limpieza y logística, por eso el recargo.
        if _a_numero(opciones["asistentes"], "asistentes") > 0.8 * self.capacidad:
            costo *= 1 + self.RECARGO_OCUPACION
        return costo

    def describir(self) -> str:
        """Descripción de la sala."""
        return (
            f"Sala {self.id} '{self.nombre}': capacidad {self.capacidad} personas, "
            f"${self.tarifa_base:,.0f}/h, {'disponible' if self.disponible else 'no disponible'}"
        )


class AlquilerEquipo(Servicio):
    """Alquiler de equipos (portátiles, proyectores...) con control de inventario.

    Attributes:
        tipo_equipo: Descripción del tipo de equipo.
        unidades_totales: Inventario total.
        unidades_disponibles: Unidades libres para nuevas reservas.
    """

    DURACION_MINIMA = 1
    DURACION_MAXIMA = 72
    # Seguro obligatorio sobre el valor del alquiler.
    SEGURO = 0.05

    def __init__(
        self,
        nombre: str,
        tarifa_base: float,
        tipo_equipo: str,
        unidades: int,
        disponible: bool = True,
    ) -> None:
        super().__init__(nombre, tarifa_base, disponible)
        if tipo_equipo is None or not str(tipo_equipo).strip():
            raise ParametroFaltanteError("El alquiler de equipo requiere 'tipo_equipo'.")
        self._tipo_equipo = str(tipo_equipo).strip()
        self._unidades_totales = _a_numero(unidades, "unidades")
        self.validar()
        self._unidades_totales = int(self._unidades_totales)
        self._unidades_disponibles = self._unidades_totales
        self._asignar_id()  # Solo un servicio válido recibe ID.

    @property
    def tipo_equipo(self) -> str:
        """Tipo de equipo alquilado."""
        return self._tipo_equipo

    @property
    def unidades_totales(self) -> int:
        """Inventario total de unidades."""
        return int(self._unidades_totales)

    @property
    def unidades_disponibles(self) -> int:
        """Unidades libres en este momento."""
        return self._unidades_disponibles

    def validar(self) -> None:
        """Valida la tarifa y que el inventario sea un entero positivo."""
        super().validar()
        if self._unidades_totales <= 0 or not float(self._unidades_totales).is_integer():
            raise ParametroServicioError("Las unidades de equipo deben ser un entero positivo.")

    def validar_parametros(self, duracion: object, **opciones: object) -> None:
        """Valida duración y cantidad de unidades solicitadas (por defecto 1)."""
        self.validar_duracion(duracion)
        cantidad = _a_numero(opciones.get("cantidad", 1), "cantidad")
        if cantidad < 1 or not cantidad.is_integer():
            raise ParametroServicioError("La cantidad de equipos debe ser un entero ≥ 1.")
        if cantidad > self.unidades_totales:
            raise ParametroServicioError(
                f"Se solicitaron {cantidad:g} unidades pero el inventario total es "
                f"{self.unidades_totales}."
            )

    def reservar_recursos(self, **opciones: object) -> None:
        """Descuenta del inventario las unidades de una reserva confirmada."""
        cantidad = int(_a_numero(opciones.get("cantidad", 1), "cantidad"))
        if cantidad > self._unidades_disponibles:
            raise ServicioNoDisponibleError(
                f"Solo quedan {self._unidades_disponibles} unidades de '{self.nombre}' "
                f"y se solicitaron {cantidad}."
            )
        self._unidades_disponibles -= cantidad
        logger.debug("%s: %d unidades apartadas, quedan %d.", self.id, cantidad, self._unidades_disponibles)

    def liberar_recursos(self, **opciones: object) -> None:
        """Devuelve al inventario las unidades de una reserva cancelada."""
        cantidad = int(_a_numero(opciones.get("cantidad", 1), "cantidad"))
        # min() evita superar el inventario total si se liberara dos veces por error.
        self._unidades_disponibles = min(self.unidades_totales, self._unidades_disponibles + cantidad)
        logger.debug("%s: %d unidades liberadas, quedan %d.", self.id, cantidad, self._unidades_disponibles)

    def _costo_base(self, horas: float, **opciones: object) -> float:
        cantidad = _a_numero(opciones.get("cantidad", 1), "cantidad")
        return self.tarifa_base * horas * cantidad * (1 + self.SEGURO)

    def describir(self) -> str:
        """Descripción del equipo e inventario."""
        return (
            f"Equipo {self.id} '{self.nombre}' ({self.tipo_equipo}): "
            f"{self.unidades_disponibles}/{self.unidades_totales} unidades libres, "
            f"${self.tarifa_base:,.0f}/h por unidad"
        )


class AsesoriaEspecializada(Servicio):
    """Asesoría profesional cuyo costo depende del nivel del asesor y la modalidad.

    Attributes:
        especialidad: Área de la asesoría (p. ej. "Ciberseguridad").
        nivel: Nivel del asesor: "junior", "senior" o "experto".
    """

    DURACION_MINIMA = 1
    DURACION_MAXIMA = 8
    # Multiplicador de la tarifa según la experiencia del asesor.
    MULTIPLICADORES: ClassVar[dict[str, float]] = {"junior": 1.0, "senior": 1.5, "experto": 2.0}
    MODALIDADES: ClassVar[tuple[str, ...]] = ("virtual", "presencial")
    # Costo fijo de desplazamiento para asesorías presenciales.
    RECARGO_PRESENCIAL = 50_000

    def __init__(
        self,
        nombre: str,
        tarifa_base: float,
        especialidad: str,
        nivel: str = "junior",
        disponible: bool = True,
    ) -> None:
        super().__init__(nombre, tarifa_base, disponible)
        if especialidad is None or not str(especialidad).strip():
            raise ParametroFaltanteError("La asesoría requiere una 'especialidad'.")
        self._especialidad = str(especialidad).strip()
        self._nivel = str(nivel).strip().lower()
        self.validar()
        self._asignar_id()  # Solo un servicio válido recibe ID.

    @property
    def especialidad(self) -> str:
        """Área de la asesoría."""
        return self._especialidad

    @property
    def nivel(self) -> str:
        """Nivel del asesor."""
        return self._nivel

    def validar(self) -> None:
        """Valida la tarifa y que el nivel sea uno de los permitidos."""
        super().validar()
        if self._nivel not in self.MULTIPLICADORES:
            raise ParametroServicioError(
                f"Nivel '{self._nivel}' inválido; use uno de {list(self.MULTIPLICADORES)}."
            )

    def validar_parametros(self, duracion: object, **opciones: object) -> None:
        """Valida duración y modalidad (por defecto "virtual")."""
        self.validar_duracion(duracion)
        modalidad = str(opciones.get("modalidad", "virtual")).lower()
        if modalidad not in self.MODALIDADES:
            raise ParametroServicioError(
                f"Modalidad '{modalidad}' inválida; use {self.MODALIDADES}."
            )

    def _costo_base(self, horas: float, **opciones: object) -> float:
        costo = self.tarifa_base * horas * self.MULTIPLICADORES[self.nivel]
        if str(opciones.get("modalidad", "virtual")).lower() == "presencial":
            costo += self.RECARGO_PRESENCIAL
        return costo

    def describir(self) -> str:
        """Descripción de la asesoría."""
        return (
            f"Asesoría {self.id} '{self.nombre}' en {self.especialidad} "
            f"(nivel {self.nivel}), ${self.tarifa_base:,.0f}/h base"
        )
