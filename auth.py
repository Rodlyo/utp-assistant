# Autenticación: contraseñas, validaciones, registro y login.
import hashlib
import hmac
import re
import secrets

import pymysql

from db import get_connection

# Parámetros del hash de contraseñas.
ITERACIONES_PBKDF2 = 200_000


# Expresión regular para validar el formato del correo.
REGEX_CORREO = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")


# --- Contraseñas ---
# Devuelve (hash_hex, salt) usando PBKDF2-HMAC-SHA256.
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERACIONES_PBKDF2
    )
    return digest.hex(), salt


# Comprueba la contraseña en tiempo constante.
def verify_password(password, password_hash, salt):
    calculado, _ = hash_password(password, salt)
    return hmac.compare_digest(calculado, password_hash)


# --- Validaciones ---
# Correo siempre en minúsculas y sin espacios.
def normalizar_correo(correo):
    return re.sub(r"\s+", "", correo or "").lower()


# True si el correo ya existe en la tabla usuarios.
def correo_registrado(correo):
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM usuarios WHERE correo = %s LIMIT 1",
                (normalizar_correo(correo),),
            )
            return cursor.fetchone() is not None
    finally:
        conexion.close()


# Devuelve la lista con TODOS los errores del formulario de registro.
def validar_registro(nombre, correo, password, confirmacion):
    errores = []
    nombre = (nombre or "").strip()
    correo = normalizar_correo(correo)
    password = password or ""

    if not nombre:
        errores.append("El nombre es obligatorio.")
    elif len(nombre) < 3:
        errores.append("El nombre debe tener al menos 3 caracteres.")
    elif len(nombre) > 100:
        errores.append("El nombre no puede superar los 100 caracteres.")

    if not correo:
        errores.append("El correo es obligatorio.")
    elif len(correo) > 150 or not REGEX_CORREO.match(correo):
        errores.append("El correo no tiene un formato válido.")
    elif correo_registrado(correo):
        errores.append("Este correo ya está registrado")

    if len(password) < 8:
        errores.append("La contraseña debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", password):
        errores.append("La contraseña debe contener al menos una letra.")
    if not re.search(r"\d", password):
        errores.append("La contraseña debe contener al menos un número.")

    if password != (confirmacion or ""):
        errores.append("Las contraseñas no coinciden.")

    return errores


# Error si falta correo o contraseña; None si está completo.
def validar_login(correo, password):
    if not (correo or "").strip() or not password:
        return "Introduce tu correo y tu contraseña."
    return None


# --- Registro y login ---
# Inserta un usuario nuevo y devuelve su rol, o None si el correo ya existía.
def registrar_usuario(nombre, correo, password):
    password_hash, salt = hash_password(password)
    conexion = get_connection()
    try:
        conexion.begin()
        with conexion.cursor() as cursor:
            # FOR UPDATE: evita dos "primeros administradores" simultáneos.
            cursor.execute(
                "SELECT COUNT(*) AS total FROM usuarios WHERE rol = 'administrador' FOR UPDATE"
            )
            rol = "usuario" if cursor.fetchone()["total"] > 0 else "administrador"
            cursor.execute(
                "INSERT INTO usuarios (nombre, correo, password_hash, salt, rol) "
                "VALUES (%s, %s, %s, %s, %s)",
                (nombre.strip(), normalizar_correo(correo), password_hash, salt, rol),
            )
        conexion.commit()
        return rol
    except pymysql.err.IntegrityError:
        conexion.rollback()
        return None
    finally:
        conexion.close()


# Usuario (id, nombre, correo, rol, activo) o None si falla.
def autenticar_usuario(correo, password):
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, nombre, correo, password_hash, salt, rol, activo "
                "FROM usuarios WHERE correo = %s LIMIT 1",
                (normalizar_correo(correo),),
            )
            usuario = cursor.fetchone()
    finally:
        conexion.close()

    if usuario is None:
        # Hash igualmente: no revelar por tiempo si el correo existe.
        hash_password(password or "", "0" * 32)
        return None

    if not verify_password(password or "", usuario["password_hash"], usuario["salt"]):
        return None

    return {
        "id": usuario["id"],
        "nombre": usuario["nombre"],
        "correo": usuario["correo"],
        "rol": usuario["rol"],
        "activo": bool(usuario["activo"]),
    }


# Actualiza la fecha del último acceso tras un login correcto.
def registrar_acceso(usuario_id):
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = %s", (usuario_id,))
        conexion.commit()
    finally:
        conexion.close()
