"""VISTA: interfaz gráfica de escritorio de Software FJ construida con Tkinter.

Sigue la misma forma que la aplicación de la Fase 3: la ventana es una clase
``App`` que hereda de ``tk.Tk``, usa widgets ``ttk``, se organiza con ``grid``,
muestra los errores con ``messagebox`` y oculta o muestra campos con
``grid_remove()`` / ``grid()`` según la opción elegida en un ``Combobox``.

Robustez frente a errores:

* Cada botón pasa por :meth:`App.ejecutar_accion`, que captura los errores de
  negocio (``SoftwareFJError``) y los inesperados, los registra en el log y los
  muestra en un cuadro de diálogo sin cerrar la ventana.
* :meth:`App.report_callback_exception` es la última red de seguridad: atrapa
  cualquier excepción que escape de un callback de Tkinter.
* :class:`ManejadorLogTkinter` envía los registros del logger a una cola que la
  ventana lee periódicamente, de modo que la pestaña "Registro" muestra en vivo
  lo mismo que se guarda en ``logs/software_fj.log``.
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from tkinter import messagebox, ttk
from types import TracebackType

from .excepciones import ParametroFaltanteError, SoftwareFJError
from .logger_config import NOMBRE_LOGGER_RAIZ, RUTA_LOG_POR_DEFECTO
from .reserva import IVA_POR_DEFECTO, EstadoReserva
from .servicios import AlquilerEquipo, AsesoriaEspecializada, ReservaSala, Servicio
from .simulacion import ejecutar_simulacion
from .sistema import SistemaGestion

logger = logging.getLogger(__name__)

# Tipos de servicio que muestra el Combobox → clave que entiende SistemaGestion.
TIPOS_SERVICIO = {"Sala": "sala", "Equipo": "equipo", "Asesoría": "asesoria"}
# Nombre legible de cada clase de servicio para la tabla.
NOMBRE_TIPO = {ReservaSala: "Sala", AlquilerEquipo: "Equipo", AsesoriaEspecializada: "Asesoría"}
# Colores del registro según el nivel del mensaje.
COLORES_NIVEL = {
    logging.DEBUG: "#808080",
    logging.INFO: "#1f6feb",
    logging.WARNING: "#b8860b",
    logging.ERROR: "#d1242f",
    logging.CRITICAL: "#a40e26",
}
# Máximo de líneas que conserva la vista del registro (el archivo guarda todo).
MAX_LINEAS_REGISTRO = 3000


class ManejadorLogTkinter(logging.Handler):
    """Handler de ``logging`` que deja cada registro en una cola para la ventana.

    Se usa una cola en lugar de escribir directamente en el widget porque
    Tkinter no es seguro entre hilos: la ventana lee la cola con ``after()``.

    Attributes:
        cola: Cola de tuplas (nivel, texto formateado).
    """

    def __init__(self, cola: queue.Queue[tuple[int, str]], nivel: int = logging.INFO) -> None:
        super().__init__(nivel)
        self.cola = cola
        self.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", "%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.cola.put_nowait((record.levelno, self.format(record)))
        except Exception:
            # Regla de logging: un handler nunca debe lanzar excepciones propias.
            self.handleError(record)


class App(tk.Tk):
    """Ventana principal de Software FJ (hereda de ``tk.Tk``, igual que en la Fase 3).

    Attributes:
        sistema: Modelo con las listas de clientes, servicios y reservas.
        cuaderno: Notebook con las pestañas Clientes, Servicios, Reservas y Registro.
        tabla_clientes: Treeview con los clientes registrados.
        tabla_servicios: Treeview con el catálogo de servicios.
        tabla_reservas: Treeview con las reservas y su estado.
        texto_registro: Área de texto donde se ve el log en vivo.
        etiqueta_estado: Barra inferior con el último mensaje y el resumen.
    """

    def __init__(self, sistema: SistemaGestion | None = None) -> None:
        super().__init__()  # Igual que las clases del modelo, se llama a super().
        self.title("Software FJ — Gestión de Clientes, Servicios y Reservas")
        self.geometry("1150x720")
        self.minsize(950, 600)

        self.sistema = sistema if sistema is not None else SistemaGestion()

        # Conexión del logger con la ventana mediante una cola.
        self._cola_log: queue.Queue[tuple[int, str]] = queue.Queue()
        self._manejador_log = ManejadorLogTkinter(self._cola_log)
        logger_raiz = logging.getLogger(NOMBRE_LOGGER_RAIZ)
        logger_raiz.addHandler(self._manejador_log)
        # Si nadie configuró el logging, el nivel heredado es WARNING y la pestaña
        # Registro no vería los eventos INFO; se garantiza al menos INFO.
        if logger_raiz.getEffectiveLevel() > logging.INFO:
            logger_raiz.setLevel(logging.INFO)

        # Mapas "texto del Combobox" → identificador, para no depender del texto mostrado.
        self._opciones_cliente: dict[str, str] = {}
        self._opciones_servicio: dict[str, str] = {}

        # La única fila/columna que crece es la del cuaderno de pestañas.
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.cuaderno = ttk.Notebook(self)
        self.cuaderno.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        self._construir_pestana_clientes()
        self._construir_pestana_servicios()
        self._construir_pestana_reservas()
        self._construir_pestana_registro()
        self._construir_barra_estado()

        # Al cerrar con la X se desconecta el handler antes de destruir la ventana.
        self.protocol("WM_DELETE_WINDOW", self.al_cerrar)
        self.after(100, self._vaciar_cola_log)
        self.actualizar_vistas()
        logger.info("Interfaz gráfica iniciada.")

    # ======================================================================
    # Utilidades de construcción de widgets
    # ======================================================================
    @staticmethod
    def _crear_campos(
        padre: tk.Misc, campos: list[tuple[str, str]], fila_inicial: int = 0
    ) -> dict[str, tuple[ttk.Label, ttk.Entry]]:
        """Crea pares etiqueta/campo en filas consecutivas y los devuelve por clave."""
        resultado: dict[str, tuple[ttk.Label, ttk.Entry]] = {}
        for desplazamiento, (clave, texto) in enumerate(campos):
            fila = fila_inicial + desplazamiento
            etiqueta = ttk.Label(padre, text=texto)
            etiqueta.grid(row=fila, column=0, padx=8, pady=4, sticky="w")
            entrada = ttk.Entry(padre, width=28)
            entrada.grid(row=fila, column=1, padx=8, pady=4, sticky="ew")
            resultado[clave] = (etiqueta, entrada)
        return resultado

    @staticmethod
    def _crear_tabla(
        padre: tk.Misc, columnas: list[tuple[str, str, int]]
    ) -> ttk.Treeview:
        """Crea un Treeview con barra de desplazamiento que ocupa todo el ``padre``."""
        padre.rowconfigure(0, weight=1)
        padre.columnconfigure(0, weight=1)
        tabla = ttk.Treeview(
            padre, columns=[c[0] for c in columnas], show="headings", selectmode="browse"
        )
        for clave, titulo, ancho in columnas:
            tabla.heading(clave, text=titulo)
            tabla.column(clave, width=ancho, anchor="w")
        tabla.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(padre, orient="vertical", command=tabla.yview)
        barra.grid(row=0, column=1, sticky="ns")
        tabla.configure(yscrollcommand=barra.set)
        return tabla

    @staticmethod
    def _limpiar_campos(*entradas: ttk.Entry) -> None:
        """Borra el contenido de varios Entry."""
        for entrada in entradas:
            entrada.delete(0, tk.END)

    # ======================================================================
    # Pestaña Clientes
    # ======================================================================
    def _construir_pestana_clientes(self) -> None:
        pestana = ttk.Frame(self.cuaderno, padding=8)
        self.cuaderno.add(pestana, text="Clientes")
        pestana.columnconfigure(1, weight=1)
        pestana.rowconfigure(0, weight=1)

        formulario = ttk.LabelFrame(pestana, text="Nuevo cliente", padding=8)
        formulario.grid(row=0, column=0, sticky="nw", padx=(0, 8))
        self.campos_cliente = self._crear_campos(formulario, [
            ("nombre", "Nombre completo:"),
            ("documento", "Documento:"),
            ("email", "Correo electrónico:"),
            ("telefono", "Teléfono (opcional):"),
        ])
        botones = ttk.Frame(formulario)
        botones.grid(row=4, column=0, columnspan=2, pady=8)
        ttk.Button(botones, text="Registrar cliente",
                   command=self.registrar_cliente).grid(row=0, column=0, padx=4)
        ttk.Button(botones, text="Limpiar",
                   command=lambda: self._limpiar_campos(
                       *(e for _, e in self.campos_cliente.values()))
                   ).grid(row=0, column=1, padx=4)

        marco_tabla = ttk.LabelFrame(pestana, text="Clientes registrados", padding=4)
        marco_tabla.grid(row=0, column=1, sticky="nsew")
        self.tabla_clientes = self._crear_tabla(marco_tabla, [
            ("id", "ID", 80), ("nombre", "Nombre", 200), ("documento", "Documento", 110),
            ("email", "Correo", 180), ("telefono", "Teléfono", 120),
        ])

    def registrar_cliente(self) -> None:
        """Registra un cliente con los datos del formulario."""
        datos = {clave: entrada.get() for clave, (_, entrada) in self.campos_cliente.items()}
        cliente = self.ejecutar_accion(
            "Registrar cliente",
            lambda: self.sistema.registrar_cliente(
                datos["nombre"], datos["documento"], datos["email"], datos["telefono"]
            ),
        )
        if cliente is not None:
            self._limpiar_campos(*(e for _, e in self.campos_cliente.values()))
            self.mostrar_estado(f"Cliente {cliente.id} registrado.")

    # ======================================================================
    # Pestaña Servicios
    # ======================================================================
    def _construir_pestana_servicios(self) -> None:
        pestana = ttk.Frame(self.cuaderno, padding=8)
        self.cuaderno.add(pestana, text="Servicios")
        pestana.columnconfigure(1, weight=1)
        pestana.rowconfigure(0, weight=1)

        formulario = ttk.LabelFrame(pestana, text="Nuevo servicio", padding=8)
        formulario.grid(row=0, column=0, sticky="nw", padx=(0, 8))

        ttk.Label(formulario, text="Tipo de servicio:").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self.tipo_servicio = tk.StringVar(value="Sala")
        combo = ttk.Combobox(formulario, textvariable=self.tipo_servicio,
                             values=list(TIPOS_SERVICIO), state="readonly", width=26)
        combo.grid(row=0, column=1, padx=8, pady=4, sticky="ew")
        # Evento: al cambiar el tipo se muestran solo los campos que le corresponden.
        combo.bind("<<ComboboxSelected>>", self.al_cambiar_tipo_servicio)

        self.campos_servicio = self._crear_campos(formulario, [
            ("nombre", "Nombre:"),
            ("tarifa_base", "Tarifa por hora ($):"),
            ("capacidad", "Capacidad (personas):"),
            ("tipo_equipo", "Tipo de equipo:"),
            ("unidades", "Unidades en inventario:"),
            ("especialidad", "Especialidad:"),
        ], fila_inicial=1)

        # El nivel de la asesoría es una lista cerrada, por eso va en un Combobox.
        self.etiqueta_nivel = ttk.Label(formulario, text="Nivel del asesor:")
        self.etiqueta_nivel.grid(row=7, column=0, padx=8, pady=4, sticky="w")
        self.nivel_asesoria = tk.StringVar(value="junior")
        self.combo_nivel = ttk.Combobox(
            formulario, textvariable=self.nivel_asesoria, state="readonly", width=26,
            values=list(AsesoriaEspecializada.MULTIPLICADORES),
        )
        self.combo_nivel.grid(row=7, column=1, padx=8, pady=4, sticky="ew")

        botones = ttk.Frame(formulario)
        botones.grid(row=8, column=0, columnspan=2, pady=8)
        ttk.Button(botones, text="Crear servicio",
                   command=self.crear_servicio).grid(row=0, column=0, padx=4)
        ttk.Button(botones, text="Habilitar / deshabilitar",
                   command=self.alternar_disponibilidad).grid(row=0, column=1, padx=4)

        marco_tabla = ttk.LabelFrame(pestana, text="Catálogo de servicios", padding=4)
        marco_tabla.grid(row=0, column=1, sticky="nsew")
        self.tabla_servicios = self._crear_tabla(marco_tabla, [
            ("id", "ID", 80), ("tipo", "Tipo", 80), ("nombre", "Nombre", 170),
            ("tarifa", "Tarifa/h", 90), ("detalle", "Detalle", 260), ("estado", "Estado", 100),
        ])
        self.al_cambiar_tipo_servicio()  # Estado inicial: campos de "Sala".

    # Campos específicos que se muestran para cada tipo de servicio.
    _CAMPOS_POR_TIPO: dict[str, tuple[str, ...]] = {
        "sala": ("capacidad",),
        "equipo": ("tipo_equipo", "unidades"),
        "asesoria": ("especialidad", "nivel"),
    }

    def al_cambiar_tipo_servicio(self, event: tk.Event | None = None) -> None:
        """Muestra solo los campos del tipo de servicio elegido.

        Args:
            event: Evento de Tkinter; es None cuando se llama manualmente.
        """
        visibles = self._CAMPOS_POR_TIPO[TIPOS_SERVICIO[self.tipo_servicio.get()]]
        especificos = {clave: par for clave, par in self.campos_servicio.items()
                       if clave not in ("nombre", "tarifa_base")}
        especificos["nivel"] = (self.etiqueta_nivel, self.combo_nivel)  # type: ignore[assignment]
        for clave, (etiqueta, widget) in especificos.items():
            if clave in visibles:
                etiqueta.grid()
                widget.grid()
            else:
                # grid_remove() oculta el widget pero recuerda su posición (como en la Fase 3).
                if isinstance(widget, ttk.Entry) and not isinstance(widget, ttk.Combobox):
                    widget.delete(0, tk.END)
                etiqueta.grid_remove()
                widget.grid_remove()

    def crear_servicio(self) -> None:
        """Crea un servicio del tipo seleccionado con los datos del formulario."""
        tipo = TIPOS_SERVICIO[self.tipo_servicio.get()]
        datos: dict[str, object] = {
            "nombre": self.campos_servicio["nombre"][1].get(),
            "tarifa_base": self.campos_servicio["tarifa_base"][1].get(),
        }
        for clave in self._CAMPOS_POR_TIPO[tipo]:
            datos[clave] = (self.nivel_asesoria.get() if clave == "nivel"
                            else self.campos_servicio[clave][1].get())
        # Los números se envían como texto: el modelo los convierte y valida
        # (con encadenamiento de excepciones si el texto no es numérico).
        servicio = self.ejecutar_accion(
            "Crear servicio", lambda: self.sistema.crear_servicio(tipo, **datos)
        )
        if servicio is not None:
            self._limpiar_campos(*(e for _, e in self.campos_servicio.values()))
            self.mostrar_estado(f"Servicio {servicio.id} creado.")

    def alternar_disponibilidad(self) -> None:
        """Habilita o deshabilita el servicio seleccionado en la tabla."""
        def accion() -> Servicio:
            id_servicio = self._id_seleccionado(self.tabla_servicios, "servicio")
            servicio = self.sistema.buscar_servicio(id_servicio)
            if servicio.disponible:
                return self.sistema.deshabilitar_servicio(id_servicio)
            return self.sistema.habilitar_servicio(id_servicio)

        servicio = self.ejecutar_accion("Cambiar disponibilidad", accion)
        if servicio is not None:
            estado = "habilitado" if servicio.disponible else "deshabilitado"
            self.mostrar_estado(f"Servicio {servicio.id} {estado}.")

    # ======================================================================
    # Pestaña Reservas
    # ======================================================================
    def _construir_pestana_reservas(self) -> None:
        pestana = ttk.Frame(self.cuaderno, padding=8)
        self.cuaderno.add(pestana, text="Reservas")
        pestana.columnconfigure(1, weight=1)
        pestana.rowconfigure(0, weight=1)

        formulario = ttk.LabelFrame(pestana, text="Nueva reserva", padding=8)
        formulario.grid(row=0, column=0, sticky="nw", padx=(0, 8))

        ttk.Label(formulario, text="Cliente:").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self.cliente_reserva = tk.StringVar()
        self.combo_cliente = ttk.Combobox(formulario, textvariable=self.cliente_reserva,
                                          state="readonly", width=30)
        self.combo_cliente.grid(row=0, column=1, padx=8, pady=4, sticky="ew")

        ttk.Label(formulario, text="Servicio:").grid(row=1, column=0, padx=8, pady=4, sticky="w")
        self.servicio_reserva = tk.StringVar()
        self.combo_servicio = ttk.Combobox(formulario, textvariable=self.servicio_reserva,
                                           state="readonly", width=30)
        self.combo_servicio.grid(row=1, column=1, padx=8, pady=4, sticky="ew")
        self.combo_servicio.bind("<<ComboboxSelected>>", self.al_cambiar_servicio_reserva)

        self.campos_reserva = self._crear_campos(formulario, [
            ("duracion", "Duración (horas):"),
            ("asistentes", "Asistentes:"),
            ("cantidad", "Cantidad de equipos:"),
        ], fila_inicial=2)

        self.etiqueta_modalidad = ttk.Label(formulario, text="Modalidad:")
        self.etiqueta_modalidad.grid(row=5, column=0, padx=8, pady=4, sticky="w")
        self.modalidad = tk.StringVar(value="virtual")
        self.combo_modalidad = ttk.Combobox(formulario, textvariable=self.modalidad,
                                            state="readonly", width=30,
                                            values=list(AsesoriaEspecializada.MODALIDADES))
        self.combo_modalidad.grid(row=5, column=1, padx=8, pady=4, sticky="ew")

        ttk.Separator(formulario).grid(row=6, column=0, columnspan=2, sticky="ew", pady=6)
        self.campos_cobro = self._crear_campos(formulario, [
            ("impuesto", "Impuesto (0 a 1):"),
            ("descuento", "Descuento (0 a 1):"),
        ], fila_inicial=7)
        self.campos_cobro["impuesto"][1].insert(0, str(IVA_POR_DEFECTO))  # IVA sugerido
        self.campos_cobro["descuento"][1].insert(0, "0")

        botones = ttk.Frame(formulario)
        botones.grid(row=9, column=0, columnspan=2, pady=8)
        ttk.Button(botones, text="Crear reserva",
                   command=self.crear_reserva).grid(row=0, column=0, columnspan=2, padx=4, pady=2, sticky="ew")
        ttk.Button(botones, text="Confirmar",
                   command=self.confirmar_reserva).grid(row=1, column=0, padx=4, pady=2, sticky="ew")
        ttk.Button(botones, text="Procesar",
                   command=self.procesar_reserva).grid(row=1, column=1, padx=4, pady=2, sticky="ew")
        ttk.Button(botones, text="Cancelar reserva",
                   command=self.cancelar_reserva).grid(row=2, column=0, columnspan=2, padx=4, pady=2, sticky="ew")
        ttk.Label(formulario, text="Confirmar, Procesar y Cancelar actúan\nsobre la reserva seleccionada.",
                  foreground="#666666").grid(row=10, column=0, columnspan=2)

        marco_tabla = ttk.LabelFrame(pestana, text="Reservas", padding=4)
        marco_tabla.grid(row=0, column=1, sticky="nsew")
        self.tabla_reservas = self._crear_tabla(marco_tabla, [
            ("id", "ID", 80), ("cliente", "Cliente", 150), ("servicio", "Servicio", 170),
            ("horas", "Horas", 60), ("estado", "Estado", 100), ("costo", "Costo total", 120),
        ])
        self.al_cambiar_servicio_reserva()

    def al_cambiar_servicio_reserva(self, event: tk.Event | None = None) -> None:
        """Muestra el campo de opción propio del servicio elegido (asistentes, cantidad o modalidad)."""
        servicio = self._servicio_elegido()
        visibles: set[str] = set()
        if isinstance(servicio, ReservaSala):
            visibles = {"asistentes"}
        elif isinstance(servicio, AlquilerEquipo):
            visibles = {"cantidad"}
        elif isinstance(servicio, AsesoriaEspecializada):
            visibles = {"modalidad"}

        pares: dict[str, tuple[ttk.Label, tk.Widget]] = {
            "asistentes": self.campos_reserva["asistentes"],
            "cantidad": self.campos_reserva["cantidad"],
            "modalidad": (self.etiqueta_modalidad, self.combo_modalidad),
        }
        for clave, (etiqueta, widget) in pares.items():
            if clave in visibles:
                etiqueta.grid()
                widget.grid()
            else:
                etiqueta.grid_remove()
                widget.grid_remove()

    def _servicio_elegido(self) -> Servicio | None:
        """Devuelve el servicio seleccionado en el Combobox de reservas, o None."""
        id_servicio = self._opciones_servicio.get(self.servicio_reserva.get())
        if id_servicio is None:
            return None
        try:
            return self.sistema.buscar_servicio(id_servicio)
        except SoftwareFJError:
            return None

    def crear_reserva(self) -> None:
        """Crea una reserva PENDIENTE con el cliente, servicio y opciones del formulario."""
        def accion() -> object:
            documento = self._opciones_cliente.get(self.cliente_reserva.get())
            if documento is None:
                raise ParametroFaltanteError("Seleccione un cliente para la reserva.")
            servicio = self._servicio_elegido()
            if servicio is None:
                raise ParametroFaltanteError("Seleccione un servicio para la reserva.")
            opciones: dict[str, object] = {}
            if isinstance(servicio, ReservaSala):
                opciones["asistentes"] = self.campos_reserva["asistentes"][1].get()
            elif isinstance(servicio, AlquilerEquipo):
                # Si se deja vacío se reserva una unidad (valor por defecto del modelo).
                cantidad = self.campos_reserva["cantidad"][1].get().strip()
                if cantidad:
                    opciones["cantidad"] = cantidad
            elif isinstance(servicio, AsesoriaEspecializada):
                opciones["modalidad"] = self.modalidad.get()
            duracion = self.campos_reserva["duracion"][1].get()
            return self.sistema.crear_reserva(documento, servicio.id, duracion, **opciones)

        reserva = self.ejecutar_accion("Crear reserva", accion)
        if reserva is not None:
            self._limpiar_campos(*(e for _, e in self.campos_reserva.values()))
            self._seleccionar(self.tabla_reservas, reserva.id)  # type: ignore[attr-defined]
            self.mostrar_estado(f"Reserva {reserva.id} creada (pendiente de confirmar).")  # type: ignore[attr-defined]

    def _valor_cobro(self, clave: str, por_defecto: float) -> str | float:
        """Lee impuesto/descuento; vacío significa usar el valor por defecto."""
        texto = self.campos_cobro[clave][1].get().strip()
        return texto if texto else por_defecto

    def confirmar_reserva(self) -> None:
        """Confirma la reserva seleccionada aplicando impuesto y descuento."""
        def accion() -> object:
            id_reserva = self._id_seleccionado(self.tabla_reservas, "reserva")
            return self.sistema.confirmar_reserva(
                id_reserva,
                impuesto=self._valor_cobro("impuesto", IVA_POR_DEFECTO),  # type: ignore[arg-type]
                descuento=self._valor_cobro("descuento", 0.0),  # type: ignore[arg-type]
            )

        reserva = self.ejecutar_accion("Confirmar reserva", accion)
        if reserva is not None:
            self.mostrar_estado(
                f"Reserva {reserva.id} confirmada por ${reserva.costo:,.2f}."  # type: ignore[attr-defined]
            )

    def procesar_reserva(self) -> None:
        """Procesa la reserva seleccionada y muestra su comprobante."""
        comprobante = self.ejecutar_accion(
            "Procesar reserva",
            lambda: self.sistema.procesar_reserva(
                self._id_seleccionado(self.tabla_reservas, "reserva")
            ),
        )
        if comprobante is not None:
            lineas = "\n".join(f"{clave}: {valor}" for clave, valor in comprobante.items())  # type: ignore[attr-defined]
            self.mostrar_info("Comprobante de pago", lineas)
            self.mostrar_estado(f"Reserva {comprobante['reserva']} procesada.")  # type: ignore[index]

    def cancelar_reserva(self) -> None:
        """Cancela la reserva seleccionada, previa confirmación del usuario."""
        seleccion = self.tabla_reservas.selection()
        # Se pide confirmación porque cancelar no se puede deshacer (como "Clear" en la Fase 3).
        if seleccion and not self.preguntar("Cancelar reserva", f"¿Cancelar la reserva {seleccion[0]}?"):
            return
        reserva = self.ejecutar_accion(
            "Cancelar reserva",
            lambda: self.sistema.cancelar_reserva(
                self._id_seleccionado(self.tabla_reservas, "reserva"), "Cancelada desde la interfaz"
            ),
        )
        if reserva is not None:
            self.mostrar_estado(f"Reserva {reserva.id} cancelada.")  # type: ignore[attr-defined]

    # ======================================================================
    # Pestaña Registro (log en vivo) y simulación
    # ======================================================================
    def _construir_pestana_registro(self) -> None:
        pestana = ttk.Frame(self.cuaderno, padding=8)
        self.cuaderno.add(pestana, text="Registro (logs)")
        pestana.columnconfigure(0, weight=1)
        pestana.rowconfigure(1, weight=1)

        barra = ttk.Frame(pestana)
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(barra, text="Ejecutar simulación (25 operaciones)",
                   command=self.ejecutar_simulacion).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(barra, text="Limpiar vista",
                   command=self.limpiar_registro).grid(row=0, column=1, padx=4)
        ttk.Label(barra, text=f"Archivo: {RUTA_LOG_POR_DEFECTO}",
                  foreground="#666666").grid(row=0, column=2, padx=8)

        # Fuente monoespaciada para que las columnas del log queden alineadas.
        self.texto_registro = tk.Text(pestana, wrap="none", font=("Courier", 11), state="disabled")
        self.texto_registro.grid(row=1, column=0, sticky="nsew")
        barra_v = ttk.Scrollbar(pestana, orient="vertical", command=self.texto_registro.yview)
        barra_v.grid(row=1, column=1, sticky="ns")
        barra_h = ttk.Scrollbar(pestana, orient="horizontal", command=self.texto_registro.xview)
        barra_h.grid(row=2, column=0, sticky="ew")
        self.texto_registro.configure(yscrollcommand=barra_v.set, xscrollcommand=barra_h.set)
        for nivel, color in COLORES_NIVEL.items():
            self.texto_registro.tag_configure(logging.getLevelName(nivel), foreground=color)

    def _vaciar_cola_log(self) -> None:
        """Pasa a la vista los mensajes pendientes del logger y se reprograma."""
        try:
            self._volcar_mensajes_log()
        except tk.TclError:
            # La ventana se está cerrando: no se reprograma.
            return
        self.after(100, self._vaciar_cola_log)

    def _volcar_mensajes_log(self) -> None:
        """Inserta en el Text todos los mensajes que haya en la cola."""
        mensajes: list[tuple[int, str]] = []
        while True:
            try:
                mensajes.append(self._cola_log.get_nowait())
            except queue.Empty:
                break
        if not mensajes:
            return
        self.texto_registro.configure(state="normal")
        for nivel, texto in mensajes:
            self.texto_registro.insert(tk.END, texto + "\n", logging.getLevelName(nivel))
        # Se recorta la vista para que no crezca sin límite en sesiones largas.
        exceso = int(self.texto_registro.index("end-1c").split(".")[0]) - MAX_LINEAS_REGISTRO
        if exceso > 0:
            self.texto_registro.delete("1.0", f"{exceso + 1}.0")
        self.texto_registro.configure(state="disabled")
        self.texto_registro.see(tk.END)

    def limpiar_registro(self) -> None:
        """Vacía la vista del registro (el archivo de logs no se modifica)."""
        self.texto_registro.configure(state="normal")
        self.texto_registro.delete("1.0", tk.END)
        self.texto_registro.configure(state="disabled")

    def ejecutar_simulacion(self) -> None:
        """Ejecuta las 25 operaciones de prueba sobre un sistema nuevo y muestra el resultado."""
        hay_datos = self.sistema.clientes or self.sistema.servicios or self.sistema.reservas
        if hay_datos and not self.preguntar(
            "Ejecutar simulación",
            "La simulación empieza con un sistema vacío y reemplaza los datos actuales.\n¿Continuar?",
        ):
            return
        self.sistema = SistemaGestion()
        self.cuaderno.select(3)  # Se muestra la pestaña Registro para ver el avance.
        resultado = self.ejecutar_accion("Simulación", lambda: ejecutar_simulacion(self.sistema))
        if resultado is not None:
            self._volcar_mensajes_log()
            resumen = (f"{len(resultado.detalle)} operaciones ejecutadas:\n"  # type: ignore[attr-defined]
                       f"  • {resultado.exitosas} exitosas\n"  # type: ignore[attr-defined]
                       f"  • {resultado.controladas} errores controlados\n"  # type: ignore[attr-defined]
                       f"  • {resultado.inesperadas} errores inesperados\n\n"  # type: ignore[attr-defined]
                       "La aplicación siguió funcionando en todos los casos.")
            self.mostrar_info("Simulación finalizada", resumen)
            self.mostrar_estado("Simulación finalizada. Revise las pestañas y el registro.")

    # ======================================================================
    # Barra de estado
    # ======================================================================
    def _construir_barra_estado(self) -> None:
        barra = ttk.Frame(self, padding=(8, 2))
        barra.grid(row=1, column=0, sticky="ew")
        barra.columnconfigure(1, weight=1)
        # Fecha y hora de ejecución, como evidencia para las capturas (igual que en la Fase 3).
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        ttk.Label(barra, text=f"Fecha de ejecución: {ahora}").grid(row=0, column=0, sticky="w")
        self.etiqueta_estado = ttk.Label(barra, text="Listo.", anchor="center")
        self.etiqueta_estado.grid(row=0, column=1, sticky="ew")
        self.etiqueta_resumen = ttk.Label(barra, text="")
        self.etiqueta_resumen.grid(row=0, column=2, sticky="e")

    def mostrar_estado(self, mensaje: str) -> None:
        """Muestra un mensaje breve en la barra inferior."""
        self.etiqueta_estado.configure(text=mensaje)

    # ======================================================================
    # Manejo centralizado de acciones y errores
    # ======================================================================
    def ejecutar_accion(self, descripcion: str, accion: Callable[[], object]) -> object | None:
        """Ejecuta la acción de un botón aislando sus errores.

        Args:
            descripcion: Nombre de la acción para el log y los mensajes.
            accion: Función sin argumentos que realiza la operación.

        Returns:
            El resultado de ``accion`` o None si falló (el error ya se registró y mostró).
        """
        try:
            resultado = accion()
        except SoftwareFJError as error:
            # Error de negocio: se informa al usuario y la ventana sigue abierta.
            logger.warning("Acción '%s' rechazada: %s", descripcion, error)
            self.mostrar_estado(f"{descripcion}: no completada.")
            self.mostrar_error(descripcion, error.mensaje)
            return None
        except Exception as error:
            logger.exception("Error inesperado en la acción '%s'", descripcion)
            self.mostrar_estado(f"{descripcion}: error inesperado.")
            self.mostrar_error(
                descripcion,
                f"Ocurrió un error inesperado ({type(error).__name__}).\n"
                "Quedó registrado en el archivo de logs; la aplicación sigue activa.",
            )
            return None
        else:
            return resultado
        finally:
            # Pase lo que pase, tablas y listas reflejan el estado real del sistema.
            self.actualizar_vistas()

    def report_callback_exception(
        self, tipo: type[BaseException], valor: BaseException, rastro: TracebackType | None
    ) -> None:
        """Última red de seguridad para excepciones que escapen de un callback de Tkinter."""
        logger.critical("Excepción no controlada en la interfaz", exc_info=(tipo, valor, rastro))
        try:
            self.mostrar_error("Error interno", f"{tipo.__name__}: {valor}\nLa aplicación sigue activa.")
        except tk.TclError:
            pass  # Si ni siquiera se puede mostrar el diálogo, basta con el registro en el log.

    def mostrar_error(self, titulo: str, mensaje: str) -> None:
        """Muestra un cuadro de error (método aparte para poder sustituirlo en pruebas)."""
        messagebox.showerror(titulo, mensaje, parent=self)

    def mostrar_info(self, titulo: str, mensaje: str) -> None:
        """Muestra un cuadro informativo."""
        messagebox.showinfo(titulo, mensaje, parent=self)

    def preguntar(self, titulo: str, mensaje: str) -> bool:
        """Pide confirmación Sí/No al usuario."""
        return bool(messagebox.askyesno(titulo, mensaje, parent=self))

    # ======================================================================
    # Sincronización de la vista con el modelo
    # ======================================================================
    @staticmethod
    def _id_seleccionado(tabla: ttk.Treeview, entidad: str) -> str:
        """Devuelve el ID de la fila seleccionada o lanza ParametroFaltanteError."""
        seleccion = tabla.selection()
        if not seleccion:
            raise ParametroFaltanteError(f"Seleccione una {entidad} en la tabla."
                                         if entidad == "reserva"
                                         else f"Seleccione un {entidad} en la tabla.")
        return seleccion[0]

    @staticmethod
    def _seleccionar(tabla: ttk.Treeview, iid: str) -> None:
        """Selecciona y hace visible una fila si existe."""
        if tabla.exists(iid):
            tabla.selection_set(iid)
            tabla.see(iid)

    @staticmethod
    def _rellenar(tabla: ttk.Treeview, filas: list[tuple[str, tuple[object, ...]]]) -> None:
        """Reemplaza las filas de una tabla conservando la selección actual."""
        seleccion = tabla.selection()
        tabla.delete(*tabla.get_children())
        for iid, valores in filas:
            # El ID de la entidad se usa como iid para recuperarlo al seleccionar.
            tabla.insert("", tk.END, iid=iid, values=valores)
        for iid in seleccion:
            if tabla.exists(iid):
                tabla.selection_set(iid)

    def actualizar_vistas(self) -> None:
        """Refresca tablas, listas desplegables y resumen a partir del modelo."""
        clientes = self.sistema.clientes
        servicios = self.sistema.servicios
        reservas = self.sistema.reservas

        self._rellenar(self.tabla_clientes, [
            (c.id, (c.id, c.nombre, c.documento_enmascarado, c.email_enmascarado, c.telefono or "—"))
            for c in clientes
        ])
        self._rellenar(self.tabla_servicios, [
            (s.id, (s.id, NOMBRE_TIPO.get(type(s), type(s).__name__), s.nombre,
                    f"${s.tarifa_base:,.0f}", self._detalle_servicio(s),
                    "Disponible" if s.disponible else "No disponible"))
            for s in servicios
        ])
        self._rellenar(self.tabla_reservas, [
            (r.id, (r.id, r.cliente.nombre, r.servicio.nombre, f"{r.duracion:g}",
                    r.estado.value.capitalize(),
                    f"${r.costo:,.2f}" if r.costo is not None else "—"))
            for r in reservas
        ])

        # Listas desplegables de la pestaña Reservas.
        self._opciones_cliente = {f"{c.id} — {c.nombre}": c.documento for c in clientes}
        self._opciones_servicio = {f"{s.id} — {s.nombre}": s.id for s in servicios if s.disponible}
        self.combo_cliente.configure(values=list(self._opciones_cliente))
        self.combo_servicio.configure(values=list(self._opciones_servicio))
        # Si la opción elegida ya no existe (p. ej. servicio deshabilitado), se limpia.
        if self.cliente_reserva.get() not in self._opciones_cliente:
            self.cliente_reserva.set("")
        if self.servicio_reserva.get() not in self._opciones_servicio:
            self.servicio_reserva.set("")
            self.al_cambiar_servicio_reserva()

        resumen = self.sistema.resumen()
        procesadas = sum(1 for r in reservas if r.estado is EstadoReserva.PROCESADA)
        self.etiqueta_resumen.configure(
            text=(f"Clientes: {resumen['clientes']}  |  Servicios: {resumen['servicios']}  |  "
                  f"Reservas: {resumen['reservas']} ({procesadas} procesadas)  |  "
                  f"Ingresos: ${resumen['ingresos_procesados']:,.2f}")
        )

    @staticmethod
    def _detalle_servicio(servicio: Servicio) -> str:
        """Texto corto con los datos propios de cada tipo de servicio."""
        if isinstance(servicio, ReservaSala):
            return f"Capacidad: {servicio.capacidad} personas"
        if isinstance(servicio, AlquilerEquipo):
            return (f"{servicio.tipo_equipo}: {servicio.unidades_disponibles}/"
                    f"{servicio.unidades_totales} unidades libres")
        if isinstance(servicio, AsesoriaEspecializada):
            return f"{servicio.especialidad} (nivel {servicio.nivel})"
        return "—"

    def al_cerrar(self) -> None:
        """Desconecta el handler del logger y cierra la ventana."""
        logger.info("Interfaz gráfica cerrada por el usuario.")
        logging.getLogger(NOMBRE_LOGGER_RAIZ).removeHandler(self._manejador_log)
        self.destroy()
