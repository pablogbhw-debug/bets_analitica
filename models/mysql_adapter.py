"""Adaptador de mysql.connector para la interfaz interna del repositorio."""

from models.conexion_mysql import crear_conexion_mysql


class Fila(dict):
    def __getitem__(self, clave):
        """Permite acceder a una columna de la fila mediante índice o nombre."""
        return tuple(self.values())[clave] if isinstance(clave, int) else super().__getitem__(clave)


def _sql_mysql(sql):
    """Adapta los marcadores de parámetros SQL al formato requerido por MySQL."""
    return sql.replace("?", "%s").replace(
        "datetime(fecha)>=datetime(%s)", "fecha >= %s"
    )


class CursorMySQL:
    def __init__(self, cursor):
        """Inicializa la instancia con los datos necesarios para su funcionamiento."""
        self._cursor = cursor

    @property
    def lastrowid(self):
        """Devuelve el identificador generado por la última inserción."""
        return self._cursor.lastrowid

    def execute(self, sql, parametros=()):
        """Ejecuta una sentencia SQL con sus parámetros."""
        self._cursor.execute(_sql_mysql(sql), parametros)
        return self

    def executemany(self, sql, parametros):
        """Ejecuta una misma sentencia SQL para múltiples grupos de parámetros."""
        self._cursor.executemany(_sql_mysql(sql), parametros)
        return self

    def fetchone(self):
        """Devuelve la siguiente fila del resultado como un objeto compatible."""
        fila = self._cursor.fetchone()
        return Fila(fila) if fila is not None else None

    def fetchall(self):
        """Devuelve todas las filas restantes del resultado."""
        return [Fila(fila) for fila in self._cursor.fetchall()]

    def __iter__(self):
        """Permite recorrer directamente las filas devueltas por el cursor."""
        return iter(self.fetchall())

    def close(self):
        """Cierra el cursor o la conexión subyacente."""
        self._cursor.close()


class ConexionMySQL:
    def __init__(self, base_datos=None):
        """Inicializa la instancia con los datos necesarios para su funcionamiento."""
        self._conexion = crear_conexion_mysql(base_datos)
        self._cursores = []

    def cursor(self):
        """Crea y devuelve un cursor adaptado para ejecutar consultas."""
        cursor = CursorMySQL(self._conexion.cursor(dictionary=True, buffered=True))
        self._cursores.append(cursor)
        return cursor

    def execute(self, sql, parametros=()):
        """Ejecuta una sentencia SQL con sus parámetros."""
        return self.cursor().execute(sql, parametros)

    def executemany(self, sql, parametros):
        """Ejecuta una misma sentencia SQL para múltiples grupos de parámetros."""
        return self.cursor().executemany(sql, parametros)

    def commit(self):
        """Confirma de forma permanente los cambios de la transacción."""
        self._conexion.commit()

    def rollback(self):
        """Revierte los cambios pendientes de la transacción."""
        self._conexion.rollback()

    def close(self):
        """Cierra el cursor o la conexión subyacente."""
        for cursor in self._cursores:
            try:
                cursor.close()
            except Exception:
                pass
        self._cursores.clear()
        self._conexion.close()
