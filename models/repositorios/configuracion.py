"""Configuración de control, pausas y límites financieros."""

from datetime import datetime, timedelta, timezone
from models.repositorios.conexion import ZONA_LOCAL, obtener_conexion


def obtener_configuracion():
    with obtener_conexion() as conn:
        return dict(conn.execute("SELECT * FROM configuracion_control WHERE id=1").fetchone())


def actualizar_configuracion(limite_deposito_diario, limite_apuesta_diario,
                             limite_apuesta_individual, limite_perdida_semanal, modo_estricto):
    valores = list(map(float, (limite_deposito_diario, limite_apuesta_diario,
                              limite_apuesta_individual, limite_perdida_semanal)))
    if min(valores) <= 0:
        raise ValueError("Todos los límites deben ser mayores que cero.")
    with obtener_conexion() as conn:
        conn.execute("""UPDATE configuracion_control SET limite_deposito_diario=?,
            limite_apuesta_diario=?, limite_apuesta_individual=?, limite_perdida_semanal=?,
            modo_estricto=? WHERE id=1""", (*valores, int(bool(modo_estricto))))


def activar_pausa(horas=24):
    hasta = (datetime.now(timezone.utc) + timedelta(hours=int(horas))).isoformat(timespec="seconds")
    with obtener_conexion() as conn:
        conn.execute("UPDATE configuracion_control SET pausa_hasta=? WHERE id=1", (hasta,))
    return hasta


def estado_pausa():
    config = obtener_configuracion()
    if not config["pausa_hasta"]:
        return False, None
    hasta = datetime.fromisoformat(config["pausa_hasta"])
    # Compatibilidad con pausas antiguas, que se guardaban como hora local sin zona.
    if hasta.tzinfo is None:
        hasta = hasta.replace(tzinfo=ZONA_LOCAL)
    return hasta > datetime.now(timezone.utc), hasta.astimezone(ZONA_LOCAL)


def _suma_periodo(conn, tipos, desde):
    marcas = ",".join("?" for _ in tipos)
    fila = conn.execute(f"SELECT COALESCE(SUM(monto),0) FROM historial_transacciones "
                        f"WHERE tipo_movimiento IN ({marcas}) AND datetime(fecha)>=datetime(?)",
                        (*tipos, desde)).fetchone()
    return float(fila[0])


def evaluar_limites(tipo, monto):
    monto = float(monto)
    config = obtener_configuracion()
    pausado, hasta = estado_pausa()
    razones = []
    with obtener_conexion() as conn:
        ahora_local = datetime.now(ZONA_LOCAL)
        hoy_local = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
        hoy = hoy_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        semana = (ahora_local - timedelta(days=7)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if tipo == "RECARGA":
            usado = _suma_periodo(conn, ["RECARGA"], hoy)
            if usado + monto > config["limite_deposito_diario"]:
                razones.append(f"Límite diario de depósitos: S/ {config['limite_deposito_diario']:.2f}.")
        if tipo == "APUESTA":
            usado = _suma_periodo(conn, ["APUESTA_PENDIENTE"], hoy)
            if monto > config["limite_apuesta_individual"]:
                razones.append(f"Límite por apuesta: S/ {config['limite_apuesta_individual']:.2f}.")
            if usado + monto > config["limite_apuesta_diario"]:
                razones.append(f"Límite diario apostado: S/ {config['limite_apuesta_diario']:.2f}.")
            perdidas = _suma_periodo(conn, ["APUESTA_PERDIDA", "LIQUIDACION_PERDIDA"], semana)
            if perdidas >= config["limite_perdida_semanal"]:
                razones.append(f"Límite semanal de pérdidas: S/ {config['limite_perdida_semanal']:.2f}.")
    if pausado:
        razones.append(f"Pausa activa hasta {hasta:%d/%m/%Y %H:%M}.")
    # Los límites son referencias analíticas. El sistema registra la decisión del usuario
    # aunque se superen; únicamente los retiros obedecen reglas operativas de la casa.
    return {"permitido": True, "razones": razones, "modo_estricto": False}
