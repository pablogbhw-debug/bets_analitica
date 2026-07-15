"""Persistencia MySQL de usuarios."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from mysql.connector import IntegrityError

from models.database import obtener_conexion_global


def buscar_usuario_por_correo(correo):
    """Busca y devuelve un usuario registrado mediante su correo normalizado."""
    with obtener_conexion_global() as conexion:
        fila = conexion.execute(
            "SELECT id,nombre,correo,password_hash,activo FROM usuarios WHERE correo=?",
            (correo,),
        ).fetchone()
        return dict(fila) if fila else None


def crear_usuario(nombre, correo, password_hash):
    """Inserta un usuario; UNIQUE(correo) garantiza la no duplicidad concurrente."""
    try:
        with obtener_conexion_global() as conexion:
            cursor = conexion.execute(
                "INSERT INTO usuarios (nombre,correo,password_hash) VALUES (?,?,?)",
                (nombre, correo, password_hash),
            )
            return int(cursor.lastrowid)
    except IntegrityError:
        return None


def crear_sesion_usuario(usuario_id, dias=7):
    """Crea una credencial opaca; MySQL conserva solo su huella irreversible."""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expira = (datetime.now(timezone.utc) + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
    with obtener_conexion_global() as conexion:
        conexion.execute("DELETE FROM sesiones_usuario WHERE expira<=UTC_TIMESTAMP()")
        conexion.execute(
            "INSERT INTO sesiones_usuario (token_hash,usuario_id,expira) VALUES (?,?,?)",
            (token_hash, int(usuario_id), expira),
        )
    return token


def buscar_usuario_por_sesion(token):
    """Valida el token de sesión y devuelve el usuario asociado."""
    if not token or not isinstance(token, str) or len(token) > 200:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with obtener_conexion_global() as conexion:
        fila = conexion.execute("""
            SELECT u.id,u.nombre,u.correo
            FROM sesiones_usuario s
            JOIN usuarios u ON u.id=s.usuario_id
            WHERE s.token_hash=? AND s.expira>UTC_TIMESTAMP() AND u.activo=TRUE
        """, (token_hash,)).fetchone()
        return dict(fila) if fila else None


def eliminar_sesion_usuario(token):
    """Elimina una sesión persistente usando el hash seguro de su token."""
    if not token or not isinstance(token, str):
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with obtener_conexion_global() as conexion:
        conexion.execute("DELETE FROM sesiones_usuario WHERE token_hash=?", (token_hash,))
