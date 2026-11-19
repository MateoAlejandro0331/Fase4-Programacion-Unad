# Portada

**Fase 4 – Componente práctico: Prácticas simuladas**
**Sistema Integral de Gestión de Clientes, Servicios y Reservas – Software FJ**

Curso: Programación (213023)
Grupo: [número de grupo]

Integrantes:
- [Nombre completo – código]
- [Nombre completo – código]
- [Nombre completo – código]
- [Nombre completo – código]
- [Nombre completo – código]

Tutor(a): [Nombre del tutor]

Universidad Nacional Abierta y a Distancia – UNAD
Escuela de Ciencias Básicas, Tecnología e Ingeniería (ECBTI)
Ingeniería de Sistemas
Noviembre de 2026

---

# Introducción

En el desarrollo de software, la capacidad de una aplicación para responder de forma
controlada ante situaciones inesperadas es tan importante como su funcionalidad. Datos mal
digitados, parámetros faltantes, recursos agotados u operaciones fuera de orden son
situaciones habituales que, si no se gestionan, interrumpen la ejecución y afectan la
confianza de los usuarios.

En este trabajo se desarrolló, en Python, una aplicación de escritorio orientada a objetos,
con interfaz gráfica en Tkinter, para la empresa
ficticia Software FJ, que gestiona clientes, servicios (reserva de salas, alquiler de
equipos y asesorías especializadas) y reservas sin utilizar bases de datos: toda la
información se maneja con objetos y listas en memoria. La solución aplica abstracción
(clases abstractas `EntidadBase` y `Servicio`), herencia y polimorfismo (tres servicios
especializados que calculan costos y validan parámetros de forma distinta), encapsulación
(datos personales del cliente protegidos y validados) y sobrecarga de métodos (variantes
del cálculo de costos con impuestos y descuentos).

El eje central es el manejo avanzado de excepciones: una jerarquía de excepciones
personalizadas, bloques `try/except`, `try/except/else` y `try/except/finally`,
encadenamiento de excepciones con `raise ... from` y el registro de todos los eventos y
errores en un archivo de logs mediante el módulo `logging` de Python. Una simulación de 25
operaciones demuestra que el sistema continúa funcionando aun cuando ocurren errores.

---

# Enlace del repositorio en GitHub

https://github.com/MateoAlejandro0331/Fase4-Programacion-Unad

---

# Conclusiones

- El manejo de excepciones permitió que la aplicación completara las 25 operaciones
  simuladas sin interrupciones: 15 errores de negocio y 1 error inesperado fueron
  capturados, registrados y aislados, mientras las operaciones válidas siguieron
  ejecutándose con normalidad.
- Definir una jerarquía de excepciones personalizadas con una clase base común facilita
  capturar cualquier error del dominio en un solo punto y, a la vez, reaccionar de forma
  específica según el tipo de falla (datos inválidos, servicio no disponible, operación no
  permitida, cálculo inconsistente).
- El encadenamiento de excepciones conserva la causa técnica original (por ejemplo, un
  `ValueError` al convertir una duración) dentro de un error de negocio comprensible, lo
  que agiliza el diagnóstico a partir del archivo de logs.
- El módulo `logging` resulta superior a `print()` para registrar eventos: permite niveles
  de severidad, varios destinos (archivo y consola), formato con fecha y origen del
  mensaje, y rotación de archivos, sin modificar la lógica del programa.
- Separar el modelo de la interfaz gráfica (Tkinter) permitió reutilizar la misma lógica
  y el mismo manejo de errores desde la ventana y desde la consola; la interfaz captura
  cada error en un único punto y lo muestra al usuario sin cerrarse.
- La abstracción, la herencia y el polimorfismo hicieron el sistema extensible: agregar un
  nuevo tipo de servicio solo requiere crear una subclase de `Servicio` y registrarla en la
  fábrica de `SistemaGestion`.

---

# Referencias bibliográficas

Cuevas Álvarez, A. (2016). *Python 3: Curso práctico*. RA-MA Editorial.
https://elibro-net.bibliotecavirtual.unad.edu.co/es/ereader/unad/106404?page=373

Python Software Foundation. (2024). *tkinter — Python interface to Tcl/Tk*. En *The Python
standard library*. https://docs.python.org/3/library/tkinter.html

Python Software Foundation. (2024). *logging — Logging facility for Python*. En *The Python
standard library*. https://docs.python.org/3/library/logging.html

Romano, F., Baka, B., & Phillips, D. (2019). *Getting started with Python: Understand key
data structures and use Python in object-oriented programming*. Packt Publishing.
https://research-ebsco-com.bibliotecavirtual.unad.edu.co/linkprocessor/plink?id=b41fd66a-1134-3dcd-8dba-90f36451f08d

Silva, F. D. (2025). *Basics of using GitHub* [Objeto virtual de información]. Repositorio
Institucional UNAD. https://repository.unad.edu.co/handle/10596/75882

Van Rossum, G., & Drake Jr., F. L. (2024). *El tutorial de Python: Errores y excepciones*.
Python Software Foundation. https://docs.python.org/es/3.12/tutorial/errors.html

Zambrano, J. P. (2025). *Introducción al uso de GitHub* [Objeto virtual de información].
Repositorio Institucional UNAD. https://repository.unad.edu.co/handle/10596/75876
