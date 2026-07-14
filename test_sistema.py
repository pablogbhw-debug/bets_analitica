import os
import unittest
from datetime import date

import database
import analitica


@unittest.skipUnless(
    os.getenv("MYSQL_TEST_DATABASE"),
    "Define MYSQL_TEST_DATABASE para ejecutar las pruebas de integración MySQL.",
)
class SistemaApuestasTest(unittest.TestCase):
    def test_fechas_utc_se_presentan_en_hora_lima(self):
        fecha = database.fecha_utc_a_local("2026-07-11 08:07:35")
        self.assertEqual(fecha.strftime("%Y-%m-%d %H:%M:%S"), "2026-07-11 03:07:35")

    def test_fecha_evento_exige_formato_iso(self):
        with self.assertRaisesRegex(ValueError, "AAAA-MM-DD"):
            database.registrar_apuesta_bitacora(
                "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "A",
                "11/07/2026", 10, 2, "DEPOSITO", "PENDIENTE"
            )

    def test_recargas_permanecen_separadas_por_casa(self):
        database.registrar_casa_apuesta("OTRA", "Otra Casa")
        database.registrar_recarga_bitacora("OTRA", 30, 5)
        self.assertEqual(database.obtener_casa("OTRA")["saldo_deposito"], 30)
        self.assertEqual(database.obtener_casa("OTRA")["saldo_bono"], 5)
        self.assertEqual(database.obtener_casa("TEST")["saldo_deposito"], 0)

    def test_editar_apuesta_actualiza_su_movimiento(self):
        database.registrar_recarga_bitacora("TEST", 10)
        apuesta_id = database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "Detalle",
            date.today(), 10, 2, "DEPOSITO", "PERDIDA"
        )
        database.editar_apuesta_bitacora(
            apuesta_id, "Tenis", "ATP", "C vs D", "Ganador", "C",
            date.today(), 2.5, "SALDO"
        )
        apuesta = next(a for a in database.obtener_apuestas() if a["id"] == apuesta_id)
        movimiento = next(m for m in database.obtener_historial_completo()
                          if m["apuesta_id"] == apuesta_id)
        self.assertEqual(apuesta["tipo_saldo"], "DEPOSITO")
        self.assertEqual(movimiento["tipo_saldo_usado"], "DEPOSITO")
        self.assertEqual(apuesta["evento"], "C vs D")

    def test_eliminar_apuesta_revierte_capital_y_rollover(self):
        database.registrar_recarga_bitacora("TEST", 100)
        apuesta_id = database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "A",
            date.today(), 20, 2, "DEPOSITO", "PERDIDA"
        )
        self.assertEqual(database.obtener_casa("TEST")["saldo_deposito"], 80)
        database.eliminar_apuesta_bitacora(apuesta_id)
        casa = database.obtener_casa("TEST")
        self.assertEqual(casa["saldo_deposito"], 100)
        self.assertEqual(casa["rollover_pendiente"], 100)
        self.assertFalse(any(a["id"] == apuesta_id for a in database.obtener_apuestas()))

    def test_eliminar_apuesta_recalcula_rollover_desde_historial(self):
        database.registrar_recarga_bitacora("TEST", 10)
        apuesta_id = database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "A",
            date.today(), 10, 2, "SALDO", "GANADA"
        )
        self.assertEqual(database.obtener_casa("TEST")["rollover_pendiente"], 0)
        database.eliminar_apuesta_bitacora(apuesta_id)
        desglose = database.recalcular_rollover_casa("TEST")
        self.assertEqual(desglose["generado"], 10)
        self.assertEqual(desglose["liberado"], 0)
        self.assertEqual(desglose["pendiente"], 10)

    def setUp(self):
        os.environ["MYSQL_DATABASE"] = os.environ["MYSQL_TEST_DATABASE"]
        database.inicializar_db()
        database.reiniciar_datos_conservando_casas()
        database.registrar_casa_apuesta("TEST", "Casa Test", 20, 1, 2, 1.20, "Fútbol,Tenis")
        database.actualizar_configuracion(500, 200, 50, 100, True)

    def test_apuesta_pendiente_y_ganada(self):
        database.registrar_movimiento_bd("TEST", "RECARGA", 100)
        apuesta_id = database.registrar_apuesta(
            "TEST", "Fútbol", "Liga 1", "A vs B", "Ganador", "A", date.today(), 20, 2, "DEPOSITO"
        )
        casa = database.obtener_casa("TEST")
        self.assertEqual(casa["saldo_deposito"], 80)
        self.assertEqual(casa["rollover_pendiente"], 80)
        self.assertEqual(database.obtener_apuestas("PENDIENTE")[0]["id"], apuesta_id)
        database.resolver_apuesta(apuesta_id, "GANADA")
        casa = database.obtener_casa("TEST")
        self.assertEqual(casa["saldo_retirable"], 40)
        self.assertEqual(database.obtener_apuestas()[0]["estado"], "GANADA")

    def test_anulada_devuelve_a_billetera_original(self):
        database.registrar_movimiento_bd("TEST", "RECARGA", 50)
        apuesta_id = database.registrar_apuesta(
            "TEST", "Tenis", "ATP", "A vs B", "Ganador", "B", date.today(), 10, 1.5, "DEPOSITO"
        )
        database.resolver_apuesta(apuesta_id, "ANULADA")
        self.assertEqual(database.obtener_casa("TEST")["saldo_deposito"], 50)

    def test_limite_individual_advierte_pero_registra(self):
        database.registrar_movimiento_bd("TEST", "RECARGA", 100)
        control = database.evaluar_limites("APUESTA", 51)
        self.assertTrue(control["permitido"])
        self.assertTrue(any("Límite por apuesta" in razon for razon in control["razones"]))
        apuesta_id = database.registrar_apuesta(
            "TEST", "Fútbol", "Liga", "A vs B", "Ganador", "A", date.today(), 51, 2, "DEPOSITO"
        )
        self.assertIsInstance(apuesta_id, int)

    def test_retiro_respeta_reglas_de_casa(self):
        database.registrar_movimiento_bd("TEST", "RECARGA", 20)
        apuesta_id = database.registrar_apuesta(
            "TEST", "Fútbol", "Liga", "A vs B", "Ganador", "A", date.today(), 20, 2, "DEPOSITO"
        )
        database.resolver_apuesta(apuesta_id, "GANADA")
        database.registrar_movimiento_bd("TEST", "RETIRO", 40, 1, "RETIRO")
        self.assertEqual(database.obtener_casa("TEST")["saldo_retirable"], 0)

    def test_retiro_se_rechaza_si_hay_rollover(self):
        database.registrar_movimiento_bd("TEST", "RECARGA", 20)
        database.registrar_movimiento_bd("TEST", "APUESTA_GANADA", 10, 3, "DEPOSITO")
        with self.assertRaisesRegex(ValueError, "reglas configuradas"):
            database.registrar_movimiento_bd("TEST", "RETIRO", 20, 1, "RETIRO")

    def test_bono_ganado_convierte_solo_ganancia_neta(self):
        database.registrar_movimiento_bd("TEST", "BONO", 20, 1, "BONO")
        apuesta_id = database.registrar_apuesta(
            "TEST", "Fútbol", "Liga", "A vs B", "Ganador", "A", date.today(), 20, 2, "BONO"
        )
        database.resolver_apuesta(apuesta_id, "GANADA")
        casa = database.obtener_casa("TEST")
        self.assertEqual(casa["saldo_bono"], 0)
        self.assertEqual(casa["saldo_retirable"], 20)

    def test_alerta_ilusion_con_tasa_alta_y_balance_negativo(self):
        database.registrar_movimiento_bd("TEST", "RECARGA", 100)
        casos = [(10, 1.1, "GANADA"), (10, 1.1, "GANADA"), (50, 2, "PERDIDA")]
        for indice, (monto, cuota, resultado) in enumerate(casos):
            apuesta_id = database.registrar_apuesta(
                "TEST", "Fútbol", "Liga", f"Evento {indice}", "Ganador", "A",
                date.today(), monto, cuota, "DEPOSITO"
            )
            database.resolver_apuesta(apuesta_id, resultado)
        _, metricas = analitica.analizar_rendimiento_psicologico()
        codigos = [alerta["codigo"] for alerta in metricas["mensajes_riesgo"]]
        self.assertEqual(metricas["total_apostado"], 70)
        self.assertEqual(metricas["apuestas_ganadas"], 2)
        self.assertEqual(metricas["apuestas_perdidas"], 1)
        resumen_casa = metricas["por_casa"].iloc[0]
        self.assertEqual(resumen_casa["ganadas"], 2)
        self.assertEqual(resumen_casa["perdidas"], 1)
        self.assertTrue(metricas["sesgo_ilusion"])
        self.assertIn("ILUSION_GANANCIA", codigos)

    def test_inicializa_tres_activos_predeterminados(self):
        database.inicializar_casas_predeterminadas(forzar=True)
        codigos = {casa["id"] for casa in database.obtener_resumen_casas()}
        self.assertTrue({"BETANO", "INKABET", "TE_APUESTO"}.issubset(codigos))

    def test_bitacora_rechaza_apuesta_sin_deposito_previo(self):
        with self.assertRaisesRegex(ValueError, "Saldo insuficiente"):
            database.registrar_apuesta_bitacora(
                "TEST", "Fútbol", "Liga", "A vs B", "Ganador", "A", date.today(),
                25, 1.8, "DEPOSITO", "PERDIDA"
            )

    def test_recomendacion_bitacora_no_supera_referencia_personal(self):
        database.registrar_recarga_bitacora("TEST", 100)
        database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "Ganador", "A", date.today(),
            100, 2, "DEPOSITO", "PERDIDA"
        )
        recomendacion = analitica.recomendar_monto_bitacora("TEST")
        self.assertLessEqual(recomendacion["monto"], 50)

    def test_recomendacion_no_supera_saldo_disponible(self):
        database.registrar_recarga_bitacora("TEST", 8)
        recomendacion = analitica.recomendar_monto_bitacora("TEST")
        self.assertLessEqual(recomendacion["monto"], 8)

    def test_no_recomienda_recarga_cuando_hay_perdida(self):
        database.registrar_recarga_bitacora("TEST", 30)
        database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "Ganador", "A", date.today(),
            30, 2, "DEPOSITO", "PERDIDA"
        )
        recomendacion = analitica.recomendar_recarga_bitacora()
        self.assertEqual(recomendacion["sugerida"], 0)
        self.assertEqual(recomendacion["maxima"], 0)

    def test_perdida_exige_confirmacion_para_recargar(self):
        database.registrar_recarga_bitacora("TEST", 10)
        database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "A",
            date.today(), 10, 2, "DEPOSITO", "PERDIDA"
        )
        proteccion = analitica.evaluar_proteccion_perdidas("TEST")
        self.assertTrue(proteccion["requiere_confirmacion"] or proteccion["bloqueada"])
        self.assertEqual(proteccion["perdida_casa"], 10)

    def test_racha_de_perdidas_bloquea_recarga_y_recomendacion(self):
        database.registrar_recarga_bitacora("TEST", 30)
        for indice in range(3):
            database.registrar_apuesta_bitacora(
                "TEST", "Fútbol", "Liga", f"Evento {indice}", "BITACORA", "A",
                date.today(), 10, 2, "DEPOSITO", "PERDIDA"
            )
        proteccion = analitica.evaluar_proteccion_perdidas("TEST")
        recomendacion = analitica.recomendar_monto_bitacora("TEST")
        self.assertTrue(proteccion["bloqueada"])
        self.assertGreaterEqual(proteccion["racha_perdidas"], 3)
        self.assertEqual(recomendacion["monto"], 0)

    def test_recarga_aplica_condiciones_de_rollover_de_la_casa(self):
        registro = database.registrar_recarga_bitacora("TEST", 100, 20)
        casa = database.obtener_casa("TEST")
        self.assertEqual(registro["rollover_generado"], 140)
        self.assertEqual(casa["saldo_deposito"], 100)
        self.assertEqual(casa["saldo_bono"], 20)
        self.assertEqual(casa["rollover_pendiente"], 140)
        database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "Ganador", "A", date.today(),
            20, 2, "DEPOSITO", "PERDIDA"
        )
        casa = database.obtener_casa("TEST")
        self.assertEqual(casa["saldo_deposito"], 80)
        self.assertEqual(casa["rollover_pendiente"], 120)

    def test_configura_reglas_de_una_casa(self):
        database.actualizar_casa("TEST", 75, 2, 4, 1.5, "Fútbol,Vóley")
        casa = database.obtener_casa("TEST")
        self.assertEqual(casa["minimo_retiro"], 75)
        self.assertEqual(casa["rollover_deposito"], 2)
        self.assertEqual(casa["rollover_bono"], 4)
        self.assertEqual(casa["cuota_minima_rollover"], 1.5)
        self.assertEqual(casa["deportes"], "Fútbol,Vóley")

    def test_elimina_casa_sin_datos(self):
        database.registrar_casa_apuesta("VACIA", "Casa Vacía")
        self.assertTrue(database.eliminar_casa_apuesta("VACIA"))
        self.assertIsNone(database.obtener_casa("VACIA"))

    def test_no_elimina_casa_con_movimientos(self):
        database.registrar_recarga_bitacora("TEST", 10)
        with self.assertRaisesRegex(ValueError, "No se puede eliminar"):
            database.eliminar_casa_apuesta("TEST")

    def test_reinicia_datos_pero_conserva_casas_y_reglas(self):
        database.actualizar_casa("TEST", 75, 2, 3, 1.5, "Fútbol")
        database.registrar_recarga_bitacora("TEST", 100, 10)
        database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "Ganador", "A", date.today(),
            20, 2, "DEPOSITO", "GANADA"
        )
        resumen = database.reiniciar_datos_conservando_casas()
        casa = database.obtener_casa("TEST")
        self.assertGreater(resumen["movimientos_eliminados"], 0)
        self.assertEqual(database.obtener_apuestas(), [])
        self.assertEqual(database.obtener_historial_completo(), [])
        self.assertEqual(casa["saldo_deposito"], 0)
        self.assertEqual(casa["saldo_bono"], 0)
        self.assertEqual(casa["saldo_retirable"], 0)
        self.assertEqual(casa["rollover_pendiente"], 0)
        self.assertEqual(casa["minimo_retiro"], 75)
        self.assertEqual(casa["rollover_deposito"], 2)

    def test_resumen_recargas_no_retirable_y_perdidas_por_casa(self):
        database.registrar_recarga_bitacora("TEST", 100, 20)
        database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "Detalle", "A", date.today(),
            30, 2, "DEPOSITO", "PERDIDA"
        )
        resumen = analitica.resumen_financiero_casa("TEST")
        self.assertEqual(resumen["total_recargado"], 100)
        self.assertEqual(resumen["total_bonos"], 20)
        self.assertEqual(resumen["monto_no_retirable"], 90)
        self.assertEqual(resumen["perdida_acumulada"], 30)

    def test_calcula_retorno_potencial_antes_de_guardar(self):
        deposito = analitica.calcular_retorno_potencial(20, 2.5, "DEPOSITO")
        bono = analitica.calcular_retorno_potencial(20, 2.5, "BONO")
        self.assertEqual(deposito["retorno_total"], 50)
        self.assertEqual(deposito["ganancia_neta"], 30)
        self.assertEqual(deposito["retirable_estimado"], 50)
        self.assertEqual(bono["retirable_estimado"], 30)

    def test_pendiente_se_puede_eliminar_sin_modificar_saldo_rollover(self):
        database.registrar_recarga_bitacora("TEST", 100)
        apuesta_id = database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "Detalle", date.today(),
            20, 2, "DEPOSITO", "PENDIENTE"
        )
        casa = database.obtener_casa("TEST")
        self.assertEqual(casa["saldo_deposito"], 100)
        self.assertEqual(casa["rollover_pendiente"], 100)
        database.eliminar_apuesta_pendiente(apuesta_id)
        casa = database.obtener_casa("TEST")
        self.assertEqual(casa["saldo_deposito"], 100)
        self.assertEqual(casa["rollover_pendiente"], 100)
        self.assertEqual(database.obtener_apuestas("PENDIENTE"), [])

    def test_cash_out_registra_retorno_y_resultado_real(self):
        database.registrar_recarga_bitacora("TEST", 100)
        apuesta_id = database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "Detalle", date.today(),
            20, 2, "DEPOSITO", "PENDIENTE"
        )
        database.resolver_apuesta(apuesta_id, "CASH_OUT", 12)
        apuesta = next(a for a in database.obtener_apuestas() if a["id"] == apuesta_id)
        self.assertEqual(apuesta["estado"], "CASH_OUT")
        self.assertEqual(apuesta["retorno"], 12)
        self.assertEqual(database.obtener_casa("TEST")["saldo_retirable"], 12)
        _, metricas = analitica.analizar_rendimiento_psicologico()
        self.assertEqual(metricas["balance_neto_real"], -8)
        resumen = metricas["por_casa"].iloc[0]
        self.assertEqual(resumen["cashout_perdida"], 1)
        self.assertEqual(resumen["cashout_neutros"], 0)

    def test_cash_out_igual_al_monto_es_neutral(self):
        database.registrar_recarga_bitacora("TEST", 100)
        apuesta_id = database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "Detalle", date.today(),
            20, 2, "SALDO", "PENDIENTE"
        )
        database.resolver_apuesta(apuesta_id, "CASH_OUT", 20)
        _, metricas = analitica.analizar_rendimiento_psicologico()
        resumen = metricas["por_casa"].iloc[0]
        self.assertEqual(metricas["resultado_apuestas"], 0)
        self.assertEqual(resumen["cashout_neutros"], 1)
        self.assertEqual(resumen["cashout_perdida"], 0)

    def test_bono_no_infla_balance_de_dinero_propio(self):
        database.registrar_recarga_bitacora("TEST", 20, 80)
        _, metricas = analitica.analizar_rendimiento_psicologico()
        # Se necesita una apuesta liquidada para activar el análisis.
        if not isinstance(metricas, dict):
            database.registrar_apuesta_bitacora(
                "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "A",
                date.today(), 1, 2, "BONO", "PERDIDA"
            )
            _, metricas = analitica.analizar_rendimiento_psicologico()
        self.assertEqual(metricas["saldo_bonos"], 79)
        self.assertEqual(metricas["balance_neto_real"], 0)

    def test_diagnostico_retiro_distingue_minimo_y_rollover(self):
        casa = database.obtener_casa("TEST")
        casa.update({"saldo_retirable": 41, "saldo_deposito": 0,
                     "saldo_bono": 0, "rollover_pendiente": 0, "minimo_retiro": 50})
        diagnostico = database.diagnosticar_ciclo(casa)
        self.assertEqual(diagnostico["estado"], "MINIMO_NO_ALCANZADO")
        self.assertEqual(diagnostico["faltante_retiro"], 9)
        casa["rollover_pendiente"] = 10
        self.assertEqual(database.diagnosticar_ciclo(casa)["estado"], "ROLLOVER_PENDIENTE")

    def test_auditoria_detecta_apuesta_sin_capital_conciliado(self):
        database.registrar_recarga_bitacora("TEST", 20)
        apuesta_id = database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "A",
            date.today(), 20, 2, "DEPOSITO", "PERDIDA"
        )
        with database.obtener_conexion() as conn:
            conn.execute("UPDATE apuestas SET monto_conciliado=0 WHERE id=?", (apuesta_id,))
        auditoria = analitica.auditar_conciliacion_historial()
        self.assertFalse(auditoria["confiable_saldos"])
        self.assertEqual(auditoria["monto_sin_conciliar"], 20)

    def test_origen_saldo_combina_deposito_y_retirable_sin_usar_bono(self):
        database.registrar_recarga_bitacora("TEST", 10, 50)
        with database.obtener_conexion() as conn:
            conn.execute("UPDATE casas_apuestas SET saldo_retirable=15 WHERE id='TEST'")
        apuesta_id = database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "A",
            date.today(), 20, 2, "SALDO", "PERDIDA"
        )
        casa = database.obtener_casa("TEST")
        apuesta = next(a for a in database.obtener_apuestas() if a["id"] == apuesta_id)
        self.assertEqual(apuesta["monto_conciliado"], 20)
        self.assertEqual(casa["saldo_deposito"], 0)
        self.assertEqual(casa["saldo_retirable"], 5)
        self.assertEqual(casa["saldo_bono"], 50)

    def test_cotejo_advierte_si_falta_registrar_saldo(self):
        cotejo = analitica.verificar_saldo_para_apuesta("TEST", "SALDO", 20)
        self.assertFalse(cotejo["suficiente"])
        self.assertEqual(cotejo["faltante"], 20)
        self.assertIn("Verifica si olvidaste registrar", cotejo["mensaje"])

    def test_cotejo_separa_saldo_de_bono(self):
        database.registrar_recarga_bitacora("TEST", 10, 30)
        saldo = analitica.verificar_saldo_para_apuesta("TEST", "SALDO", 20)
        bono = analitica.verificar_saldo_para_apuesta("TEST", "BONO", 20)
        self.assertFalse(saldo["suficiente"])
        self.assertTrue(bono["suficiente"])
        self.assertEqual(saldo["disponible"], 10)
        self.assertEqual(bono["disponible"], 30)

    def test_dashboard_resume_exposicion_pendiente(self):
        database.registrar_recarga_bitacora("TEST", 25)
        database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "Detalle", date.today(),
            25, 3, "DEPOSITO", "PENDIENTE"
        )
        resumen = analitica.resumen_apuestas_pendientes()
        self.assertEqual(resumen["cantidad"], 1)
        self.assertEqual(resumen["capital_en_riesgo"], 25)
        self.assertEqual(resumen["retorno_potencial"], 75)
        self.assertEqual(resumen["ganancia_potencial"], 50)

    def test_pendiente_reserva_saldo_para_evitar_sobreapostar(self):
        database.registrar_recarga_bitacora("TEST", 30)
        database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "A",
            date.today(), 20, 2, "SALDO", "PENDIENTE"
        )
        cotejo = analitica.verificar_saldo_para_apuesta("TEST", "SALDO", 20)
        self.assertEqual(cotejo["disponible"], 10)
        self.assertEqual(cotejo["reservado_pendientes"], 20)
        with self.assertRaisesRegex(ValueError, "Saldo insuficiente"):
            database.registrar_apuesta_bitacora(
                "TEST", "Fútbol", "Liga", "C vs D", "BITACORA", "C",
                date.today(), 20, 2, "SALDO", "PENDIENTE"
            )

    def test_perdida_pendiente_se_descuenta_al_finalizar(self):
        database.registrar_recarga_bitacora("TEST", 100)
        apuesta_id = database.registrar_apuesta_bitacora(
            "TEST", "Fútbol", "Liga", "A vs B", "BITACORA", "Detalle", date.today(),
            20, 2, "DEPOSITO", "PENDIENTE"
        )
        self.assertEqual(database.obtener_casa("TEST")["saldo_deposito"], 100)
        liquidacion = database.resolver_apuesta(apuesta_id, "PERDIDA")
        self.assertEqual(database.obtener_casa("TEST")["saldo_deposito"], 80)
        self.assertEqual(liquidacion["descontado_al_finalizar"], 20)
        self.assertEqual(liquidacion["saldo_para_jugar"], 80)


if __name__ == "__main__":
    unittest.main()
