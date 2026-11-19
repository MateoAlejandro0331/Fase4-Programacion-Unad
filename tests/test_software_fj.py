"""Pruebas unitarias del sistema Software FJ (ejecutar con ``python -m unittest``)."""

from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from software_fj import (
    AlquilerEquipo,
    AsesoriaEspecializada,
    Cliente,
    EstadoReserva,
    Reserva,
    ReservaSala,
    Servicio,
    SistemaGestion,
    configurar_logging,
)
from software_fj.excepciones import (
    CalculoInconsistenteError,
    ClienteInvalidoError,
    EntidadDuplicadaError,
    EntidadNoEncontradaError,
    OperacionNoPermitidaError,
    ParametroFaltanteError,
    ParametroServicioError,
    ReservaInvalidaError,
    ServicioError,
    ServicioNoDisponibleError,
    SoftwareFJError,
)


def _cliente() -> Cliente:
    return Cliente("Ana Gómez", "1020304050", "ana@correo.com")


def _sala() -> ReservaSala:
    return ReservaSala("Sala A", 100_000, capacidad=10)


class TestCliente(unittest.TestCase):
    def test_cliente_valido_normaliza_y_enmascara(self) -> None:
        cliente = Cliente("  ana   gómez ", "1020304050", "ANA@Correo.com", "300 123 4567")
        self.assertEqual(cliente.nombre, "Ana Gómez")
        self.assertEqual(cliente.email, "ana@correo.com")
        self.assertEqual(cliente.documento_enmascarado, "******4050")
        self.assertNotIn("1020304050", cliente.describir())
        self.assertTrue(cliente.id.startswith("CLI-"))

    def test_validaciones(self) -> None:
        with self.assertRaises(ClienteInvalidoError):
            Cliente("Ana", "12ab", "ana@correo.com")
        with self.assertRaises(ClienteInvalidoError):
            Cliente("Ana", "123456", "sin-arroba")
        with self.assertRaises(ParametroFaltanteError):
            Cliente("", "123456", "ana@correo.com")
        with self.assertRaises(ClienteInvalidoError):
            Cliente("Ana", "123456", "ana@correo.com", telefono="12")

    def test_documento_inmutable(self) -> None:
        cliente = _cliente()
        with self.assertRaises(ClienteInvalidoError):
            cliente.documento = "999999"

    def test_documento_numerico_se_acepta_como_texto(self) -> None:
        cliente = Cliente("Ana Gómez", 80123456, "ana@correo.com")  # type: ignore[arg-type]
        self.assertEqual(cliente.documento, "80123456")
        with self.assertRaises(ClienteInvalidoError):
            Cliente("Ana Gómez", True, "ana@correo.com")  # type: ignore[arg-type]

    def test_cliente_invalido_no_consume_id(self) -> None:
        primero = _cliente()
        with self.assertRaises(ClienteInvalidoError):
            Cliente("Ana", "12ab", "ana@correo.com")
        segundo = _cliente()
        numero = lambda c: int(c.id.split("-")[1])  # noqa: E731
        self.assertEqual(numero(segundo), numero(primero) + 1)


class TestServicios(unittest.TestCase):
    def test_servicio_es_abstracto(self) -> None:
        with self.assertRaises(TypeError):
            Servicio("X", 1000)  # type: ignore[abstract]

    def test_ids_compartidos_entre_subclases(self) -> None:
        sala = _sala()
        equipo = AlquilerEquipo("Proyector", 10_000, "Proyector", 2)
        self.assertNotEqual(sala.id, equipo.id)
        self.assertTrue(equipo.id.startswith("SRV-"))

    def test_sobrecarga_calcular_costo(self) -> None:
        sala = _sala()
        self.assertEqual(sala.calcular_costo(2, asistentes=5), 200_000)
        self.assertEqual(sala.calcular_costo(2, 0.19, asistentes=5), 238_000)
        self.assertEqual(sala.calcular_costo(2, 0.19, 0.5, asistentes=5), 119_000)

    def test_polimorfismo_costos(self) -> None:
        servicios_y_opciones = [
            (_sala(), {"asistentes": 9}, 100_000 * 2 * 1.10),
            (AlquilerEquipo("PC", 10_000, "Portátil", 5), {"cantidad": 2}, 10_000 * 2 * 2 * 1.05),
            (AsesoriaEspecializada("Cloud", 50_000, "AWS", "senior"),
             {"modalidad": "presencial"}, 50_000 * 2 * 1.5 + 50_000),
        ]
        for servicio, opciones, esperado in servicios_y_opciones:
            with self.subTest(servicio=type(servicio).__name__):
                self.assertAlmostEqual(servicio.calcular_costo(2, **opciones), esperado)

    def test_parametros_invalidos(self) -> None:
        with self.assertRaises(ParametroServicioError):
            ReservaSala("Sala", -1, 10)
        with self.assertRaises(ParametroServicioError):
            AsesoriaEspecializada("A", 1000, "X", nivel="maestro")
        with self.assertRaises(ParametroServicioError):
            _sala().calcular_costo(20, asistentes=2)  # supera 12 h
        with self.assertRaises(ParametroFaltanteError):
            _sala().calcular_costo(2)  # falta 'asistentes'
        with self.assertRaises(CalculoInconsistenteError):
            _sala().calcular_costo(2, 0.19, 1.5, asistentes=2)

    def test_encadenamiento_en_conversion_numerica(self) -> None:
        with self.assertRaises(ParametroServicioError) as ctx:
            _sala().validar_duracion("tres")
        self.assertIsInstance(ctx.exception.__cause__, ValueError)


class TestReserva(unittest.TestCase):
    def test_ciclo_completo(self) -> None:
        reserva = Reserva(_cliente(), _sala(), 2, asistentes=4)
        self.assertIs(reserva.estado, EstadoReserva.PENDIENTE)
        costo = reserva.confirmar()
        self.assertEqual(costo, 238_000)
        comprobante = reserva.procesar()
        self.assertEqual(comprobante["total"], 238_000)
        self.assertIs(reserva.estado, EstadoReserva.PROCESADA)
        self.assertEqual(len(reserva.historial), 3)

    def test_reserva_invalida_encadena_causa(self) -> None:
        with self.assertRaises(ReservaInvalidaError) as ctx:
            Reserva(_cliente(), _sala(), 2, asistentes=50)
        self.assertIsInstance(ctx.exception.__cause__, ParametroServicioError)

    def test_transiciones_no_permitidas(self) -> None:
        reserva = Reserva(_cliente(), _sala(), 2, asistentes=4)
        with self.assertRaises(OperacionNoPermitidaError):
            reserva.procesar()
        reserva.cancelar()
        with self.assertRaises(OperacionNoPermitidaError):
            reserva.confirmar()
        with self.assertRaises(OperacionNoPermitidaError):
            reserva.cancelar()

    def test_inventario_se_aparta_y_libera(self) -> None:
        equipo = AlquilerEquipo("PC", 10_000, "Portátil", 3)
        r1 = Reserva(_cliente(), equipo, 2, cantidad=2)
        r2 = Reserva(_cliente(), equipo, 2, cantidad=2)
        r1.confirmar()
        self.assertEqual(equipo.unidades_disponibles, 1)
        with self.assertRaises(ServicioNoDisponibleError):
            r2.confirmar()
        self.assertIs(r2.estado, EstadoReserva.PENDIENTE)
        r1.cancelar()
        self.assertEqual(equipo.unidades_disponibles, 3)
        r2.confirmar()
        self.assertEqual(equipo.unidades_disponibles, 1)

    def test_servicio_deshabilitado(self) -> None:
        sala = _sala()
        reserva = Reserva(_cliente(), sala, 2, asistentes=4)
        sala.deshabilitar()
        with self.assertRaises(ServicioNoDisponibleError):
            reserva.confirmar()


class TestSistema(unittest.TestCase):
    def setUp(self) -> None:
        self.sistema = SistemaGestion()
        self.sistema.registrar_cliente("Ana Gómez", "1020304050", "ana@correo.com")
        self.sala = self.sistema.crear_servicio("sala", nombre="Sala A",
                                                tarifa_base=100_000, capacidad=10)

    def test_duplicados_y_busquedas(self) -> None:
        with self.assertRaises(EntidadDuplicadaError):
            self.sistema.registrar_cliente("Otra", "1020304050", "otra@correo.com")
        with self.assertRaises(EntidadNoEncontradaError):
            self.sistema.buscar_cliente("000000")

    def test_reservas_fallidas_no_dejan_huecos_en_ids(self) -> None:
        r1 = self.sistema.crear_reserva("1020304050", "Sala A", 2, asistentes=4)
        for _ in range(3):
            with self.assertRaises(ReservaInvalidaError):
                self.sistema.crear_reserva("1020304050", "Sala A", 2, asistentes=99)
        r2 = self.sistema.crear_reserva("1020304050", "Sala A", 2, asistentes=4)
        self.assertEqual(int(r2.id.split("-")[1]), int(r1.id.split("-")[1]) + 1)

    def test_mensaje_de_duplicado_ignora_espacios(self) -> None:
        with self.assertRaises(EntidadDuplicadaError) as ctx:
            self.sistema.registrar_cliente("Otra", " 1020304050 ", "otra@correo.com")
        self.assertIn("terminado en 4050.", str(ctx.exception))
        self.assertIsNotNone(self.sistema.buscar_cliente(1020304050))  # type: ignore[arg-type]

    def test_busqueda_sobrecargada_de_servicio(self) -> None:
        numero = int(self.sala.id.split("-")[1])
        self.assertIs(self.sistema.buscar_servicio(numero), self.sala)
        self.assertIs(self.sistema.buscar_servicio("sala a"), self.sala)
        self.assertIs(self.sistema.buscar_servicio(self.sala.id), self.sala)

    def test_tipo_de_servicio_invalido(self) -> None:
        with self.assertRaises(ServicioError):
            self.sistema.crear_servicio("transporte", nombre="Van", tarifa_base=1)
        with self.assertRaises(ServicioError) as ctx:
            self.sistema.crear_servicio("equipo", nombre="PC", tarifa_base=1)
        self.assertIsInstance(ctx.exception.__cause__, TypeError)

    def test_flujo_y_resumen(self) -> None:
        reserva = self.sistema.crear_reserva("1020304050", "Sala A", 2, asistentes=4)
        self.sistema.confirmar_reserva(reserva.id)
        self.sistema.procesar_reserva(reserva.id)
        resumen = self.sistema.resumen()
        self.assertEqual(resumen["reservas_por_estado"]["procesada"], 1)  # type: ignore[index]
        self.assertEqual(resumen["ingresos_procesados"], 238_000)

    def test_errores_se_registran_en_el_log(self) -> None:
        with self.assertLogs("software_fj.sistema", level="ERROR") as registros:
            with self.assertRaises(SoftwareFJError):
                self.sistema.registrar_cliente("Pedro", "11223344", "correo-invalido")
        self.assertIn("Registro de cliente falló", registros.output[0])


class TestLogging(unittest.TestCase):
    def test_archivo_de_log_recibe_eventos(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "sub" / "prueba.log"
            logger = configurar_logging(ruta, nivel_consola=logging.CRITICAL, forzar=True)
            logging.getLogger("software_fj.prueba").error("Mensaje de prueba")
            for handler in logger.handlers:
                handler.flush()
            contenido = ruta.read_text(encoding="utf-8")
            # Se cierran los handlers para liberar el archivo temporal.
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)
            # Se deja un NullHandler para que otras pruebas no impriman por el handler de último recurso.
            logger.addHandler(logging.NullHandler())
        self.assertIn("ERROR", contenido)
        self.assertIn("Mensaje de prueba", contenido)


if __name__ == "__main__":
    unittest.main()
