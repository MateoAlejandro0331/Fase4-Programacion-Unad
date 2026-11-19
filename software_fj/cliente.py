"""Clase Cliente con validaciones robustas y encapsulación de datos personales."""

from __future__ import annotations

import logging
import re

from .entidad import EntidadBase
from .excepciones import ClienteInvalidoError, ParametroFaltanteError

logger = logging.getLogger(__name__)

# Expresiones regulares precompiladas para validar los datos personales.
# Nombre: letras (incluye tildes y ñ), espacios y apóstrofos, entre 3 y 80 caracteres.
_PATRON_NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' ]{3,80}$")
# Documento de identidad: solo dígitos, entre 6 y 12.
_PATRON_DOCUMENTO = re.compile(r"^\d{6,12}$")
# Correo electrónico con estructura usuario@dominio.ext.
_PATRON_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)*\.[A-Za-z]{2,}$")
# Teléfono: signo + opcional y entre 7 y 15 dígitos.
_PATRON_TELEFONO = re.compile(r"^\+?\d{7,15}$")


def _requerido(valor: object, campo: str) -> str:
    """Comprueba que un campo obligatorio exista y lo devuelve como texto limpio."""
    # None o cadena vacía/espacios se consideran parámetros faltantes.
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ParametroFaltanteError(f"El campo '{campo}' es obligatorio.")
    if not isinstance(valor, str):
        raise ClienteInvalidoError(
            f"El campo '{campo}' debe ser texto, se recibió {type(valor).__name__}."
        )
    return valor.strip()


class Cliente(EntidadBase):
    """Cliente de Software FJ.

    Los datos personales se guardan en atributos privados y solo se modifican a
    través de propiedades con validación; ``describir()`` enmascara el
    documento y el correo para no exponerlos en pantalla ni en los logs.

    Attributes:
        nombre: Nombre completo del cliente.
        documento: Número de documento de identidad (solo dígitos).
        email: Correo electrónico de contacto.
        telefono: Teléfono de contacto (opcional).
    """

    PREFIJO = "CLI"

    def __init__(
        self, nombre: str, documento: str, email: str, telefono: str | None = None
    ) -> None:
        super().__init__()
        # Se asigna a través de los setters para que todas las validaciones se apliquen.
        self.nombre = nombre
        self.documento = documento
        self.email = email
        self.telefono = telefono
        self.validar()
        self._asignar_id()  # Solo un cliente válido recibe ID.
        logger.debug("Cliente creado: %s", self.describir())

    # --- Propiedades con validación (encapsulación) -------------------------
    @property
    def nombre(self) -> str:
        """Nombre completo del cliente."""
        return self.__nombre

    @nombre.setter
    def nombre(self, valor: str) -> None:
        texto = _requerido(valor, "nombre")
        if not _PATRON_NOMBRE.match(texto):
            raise ClienteInvalidoError(
                f"Nombre inválido '{texto}': use solo letras y espacios (3-80 caracteres)."
            )
        # Se normaliza a formato título: "ana gómez" -> "Ana Gómez".
        self.__nombre = " ".join(texto.split()).title()

    @property
    def documento(self) -> str:
        """Documento de identidad (solo lectura tras la creación)."""
        return self.__documento

    @documento.setter
    def documento(self, valor: str) -> None:
        # El documento identifica al cliente: no se permite cambiarlo una vez asignado.
        if hasattr(self, "_Cliente__documento"):
            raise ClienteInvalidoError("El documento de un cliente no puede modificarse.")
        # Se acepta el documento como número entero (p. ej. 80123456) y se convierte a
        # texto; bool se excluye porque en Python True/False también son int.
        if isinstance(valor, int) and not isinstance(valor, bool):
            valor = str(valor)
        texto = _requerido(valor, "documento")
        if not _PATRON_DOCUMENTO.match(texto):
            raise ClienteInvalidoError(
                f"Documento inválido '{texto}': debe tener entre 6 y 12 dígitos."
            )
        self.__documento = texto

    @property
    def email(self) -> str:
        """Correo electrónico del cliente."""
        return self.__email

    @email.setter
    def email(self, valor: str) -> None:
        texto = _requerido(valor, "email").lower()
        if not _PATRON_EMAIL.match(texto):
            raise ClienteInvalidoError(f"Correo electrónico inválido: '{texto}'.")
        self.__email = texto

    @property
    def telefono(self) -> str | None:
        """Teléfono de contacto, o None si no se registró."""
        return self.__telefono

    @telefono.setter
    def telefono(self, valor: str | None) -> None:
        # El teléfono es opcional: None o vacío significa "sin teléfono".
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            self.__telefono = None
            return
        texto = str(valor).strip().replace(" ", "")
        if not _PATRON_TELEFONO.match(texto):
            raise ClienteInvalidoError(
                f"Teléfono inválido '{valor}': entre 7 y 15 dígitos, '+' opcional."
            )
        self.__telefono = texto

    # --- Métodos de EntidadBase ---------------------------------------------
    def validar(self) -> None:
        """Revalida que todos los campos obligatorios estén presentes."""
        for campo in ("nombre", "documento", "email"):
            if not getattr(self, campo, None):
                raise ParametroFaltanteError(f"El cliente no tiene '{campo}'.")

    def describir(self) -> str:
        """Descripción con datos sensibles enmascarados."""
        return (
            f"Cliente {self.id}: {self.nombre} | Doc: {self.documento_enmascarado} "
            f"| Email: {self.email_enmascarado}"
        )

    @property
    def documento_enmascarado(self) -> str:
        """Documento con todos los dígitos ocultos excepto los cuatro últimos."""
        return "*" * (len(self.documento) - 4) + self.documento[-4:]

    @property
    def email_enmascarado(self) -> str:
        """Correo con el usuario oculto salvo su primera letra."""
        usuario, dominio = self.email.split("@", 1)
        return f"{usuario[0]}***@{dominio}"
