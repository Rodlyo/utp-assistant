# Base de datos MySQL (XAMPP): conexión, tablas, migraciones y consultas.
import re
from datetime import datetime, timedelta

import pymysql
import streamlit as st

# --- Conexión ---

# Error de configuración o conexión (lo muestra utp_assistant.py).
class ErrorBaseDatos(Exception):
    pass


MENSAJE_ERROR_MYSQL = (
    "No se pudo conectar a MySQL. Verifica que el servicio MySQL esté "
    "iniciado en el panel de XAMPP."
)


# Lee la sección [mysql] de secrets.toml.
def _config_mysql():
    try:
        return dict(st.secrets["mysql"])
    except Exception:
        raise ErrorBaseDatos(
            "Falta la sección [mysql] en .streamlit/secrets.toml. "
            "Copia .streamlit/secrets.toml.example y ajusta los valores."
        ) from None


# Nombre de la BD validado (letras, números y _).
def _nombre_base_datos(config):
    nombre = str(config.get("database", "assistantutpdb"))
    if not re.fullmatch(r"[A-Za-z0-9_]+", nombre):
        raise ErrorBaseDatos("El nombre de la base de datos en secrets.toml no es válido.")
    return nombre


# Abre una conexión PyMySQL; si falla, lanza ErrorBaseDatos.
def _conectar(incluir_bd=True):
    config = _config_mysql()
    parametros = {
        "host": config.get("host", "localhost"),
        "port": int(config.get("port", 3306)),
        "user": config.get("user", "root"),
        "password": config.get("password", ""),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "connect_timeout": 5,
    }
    if incluir_bd:
        parametros["database"] = _nombre_base_datos(config)
    try:
        return pymysql.connect(**parametros)
    except pymysql.MySQLError:
        raise ErrorBaseDatos(MENSAJE_ERROR_MYSQL) from None


# Conexión a la base de datos de la aplicación.
def get_connection():
    return _conectar(incluir_bd=True)


# --- Creación de tablas y migraciones ---

# Tablas en orden de creación (respetando las claves foráneas).
TABLAS_SQL = [
    """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL,
        correo VARCHAR(150) NOT NULL UNIQUE,
        password_hash VARCHAR(128) NOT NULL,
        salt VARCHAR(64) NOT NULL,
        fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        rol ENUM('usuario','administrador') NOT NULL DEFAULT 'usuario',
        activo TINYINT(1) NOT NULL DEFAULT 1,
        ultimo_acceso DATETIME NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
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
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
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
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
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
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
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
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


# Columnas de roles que se añaden si faltan (constantes internas).
COLUMNAS_ROLES_USUARIOS = [
    ("rol", "ENUM('usuario','administrador') NOT NULL DEFAULT 'usuario'"),
    ("activo", "TINYINT(1) NOT NULL DEFAULT 1"),
    ("ultimo_acceso", "DATETIME NULL"),
]


# Añade las columnas de roles que falten (compatible con MariaDB).
def _migrar_columnas_usuarios(cursor):
    for columna, definicion in COLUMNAS_ROLES_USUARIOS:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'usuarios' "
            "AND COLUMN_NAME = %s",
            (columna,),
        )
        if cursor.fetchone()["total"] == 0:
            cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {columna} {definicion}")


# Sin administradores: promueve al usuario de id más bajo.
def _asegurar_administrador(cursor):
    cursor.execute(
        "SELECT "
        "  (SELECT COUNT(*) FROM usuarios) AS total, "
        "  (SELECT COUNT(*) FROM usuarios WHERE rol = 'administrador') AS admins, "
        "  (SELECT MIN(id) FROM usuarios) AS primero"
    )
    fila = cursor.fetchone()
    if fila["total"] > 0 and fila["admins"] == 0:
        cursor.execute(
            "UPDATE usuarios SET rol = 'administrador' WHERE id = %s", (fila["primero"],)
        )


# Crea la BD y las tablas si no existen, y aplica migraciones.
def init_db():
    nombre_bd = _nombre_base_datos(_config_mysql())

    # 1) Crear la base de datos (conexión sin base de datos seleccionada).
    conexion = _conectar(incluir_bd=False)
    try:
        with conexion.cursor() as cursor:
            # Nombre validado con regex (los identificadores no admiten %s).
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{nombre_bd}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conexion.commit()
    finally:
        conexion.close()

    # 2) Tablas en orden por las claves foráneas.
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            for sentencia in TABLAS_SQL:
                cursor.execute(sentencia)
            # 3) Migración de columnas y primer administrador.
            _migrar_columnas_usuarios(cursor)
            _asegurar_administrador(cursor)
        conexion.commit()
    finally:
        conexion.close()


# --- Consultas del dashboard ---
# SELECT parametrizado: una fila (uno=True) o todas.
def _consultar(sql, parametros, uno=False):
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchone() if uno else cursor.fetchall()
    finally:
        conexion.close()


# Ejecuta un SELECT COUNT(*) AS total y devuelve el número.
def _contar(sql, parametros):
    return int(_consultar(sql, parametros, uno=True)["total"])


# Filtro por alcance (alias siempre literal interno).
def _filtro_alcance(alcance_usuario_id, alias):
    if alcance_usuario_id is None:
        return "1 = 1", ()
    return f"{alias}.usuario_id = %s", (int(alcance_usuario_id),)


# COUNT(*) con filtro de alcance (SQL literal interno).
def _contar_en(tabla_alias, alcance_usuario_id, condicion_extra="1 = 1"):
    condicion, params = _filtro_alcance(alcance_usuario_id, tabla_alias.split()[1])
    return _contar(
        f"SELECT COUNT(*) AS total FROM {tabla_alias} WHERE {condicion} AND {condicion_extra}",
        params,
    )


def contar_correos_procesados(alcance_usuario_id):
    return _contar_en("correos co", alcance_usuario_id, "co.estado = 'procesado'")


def contar_tareas_pendientes(alcance_usuario_id):
    return _contar_en("tareas t", alcance_usuario_id, "t.estado <> 'completada'")


def contar_reuniones_proximas(alcance_usuario_id):
    return _contar_en(
        "eventos e", alcance_usuario_id, "e.estado = 'programada' AND e.fecha_inicio >= NOW()"
    )


def contar_contactos(alcance_usuario_id):
    return _contar_en("contactos c", alcance_usuario_id)


# Próximas reuniones con contacto y responsable.
def obtener_proximas_reuniones(alcance_usuario_id, limite=5):
    condicion, params = _filtro_alcance(alcance_usuario_id, "e")
    return _consultar(
        "SELECT e.id, e.titulo, e.fecha_inicio, e.fecha_fin, e.modalidad, "
        "       c.nombre AS contacto_nombre, c.empresa AS contacto_empresa, "
        "       u.nombre AS responsable "
        "FROM eventos e "
        "JOIN usuarios u ON u.id = e.usuario_id "
        "LEFT JOIN contactos c ON c.id = e.contacto_id AND c.usuario_id = e.usuario_id "
        f"WHERE {condicion} AND e.estado = 'programada' AND e.fecha_inicio >= NOW() "
        "ORDER BY e.fecha_inicio ASC "
        "LIMIT %s",
        params + (int(limite),),
    )


# Tareas no completadas, por prioridad y fecha límite.
def obtener_tareas_pendientes(alcance_usuario_id, limite=5):
    condicion, params = _filtro_alcance(alcance_usuario_id, "t")
    return _consultar(
        "SELECT t.id, t.titulo, t.prioridad, t.estado, t.fecha_limite, "
        "       u.nombre AS responsable "
        "FROM tareas t "
        "JOIN usuarios u ON u.id = t.usuario_id "
        f"WHERE {condicion} AND t.estado <> 'completada' "
        "ORDER BY FIELD(t.prioridad, 'urgente', 'alta', 'media', 'baja'), "
        "         t.fecha_limite IS NULL, t.fecha_limite ASC, t.id ASC "
        "LIMIT %s",
        params + (int(limite),),
    )


# Últimos correos registrados, con su responsable.
def obtener_actividad_reciente(alcance_usuario_id, limite=5):
    condicion, params = _filtro_alcance(alcance_usuario_id, "co")
    return _consultar(
        "SELECT co.id, co.remitente_nombre, co.remitente_correo, co.asunto, co.estado, "
        "       co.fecha_recepcion, u.nombre AS responsable "
        "FROM correos co "
        "JOIN usuarios u ON u.id = co.usuario_id "
        f"WHERE {condicion} "
        "ORDER BY co.fecha_recepcion DESC, co.id DESC "
        "LIMIT %s",
        params + (int(limite),),
    )


# --- Gestión de usuarios ---
# Nombre, rol y activo actuales (None si no existe).
def obtener_estado_usuario(usuario_id):
    return _consultar(
        "SELECT nombre, rol, activo FROM usuarios WHERE id = %s", (usuario_id,), uno=True
    )


# Todos los usuarios con su actividad (sin contraseñas, hashes ni salts).
def listar_usuarios():
    return _consultar(
        "SELECT u.id, u.nombre, u.correo, u.rol, u.activo, u.fecha_registro, "
        "       u.ultimo_acceso, "
        "       (SELECT COUNT(*) FROM correos c WHERE c.usuario_id = u.id) AS num_correos, "
        "       (SELECT COUNT(*) FROM tareas t WHERE t.usuario_id = u.id) AS num_tareas "
        "FROM usuarios u "
        "ORDER BY u.fecha_registro ASC, u.id ASC",
        (),
    )


# Usuarios activos para el selector 'Ver datos de:' del dashboard.
def listar_usuarios_activos():
    return _consultar(
        "SELECT id, nombre FROM usuarios WHERE activo = 1 ORDER BY nombre ASC", ()
    )


# Cambia rol/activo con las protecciones validadas en servidor.
def _modificar_usuario(admin_id, objetivo_id, nuevo_rol=None, nuevo_activo=None):
    if nuevo_rol not in (None, "usuario", "administrador"):
        return False, "Rol no válido."

    conexion = get_connection()
    try:
        conexion.begin()
        with conexion.cursor() as cursor:
            # FOR UPDATE: evita quedarse sin admin por cambios simultáneos.
            cursor.execute("SELECT id, nombre, rol, activo FROM usuarios FOR UPDATE")
            usuarios = {fila["id"]: fila for fila in cursor.fetchall()}

            admin = usuarios.get(admin_id)
            if not admin or admin["rol"] != "administrador" or not admin["activo"]:
                conexion.rollback()
                return False, "No tienes permisos para gestionar usuarios."

            objetivo = usuarios.get(objetivo_id)
            if not objetivo:
                conexion.rollback()
                return False, "El usuario seleccionado no existe."

            rol_final = nuevo_rol or objetivo["rol"]
            activo_final = objetivo["activo"] if nuevo_activo is None else int(bool(nuevo_activo))

            if objetivo_id == admin_id and (rol_final != "administrador" or not activo_final):
                conexion.rollback()
                return False, (
                    "No puedes quitarte tu propio rol de administrador ni desactivar tu cuenta."
                )

            admins_activos = sum(
                1
                for uid, fila in usuarios.items()
                if (rol_final if uid == objetivo_id else fila["rol"]) == "administrador"
                and (activo_final if uid == objetivo_id else fila["activo"])
            )
            if admins_activos == 0:
                conexion.rollback()
                return False, "El sistema debe tener al menos un administrador activo."

            if rol_final == objetivo["rol"] and activo_final == objetivo["activo"]:
                conexion.rollback()
                return True, "No había nada que cambiar."

            cursor.execute(
                "UPDATE usuarios SET rol = %s, activo = %s WHERE id = %s",
                (rol_final, activo_final, objetivo_id),
            )
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()

    nombre = objetivo["nombre"]
    if nuevo_rol is not None:
        return True, (
            f"{nombre} ahora es administrador." if rol_final == "administrador"
            else f"{nombre} ahora es usuario."
        )
    return True, (
        f"Cuenta de {nombre} activada." if activo_final else f"Cuenta de {nombre} desactivada."
    )


def cambiar_rol_usuario(admin_id, objetivo_id, nuevo_rol):
    return _modificar_usuario(admin_id, objetivo_id, nuevo_rol=nuevo_rol)


def cambiar_estado_usuario(admin_id, objetivo_id, activo):
    return _modificar_usuario(admin_id, objetivo_id, nuevo_activo=activo)


# --- Datos de ejemplo ---

# True si el usuario tiene datos propios.
def tiene_datos(usuario_id):
    fila = _consultar(
        "SELECT EXISTS(SELECT 1 FROM correos WHERE usuario_id = %s) "
        "    OR EXISTS(SELECT 1 FROM tareas WHERE usuario_id = %s) "
        "    OR EXISTS(SELECT 1 FROM eventos WHERE usuario_id = %s) "
        "    OR EXISTS(SELECT 1 FROM contactos WHERE usuario_id = %s) AS hay",
        (usuario_id,) * 4,
        uno=True,
    )
    return bool(fila["hay"])


# Inserta datos de demostración para el usuario en una sola transacción.
def cargar_datos_ejemplo(usuario_id):
    if tiene_datos(usuario_id):
        return False

    ahora = datetime.now().replace(second=0, microsecond=0)
    hoy = ahora.date()

    def a_las(dias, hora, minuto=0):
        return (ahora + timedelta(days=dias)).replace(hour=hora, minute=minuto)

    conexion = get_connection()
    try:
        conexion.begin()
        with conexion.cursor() as cursor:
            # --- Contactos ---
            contactos = [
                ("Ana Torres", "TechCorp", "ana.torres@techcorp.com", "+51 987 654 321",
                 "Gerente de Producto", "prospecto",
                 "Interesada en un módulo de pagos para su tienda online."),
                ("Luis Ramírez", "Constructora Andina", "luis.ramirez@constructoraandina.pe",
                 "+51 912 345 678", "Jefe de TI", "cliente",
                 "Cliente desde 2025. Sistema de reportes de avance de obras."),
                ("María Fernández", "Clínica San Gabriel", "maria.fernandez@sangabriel.pe",
                 "+51 956 111 222", "Coordinadora de Operaciones", "cliente",
                 "Sistema de citas en producción; evaluando nuevas funcionalidades."),
            ]
            ids_contacto = []
            for nombre, empresa, correo, telefono, cargo, estado, notas in contactos:
                cursor.execute(
                    "INSERT INTO contactos "
                    "(usuario_id, nombre, empresa, correo, telefono, cargo, estado, notas) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (usuario_id, nombre, empresa, correo, telefono, cargo, estado, notas),
                )
                ids_contacto.append(cursor.lastrowid)
            ana, luis, maria = ids_contacto

            # --- Correos (ya procesados) ---
            correos = [
                (ana, "Ana Torres", "ana.torres@techcorp.com",
                 "Propuesta para módulo de pagos",
                 "Hola, equipo de UTPConsult:\n\nQueremos integrar pagos con tarjeta y "
                 "billeteras digitales en nuestra tienda online. ¿Podrían enviarnos una "
                 "propuesta y agendar una reunión esta semana?\n\nSaludos,\nAna Torres",
                 "TechCorp solicita una propuesta para integrar pagos con tarjeta y "
                 "billeteras digitales, y pide una reunión esta semana.",
                 ahora - timedelta(days=2, hours=3)),
                (luis, "Luis Ramírez", "luis.ramirez@constructoraandina.pe",
                 "Error en el reporte de avance de obras",
                 "Buenos días:\n\nEl reporte mensual de avance no se exporta a PDF. "
                 "Necesitamos la corrección antes del cierre de mes.\n\nGracias,\nLuis",
                 "El reporte mensual no exporta a PDF; piden corrección urgente antes "
                 "del cierre de mes y una revisión presencial.",
                 ahora - timedelta(days=1, hours=5)),
                (maria, "María Fernández", "maria.fernandez@sangabriel.pe",
                 "Nuevos requisitos para el sistema de citas",
                 "Hola:\n\nNos gustaría añadir recordatorios por SMS y un panel para "
                 "recepción. ¿Podemos revisar alcance y costos?\n\nMaría",
                 "Solicitan recordatorios por SMS y un panel de recepción; quieren "
                 "revisar alcance y costos en una reunión de inicio.",
                 ahora - timedelta(hours=4)),
            ]
            ids_correo = []
            for contacto_id, rem_nombre, rem_correo, asunto, cuerpo, resumen, recibido in correos:
                cursor.execute(
                    "INSERT INTO correos (usuario_id, contacto_id, remitente_nombre, "
                    "remitente_correo, asunto, cuerpo, resumen, estado, fecha_recepcion, "
                    "fecha_procesado) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, 'procesado', %s, %s)",
                    (usuario_id, contacto_id, rem_nombre, rem_correo, asunto, cuerpo,
                     resumen, recibido, recibido + timedelta(minutes=5)),
                )
                ids_correo.append(cursor.lastrowid)
            correo_ana, correo_luis, correo_maria = ids_correo

            # --- Tareas (prioridades variadas; una ya completada) ---
            tareas = [
                (correo_luis, luis, "Corregir la exportación a PDF del reporte de obras",
                 "Revisar la librería de PDF y probar con el reporte de agosto.",
                 "urgente", "en_progreso", hoy + timedelta(days=1)),
                (correo_ana, ana, "Preparar propuesta técnica del módulo de pagos",
                 "Incluir pasarela de tarjetas, billeteras digitales y cronograma.",
                 "alta", "pendiente", hoy + timedelta(days=3)),
                (correo_maria, maria, "Estimar costos de recordatorios por SMS",
                 "Comparar proveedores de SMS y volumen mensual de citas.",
                 "media", "pendiente", hoy + timedelta(days=5)),
                (correo_maria, maria, "Diseñar maqueta del panel de recepción",
                 "Pantalla con citas del día, llegadas y reprogramaciones.",
                 "baja", "pendiente", hoy + timedelta(days=9)),
                (correo_luis, luis, "Enviar acta de la última reunión a Constructora Andina",
                 None, "media", "completada", hoy - timedelta(days=1)),
            ]
            for correo_id, contacto_id, titulo, descripcion, prioridad, estado, limite in tareas:
                cursor.execute(
                    "INSERT INTO tareas (usuario_id, correo_id, contacto_id, titulo, "
                    "descripcion, prioridad, estado, fecha_limite) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (usuario_id, correo_id, contacto_id, titulo, descripcion, prioridad,
                     estado, limite),
                )

            # --- Reuniones futuras ---
            eventos = [
                (correo_ana, ana, "Reunión con Ana Torres: módulo de pagos",
                 "Presentar la propuesta del módulo de pagos para TechCorp.",
                 a_las(2, 10), "virtual"),
                (correo_luis, luis, "Revisión del reporte de obras",
                 "Validar la corrección de la exportación a PDF con el cliente.",
                 a_las(4, 15, 30), "presencial"),
                (correo_maria, maria, "Kick-off: requisitos del sistema de citas",
                 "Definir alcance de recordatorios por SMS y panel de recepción.",
                 a_las(7, 9), "virtual"),
            ]
            for correo_id, contacto_id, titulo, descripcion, inicio, modalidad in eventos:
                cursor.execute(
                    "INSERT INTO eventos (usuario_id, correo_id, contacto_id, titulo, "
                    "descripcion, fecha_inicio, fecha_fin, modalidad) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (usuario_id, correo_id, contacto_id, titulo, descripcion, inicio,
                     inicio + timedelta(hours=1), modalidad),
                )
        conexion.commit()
        return True
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
