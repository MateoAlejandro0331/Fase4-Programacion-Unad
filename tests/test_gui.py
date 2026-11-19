"""Pruebas de la interfaz Tkinter: se manipula la ventana por código, sin clics.

Se omiten automáticamente si no hay entorno gráfico disponible.
"""

from __future__ import annotations

import tkinter as tk
import unittest
from tkinter import ttk

from software_fj.reserva import EstadoReserva

try:
    from software_fj.gui import App

    _raiz = tk.Tk()
    _raiz.destroy()
    HAY_PANTALLA = True
except tk.TclError:
    HAY_PANTALLA = False


def _escribir(entrada: ttk.Entry, texto: str) -> None:
    entrada.delete(0, tk.END)
    entrada.insert(0, texto)


@unittest.skipUnless(HAY_PANTALLA, "No hay entorno gráfico disponible")
class TestApp(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()
        self.app.withdraw()  # La ventana no se muestra durante las pruebas.
        self.errores: list[tuple[str, str]] = []
        self.infos: list[tuple[str, str]] = []
        # Se sustituyen los diálogos modales para que no bloqueen la prueba.
        self.app.mostrar_error = lambda t, m: self.errores.append((t, m))  # type: ignore[method-assign]
        self.app.mostrar_info = lambda t, m: self.infos.append((t, m))  # type: ignore[method-assign]
        self.app.preguntar = lambda t, m: True  # type: ignore[method-assign]

    def tearDown(self) -> None:
        self.app.al_cerrar()

    def _registrar_cliente(self, nombre: str, documento: str, email: str) -> None:
        campos = self.app.campos_cliente
        _escribir(campos["nombre"][1], nombre)
        _escribir(campos["documento"][1], documento)
        _escribir(campos["email"][1], email)
        self.app.registrar_cliente()

    def _crear_sala(self) -> None:
        self.app.tipo_servicio.set("Sala")
        self.app.al_cambiar_tipo_servicio()
        _escribir(self.app.campos_servicio["nombre"][1], "Sala Azul")
        _escribir(self.app.campos_servicio["tarifa_base"][1], "50000")
        _escribir(self.app.campos_servicio["capacidad"][1], "10")
        self.app.crear_servicio()

    def test_registro_valido_e_invalido_de_cliente(self) -> None:
        self._registrar_cliente("Ana Gómez", "1020304050", "ana@correo.com")
        self.assertEqual(len(self.app.tabla_clientes.get_children()), 1)
        self.assertEqual(self.errores, [])

        self._registrar_cliente("Ana Gómez", "1020304050", "ana@correo.com")  # duplicado
        self._registrar_cliente("Pedro", "123", "mal")                         # inválido
        self.assertEqual(len(self.errores), 2)
        self.assertEqual(len(self.app.tabla_clientes.get_children()), 1)

    def test_campos_dinamicos_por_tipo_de_servicio(self) -> None:
        self.app.tipo_servicio.set("Equipo")
        self.app.al_cambiar_tipo_servicio()
        self.assertTrue(self.app.campos_servicio["unidades"][1].grid_info())
        self.assertFalse(self.app.campos_servicio["capacidad"][1].grid_info())

    def test_servicio_con_tarifa_no_numerica_no_cierra_la_app(self) -> None:
        self.app.tipo_servicio.set("Sala")
        self.app.al_cambiar_tipo_servicio()
        _escribir(self.app.campos_servicio["nombre"][1], "Sala X")
        _escribir(self.app.campos_servicio["tarifa_base"][1], "cien mil")
        _escribir(self.app.campos_servicio["capacidad"][1], "5")
        self.app.crear_servicio()
        self.assertEqual(len(self.errores), 1)
        self.assertIn("numérico", self.errores[0][1])

    def test_flujo_completo_de_reserva(self) -> None:
        self._registrar_cliente("Ana Gómez", "1020304050", "ana@correo.com")
        self._crear_sala()
        self.app.cliente_reserva.set(next(iter(self.app._opciones_cliente)))
        self.app.servicio_reserva.set(next(iter(self.app._opciones_servicio)))
        self.app.al_cambiar_servicio_reserva()
        _escribir(self.app.campos_reserva["duracion"][1], "2")
        _escribir(self.app.campos_reserva["asistentes"][1], "4")
        self.app.crear_reserva()
        self.assertEqual(self.errores, [])

        # La reserva recién creada queda seleccionada: confirmar y procesar.
        self.app.confirmar_reserva()
        self.app.procesar_reserva()
        reserva = self.app.sistema.reservas[0]
        self.assertIs(reserva.estado, EstadoReserva.PROCESADA)
        self.assertEqual(reserva.costo, 119_000)
        self.assertEqual(self.infos[0][0], "Comprobante de pago")

        # Cancelar una reserva procesada no está permitido: error controlado.
        self.app.cancelar_reserva()
        self.assertEqual(len(self.errores), 1)

    def test_acciones_sin_seleccion_muestran_error(self) -> None:
        self.app.crear_reserva()
        self.app.confirmar_reserva()
        self.app.alternar_disponibilidad()
        self.assertEqual(len(self.errores), 3)

    def test_error_inesperado_queda_controlado(self) -> None:
        resultado = self.app.ejecutar_accion("Prueba", lambda: 1 / 0)
        self.assertIsNone(resultado)
        self.assertIn("inesperado", self.errores[0][1])

    def test_simulacion_desde_la_ventana(self) -> None:
        self.app.ejecutar_simulacion()
        self.assertEqual(self.infos[0][0], "Simulación finalizada")
        self.assertEqual(len(self.app.tabla_reservas.get_children()), 6)
        self.app._volcar_mensajes_log()
        self.assertIn("Simulación finalizada", self.app.texto_registro.get("1.0", tk.END))


if __name__ == "__main__":
    unittest.main()
