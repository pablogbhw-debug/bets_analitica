"""Casos de uso transaccionales expuestos a las vistas."""

from models.database import (
    actualizar_casa,
    diagnosticar_ciclo,
    editar_apuesta_bitacora,
    eliminar_apuesta_bitacora,
    eliminar_apuesta_pendiente,
    eliminar_casa_apuesta,
    establecer_usuario_actual,
    fecha_utc_a_local,
    inicializar_casas_predeterminadas,
    inicializar_db,
    obtener_apuestas,
    obtener_historial_completo,
    obtener_resumen_casas,
    recalcular_rollover_casa,
    registrar_casa_apuesta,
    registrar_movimiento_bd,
    registrar_recarga_bitacora,
    reiniciar_datos_conservando_casas,
    resolver_apuesta,
    retiro_permitido,
)
from models.database import registrar_apuesta_bitacora as _registrar_apuesta_bitacora
from models.entidades import RegistroApuesta


def registrar_apuesta_desde_formulario(id_casa, monto, tipo_saldo, cuota, deporte,
                                       liga, evento, mercado, seleccion, fecha_evento,
                                       resultado):
    """Valida la entidad de dominio antes de delegar su persistencia al modelo."""
    apuesta = RegistroApuesta(
        id_casa, monto, tipo_saldo, cuota, deporte, liga, evento,
        mercado, seleccion, fecha_evento,
    )
    return _registrar_apuesta_bitacora(
        apuesta.id_casa, apuesta.deporte, apuesta.liga, apuesta.evento,
        apuesta.mercado, apuesta.seleccion, apuesta.fecha_evento,
        apuesta.monto, apuesta.cuota, apuesta.tipo_saldo, resultado,
    )
