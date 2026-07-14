"""Fachada compatible de las funciones analíticas, ahora separadas por módulo."""

from controllers.analitica_resumen import analizar_rendimiento_psicologico, auditar_conciliacion_historial
from controllers.analitica_recarga import recomendar_recarga_bitacora, evaluar_proteccion_perdidas, resumen_financiero_casa
from controllers.analitica_apuesta import (calcular_retorno_potencial, recomendar_monto_maximo,
    recomendar_monto_bitacora, verificar_saldo_para_apuesta)
from controllers.analitica_pendientes import resumen_apuestas_pendientes

__all__ = [nombre for nombre in globals() if not nombre.startswith("_")]
