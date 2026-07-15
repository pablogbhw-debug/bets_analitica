"""Configuración de control y límites aislada por usuario."""

from datetime import datetime, timedelta, timezone

from models.repositorios.conexion import ZONA_LOCAL, obtener_conexion, obtener_usuario_actual


def _asegurar_configuracion(conn, usuario_id):
    """Crea la configuración preventiva predeterminada cuando aún no existe."""
    conn.execute("INSERT IGNORE INTO configuracion_control (usuario_id) VALUES (?)", (usuario_id,))


def obtener_configuracion():
    """Consulta los límites y controles preventivos del usuario."""
    usuario_id = obtener_usuario_actual()
    with obtener_conexion() as conn:
        _asegurar_configuracion(conn, usuario_id)
        return dict(conn.execute(
            "SELECT * FROM configuracion_control WHERE usuario_id=?", (usuario_id,)
        ).fetchone())


def actualizar_configuracion(limite_deposito_diario, limite_apuesta_diario,
                             limite_apuesta_individual, limite_perdida_semanal, modo_estricto):
    """Guarda los límites personales y el modo de control preventivo."""
    usuario_id = obtener_usuario_actual()
    valores = list(map(float, (limite_deposito_diario, limite_apuesta_diario,
                              limite_apuesta_individual, limite_perdida_semanal)))
    if min(valores) <= 0:
        raise ValueError("Todos los límites deben ser mayores que cero.")
    with obtener_conexion() as conn:
        _asegurar_configuracion(conn, usuario_id)
        conn.execute("""UPDATE configuracion_control SET limite_deposito_diario=?,
            limite_apuesta_diario=?,limite_apuesta_individual=?,limite_perdida_semanal=?,
            modo_estricto=? WHERE usuario_id=?""", (*valores, int(bool(modo_estricto)), usuario_id))


def activar_pausa(horas=24):
    """Impide temporalmente nuevas operaciones durante la cantidad de horas indicada."""
    usuario_id = obtener_usuario_actual()
    hasta = (datetime.now(timezone.utc) + timedelta(hours=int(horas))).strftime("%Y-%m-%d %H:%M:%S")
    with obtener_conexion() as conn:
        _asegurar_configuracion(conn, usuario_id)
        conn.execute("UPDATE configuracion_control SET pausa_hasta=? WHERE usuario_id=?",
                     (hasta, usuario_id))
    return hasta


def estado_pausa():
    """Informa si la pausa preventiva continúa activa y cuándo termina."""
    config = obtener_configuracion()
    if not config["pausa_hasta"]:
        return False, None
    hasta = datetime.fromisoformat(str(config["pausa_hasta"]))
    if hasta.tzinfo is None:
        hasta = hasta.replace(tzinfo=timezone.utc)
    return hasta > datetime.now(timezone.utc), hasta.astimezone(ZONA_LOCAL)


def _suma_periodo(conn, usuario_id, tipos, desde):
    """Suma movimientos específicos del usuario desde una fecha determinada."""
    marcas = ",".join("?" for _ in tipos)
    fila = conn.execute(
        f"SELECT COALESCE(SUM(monto),0) FROM historial_transacciones "
        f"WHERE usuario_id=? AND tipo_movimiento IN ({marcas}) AND datetime(fecha)>=datetime(?)",
        (usuario_id, *tipos, desde),
    ).fetchone()
    return float(fila[0])


def evaluar_limites(tipo, monto):
    """Evalúa una operación contra límites personales y pausas preventivas."""
    usuario_id = obtener_usuario_actual()
    monto = float(monto)
    config = obtener_configuracion()
    pausado, hasta = estado_pausa()
    razones = []
    with obtener_conexion() as conn:
        ahora_local = datetime.now(ZONA_LOCAL)
        hoy = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")
        semana = (ahora_local - timedelta(days=7)).astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if tipo == "RECARGA":
            usado = _suma_periodo(conn, usuario_id, ["RECARGA"], hoy)
            if usado + monto > float(config["limite_deposito_diario"]):
                razones.append(f"Límite diario de depósitos: S/ {config['limite_deposito_diario']:.2f}.")
        if tipo == "APUESTA":
            usado = _suma_periodo(conn, usuario_id, ["APUESTA_PENDIENTE"], hoy)
            if monto > float(config["limite_apuesta_individual"]):
                razones.append(f"Límite por apuesta: S/ {config['limite_apuesta_individual']:.2f}.")
            if usado + monto > float(config["limite_apuesta_diario"]):
                razones.append(f"Límite diario apostado: S/ {config['limite_apuesta_diario']:.2f}.")
            perdidas = _suma_periodo(
                conn, usuario_id, ["APUESTA_PERDIDA", "LIQUIDACION_PERDIDA"], semana
            )
            if perdidas >= float(config["limite_perdida_semanal"]):
                razones.append(f"Límite semanal de pérdidas: S/ {config['limite_perdida_semanal']:.2f}.")
    if pausado:
        razones.append(f"Pausa activa hasta {hasta:%d/%m/%Y %H:%M}.")
    return {"permitido": True, "razones": razones, "modo_estricto": False}
