"""Reglas de registro e inicio de sesión con bcrypt."""

import re

import bcrypt

from models.usuarios import (
    buscar_usuario_por_correo,
    buscar_usuario_por_sesion,
    crear_sesion_usuario,
    crear_usuario,
    eliminar_sesion_usuario,
)


PATRON_CORREO = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
HASH_FICTICIO = b"$2b$12$C6UzMDM.H6dfI/f/IKcEe.ou7tHZQ1XH4mOaP38YI2Ca8b7fV8x.q"


def normalizar_correo(correo):
    """Limpia y convierte el correo a un formato uniforme para comparaciones."""
    return str(correo).strip().lower()


def registrar_usuario(nombre, correo, password, confirmacion):
    """Valida los datos y crea una nueva cuenta de usuario."""
    nombre = " ".join(str(nombre).strip().split())
    correo = normalizar_correo(correo)
    if len(nombre) < 2:
        raise ValueError("Ingresa un nombre válido.")
    if not PATRON_CORREO.fullmatch(correo) or len(correo) > 254:
        raise ValueError("Ingresa un correo electrónico válido.")
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes.")
    if password != confirmacion:
        raise ValueError("Las contraseñas no coinciden.")
    if buscar_usuario_por_correo(correo):
        raise ValueError("Ya existe una cuenta registrada con ese correo.")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    usuario_id = crear_usuario(nombre, correo, password_hash)
    if usuario_id is None:
        raise ValueError("Ya existe una cuenta registrada con ese correo.")
    return {"id": usuario_id, "nombre": nombre, "correo": correo}


def autenticar_usuario(correo, password):
    """Comprueba las credenciales y devuelve el usuario autenticado."""
    correo = normalizar_correo(correo)
    usuario = buscar_usuario_por_correo(correo) if PATRON_CORREO.fullmatch(correo) else None
    hash_guardado = usuario["password_hash"].encode("utf-8") if usuario else HASH_FICTICIO
    coincide = bcrypt.checkpw(password.encode("utf-8")[:72], hash_guardado)
    if not usuario or not usuario["activo"] or not coincide:
        raise ValueError("Correo o contraseña incorrectos.")
    return {"id": usuario["id"], "nombre": usuario["nombre"], "correo": usuario["correo"]}


def iniciar_sesion_persistente(usuario):
    """Crea y devuelve un token para mantener iniciada la sesión."""
    return crear_sesion_usuario(usuario["id"])


def restaurar_sesion(token):
    """Recupera un usuario a partir de un token de sesión vigente."""
    return buscar_usuario_por_sesion(token)


def cerrar_sesion(token):
    """Elimina el token indicado para cerrar la sesión persistente."""
    eliminar_sesion_usuario(token)
