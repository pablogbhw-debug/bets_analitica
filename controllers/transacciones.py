"""Controlador transaccional y punto único de acceso para las vistas.

Las validaciones de saldo, rollover, retiro y liquidación se delegan al modelo
persistente, manteniendo a Streamlit desacoplado de la infraestructura.
"""

from models.database import *
