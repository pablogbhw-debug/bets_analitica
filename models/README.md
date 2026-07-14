# Capa Modelo

Responsabilidad MVC: representar el dominio y encapsular la persistencia, sin importar Streamlit.

- `entidades.py`: evidencia de POO. `RegistroApuesta` hereda de `Transaccion` mediante `super()`.
- `conexion_mysql.py`: conexión transaccional MySQL configurable por variables de entorno, con `commit`, `rollback` y cierre garantizado.
- `database.py`: fachada compatible que reúne los repositorios especializados.
- `repositorios/conexion.py`: conexión, fechas e inicialización del esquema.
- `repositorios/casas.py`: catálogo, reglas y saldos por casa.
- `repositorios/configuracion.py`: límites, pausas y configuración de control.
- `repositorios/movimientos.py`: recargas, bonos, retiros y movimientos.
- `repositorios/apuestas.py`: registro, edición y liquidación de apuestas.
- `repositorios/historial.py`: historial, rollover y diagnóstico financiero.
- `usuarios.py`: alta y consulta de cuentas con restricción única sobre el correo.
- `schema_mysql.sql`: definición relacional de las entidades persistentes para MySQL.

Mapeo del sílabo: clases, herencia, constructores, encapsulamiento, tipos de datos, relaciones, claves primarias y foráneas, excepciones y persistencia transaccional.

Variables MySQL: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` y `MYSQL_DATABASE`.
