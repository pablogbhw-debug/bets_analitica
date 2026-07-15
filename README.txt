OBJETIVO
Funcionar como una bitácora para una o mas casas de apuesatas. El usuario registra recargas,
apuestas terminadas y retiros; el sistema calcula indicadores y muestra alertas. No predice
resultados ni garantiza ganancias.

ARQUITECTURA MVC
1. models/: entidades, herencia, conexión MySQL, esquema relacional y persistencia.
2. controllers/: casos de uso, validaciones, rollover y analítica Pandas/NumPy.
3. views/: formularios, tablas, métricas, gráficos y alertas de Streamlit.
4. app.py: composición e inicio; no contiene reglas financieras.
5. test_sistema.py: pruebas de integración que importan directamente models/ y controllers/.

MySQL carga MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD y MYSQL_DATABASE desde `.env`.
MySQL es el único motor de persistencia de la aplicación.
Todas las entidades financieras incluyen `usuario_id` y llaves foráneas hacia `usuarios`.
Cada consulta filtra el usuario autenticado; casas, configuración, apuestas, movimientos,
saldos y analítica no se comparten entre cuentas.

ESTRUCTURA Y FUNCIONALIDADES
- Estructurado: flujo de módulos, formularios, if/elif/else y bucles for.
- Funcional: funciones de transformación, filtros y cálculos en controllers/.
- POO: herencia, __init__, self y super() en models/entidades.py.
- Entrada y tipos: formularios con cast a str, float, int y bool.
- Cadenas: strip(), upper(), split() y normalización de identificadores.
- Repetición: for para colecciones y while finito en normalizar_campos_texto().
- Estructuras: listas de alertas, tuplas SQL/estados y diccionarios de métricas.
- Pandas: carga, limpieza, fechas, filtros, agrupaciones y columnas derivadas.
- NumPy: sumas, medias, mínimos, máximos, máscaras, cumsum y drawdown.
- MySQL: conexión configurable, InnoDB, llaves primarias/foráneas, commit y rollback.

FLUJO PRINCIPAL
- Registro de usuario con correo único y contraseña protegida mediante bcrypt.
- Inicio y cierre de sesión; el resto de la aplicación requiere autenticación.
- La sesión se restaura al recargar la página mediante una credencial temporal revocable.
- Dashboard con estadísticas, alertas, sugerencia de recarga, máximo por jugada,
  disponibilidad de retiros y movimientos recientes.
- Tarjetas grandes por casa para decidir retiros según saldo, mínimo, faltante y rollover.
- Registrar recarga y bono aplicando el rollover configurado de cada casa.
- Mostrar por casa el total recargado, bono, monto no retirable y pérdida acumulada.
- Configurar o agregar casas: retiro mínimo, rollover, cuota mínima y deportes.
- Eliminar casas únicamente cuando no tengan datos, saldos ni rollover asociados.
- Reiniciar toda la actividad con doble confirmación, conservando las casas y sus reglas.
- Registrar apuesta con su resultado.
- Registrar retiro.
- Consultar historial.

REGLAS PRINCIPALES
- Tres billeteras por casa: depósito, bono y retirable.
- La bitácora permite GANADA, PERDIDA o ANULADA sin exigir un depósito previo.
- El formulario usa un único campo "Detalle de la apuesta" para apuestas simples o combinadas.
- Antes de guardar muestra retorno teórico, ganancia neta, retirable estimado y pérdida máxima.
- Antes de apostar muestra únicamente saldo para jugar, máximo recomendado y riesgo actual.
- Permite registrar PENDIENTE, medir su exposición y completarla como ganada, perdida,
  anulada o CASH_OUT con el monto realmente recibido.
- Una pendiente creada por error puede eliminarse con confirmación y restitución conciliada.
- Una pendiente no altera saldos; el stake se descuenta al finalizarla, excepto si se anula.
- Una apuesta anulada vuelve a su billetera original.
- Una ganancia con bono convierte solo monto * (cuota - 1) en retirable.
- El retiro exige saldo suficiente, mínimo configurado y rollover igual a cero.
- Alertas y límites de apuestas son informativos; no bloquean el registro.
- El máximo sugerido usa entre 1% y 5% del depósito más bono según el riesgo.

ALERTAS
- Ilusión de ganancia: tasa de acierto alta con balance negativo.
- ROI y drawdown peligrosos.
- Capital restringido por rollover.
- Persecución de pérdidas por aumento de monto.
- Racha de pérdidas.
- Bono que camufla flujo de caja negativo.
- Concentración del portafolio en una sola casa.

INSTALACIÓN Y EJECUCIÓN
1. pip install -r requirements.txt
2. Configurar las credenciales MySQL en el archivo `.env`.
3. El usuario indicado debe poder crear la base si todavía no existe.
4. streamlit run app.py

PRUEBAS
Configurar MYSQL_TEST_DATABASE con una base exclusiva para pruebas y ejecutar:
python -m unittest -v

Las pruebas verifican saldos, apuestas pendientes, anulaciones, bonos, retiros, rollover,
alertas de ilusión y creación de los tres activos predeterminados.

ESTRUCTURA VARIABLE DE ENTORNO
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=usuario_mysql
MYSQL_PASSWORD=contraseña_mysql
MYSQL_DATABASE=nombre_base_datos
MYSQL_POOL_SIZE=8
