# Capa Controlador

Responsabilidad MVC: recibir acciones de las vistas, aplicar reglas del negocio y coordinar el Modelo.

- `transacciones.py`: puerta de entrada para recargas, apuestas, liquidaciones, retiros, saldos y rollover.
- `autenticacion.py`: normalización del correo, validaciones y hashing/verificación bcrypt.
- `analitica_comun.py`: preparación del historial financiero.
- `analitica_resumen.py`: ROI, drawdown, rachas, concentración y nivel de riesgo.
- `analitica_apuesta.py`: retorno potencial, saldo disponible y monto recomendado.
- `analitica_recarga.py`: protección ante pérdidas y límites de recarga.
- `analitica_pendientes.py`: capital expuesto y ganancia potencial pendiente.

Mapeo del sílabo: funciones, condicionales, bucles, listas, diccionarios, validaciones, manejo de excepciones, Pandas y vectorización NumPy (`sum`, `mean`, máscaras, `cumsum`, agrupación y drawdown).

Las reglas conservadas incluyen billeteras separadas, rollover, cuota mínima, retiro mínimo, apuestas pendientes, anulaciones, cash out, bono, límites informativos y alertas de inversión.
