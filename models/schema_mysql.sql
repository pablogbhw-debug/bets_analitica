CREATE DATABASE IF NOT EXISTS apuestas_analitica
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE apuestas_analitica;

CREATE TABLE IF NOT EXISTS usuarios (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  correo VARCHAR(254) NOT NULL UNIQUE,
  password_hash VARCHAR(60) NOT NULL,
  fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  activo BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sesiones_usuario (
  token_hash CHAR(64) PRIMARY KEY,
  usuario_id BIGINT NOT NULL,
  creada TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expira DATETIME NOT NULL,
  CONSTRAINT fk_sesion_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS casas_apuestas (
  id VARCHAR(40) PRIMARY KEY,
  nombre_casa VARCHAR(120) NOT NULL,
  saldo_deposito DECIMAL(12,2) NOT NULL DEFAULT 0,
  saldo_bono DECIMAL(12,2) NOT NULL DEFAULT 0,
  saldo_retirable DECIMAL(12,2) NOT NULL DEFAULT 0,
  rollover_pendiente DECIMAL(12,2) NOT NULL DEFAULT 0,
  minimo_retiro DECIMAL(12,2) NOT NULL DEFAULT 50,
  rollover_deposito DECIMAL(8,2) NOT NULL DEFAULT 1,
  rollover_bono DECIMAL(8,2) NOT NULL DEFAULT 1,
  cuota_minima_rollover DECIMAL(8,2) NOT NULL DEFAULT 1.01,
  deportes TEXT NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS apuestas (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  id_casa VARCHAR(40) NOT NULL,
  deporte VARCHAR(80) NOT NULL,
  liga VARCHAR(120) NOT NULL,
  evento VARCHAR(255) NOT NULL,
  mercado VARCHAR(120) NOT NULL,
  seleccion VARCHAR(255) NOT NULL,
  fecha_evento DATE NOT NULL,
  monto DECIMAL(12,2) NOT NULL,
  cuota DECIMAL(8,2) NOT NULL,
  tipo_saldo VARCHAR(20) NOT NULL,
  estado VARCHAR(20) NOT NULL,
  retorno DECIMAL(12,2) NOT NULL DEFAULT 0,
  monto_conciliado DECIMAL(12,2) NOT NULL DEFAULT 0,
  rollover_liberado DECIMAL(12,2) NOT NULL DEFAULT 0,
  fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_resolucion TIMESTAMP NULL,
  CONSTRAINT fk_apuesta_casa FOREIGN KEY (id_casa) REFERENCES casas_apuestas(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS historial_transacciones (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  id_casa VARCHAR(40) NOT NULL,
  apuesta_id BIGINT NULL,
  tipo_movimiento VARCHAR(40) NOT NULL,
  monto DECIMAL(12,2) NOT NULL,
  cuota DECIMAL(8,2) NOT NULL DEFAULT 1,
  tipo_saldo_usado VARCHAR(20) NOT NULL,
  fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_historial_casa FOREIGN KEY (id_casa) REFERENCES casas_apuestas(id),
  CONSTRAINT fk_historial_apuesta FOREIGN KEY (apuesta_id) REFERENCES apuestas(id)
) ENGINE=InnoDB;
