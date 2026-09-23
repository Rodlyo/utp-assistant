-- UTP Assistant · Esquema completo de la base de datos
-- Crea la base de datos y todas las tablas.
-- Importar desde phpMyAdmin (pestaña "Importar") si hiciera falta.
-- La aplicación también las crea automáticamente al arrancar.

CREATE DATABASE IF NOT EXISTS assistantutpdb
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE assistantutpdb;

-- Usuarios del sistema
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(150) NOT NULL UNIQUE,      -- siempre en minúsculas y sin espacios
    password_hash VARCHAR(128) NOT NULL,      -- PBKDF2-HMAC-SHA256 en hexadecimal
    salt VARCHAR(64) NOT NULL,
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rol ENUM('usuario','administrador') NOT NULL DEFAULT 'usuario',
    activo TINYINT(1) NOT NULL DEFAULT 1,
    ultimo_acceso DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Migración: añade las columnas de roles si faltan.
-- ADD COLUMN IF NOT EXISTS es sintaxis de MariaDB (la que trae XAMPP).
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol ENUM('usuario','administrador') NOT NULL DEFAULT 'usuario';
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo TINYINT(1) NOT NULL DEFAULT 1;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_acceso DATETIME NULL;

-- CRM interno
CREATE TABLE IF NOT EXISTS contactos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    empresa VARCHAR(150) NULL,
    correo VARCHAR(150) NULL,
    telefono VARCHAR(30) NULL,
    cargo VARCHAR(100) NULL,
    estado ENUM('prospecto','cliente','inactivo') NOT NULL DEFAULT 'prospecto',
    notas TEXT NULL,
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_contactos_usuario_correo (usuario_id, correo),
    CONSTRAINT fk_contactos_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Correos recibidos de clientes
CREATE TABLE IF NOT EXISTS correos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    contacto_id INT NULL,
    remitente_nombre VARCHAR(100) NULL,
    remitente_correo VARCHAR(150) NULL,
    asunto VARCHAR(255) NULL,
    cuerpo TEXT NOT NULL,
    resumen TEXT NULL,
    estado ENUM('pendiente','procesado','error') NOT NULL DEFAULT 'pendiente',
    fecha_recepcion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_procesado DATETIME NULL,
    CONSTRAINT fk_correos_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_correos_contacto FOREIGN KEY (contacto_id)
        REFERENCES contactos(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Gestor de tareas interno
CREATE TABLE IF NOT EXISTS tareas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    correo_id INT NULL,
    contacto_id INT NULL,
    titulo VARCHAR(200) NOT NULL,
    descripcion TEXT NULL,
    prioridad ENUM('baja','media','alta','urgente') NOT NULL DEFAULT 'media',
    estado ENUM('pendiente','en_progreso','completada') NOT NULL DEFAULT 'pendiente',
    fecha_limite DATE NULL,
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tareas_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_tareas_correo FOREIGN KEY (correo_id)
        REFERENCES correos(id) ON DELETE SET NULL,
    CONSTRAINT fk_tareas_contacto FOREIGN KEY (contacto_id)
        REFERENCES contactos(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Calendario propio (reuniones)
CREATE TABLE IF NOT EXISTS eventos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    correo_id INT NULL,
    contacto_id INT NULL,
    titulo VARCHAR(200) NOT NULL,
    descripcion TEXT NULL,
    fecha_inicio DATETIME NOT NULL,
    fecha_fin DATETIME NOT NULL,
    modalidad ENUM('virtual','presencial') NOT NULL DEFAULT 'virtual',
    estado ENUM('programada','realizada','cancelada') NOT NULL DEFAULT 'programada',
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_eventos_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_eventos_correo FOREIGN KEY (correo_id)
        REFERENCES correos(id) ON DELETE SET NULL,
    CONSTRAINT fk_eventos_contacto FOREIGN KEY (contacto_id)
        REFERENCES contactos(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Ejecuciones del asistente (ciclo de un Run)
CREATE TABLE IF NOT EXISTS ejecuciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    correo_id INT NOT NULL,
    usuario_id INT NOT NULL,
    estado ENUM('en_cola','en_progreso','requiere_accion','completado','fallido','cancelado')
        NOT NULL DEFAULT 'en_cola',
    iteraciones INT NOT NULL DEFAULT 0,
    modelo VARCHAR(100) NOT NULL,
    error TEXT NULL,
    fecha_inicio DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_fin DATETIME NULL,
    CONSTRAINT fk_ejecuciones_correo FOREIGN KEY (correo_id)
        REFERENCES correos(id) ON DELETE CASCADE,
    CONSTRAINT fk_ejecuciones_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Pasos de cada ejecución (trazabilidad y auditoría; argumentos y resultado en JSON)
CREATE TABLE IF NOT EXISTS pasos_ejecucion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ejecucion_id INT NOT NULL,
    tipo ENUM('llamada_modelo','funcion_propuesta','funcion_ejecutada','funcion_rechazada',
              'error_validacion','respuesta_final') NOT NULL,
    nombre_funcion VARCHAR(100) NULL,
    argumentos TEXT NULL,
    resultado TEXT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pasos_ejecucion FOREIGN KEY (ejecucion_id)
        REFERENCES ejecuciones(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Usuarios por defecto: admin / admin123 (administrador) y usuario / usuario123 (usuario).
-- Se inicia sesión con el correo. Contraseñas guardadas con PBKDF2-HMAC-SHA256
-- (200 000 iteraciones) y salt aleatorio, igual que las cuentas creadas desde la app.
-- INSERT IGNORE: si el correo ya existe, no se modifica.
INSERT IGNORE INTO usuarios (nombre, correo, password_hash, salt, rol) VALUES
    ('admin', 'admin@utpconsult.com',
     '8e518ac658de9d86e0b17352800c47eb243a6b285a37afd2a8e1947fa76e4ba8',
     'dbfb8b52bb6666af48622efa3058a388', 'administrador'),
    ('usuario', 'usuario@utpconsult.com',
     '950cf0f5114e871a220ff128d389d2bb55cc73ad583af5b902d920e210c3c4c2',
     '95d642b1abdc16c90a8ebac2d453b0ac', 'usuario');

-- Primer administrador: si hay usuarios pero ninguno es administrador,
-- se promueve al de id más bajo (la app hace lo mismo en init_db()).
UPDATE usuarios SET rol = 'administrador'
WHERE id = (SELECT id FROM (SELECT MIN(id) AS id FROM usuarios) AS primero)
  AND NOT EXISTS (
      SELECT 1 FROM (SELECT id FROM usuarios WHERE rol = 'administrador') AS admins
  );
