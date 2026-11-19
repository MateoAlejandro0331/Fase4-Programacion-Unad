"""Simulación de operaciones del sistema Software FJ.

Ejecuta una secuencia de operaciones válidas e inválidas (registro de
clientes, creación de servicios y reservas exitosas y fallidas) para demostrar
que el programa sigue funcionando ante errores. Todo queda registrado en
``logs/software_fj.log`` mediante el módulo ``logging``.

La usan tanto la interfaz gráfica (botón "Ejecutar simulación") como el modo
consola (``python main.py --consola``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from .excepciones import SoftwareFJError
from .sistema import SistemaGestion

logger = logging.getLogger(__name__)


@dataclass
class ResultadoSimulacion:
    """Contadores de la simulación.

    Attributes:
        exitosas: Operaciones completadas sin error.
        controladas: Operaciones que fallaron con un error de negocio esperado.
        inesperadas: Operaciones que fallaron con un error no previsto.
        detalle: Lista de (número, descripción, resultado) para el resumen final.
    """

    exitosas: int = 0
    controladas: int = 0
    inesperadas: int = 0
    detalle: list[tuple[int, str, str]] = field(default_factory=list)


def ejecutar_operacion(
    numero: int,
    descripcion: str,
    operacion: Callable[[], object],
    resultado: ResultadoSimulacion,
) -> None:
    """Ejecuta una operación aislando sus errores para que la simulación continúe.

    Args:
        numero: Número consecutivo de la operación.
        descripcion: Texto que describe la operación.
        operacion: Función sin argumentos que realiza la operación.
        resultado: Acumulador donde se registran los contadores.
    """
    logger.info("─" * 70)
    logger.info("Operación %02d: %s", numero, descripcion)
    estado = "?"
    try:
        valor = operacion()
    except SoftwareFJError as error:
        # Error de negocio: ya fue registrado como ERROR por el sistema.
        resultado.controladas += 1
        estado = f"FALLÓ (controlado) → {type(error).__name__}"
        logger.warning("Operación %02d no completada: %s", numero, error)
    except Exception:
        # Red de seguridad final: ningún error, por grave que sea, detiene el programa.
        resultado.inesperadas += 1
        estado = "FALLÓ (inesperado)"
        logger.critical("Operación %02d produjo un error inesperado; el sistema continúa.",
                        numero, exc_info=True)
    else:
        resultado.exitosas += 1
        estado = "OK"
        logger.info("Operación %02d completada: %s", numero, valor)
    finally:
        resultado.detalle.append((numero, descripcion, estado))


def construir_operaciones(sistema: SistemaGestion) -> list[tuple[str, Callable[[], object]]]:
    """Define la lista de operaciones de la simulación (válidas e inválidas)."""
    # Diccionario auxiliar para compartir IDs de reservas entre operaciones.
    ids: dict[str, str] = {}

    def reservar_sala_completa() -> object:
        reserva = sistema.crear_reserva("1020304050", "Sala Innovación", 3, asistentes=18)
        sistema.confirmar_reserva(reserva.id, descuento=0.10)
        return sistema.procesar_reserva(reserva.id)

    def reservar_equipos_ana() -> object:
        reserva = sistema.crear_reserva("1020304050", "Portátiles Dell", 8, cantidad=2)
        ids["equipo_ana"] = reserva.id
        return sistema.confirmar_reserva(reserva.id)

    def reservar_equipos_carlos() -> object:
        reserva = sistema.crear_reserva("80123456", "Portátiles Dell", 4, cantidad=2)
        ids["equipo_carlos"] = reserva.id
        return sistema.confirmar_reserva(reserva.id)

    def cancelar_y_reintentar() -> object:
        sistema.cancelar_reserva(ids["equipo_ana"], "Cambio de fecha del evento")
        return sistema.confirmar_reserva(ids["equipo_carlos"])

    def asesoria_presencial() -> object:
        # Se usa la variante numérica de buscar_servicio (sobrecarga por tipo int).
        # El número se obtiene del ID real porque el contador de IDs es global.
        numero = int(sistema.buscar_servicio("Auditoría de Seguridad").id.split("-")[1])
        reserva = sistema.crear_reserva("80123456", numero, 2, modalidad="presencial")
        sistema.confirmar_reserva(reserva.id, impuesto=0.19, descuento=0.05)
        return sistema.procesar_reserva(reserva.id)

    def asesoria_descuento_invalido() -> object:
        reserva = sistema.crear_reserva("1020304050", "Auditoría de Seguridad", 2)
        ids["asesoria_invalida"] = reserva.id
        return sistema.confirmar_reserva(reserva.id, descuento=1.5)

    def reserva_servicio_deshabilitado() -> object:
        sistema.deshabilitar_servicio("Sala Innovación")
        reserva = sistema.crear_reserva("80123456", "Sala Innovación", 2, asistentes=5)
        return sistema.confirmar_reserva(reserva.id)

    def carga_lote_corrupto() -> object:
        # Simula datos externos mal formados: falta la clave "email" y Python lanza
        # KeyError, un error que NO es de negocio y debe capturarse igualmente.
        lote = [{"nombre": "Laura Rincón", "documento": "55667788"}]
        return [sistema.registrar_cliente(d["nombre"], d["documento"], d["email"]) for d in lote]

    return [
        # --- Clientes ---
        ("Registrar cliente válido (Ana Gómez)",
         lambda: sistema.registrar_cliente("ana gómez", "1020304050", "ana.gomez@correo.com",
                                           "+573001234567")),
        ("Registrar cliente válido (Carlos Pérez)",
         lambda: sistema.registrar_cliente("Carlos Pérez", "80123456", "carlos@empresa.co")),
        ("Registrar cliente con correo inválido",
         lambda: sistema.registrar_cliente("Pedro Ruiz", "11223344", "pedro-arroba-correo")),
        ("Registrar cliente con documento duplicado",
         lambda: sistema.registrar_cliente("Ana María", "1020304050", "otra@correo.com")),
        ("Registrar cliente sin documento (parámetro faltante)",
         lambda: sistema.registrar_cliente("Sofía Díaz", None, "sofia@correo.com")),  # type: ignore[arg-type]
        ("Registrar cliente con nombre inválido (números)",
         lambda: sistema.registrar_cliente("R2D2", "99887766", "r2@correo.com")),
        # --- Servicios ---
        ("Crear servicio de sala válido",
         lambda: sistema.crear_servicio("sala", nombre="Sala Innovación",
                                        tarifa_base=80_000, capacidad=20)),
        ("Crear servicio de alquiler de equipos válido",
         lambda: sistema.crear_servicio("equipo", nombre="Portátiles Dell", tarifa_base=15_000,
                                        tipo_equipo="Portátil", unidades=3)),
        ("Crear servicio de asesoría válido",
         lambda: sistema.crear_servicio("asesoria", nombre="Auditoría de Seguridad",
                                        tarifa_base=120_000, especialidad="Ciberseguridad",
                                        nivel="experto")),
        ("Crear servicio con tarifa negativa",
         lambda: sistema.crear_servicio("sala", nombre="Sala Mini", tarifa_base=-5000,
                                        capacidad=4)),
        ("Crear servicio de tipo inexistente",
         lambda: sistema.crear_servicio("transporte", nombre="Van", tarifa_base=1000)),
        ("Crear asesoría con nivel inválido",
         lambda: sistema.crear_servicio("asesoria", nombre="Asesoría Cloud", tarifa_base=90_000,
                                        especialidad="AWS", nivel="maestro")),
        ("Crear equipo sin parámetros obligatorios",
         lambda: sistema.crear_servicio("equipo", nombre="Proyectores", tarifa_base=10_000)),
        # --- Reservas ---
        ("Reserva de sala exitosa: crear, confirmar con 10% desc. y procesar",
         reservar_sala_completa),
        ("Reserva de sala con más asistentes que la capacidad",
         lambda: sistema.crear_reserva("80123456", "Sala Innovación", 2, asistentes=35)),
        ("Reserva con duración no numérica ('tres')",
         lambda: sistema.crear_reserva("80123456", "Sala Innovación", "tres", asistentes=5)),  # type: ignore[arg-type]
        ("Reserva de cliente inexistente",
         lambda: sistema.crear_reserva("12345678", "Portátiles Dell", 2)),
        ("Reservar 2 portátiles para Ana (confirmada)", reservar_equipos_ana),
        ("Reservar 2 portátiles para Carlos (sin inventario suficiente)",
         reservar_equipos_carlos),
        ("Cancelar reserva de Ana y confirmar la de Carlos", cancelar_y_reintentar),
        ("Procesar una reserva ya cancelada (operación no permitida)",
         lambda: sistema.procesar_reserva(ids["equipo_ana"])),
        ("Asesoría presencial exitosa (búsqueda sobrecargada por número)",
         asesoria_presencial),
        ("Confirmar asesoría con descuento del 150% (cálculo inconsistente)",
         asesoria_descuento_invalido),
        ("Reservar sala deshabilitada por mantenimiento", reserva_servicio_deshabilitado),
        ("Carga de lote de clientes con datos corruptos (error inesperado)",
         carga_lote_corrupto),
    ]


def ejecutar_simulacion(sistema: SistemaGestion | None = None) -> ResultadoSimulacion:
    """Ejecuta todas las operaciones de la simulación y registra el resumen en el log.

    Args:
        sistema: Sistema sobre el que se simula; si es None se crea uno nuevo.

    Returns:
        Contadores y detalle de cada operación.
    """
    sistema = sistema if sistema is not None else SistemaGestion()
    resultado = ResultadoSimulacion()
    logger.info("=" * 70)
    logger.info("INICIO DE LA SIMULACIÓN — SOFTWARE FJ")
    logger.info("=" * 70)

    for numero, (descripcion, operacion) in enumerate(construir_operaciones(sistema), start=1):
        ejecutar_operacion(numero, descripcion, operacion, resultado)

    logger.info("=" * 70)
    logger.info("RESUMEN DE LA SIMULACIÓN")
    for numero, descripcion, estado in resultado.detalle:
        logger.info("  %02d. %-70s %s", numero, descripcion, estado)
    logger.info(
        "Total: %d operaciones | %d exitosas | %d errores controlados | %d inesperados",
        len(resultado.detalle), resultado.exitosas, resultado.controladas, resultado.inesperadas,
    )
    logger.info("Estado final del sistema: %s", sistema.resumen())
    for reserva in sistema.reservas:
        logger.info("  %s", reserva)
    logger.info("Simulación finalizada sin interrupciones.")
    return resultado
