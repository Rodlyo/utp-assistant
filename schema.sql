-- UTP Assistant · Fase 1
-- Crea la base de datos y la tabla de usuarios.
-- Importar desde phpMyAdmin (pestaña "Importar") si hiciera falta.
-- La aplicación también la crea automáticamente al arrancar.

CREATE DATABASE IF NOT EXISTS assistantutpdb
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE assistantutpdb;

CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(150) NOT NULL UNIQUE,      -- siempre en minúsculas y sin espacios
    password_hash VARCHAR(128) NOT NULL,      -- PBKDF2-HMAC-SHA256 en hexadecimal
    salt VARCHAR(64) NOT NULL,
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
