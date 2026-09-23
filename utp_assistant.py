# -*- coding: utf-8 -*-
"""
UTP Assistant - Sistema interno de UTPConsult.

FASE 1: landing page, registro, login y panel provisional.
Todo el sistema (frontend + backend) vive en este único archivo.

Ejecutar con:
    streamlit run utp_assistant.py
"""

# =============================================================================
# 1. IMPORTS Y CONFIGURACIÓN DE PÁGINA
# =============================================================================
import base64
import hashlib
import hmac
import html
import math
import re
import secrets
import time
from datetime import date
from pathlib import Path

import pymysql
import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="UTP Assistant",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Modelo de Groq reservado para fases futuras (no se usa todavía).
MODELO_GROQ = "openai/gpt-oss-120b"

# Parámetros de seguridad del login.
MAX_INTENTOS_LOGIN = 5
SEGUNDOS_BLOQUEO = 60

# Parámetros del hash de contraseñas.
ITERACIONES_PBKDF2 = 200_000

# Expresión regular para validar el formato del correo.
REGEX_CORREO = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")

# Meses en español (así no dependemos del locale del sistema).
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


# =============================================================================
# 2. ESTILOS
# =============================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;500;600;700;800;900&display=swap');

/* Paleta tomada de utp.edu.pe (--bs-color-rojo, grises y negro) */
:root {
    --utp-rojo: #D3052D;
    --utp-rojo-oscuro: #A80424;
    --utp-rojo-desactivado: #E78CA3;
    --utp-negro: #000000;
    --utp-texto: #262626;
    --utp-rojo-claro: #ED4F4F;    /* rojo de utp.edu.pe legible sobre fondo oscuro */
    --utp-gris: #555555;
    --utp-gris-claro: #BABABA;
    --utp-linea: #E8E8E8;
    --utp-fondo-suave: #F4F4F4;
    --utp-blanco: #FFFFFF;
    --utp-pie: #262626;           /* gris oscuro de utp.edu.pe */
    /* Textos y líneas que van directamente sobre el fondo oscuro */
    --utp-sobre-fondo: rgba(255, 255, 255, 0.78);
    --utp-linea-fondo: rgba(255, 255, 255, 0.22);
    /* Ajustes del fondo */
    --utp-oscuridad: 0.60;        /* opacidad de la capa negra (0 = sin capa, 1 = negro) */
    --utp-desenfoque: 6px;        /* desenfoque de la imagen (0px = nítida) */
    --f-base: 'Libre Franklin', 'Helvetica Neue', Arial, sans-serif;
}

/* ---------- Base: imagen desenfocada + capa negra ---------- */
.stApp, [data-testid="stApp"] {
    background: #111111 !important;
    color: var(--utp-texto);
    font-family: var(--f-base);
}
[data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
    background: transparent !important;
}
.stApp::before {
    content: "";
    position: fixed;
    inset: -40px;                 /* evita bordes claros que deja el blur */
    background-image: __FONDO__;
    background-size: cover;
    background-position: center;
    filter: blur(var(--utp-desenfoque));
    z-index: 0;
    pointer-events: none;
}
.stApp::after {
    content: "";
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, var(--utp-oscuridad));
    z-index: 0;
    pointer-events: none;
}
[data-testid="stAppViewContainer"] { position: relative; z-index: 1; }
.stApp p, .stApp label, .stApp input, .stApp button, .stApp li {
    font-family: var(--f-base) !important;
}

/* ---------- Ocultar elementos por defecto de Streamlit ---------- */
#MainMenu, footer, header,
header[data-testid="stHeader"], .stAppHeader,
[data-testid="stToolbar"], [data-testid="stMainMenu"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"], .stDeployButton,
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
[data-testid="stHeaderActionElements"], [data-testid="InputInstructions"] {
    display: none !important;
    visibility: hidden !important;
}

/* ---------- Contenedor principal (máx. 900px) ---------- */
.block-container, [data-testid="stMainBlockContainer"] {
    max-width: 900px !important;
    padding: 0 1.25rem !important;
    margin: 0 auto;
}

/* ---------- Barra superior ---------- */
.utp-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 1.1rem 0;
    border-bottom: 1px solid var(--utp-linea-fondo);
}
.utp-marca {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-weight: 800;
    font-size: 1.05rem;
    letter-spacing: -0.01em;
    color: var(--utp-blanco);
}
.utp-marca-cuadro {
    width: 30px;
    height: 30px;
    background: var(--utp-rojo);
    color: var(--utp-blanco);
    display: grid;
    place-items: center;
    font-size: 0.62rem;
    font-weight: 900;
    letter-spacing: 0.04em;
}
.utp-nav-meta {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--utp-sobre-fondo);
    text-align: right;
}

/* ---------- Landing ---------- */
.utp-eyebrow {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--utp-rojo-claro);
    margin: 4.5rem 0 1rem 0;
}
.utp-titulo {
    font-weight: 800;
    font-size: clamp(2.3rem, 6vw, 3.9rem);
    line-height: 1.05;
    letter-spacing: -0.03em;
    color: var(--utp-blanco);
    max-width: 720px;
    margin: 0 0 1.3rem 0;
}
.utp-titulo span { color: var(--utp-rojo-claro); }
.utp-lead {
    font-size: 1.08rem;
    line-height: 1.65;
    color: var(--utp-sobre-fondo);
    max-width: 580px;
    margin: 0 0 1.4rem 0;
}
.utp-pasos {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 2rem;
    margin: 4.5rem 0 3.5rem 0;
}
.utp-paso { border-top: 1px solid var(--utp-linea-fondo); padding-top: 1.2rem; }
.utp-paso-num {
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    color: var(--utp-rojo-claro);
}
.utp-paso-titulo {
    font-weight: 700;
    font-size: 1.15rem;
    color: var(--utp-blanco);
    margin: 0.5rem 0 0.4rem 0;
}
.utp-paso-texto { font-size: 0.92rem; line-height: 1.55; color: var(--utp-sobre-fondo); }
/* ---------- Zonas de contenido (empujan el pie al fondo) ---------- */
[data-testid="stAppViewContainer"] { overflow-x: hidden; }
.st-key-contenido, .st-key-contenido_auth { min-height: calc(100vh - 290px); }
/* Login y registro: formulario centrado vertical y horizontalmente */
.st-key-contenido_auth { justify-content: center; padding: 2.5rem 0; }

/* ---------- Pie de página (gris oscuro UTP, a todo el ancho) ---------- */
.utp-pie {
    width: 100vw;
    position: relative;
    left: 50%;
    margin-left: -50vw;
    margin-top: 2rem;
    background: var(--utp-pie);
    border-top: 3px solid var(--utp-rojo);
    color: rgba(255, 255, 255, 0.72);
    font-size: 0.85rem;
}
.utp-pie-interior { max-width: 900px; margin: 0 auto; padding: 2.4rem 1.25rem 0 1.25rem; }
.utp-pie-columnas {
    display: grid;
    grid-template-columns: 1.6fr 1fr 1fr;
    gap: 2rem;
    padding-bottom: 2rem;
}
.utp-pie .utp-marca { margin-bottom: 0.8rem; }
.utp-pie-texto { line-height: 1.6; max-width: 320px; }
.utp-pie-titulo {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--utp-blanco);
    margin-bottom: 0.8rem;
}
.utp-pie-lista div { margin-bottom: 0.4rem; }
.utp-pie-lista span { color: var(--utp-rojo-claro); font-size: 0.72rem; font-weight: 600; }
.utp-pie-legal {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    padding: 1.1rem 0 1.4rem 0;
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.55);
}

/* ---------- Botones de Streamlit ---------- */
button[data-testid^="stBaseButton-"], .stButton > button,
[data-testid="stFormSubmitButton"] > button {
    border-radius: 0 !important;
    min-height: 2.9rem;
    padding: 0.6rem 1.6rem !important;
    box-shadow: none !important;
    transition: background-color .15s ease, border-color .15s ease, color .15s ease;
}
button[data-testid^="stBaseButton-"] p { font-weight: 600 !important; font-size: 0.92rem !important; }
/* Primario: rojo UTP */
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"],
button[kind="primary"], button[kind="primaryFormSubmit"] {
    background: var(--utp-rojo) !important;
    border: 1px solid var(--utp-rojo) !important;
    color: var(--utp-blanco) !important;
}
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {
    background: var(--utp-rojo-oscuro) !important;
    border-color: var(--utp-rojo-oscuro) !important;
}
/* Secundario: borde blanco sobre el fondo oscuro, se rellena al pasar el ratón */
button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-secondaryFormSubmit"],
button[kind="secondary"], button[kind="secondaryFormSubmit"] {
    background: transparent !important;
    border: 1px solid var(--utp-blanco) !important;
    color: var(--utp-blanco) !important;
}
button[data-testid="stBaseButton-secondary"]:hover,
button[data-testid="stBaseButton-secondaryFormSubmit"]:hover,
button[kind="secondary"]:hover, button[kind="secondaryFormSubmit"]:hover {
    background: var(--utp-blanco) !important;
    color: var(--utp-negro) !important;
}
/* Terciario: enlace de texto */
button[data-testid="stBaseButton-tertiary"], button[kind="tertiary"] {
    background: transparent !important;
    border: none !important;
    min-height: auto;
    padding: 0.2rem 0 !important;
    color: var(--utp-sobre-fondo) !important;
}
button[data-testid="stBaseButton-tertiary"] p { font-size: 0.85rem !important; font-weight: 500 !important; }
button[data-testid="stBaseButton-tertiary"]:hover, button[kind="tertiary"]:hover {
    color: var(--utp-blanco) !important;
    text-decoration: underline;
    text-underline-offset: 4px;
}
/* Desactivado (mismo tono que utp.edu.pe) */
button[data-testid="stBaseButton-primaryFormSubmit"]:disabled,
button[data-testid="stBaseButton-primary"]:disabled {
    background: var(--utp-rojo-desactivado) !important;
    border-color: var(--utp-rojo-desactivado) !important;
    color: var(--utp-blanco) !important;
    cursor: not-allowed !important;
}
button:focus-visible { outline: 2px solid var(--utp-rojo) !important; outline-offset: 2px; }

/* ---------- Formularios (tarjeta) ---------- */
[data-testid="stForm"] {
    background: var(--utp-blanco) !important;
    border: 1px solid var(--utp-linea) !important;
    border-top: 3px solid var(--utp-rojo) !important;
    border-radius: 0 !important;
    padding: 2.2rem 2rem 2rem 2rem !important;
    box-shadow: none !important;
}
.utp-form-titulo {
    font-weight: 800;
    font-size: 1.75rem;
    letter-spacing: -0.02em;
    color: var(--utp-negro);
}
.utp-form-subtitulo {
    font-size: 0.95rem;
    color: var(--utp-gris);
    margin: 0.35rem 0 1.2rem 0;
}

/* ---------- Inputs ---------- */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: var(--utp-texto) !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stTextInputRootElement"] {
    border: 1px solid var(--utp-gris-claro) !important;
    border-radius: 0 !important;
    background: var(--utp-blanco) !important;
    box-shadow: none !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
[data-testid="stTextInputRootElement"]:focus-within {
    border-color: var(--utp-rojo) !important;
    box-shadow: 0 0 0 1px var(--utp-rojo) !important;
}
[data-testid="stTextInput"] div[data-baseweb="base-input"],
[data-testid="stTextInput"] input {
    background: var(--utp-blanco) !important;
    border-radius: 0 !important;
    color: var(--utp-texto) !important;
    caret-color: var(--utp-rojo);
}
[data-testid="stTextInput"] input::placeholder { color: var(--utp-gris-claro) !important; }
[data-testid="stTextInput"] button { background: transparent !important; border: none !important; }

/* ---------- Alertas ---------- */
[data-testid="stAlert"], [data-testid="stAlertContainer"] { border-radius: 0 !important; }
/* Fondo blanco sólido para que las alertas se lean sobre la imagen */
[data-testid="stAlertContainer"] { background-color: var(--utp-blanco) !important; }

/* ---------- Panel provisional ---------- */
.utp-saludo {
    font-weight: 800;
    font-size: clamp(2.2rem, 5vw, 3.2rem);
    letter-spacing: -0.03em;
    color: var(--utp-blanco);
    margin: 3.5rem 0 0.8rem 0;
}
.utp-saludo span { color: var(--utp-rojo-claro); }
.utp-panel-texto {
    font-size: 1.02rem;
    line-height: 1.6;
    color: var(--utp-sobre-fondo);
    max-width: 600px;
    margin-bottom: 2.2rem;
}
.utp-modulos {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-bottom: 2.2rem;
}
.utp-modulo { background: var(--utp-blanco); padding: 1.3rem 1.2rem; }
.utp-modulo-titulo { font-weight: 700; font-size: 1rem; color: var(--utp-negro); }
.utp-modulo-estado {
    margin-top: 0.35rem;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--utp-gris);
}

/* ---------- Móvil ---------- */
@media (max-width: 640px) {
    .utp-pasos, .utp-modulos { grid-template-columns: 1fr; gap: 1.2rem; }
    .utp-eyebrow { margin-top: 2.5rem; }
    .utp-nav-meta { display: none; }
    .utp-pie-columnas { grid-template-columns: 1fr; gap: 1.4rem; }
    .utp-pie-legal { flex-direction: column; }
    .st-key-contenido, .st-key-contenido_auth { min-height: auto; }
}
</style>
"""


RUTA_FONDO = Path(__file__).parent / "assets" / "fondo.jpg"


@st.cache_data(show_spinner=False)
def _fondo_css():
    """Imagen de fondo como data URI (se lee una sola vez). Sin imagen, degradado oscuro."""
    try:
        datos = base64.b64encode(RUTA_FONDO.read_bytes()).decode("ascii")
        return f'url("data:image/jpeg;base64,{datos}")'
    except OSError:
        return "linear-gradient(135deg, #2b2b2b 0%, #111111 100%)"


def aplicar_estilos():
    """Inyecta el CSS global de la aplicación."""
    st.markdown(CSS.replace("__FONDO__", _fondo_css()), unsafe_allow_html=True)


# =============================================================================
# 3. CLIENTE GROQ
# =============================================================================
@st.cache_resource(show_spinner=False)
def _crear_cliente_groq(api_key):
    """Crea (una sola vez) el cliente de Groq usando la librería openai."""
    return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)


def inicializar_cliente_groq():
    """Valida GROQ_API_KEY en secrets.toml e inicializa el cliente.

    En la fase 1 solo se inicializa: NO se hace ninguna llamada al modelo.
    """
    try:
        api_key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        api_key = ""

    if not api_key or api_key.strip() in ("", "tu_clave_aqui"):
        st.error(
            "Falta la clave de Groq. Añade GROQ_API_KEY en el archivo "
            ".streamlit/secrets.toml (puedes copiar .streamlit/secrets.toml.example) "
            "y recarga la página."
        )
        st.stop()

    return _crear_cliente_groq(api_key.strip())


# =============================================================================
# 4. BASE DE DATOS (MySQL - XAMPP)
# =============================================================================
MENSAJE_ERROR_MYSQL = (
    "No se pudo conectar a MySQL. Verifica que el servicio MySQL esté "
    "iniciado en el panel de XAMPP."
)


def _config_mysql():
    """Lee la sección [mysql] de secrets.toml."""
    try:
        return dict(st.secrets["mysql"])
    except Exception:
        st.error(
            "Falta la sección [mysql] en .streamlit/secrets.toml. "
            "Copia .streamlit/secrets.toml.example y ajusta los valores."
        )
        st.stop()


def _nombre_base_datos(config):
    """Devuelve el nombre de la base de datos validado (solo letras, números y _)."""
    nombre = str(config.get("database", "assistantutpdb"))
    if not re.fullmatch(r"[A-Za-z0-9_]+", nombre):
        st.error("El nombre de la base de datos en secrets.toml no es válido.")
        st.stop()
    return nombre


def _conectar(incluir_bd=True):
    """Abre una conexión PyMySQL; si falla, muestra el error y detiene la app."""
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
        st.error(MENSAJE_ERROR_MYSQL)
        st.stop()


def get_connection():
    """Conexión a la base de datos de la aplicación."""
    return _conectar(incluir_bd=True)


def init_db():
    """Crea la base de datos y la tabla usuarios si no existen.

    Se ejecuta una sola vez por sesión (controlado con st.session_state).
    """
    if st.session_state.get("db_inicializada"):
        return

    nombre_bd = _nombre_base_datos(_config_mysql())

    # 1) Crear la base de datos (conexión sin base de datos seleccionada).
    conexion = _conectar(incluir_bd=False)
    try:
        with conexion.cursor() as cursor:
            # El nombre ya está validado con regex; los identificadores no
            # admiten parámetros %s en MySQL.
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{nombre_bd}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conexion.commit()
    finally:
        conexion.close()

    # 2) Crear la tabla usuarios.
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    correo VARCHAR(150) NOT NULL UNIQUE,
                    password_hash VARCHAR(128) NOT NULL,
                    salt VARCHAR(64) NOT NULL,
                    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        conexion.commit()
    finally:
        conexion.close()

    st.session_state["db_inicializada"] = True


# =============================================================================
# 5. SEGURIDAD
# =============================================================================
def hash_password(password, salt=None):
    """Devuelve (hash_hex, salt) usando PBKDF2-HMAC-SHA256.

    Si no se pasa salt, se genera uno aleatorio con secrets.token_hex(16).
    """
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERACIONES_PBKDF2
    )
    return digest.hex(), salt


def verify_password(password, password_hash, salt):
    """Comprueba la contraseña en tiempo constante."""
    calculado, _ = hash_password(password, salt)
    return hmac.compare_digest(calculado, password_hash)


# =============================================================================
# 6. LÓGICA DE USUARIOS
# =============================================================================
def normalizar_correo(correo):
    """Correo siempre en minúsculas y sin espacios."""
    return re.sub(r"\s+", "", correo or "").lower()


def correo_registrado(correo):
    """True si el correo ya existe en la tabla usuarios."""
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


def validar_registro(nombre, correo, password, confirmacion):
    """Devuelve la lista con TODOS los errores del formulario de registro."""
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


def registrar_usuario(nombre, correo, password):
    """Inserta un usuario nuevo. Devuelve True si se creó, False si el correo ya existía."""
    password_hash, salt = hash_password(password)
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO usuarios (nombre, correo, password_hash, salt) "
                "VALUES (%s, %s, %s, %s)",
                (nombre.strip(), normalizar_correo(correo), password_hash, salt),
            )
        conexion.commit()
        return True
    except pymysql.err.IntegrityError:
        conexion.rollback()
        return False
    finally:
        conexion.close()


def autenticar_usuario(correo, password):
    """Devuelve el usuario (dict con id, nombre, correo) o None si las credenciales fallan."""
    conexion = get_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, nombre, correo, password_hash, salt "
                "FROM usuarios WHERE correo = %s LIMIT 1",
                (normalizar_correo(correo),),
            )
            usuario = cursor.fetchone()
    finally:
        conexion.close()

    if usuario is None:
        # Se calcula un hash igualmente para no revelar por tiempo de
        # respuesta si el correo existe o no.
        hash_password(password or "", "0" * 32)
        return None

    if not verify_password(password or "", usuario["password_hash"], usuario["salt"]):
        return None

    return {"id": usuario["id"], "nombre": usuario["nombre"], "correo": usuario["correo"]}


# =============================================================================
# 7. NAVEGACIÓN
# =============================================================================
PAGINAS_VALIDAS = ("landing", "login", "registro", "panel")
CLAVES_USUARIO = ("usuario_id", "usuario_nombre", "usuario_correo")


def inicializar_sesion():
    """Valores por defecto de st.session_state."""
    st.session_state.setdefault("pagina", "landing")
    st.session_state.setdefault("intentos_fallidos", 0)
    st.session_state.setdefault("bloqueado_hasta", 0.0)
    if st.session_state["pagina"] not in PAGINAS_VALIDAS:
        st.session_state["pagina"] = "landing"


def ir_a(pagina):
    """Cambia de página y recarga la app."""
    st.session_state["pagina"] = pagina
    st.rerun()


def iniciar_sesion(usuario):
    """Guarda los datos del usuario autenticado y va al panel."""
    st.session_state["usuario_id"] = usuario["id"]
    st.session_state["usuario_nombre"] = usuario["nombre"]
    st.session_state["usuario_correo"] = usuario["correo"]
    st.session_state["intentos_fallidos"] = 0
    st.session_state["bloqueado_hasta"] = 0.0
    ir_a("panel")


def cerrar_sesion():
    """Limpia los datos del usuario y vuelve a la landing."""
    for clave in CLAVES_USUARIO:
        st.session_state.pop(clave, None)
    ir_a("landing")


def segundos_bloqueo_restantes():
    """Segundos que faltan para desbloquear el login (0 si no está bloqueado)."""
    restante = st.session_state.get("bloqueado_hasta", 0.0) - time.time()
    return max(0, math.ceil(restante))


# =============================================================================
# 8. PANTALLAS
# =============================================================================
def fecha_es(fecha=None):
    """Fecha en español y mayúsculas, p. ej. '23 DE SEPTIEMBRE DE 2026'."""
    fecha = fecha or date.today()
    return f"{fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}".upper()


def render_cabecera(meta=None):
    """Barra superior común: marca a la izquierda y metadato (fecha o usuario) a la derecha."""
    meta = meta if meta is not None else fecha_es()
    st.markdown(
        '<div class="utp-nav">'
        '<div class="utp-marca"><span class="utp-marca-cuadro">UTP</span>Assistant</div>'
        f'<div class="utp-nav-meta">{meta}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def render_pie():
    """Pie de página gris oscuro (estilo utp.edu.pe) común a todas las pantallas."""
    anio = date.today().year
    st.markdown(
        '<div class="utp-pie"><div class="utp-pie-interior">'
        '<div class="utp-pie-columnas">'
        "<div>"
        '<div class="utp-marca"><span class="utp-marca-cuadro">UTP</span>Assistant</div>'
        '<div class="utp-pie-texto">Asistente de IA para los equipos de proyectos y ventas '
        "de UTPConsult.</div>"
        "</div>"
        '<div><div class="utp-pie-titulo">Módulos</div><div class="utp-pie-lista">'
        "<div>Correos <span>· Próximamente</span></div>"
        "<div>Calendario <span>· Próximamente</span></div>"
        "<div>CRM <span>· Próximamente</span></div>"
        "</div></div>"
        '<div><div class="utp-pie-titulo">Sistema</div><div class="utp-pie-lista">'
        "<div>Uso interno</div>"
        "<div>Versión 1.0</div>"
        f"<div>{fecha_es().capitalize()}</div>"
        "</div></div>"
        "</div>"
        '<div class="utp-pie-legal">'
        f"<span>© {anio} UTPConsult. Todos los derechos reservados.</span>"
        "<span>Sistema interno · Acceso restringido</span>"
        "</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )


def render_landing():
    """Página principal pública."""
    render_cabecera()

    with st.container(key="contenido"):
        st.markdown(
            '<div class="utp-eyebrow">Asistente de IA · UTPConsult</div>'
            '<div class="utp-titulo">Cada correo, <span>convertido en acción.</span></div>'
            '<p class="utp-lead">El asistente de IA de UTPConsult lee los correos de tus '
            "clientes, extrae los requisitos y los convierte en tareas, reuniones y contactos. "
            "Menos tiempo copiando, más tiempo construyendo.</p>",
            unsafe_allow_html=True,
        )

        col_login, col_registro, _ = st.columns([1, 1, 2.6], gap="small")
        with col_login:
            if st.button("Iniciar sesión", key="landing_login", type="primary", width="stretch"):
                ir_a("login")
        with col_registro:
            if st.button("Registrarse", key="landing_registro", type="secondary", width="stretch"):
                ir_a("registro")

        pasos = [
            ("01", "Recibe", "Pega el correo del cliente, sin importar lo largo del hilo."),
            ("02", "Analiza", "La IA identifica requisitos, reuniones y datos del contacto."),
            ("03", "Ejecuta", "Se crean tareas, se agenda la reunión y se actualiza el CRM."),
        ]
        columnas = "".join(
            '<div class="utp-paso">'
            f'<div class="utp-paso-num">{num}</div>'
            f'<div class="utp-paso-titulo">{titulo}</div>'
            f'<div class="utp-paso-texto">{texto}</div>'
            "</div>"
            for num, titulo, texto in pasos
        )
        st.markdown(f'<div class="utp-pasos">{columnas}</div>', unsafe_allow_html=True)

    render_pie()


def render_registro():
    """Formulario de creación de cuenta."""
    render_cabecera()

    with st.container(key="contenido_auth"):
        _, centro, _ = st.columns([1, 1.6, 1])
        with centro:
            with st.form("form_registro", clear_on_submit=False, border=True):
                st.markdown(
                    '<div class="utp-form-titulo">Crear cuenta</div>'
                    '<div class="utp-form-subtitulo">Regístrate para empezar a usar UTP Assistant.</div>',
                    unsafe_allow_html=True,
                )
                nombre = st.text_input("Nombre completo", max_chars=100, placeholder="Ana Pérez")
                correo = st.text_input("Correo", max_chars=150, placeholder="ana@utpconsult.com")
                password = st.text_input(
                    "Contraseña", type="password", placeholder="Mínimo 8 caracteres"
                )
                confirmacion = st.text_input("Confirmar contraseña", type="password")
                enviado = st.form_submit_button("Crear cuenta", type="primary", width="stretch")

            if enviado:
                errores = validar_registro(nombre, correo, password, confirmacion)
                if errores:
                    st.error("Revisa los siguientes datos:\n\n" + "\n".join(f"- {e}" for e in errores))
                elif registrar_usuario(nombre, correo, password):
                    st.session_state["mensaje_flash"] = (
                        "Cuenta creada correctamente. Ya puedes iniciar sesión."
                    )
                    ir_a("login")
                else:
                    st.error("Este correo ya está registrado")

            izquierda, derecha = st.columns(2)
            with izquierda:
                if st.button("¿Ya tienes cuenta? Inicia sesión", key="reg_a_login", type="tertiary"):
                    ir_a("login")
            with derecha:
                if st.button("← Volver al inicio", key="reg_a_inicio", type="tertiary"):
                    ir_a("landing")

    render_pie()


@st.fragment(run_every=1)
def _cuenta_atras_bloqueo():
    """Muestra el tiempo restante de bloqueo y desbloquea al llegar a 0."""
    restante = segundos_bloqueo_restantes()
    if restante <= 0:
        st.session_state["intentos_fallidos"] = 0
        st.session_state["bloqueado_hasta"] = 0.0
        st.rerun()
    st.warning(
        f"Demasiados intentos fallidos. Podrás volver a intentarlo en {restante} segundos."
    )


def render_login():
    """Formulario de inicio de sesión."""
    render_cabecera()

    bloqueado = segundos_bloqueo_restantes() > 0

    with st.container(key="contenido_auth"):
        _, centro, _ = st.columns([1, 1.6, 1])
        with centro:
            mensaje_flash = st.session_state.pop("mensaje_flash", None)
            if mensaje_flash:
                st.success(mensaje_flash)

            with st.form("form_login", clear_on_submit=False, border=True):
                st.markdown(
                    '<div class="utp-form-titulo">Iniciar sesión</div>'
                    '<div class="utp-form-subtitulo">Ingresa con tu correo institucional.</div>',
                    unsafe_allow_html=True,
                )
                correo = st.text_input("Correo", max_chars=150, placeholder="ana@utpconsult.com")
                password = st.text_input("Contraseña", type="password")
                enviado = st.form_submit_button(
                    "Entrar", type="primary", width="stretch", disabled=bloqueado
                )

            if bloqueado:
                _cuenta_atras_bloqueo()
            elif enviado:
                if not correo.strip() or not password:
                    st.error("Introduce tu correo y tu contraseña.")
                else:
                    usuario = autenticar_usuario(correo, password)
                    if usuario:
                        iniciar_sesion(usuario)
                    else:
                        st.session_state["intentos_fallidos"] += 1
                        if st.session_state["intentos_fallidos"] >= MAX_INTENTOS_LOGIN:
                            st.session_state["bloqueado_hasta"] = time.time() + SEGUNDOS_BLOQUEO
                            st.rerun()
                        st.error("Correo o contraseña incorrectos")

            izquierda, derecha = st.columns(2)
            with izquierda:
                if st.button("¿No tienes cuenta? Regístrate", key="login_a_reg", type="tertiary"):
                    ir_a("registro")
            with derecha:
                if st.button("← Volver al inicio", key="login_a_inicio", type="tertiary"):
                    ir_a("landing")

    render_pie()


def render_panel():
    """Panel provisional tras iniciar sesión."""
    nombre = html.escape(st.session_state.get("usuario_nombre", ""))
    correo = html.escape(st.session_state.get("usuario_correo", ""))
    render_cabecera(meta=correo)

    with st.container(key="contenido"):
        modulos = "".join(
            '<div class="utp-modulo">'
            f'<div class="utp-modulo-titulo">{titulo}</div>'
            '<div class="utp-modulo-estado">Próximamente</div>'
            "</div>"
            for titulo in ("Correos", "Calendario", "Métricas")
        )
        st.markdown(
            f'<div class="utp-saludo">Hola, <span>{nombre}.</span></div>'
            '<p class="utp-panel-texto">Tu cuenta está activa. Los módulos de correos, '
            "calendario y métricas estarán disponibles en las siguientes fases.</p>"
            f'<div class="utp-modulos">{modulos}</div>',
            unsafe_allow_html=True,
        )

        if st.button("Cerrar sesión", key="panel_logout", type="secondary"):
            cerrar_sesion()

    render_pie()


# =============================================================================
# 9. MARCADORES PARA FASES FUTURAS
# =============================================================================
# FASE 2: Dashboard con métricas
# FASE 3: Procesar correo (LLM + function calling)
# FASE 4: Calendario propio
# FASE 5: Correos almacenados


# =============================================================================
# 10. MAIN
# =============================================================================
def main():
    aplicar_estilos()
    inicializar_sesion()
    inicializar_cliente_groq()  # Solo valida la clave; no llama al modelo.
    init_db()

    pagina = st.session_state["pagina"]

    # Protección del panel: sin usuario en sesión se redirige al login.
    if pagina == "panel" and not st.session_state.get("usuario_id"):
        ir_a("login")

    if pagina == "landing":
        render_landing()
    elif pagina == "registro":
        render_registro()
    elif pagina == "login":
        render_login()
    elif pagina == "panel":
        render_panel()


if __name__ == "__main__":
    main()
