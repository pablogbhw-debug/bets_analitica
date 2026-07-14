"""Fachada retrocompatible de las entidades del Modelo."""

from models.entidades import RegistroApuesta, Transaccion, normalizar_campos_texto

__all__ = ["Transaccion", "RegistroApuesta", "normalizar_campos_texto"]
