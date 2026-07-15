"""Adaptador de mysql.connector para la interfaz interna del repositorio."""

from models.conexion_mysql import crear_conexion_mysql


class Fila(dict):
    def __getitem__(self, clave):
        return tuple(self.values())[clave] if isinstance(clave, int) else super().__getitem__(clave)


def _sql_mysql(sql):
    return sql.replace("?", "%s").replace(
        "datetime(fecha)>=datetime(%s)", "fecha >= %s"
    )


class CursorMySQL:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def execute(self, sql, parametros=()):
        self._cursor.execute(_sql_mysql(sql), parametros)
        return self

    def executemany(self, sql, parametros):
        self._cursor.executemany(_sql_mysql(sql), parametros)
        return self

    def fetchone(self):
        fila = self._cursor.fetchone()
        return Fila(fila) if fila is not None else None

    def fetchall(self):
        return [Fila(fila) for fila in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())

    def close(self):
        self._cursor.close()


class ConexionMySQL:
    def __init__(self, base_datos=None):
        self._conexion = crear_conexion_mysql(base_datos)
        self._cursores = []

    def cursor(self):
        cursor = CursorMySQL(self._conexion.cursor(dictionary=True, buffered=True))
        self._cursores.append(cursor)
        return cursor

    def execute(self, sql, parametros=()):
        return self.cursor().execute(sql, parametros)

    def executemany(self, sql, parametros):
        return self.cursor().executemany(sql, parametros)

    def commit(self):
        self._conexion.commit()

    def rollback(self):
        self._conexion.rollback()

    def close(self):
        for cursor in self._cursores:
            try:
                cursor.close()
            except Exception:
                pass
        self._cursores.clear()
        self._conexion.close()
