"""API explícita de persistencia, compuesta por repositorios de dominio."""

from models.repositorios.apuestas import (
    editar_apuesta_bitacora,
    eliminar_apuesta_bitacora,
    eliminar_apuesta_pendiente,
    obtener_apuestas,
    registrar_apuesta,
    registrar_apuesta_bitacora,
    resolver_apuesta,
)
from models.repositorios.casas import (
    actualizar_casa,
    eliminar_casa_apuesta,
    inicializar_casas_predeterminadas,
    obtener_casa,
    obtener_resumen_casas,
    registrar_casa_apuesta,
    reiniciar_datos_conservando_casas,
)
from models.repositorios.configuracion import (
    activar_pausa,
    actualizar_configuracion,
    estado_pausa,
    evaluar_limites,
    obtener_configuracion,
)
from models.repositorios.conexion import (
    MINIMO_RETIRO,
    ZONA_LOCAL,
    ahora_utc_sql,
    establecer_usuario_actual,
    fecha_utc_a_local,
    inicializar_db,
    normalizar_fecha_evento,
    obtener_conexion,
    obtener_conexion_global,
    obtener_usuario_actual,
)
from models.repositorios.historial import (
    diagnosticar_ciclo,
    obtener_historial_completo,
    recalcular_rollover_casa,
    recalcular_saldos_desde_historial,
    retiro_permitido,
    saldo_jugable,
)
from models.repositorios.movimientos import registrar_movimiento_bd, registrar_recarga_bitacora


__all__ = [nombre for nombre in globals() if not nombre.startswith("_")]
