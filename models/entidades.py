def normalizar_campos_texto(campos):
    """Normaliza una lista usando un while finito y verificable."""
    normalizados = []
    indice = 0
    while indice < len(campos):
        normalizados.append(str(campos[indice]).strip())
        indice += 1
    return normalizados


class Transaccion:
    """Clase padre de los movimientos auditables del portafolio."""
    def __init__(self, id_casa: str, monto: float, tipo_saldo: str):
        """Inicializa la instancia con los datos necesarios para su funcionamiento."""
        self.id_casa = id_casa.upper().strip()
        self.monto = float(monto)
        self.tipo_saldo = tipo_saldo.upper().strip()
        if not self.id_casa or self.monto <= 0:
            raise ValueError("La casa es obligatoria y el monto debe ser positivo.")


class RegistroApuesta(Transaccion):
    """Clase hija especializada en una inversión deportiva."""
    def __init__(self, id_casa, monto, tipo_saldo, cuota, deporte, liga, evento,
                 mercado, seleccion, fecha_evento):
        """Inicializa la instancia con los datos necesarios para su funcionamiento."""
        super().__init__(id_casa, monto, tipo_saldo)
        self.cuota = float(cuota)
        campos = normalizar_campos_texto([deporte, liga, evento, mercado, seleccion])
        self.deporte, self.liga, self.evento, self.mercado, self.seleccion = campos
        self.fecha_evento = str(fecha_evento)
        if self.tipo_saldo not in {"SALDO", "DEPOSITO", "BONO", "RETIRABLE"}:
            raise ValueError("Billetera no válida.")
        if self.cuota <= 1 or not all((self.deporte, self.liga, self.evento, self.mercado, self.seleccion)):
            raise ValueError("Complete la información deportiva y use una cuota mayor que 1.00.")
