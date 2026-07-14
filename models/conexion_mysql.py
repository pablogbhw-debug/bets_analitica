"""Conexiones MySQL reutilizables mediante un pool seguro para Streamlit."""

import os
import re
import threading
from contextlib import contextmanager

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool


_pools = {}
_lock = threading.Lock()


def _configuracion():
    base = os.getenv("MYSQL_DATABASE", "apuestas_analitica")
    if not re.fullmatch(r"[A-Za-z0-9_]+", base):
        raise ValueError("MYSQL_DATABASE solo admite letras, números y guion bajo.")
    return base, {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "pablogirao"),
        "autocommit": False,
    }


def _obtener_pool():
    base, configuracion = _configuracion()
    clave = (base, configuracion["host"], configuracion["port"], configuracion["user"])
    with _lock:
        if clave not in _pools:
            servidor = mysql.connector.connect(**configuracion)
            cursor = servidor.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{base}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.close()
            servidor.close()
            _pools[clave] = MySQLConnectionPool(
                pool_name=f"apuestas_{len(_pools)}",
                pool_size=int(os.getenv("MYSQL_POOL_SIZE", "8")),
                pool_reset_session=True,
                database=base,
                **configuracion,
            )
        return _pools[clave]


def crear_conexion_mysql():
    """Obtiene una conexión del pool; close() la devuelve para reutilizarla."""
    return _obtener_pool().get_connection()


@contextmanager
def conexion_mysql():
    conexion = crear_conexion_mysql()
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
