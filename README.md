# Fase 4 – Programación (213023) UNAD
## Sistema Integral de Gestión de Clientes, Servicios y Reservas — *Software FJ*

Aplicación de escritorio orientada a objetos en Python (interfaz con **Tkinter**, la misma
librería usada en la Fase 3), **sin base de datos**, que gestiona clientes,
servicios (salas, alquiler de equipos y asesorías) y reservas. Aplica abstracción,
herencia, polimorfismo y encapsulación, con **manejo avanzado de excepciones**: el sistema
sigue funcionando aunque ocurran errores, y cada evento o error queda registrado en un
archivo de logs mediante el módulo estándar `logging`.

## Requisitos previos

- Python **3.10 o superior** (probado con 3.15 y Tk 9.1).
- **Tkinter** para la interfaz gráfica. Viene incluido con Python en Windows y en el
  instalador oficial de macOS. Si usas Homebrew: `brew install python-tk`; en
  Debian/Ubuntu: `sudo apt install python3-tk`.
- No hay más dependencias: todo es de la biblioteca estándar (por eso no hay `requirements.txt`).

## Instalación y configuración

```bash
git clone https://github.com/MateoAlejandro0331/Fase4-Programacion-Unad.git
cd Fase4-Programacion-Unad
python3 -m venv .venv            # opcional
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
```

## Uso básico

### Aplicación de escritorio

```bash
python3 main.py
```

La ventana (`App`, que hereda de `tk.Tk`) tiene cuatro pestañas:

| Pestaña | Qué permite |
|---|---|
| **Clientes** | Registrar clientes (con validación) y verlos en una tabla con los datos sensibles enmascarados |
| **Servicios** | Crear salas, equipos o asesorías; el formulario muestra solo los campos del tipo elegido (`grid_remove()`), y habilitar/deshabilitar servicios |
| **Reservas** | Crear reservas eligiendo cliente y servicio, y confirmar, procesar (muestra el comprobante) o cancelar la reserva seleccionada |
| **Registro (logs)** | Ver el log en vivo, con colores por nivel, y ejecutar la simulación de 25 operaciones con un botón |

Cualquier error (datos inválidos, servicio no disponible, operación no permitida...) se
muestra en un cuadro de diálogo, queda en el log y la ventana sigue abierta.

### Simulación en consola

```bash
python3 main.py --consola
```

Si la interfaz no puede abrirse (Tkinter no instalado o equipo sin pantalla), `main.py`
registra el error y ejecuta automáticamente la simulación en consola.

La consola muestra los eventos a nivel INFO y el archivo `logs/software_fj.log` guarda
**todo** (nivel DEBUG) con fecha, nivel, módulo, función y línea. En
[docs/ejemplo_ejecucion.log](docs/ejemplo_ejecucion.log) hay un ejemplo de log generado.

Uso como librería:

```python
from software_fj import SistemaGestion, configurar_logging

configurar_logging()                       # archivo logs/software_fj.log + consola
sistema = SistemaGestion()
sistema.registrar_cliente("Ana Gómez", "1020304050", "ana@correo.com")
sistema.crear_servicio("sala", nombre="Sala A", tarifa_base=80_000, capacidad=20)
reserva = sistema.crear_reserva("1020304050", "Sala A", 3, asistentes=10)
sistema.confirmar_reserva(reserva.id, descuento=0.10)   # IVA 19 % por defecto
print(sistema.procesar_reserva(reserva.id))
```

## Diseño

| Requisito del Anexo 3 | Implementación |
|---|---|
| Clase abstracta de entidades generales | `EntidadBase` ([entidad.py](software_fj/entidad.py)): ID automático, `validar()` y `describir()` abstractos |
| Cliente con validaciones y encapsulación | `Cliente` ([cliente.py](software_fj/cliente.py)): atributos privados, propiedades con validación por regex, documento inmutable y datos enmascarados |
| Servicio abstracto + 3 especializados | `Servicio` → `ReservaSala`, `AlquilerEquipo`, `AsesoriaEspecializada` ([servicios.py](software_fj/servicios.py)), sobrescriben `_costo_base`, `describir`, `validar_parametros` |
| Reserva con confirmación, cancelación y procesamiento | `Reserva` + `EstadoReserva` ([reserva.py](software_fj/reserva.py)) |
| Métodos sobrecargados | `calcular_costo(duracion)`, `(duracion, impuesto)`, `(duracion, impuesto, descuento, **opciones)` con `@overload`; `buscar_servicio(str \| int)` con `@singledispatchmethod` |
| Excepciones personalizadas | Jerarquía con base `SoftwareFJError` ([excepciones.py](software_fj/excepciones.py)) |
| try/except, try/except/else, try/except/finally | `Reserva.confirmar` (else), `Reserva.cancelar` (finally), `Reserva.procesar` (except/else/finally), `main.ejecutar_operacion` |
| Encadenamiento de excepciones | `raise ... from error` en conversión numérica, validación de reserva, cálculo de costos y fábrica de servicios |
| Archivo de logs | `configurar_logging()` ([logger_config.py](software_fj/logger_config.py)) con `dictConfig` y `RotatingFileHandler` |
| Listas internas, sin base de datos | `SistemaGestion` ([sistema.py](software_fj/sistema.py)) guarda clientes, servicios y reservas en listas |
| ≥ 10 operaciones simuladas | 25 operaciones en [simulacion.py](software_fj/simulacion.py), ejecutables desde la ventana o con `--consola` |
| Aplicación de escritorio (como en la Fase 3) | `App(tk.Tk)` en [gui.py](software_fj/gui.py): `ttk`, `grid`, `messagebox`, `Combobox` con campos dinámicos, `Treeview` y `Text` con `Scrollbar` |

### Jerarquía de excepciones

```
SoftwareFJError
├── ValidacionError ── ClienteInvalidoError, ParametroFaltanteError
├── ServicioError ──── ParametroServicioError, ServicioNoDisponibleError
├── ReservaError ───── ReservaInvalidaError, OperacionNoPermitidaError
├── CalculoInconsistenteError
├── EntidadDuplicadaError
└── EntidadNoEncontradaError
```

### Configuración del logger

- Logger raíz del paquete: `software_fj`; cada módulo usa `logging.getLogger(__name__)`.
- Handler de **archivo** (`logs/software_fj.log`): nivel DEBUG, UTF-8, rota a 1 MB y guarda 3 respaldos.
- Handler de **consola**: nivel INFO (configurable con `configurar_logging(nivel_consola=...)`).
- El decorador `registrar_operacion` de `SistemaGestion` registra cada error de negocio con
  su cadena de causas (`error ← causa ← causa original`), y los errores inesperados con
  traceback completo.
- Handler de la **ventana** (`ManejadorLogTkinter`): deja cada registro en una `queue.Queue`
  que la interfaz lee cada 100 ms con `after()` (Tkinter no es seguro entre hilos).

### Robustez de la interfaz

- Todos los botones pasan por `App.ejecutar_accion`, con `try/except/else/finally`: los
  errores de negocio se muestran con `messagebox.showerror`, los inesperados se registran
  con traceback, y en el `finally` las tablas siempre se sincronizan con el modelo.
- `App.report_callback_exception` atrapa cualquier excepción que escape de un callback de
  Tkinter (que por defecto solo se imprimiría en la terminal).
- Acciones irreversibles (cancelar una reserva, reiniciar con la simulación) piden
  confirmación con `messagebox.askyesno`.

## Estructura del proyecto

```
.
├── main.py                    # Punto de entrada: ventana o --consola
├── software_fj/
│   ├── __init__.py
│   ├── gui.py                 # VISTA: aplicación de escritorio Tkinter
│   ├── simulacion.py          # Las 25 operaciones de prueba
│   ├── logger_config.py       # Configuración del logging
│   ├── excepciones.py         # Excepciones personalizadas
│   ├── entidad.py             # Clase abstracta EntidadBase
│   ├── cliente.py             # Cliente
│   ├── servicios.py           # Servicio y sus 3 especializaciones
│   ├── reserva.py             # Reserva y EstadoReserva
│   └── sistema.py             # SistemaGestion (fachada con listas internas)
├── tests/
│   ├── test_software_fj.py    # 24 pruebas del modelo
│   └── test_gui.py            # 7 pruebas de la ventana (se omiten si no hay pantalla)
├── docs/
│   └── ejemplo_ejecucion.log  # Log de ejemplo
└── logs/                      # Se crea al ejecutar (ignorado por git)
```

## Tests

```bash
python3 -m unittest -v
```
