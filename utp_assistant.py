# --- Imports y configuración de página ---
import csv
import html
import io
import json
import math
import re
import time
from datetime import date, datetime, timedelta
from datetime import time as dtime

import streamlit as st

from assistant import (
    ESQUEMAS, ahora_lima, avanzar_ejecucion, cancelar_ejecucion, iniciar_ejecucion, obtener_cliente_groq,
    reanudar_tras_confirmacion, reintentar_ejecucion, validar_argumentos, validar_correo_entrante,
    validar_decisiones,
)
from auth import (
    autenticar_usuario, registrar_acceso, registrar_usuario, validar_login, validar_registro,
)
from db import (
    ErrorBaseDatos, actualizar_estado_tarea, actualizar_evento, buscar_correos, cambiar_estado_evento,
    cambiar_estado_usuario, cambiar_rol_usuario, cargar_datos_ejemplo, contar_contactos, contar_correos,
    contar_correos_procesados, contar_reuniones_proximas, contar_tareas_pendientes, crear_evento_manual,
    eliminar_correo, init_db, listar_contactos, listar_usuarios, listar_usuarios_activos, marcar_confirmada,
    obtener_actividad_reciente, obtener_detalle_correo, obtener_estado_usuario, obtener_evento,
    obtener_eventos_rango, obtener_pasos, obtener_proximas_reuniones, obtener_tareas_pendientes,
    resumen_correos, tiene_datos,
)
from styles import aplicar_estilos

# st.set_page_config debe ser la primera llamada de Streamlit.
st.set_page_config(
    page_title="UTP Assistant",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Parámetros de seguridad del login.
MAX_INTENTOS_LOGIN = 5


SEGUNDOS_BLOQUEO = 60


# Meses en español (así no dependemos del locale del sistema).
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


MESES_CORTOS_ES = [m[:3] for m in MESES_ES]


DIAS_CORTOS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


# --- Formato de fechas (español, sin depender del locale) ---
# date/datetime → 'Lun 28 sep'.
def formato_fecha_corta(valor):
    return f"{DIAS_CORTOS_ES[valor.weekday()]} {valor.day} {MESES_CORTOS_ES[valor.month - 1]}"


# datetime → 'Lun 28 sep · 10:00'.
def formato_fecha_hora(valor):
    return f"{formato_fecha_corta(valor)} · {valor:%H:%M}"


# date/datetime → '23 sep 2026'.
def formato_fecha_anio(valor):
    return f"{valor.day} {MESES_CORTOS_ES[valor.month - 1]} {valor.year}"


# Fecha en español y mayúsculas, p. ej. '23 DE SEPTIEMBRE DE 2026'.
def fecha_es(fecha=None):
    fecha = fecha or date.today()
    return f"{fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}".upper()


# --- Sesión, navegación y permisos ---
PAGINAS_PUBLICAS = ("landing", "login", "registro")


PAGINAS_INTERNAS = ("dashboard", "procesar", "calendario", "correos", "usuarios")


PAGINAS_VALIDAS = PAGINAS_PUBLICAS + PAGINAS_INTERNAS


# Claves de sesión que se borran al cerrar sesión.
CLAVES_USUARIO = (
    "usuario_id", "usuario_nombre", "usuario_correo", "usuario_rol",
    "alcance_admin", "accion_pendiente", "usuario_gestion", "ejecucion",
    "pc_nombre", "pc_correo", "pc_asunto", "pc_cuerpo",
    "cal_vista", "cal_fecha", "cal_dia", "cal_form", "cal_cancelar", "cal_responsable",
    "alcance_calendario", "alcance_correos", "co_texto", "co_estado", "co_desde", "co_hasta",
    "co_pagina", "co_detalle", "co_confirmar",
)


# Enlaces de la barra interna: (página, etiqueta, solo admin).
ENLACES_INTERNOS = [
    ("dashboard", "Dashboard", False),
    ("procesar", "Procesar correo", False),
    ("calendario", "Calendario", False),
    ("correos", "Correos", False),
    ("usuarios", "Usuarios", True),
]


# Valores por defecto de st.session_state.
def inicializar_sesion():
    st.session_state.setdefault("pagina", "landing")
    st.session_state.setdefault("intentos_fallidos", 0)
    st.session_state.setdefault("bloqueado_hasta", 0.0)
    # "panel" ya no existe: redirige al dashboard.
    if st.session_state["pagina"] == "panel":
        st.session_state["pagina"] = "dashboard"
    if st.session_state["pagina"] not in PAGINAS_VALIDAS:
        st.session_state["pagina"] = "landing"


# Cambia de página y recarga la app.
def ir_a(pagina):
    st.session_state["pagina"] = pagina
    st.rerun()


# Guarda los datos del usuario autenticado y va al dashboard.
def iniciar_sesion(usuario):
    st.session_state["usuario_id"] = usuario["id"]
    st.session_state["usuario_nombre"] = usuario["nombre"]
    st.session_state["usuario_correo"] = usuario["correo"]
    st.session_state["usuario_rol"] = usuario["rol"]
    st.session_state["intentos_fallidos"] = 0
    st.session_state["bloqueado_hasta"] = 0.0
    ir_a("dashboard")


# Limpia los datos del usuario y vuelve a la landing.
def cerrar_sesion():
    for clave in CLAVES_USUARIO:
        st.session_state.pop(clave, None)
    ir_a("landing")


# Cierra la sesión y lleva al login mostrando un mensaje de error.
def expulsar_sesion(mensaje):
    for clave in CLAVES_USUARIO:
        st.session_state.pop(clave, None)
    st.session_state["mensaje_flash_error"] = mensaje
    ir_a("login")


# Relee rol y activo desde la BD en cada página interna.
def sincronizar_sesion():
    estado = obtener_estado_usuario(st.session_state["usuario_id"])
    if estado is None:
        expulsar_sesion("Tu sesión ya no es válida. Inicia sesión de nuevo.")
    if not estado["activo"]:
        expulsar_sesion("Tu cuenta está desactivada. Contacta al administrador.")
    if estado["rol"] != st.session_state.get("usuario_rol"):
        st.session_state["usuario_rol"] = estado["rol"]
    st.session_state["usuario_nombre"] = estado["nombre"]


def es_admin():
    return st.session_state.get("usuario_rol") == "administrador"


# Alcance: id propio (usuario) o el elegido por el admin (None = equipo).
def obtener_alcance(clave="alcance_admin"):
    if not es_admin():
        return st.session_state["usuario_id"]
    elegido = st.session_state.get(clave)
    return int(elegido) if elegido is not None else None


# Exige sesión en páginas internas; con sesión, login/registro van al dashboard.
def requiere_login():
    pagina = st.session_state["pagina"]
    con_sesion = bool(st.session_state.get("usuario_id"))
    if pagina in PAGINAS_INTERNAS and not con_sesion:
        ir_a("login")
    if pagina in ("login", "registro") and con_sesion:
        ir_a("dashboard")
    # En cada página interna se relee rol y activo desde la base de datos.
    if pagina in PAGINAS_INTERNAS:
        sincronizar_sesion()


# Solo admin (validado en servidor); si no, vuelve al dashboard con error.
def requiere_admin():
    if not es_admin():
        st.session_state["flash_error_dashboard"] = (
            "No tienes permisos para acceder a esa página. Solo está disponible para administradores."
        )
        ir_a("dashboard")


# Segundos que faltan para desbloquear el login (0 si no está bloqueado).
def segundos_bloqueo_restantes():
    restante = st.session_state.get("bloqueado_hasta", 0.0) - time.time()
    return max(0, math.ceil(restante))


# --- Pantallas ---
# Barra superior: marca a la izquierda, metadato a la derecha.
def render_cabecera(meta=None):
    meta = meta if meta is not None else fecha_es()
    st.markdown(
        '<div class="utp-nav">'
        '<div class="utp-marca"><span class="utp-marca-cuadro">UTP</span>Assistant</div>'
        f'<div class="utp-nav-meta">{meta}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


# Pie de página común (gris oscuro UTP).
def render_pie():
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
        '<div>Dashboard <span class="utp-pie-activo">· Activo</span></div>'
        '<div>Procesar correo <span class="utp-pie-activo">· Activo</span></div>'
        '<div>Calendario <span class="utp-pie-activo">· Activo</span></div>'
        '<div>Correos <span class="utp-pie-activo">· Activo</span></div>'
        "</div></div>"
        '<div><div class="utp-pie-titulo">Sistema</div><div class="utp-pie-lista">'
        "<div>Uso interno</div>"
        "<div>Versión 2.0</div>"
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


# Página principal pública.
def render_landing():
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


# Formulario de creación de cuenta.
def render_registro():
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
                else:
                    rol = registrar_usuario(nombre, correo, password)
                    if rol is None:
                        st.error("Este correo ya está registrado")
                    else:
                        st.session_state["mensaje_flash"] = (
                            "Cuenta creada como administrador (primer usuario del sistema). "
                            "Ya puedes iniciar sesión."
                            if rol == "administrador"
                            else "Cuenta creada correctamente. Ya puedes iniciar sesión."
                        )
                        ir_a("login")

            izquierda, derecha = st.columns(2)
            with izquierda:
                if st.button("¿Ya tienes cuenta? Inicia sesión", key="reg_a_login", type="tertiary"):
                    ir_a("login")
            with derecha:
                if st.button("← Volver al inicio", key="reg_a_inicio", type="tertiary"):
                    ir_a("landing")

    render_pie()


# Muestra el tiempo restante de bloqueo y desbloquea al llegar a 0.
@st.fragment(run_every=1)
def _cuenta_atras_bloqueo():
    restante = segundos_bloqueo_restantes()
    if restante <= 0:
        st.session_state["intentos_fallidos"] = 0
        st.session_state["bloqueado_hasta"] = 0.0
        st.rerun()
    st.warning(
        f"Demasiados intentos fallidos. Podrás volver a intentarlo en {restante} segundos."
    )


# Formulario de inicio de sesión.
def render_login():
    render_cabecera()

    bloqueado = segundos_bloqueo_restantes() > 0

    with st.container(key="contenido_auth"):
        _, centro, _ = st.columns([1, 1.6, 1])
        with centro:
            mensaje_flash = st.session_state.pop("mensaje_flash", None)
            if mensaje_flash:
                st.success(mensaje_flash)
            mensaje_error = st.session_state.pop("mensaje_flash_error", None)
            if mensaje_error:
                st.error(mensaje_error)

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
                error = validar_login(correo, password)
                if error:
                    st.error(error)
                else:
                    usuario = autenticar_usuario(correo, password)
                    if usuario and not usuario["activo"]:
                        st.error("Tu cuenta está desactivada. Contacta al administrador.")
                    elif usuario:
                        registrar_acceso(usuario["id"])
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


# Barra interna: enlaces, usuario y cerrar sesión.
def render_navegacion_interna(activa):
    nombre = html.escape(st.session_state.get("usuario_nombre", ""))
    etiqueta_admin = '<span class="utp-badge-admin">Admin</span>' if es_admin() else ""
    # Subrayado rojo en la página activa.
    st.markdown(
        f'<style>.st-key-nav_enlaces .st-key-nav_{activa} button[data-testid="stBaseButton-tertiary"] {{'
        "border-bottom-color: var(--utp-rojo) !important;"
        "color: var(--utp-blanco) !important;}}</style>",
        unsafe_allow_html=True,
    )
    with st.container(key="barra_interna", horizontal=True, vertical_alignment="center"):
        with st.container(key="nav_enlaces", horizontal=True, width="content", gap=None):
            for pagina, etiqueta, solo_admin in ENLACES_INTERNOS:
                if solo_admin and not es_admin():
                    continue
                if st.button(etiqueta, key=f"nav_{pagina}", type="tertiary") and pagina != activa:
                    ir_a(pagina)
        with st.container(
            key="nav_usuario", horizontal=True, horizontal_alignment="right",
            vertical_alignment="center", gap="medium",
        ):
            st.markdown(
                f'<span class="utp-nav-usuario">{nombre}{etiqueta_admin}</span>',
                unsafe_allow_html=True,
            )
            if st.button("Cerrar sesión", key="nav_logout", type="tertiary"):
                cerrar_sesion()


def _html_vacio(texto):
    return f'<p class="utp-vacio">{texto}</p>'


def _html_responsable(fila, mostrar):
    if not mostrar:
        return ""
    return f'<span class="utp-responsable">Resp.: {html.escape(fila["responsable"])}</span>'


# Franja editorial de métricas: [(valor, etiqueta), ...].
def _html_metricas(metricas):
    return (
        '<div class="utp-metricas">'
        + "".join(
            '<div class="utp-metrica">'
            f'<div class="utp-metrica-numero">{valor}</div>'
            f'<div class="utp-metrica-etiqueta">{etiqueta}</div>'
            "</div>"
            for valor, etiqueta in metricas
        )
        + "</div>"
    )


def _html_reuniones(reuniones, mostrar_responsable=False):
    if not reuniones:
        return _html_vacio("Aún no hay reuniones agendadas.")
    filas = []
    for r in reuniones:
        contacto = " · ".join(
            html.escape(v) for v in (r["contacto_nombre"], r["contacto_empresa"]) if v
        )
        modalidad = "Presencial" if r["modalidad"] == "presencial" else "Virtual"
        filas.append(
            '<div class="utp-item">'
            f'<div class="utp-item-fecha">{formato_fecha_hora(r["fecha_inicio"])}</div>'
            f'<div class="utp-item-titulo">{html.escape(r["titulo"])}</div>'
            '<div class="utp-item-meta">'
            + (f"<span>{contacto}</span>" if contacto else "")
            + f'<span class="utp-chip">{modalidad}</span>'
            + _html_responsable(r, mostrar_responsable)
            + "</div></div>"
        )
    return "".join(filas)


def _html_tareas(tareas, mostrar_responsable=False):
    if not tareas:
        return _html_vacio("No hay tareas pendientes.")
    hoy = date.today()
    filas = []
    for t in tareas:
        limite = t["fecha_limite"]
        if limite is None:
            vence = "Sin fecha límite"
        elif limite < hoy:
            vence = f'<span class="utp-vencida">Vencida · {formato_fecha_corta(limite)}</span>'
        else:
            vence = f"Vence {formato_fecha_corta(limite)}"
        if t["estado"] == "en_progreso":
            vence += " · En progreso"
        filas.append(
            '<div class="utp-item utp-item-fila">'
            "<div>"
            f'<div class="utp-item-titulo">{html.escape(t["titulo"])}</div>'
            f'<div class="utp-item-meta"><span>{vence}</span>'
            f"{_html_responsable(t, mostrar_responsable)}</div>"
            "</div>"
            f'<span class="utp-prioridad utp-prioridad-{t["prioridad"]}">{t["prioridad"]}</span>'
            "</div>"
        )
    return "".join(filas)


def _html_actividad(correos, mostrar_responsable=False):
    if not correos:
        return _html_vacio("Aún no se ha registrado ningún correo.")
    filas = []
    for c in correos:
        remitente = html.escape(
            c["remitente_nombre"] or c["remitente_correo"] or "Remitente desconocido"
        )
        asunto = html.escape(c["asunto"] or "(Sin asunto)")
        responsable = _html_responsable(c, mostrar_responsable)
        filas.append(
            '<div class="utp-actividad-fila">'
            f'<div><div class="utp-item-titulo">{remitente}</div>'
            + (f'<div class="utp-item-meta">{responsable}</div>' if responsable else "")
            + "</div>"
            f'<div class="utp-actividad-asunto">{asunto}</div>'
            f'<span class="utp-estado utp-estado-{c["estado"]}">{c["estado"]}</span>'
            f'<div class="utp-item-fecha">{formato_fecha_hora(c["fecha_recepcion"])}</div>'
            "</div>"
        )
    return "".join(filas)


# Selector de alcance (solo admin; por defecto todo el equipo).
def _render_selector_alcance(etiqueta="Ver datos de:", clave="alcance_admin", al_cambiar=None):
    activos = listar_usuarios_activos()
    nombres = {u["id"]: u["nombre"] for u in activos}
    opciones = [None] + list(nombres)
    # Si el usuario elegido ya no está activo, se vuelve a "Todo el equipo".
    if st.session_state.get(clave) not in opciones:
        st.session_state[clave] = None
    with st.container(key="selector_alcance"):
        columna, _ = st.columns([1.4, 2.6])
        with columna:
            st.selectbox(
                etiqueta,
                opciones,
                key=clave,
                on_change=al_cambiar,
                format_func=lambda v: "Todo el equipo" if v is None else nombres[v],
            )


# Dashboard con métricas, próximas reuniones, tareas y actividad reciente.
def render_dashboard():
    usuario_id = st.session_state["usuario_id"]
    nombre = html.escape(st.session_state.get("usuario_nombre", ""))
    render_cabecera(meta="UTPConsult · Sistema interno")
    render_navegacion_interna("dashboard")

    with st.container(key="contenido"):
        st.markdown(
            f'<div class="utp-saludo">Hola, <span>{nombre}.</span></div>'
            f'<div class="utp-fecha-hoy">{fecha_es()}</div>',
            unsafe_allow_html=True,
        )

        error = st.session_state.pop("flash_error_dashboard", None)
        if error:
            st.error(error)
        mensaje = st.session_state.pop("flash_dashboard", None)
        if mensaje:
            st.success(mensaje)

        if es_admin():
            _render_selector_alcance()
        alcance = obtener_alcance()
        mostrar_responsable = alcance is None  # todo el equipo

        st.markdown(
            _html_metricas([
                (contar_correos_procesados(alcance), "Correos procesados"),
                (contar_tareas_pendientes(alcance), "Tareas pendientes"),
                (contar_reuniones_proximas(alcance), "Reuniones próximas"),
                (contar_contactos(alcance), "Contactos en CRM"),
            ]),
            unsafe_allow_html=True,
        )

        # Datos de ejemplo: solo si el usuario no tiene datos propios.
        if not tiene_datos(usuario_id):
            with st.container(key="demo", horizontal=True, vertical_alignment="center"):
                st.markdown(
                    '<span class="utp-demo-texto">Tu cuenta aún no tiene datos.</span>',
                    unsafe_allow_html=True,
                )
                if st.button("Cargar datos de ejemplo", key="cargar_demo", type="tertiary"):
                    if cargar_datos_ejemplo(usuario_id):
                        st.session_state["flash_dashboard"] = "Datos de ejemplo cargados."
                    st.rerun()

        reuniones = obtener_proximas_reuniones(alcance)
        tareas = obtener_tareas_pendientes(alcance)
        actividad = obtener_actividad_reciente(alcance)
        st.markdown(
            '<div class="utp-dash-columnas">'
            '<div class="utp-tarjeta">'
            '<div class="utp-tarjeta-titulo">Próximas reuniones</div>'
            f"{_html_reuniones(reuniones, mostrar_responsable)}"
            "</div>"
            '<div class="utp-tarjeta">'
            '<div class="utp-tarjeta-titulo">Tareas pendientes</div>'
            f"{_html_tareas(tareas, mostrar_responsable)}"
            "</div>"
            "</div>"
            '<div class="utp-tarjeta utp-tarjeta-ancha">'
            '<div class="utp-tarjeta-titulo">Actividad reciente</div>'
            f"{_html_actividad(actividad, mostrar_responsable)}"
            "</div>",
            unsafe_allow_html=True,
        )

    render_pie()


# Tabla de usuarios (sin contraseñas, hashes ni salts).
def _html_tabla_usuarios(usuarios, admin_id):
    filas = []
    for u in usuarios:
        es_yo = ' <span class="utp-tu">(tú)</span>' if u["id"] == admin_id else ""
        rol = (
            '<span class="utp-chip utp-rol-admin">Administrador</span>'
            if u["rol"] == "administrador" else '<span class="utp-chip">Usuario</span>'
        )
        estado = (
            '<span class="utp-estado utp-estado-procesado">Activo</span>'
            if u["activo"] else '<span class="utp-estado">Inactivo</span>'
        )
        acceso = formato_fecha_hora(u["ultimo_acceso"]) if u["ultimo_acceso"] else "Nunca"
        filas.append(
            "<tr>"
            f'<td><strong>{html.escape(u["nombre"])}</strong>{es_yo}</td>'
            f'<td>{html.escape(u["correo"])}</td>'
            f"<td>{rol}</td>"
            f"<td>{estado}</td>"
            f'<td class="utp-nowrap">{formato_fecha_anio(u["fecha_registro"])}</td>'
            f'<td class="utp-nowrap">{acceso}</td>'
            f'<td class="utp-num">{u["num_correos"]}</td>'
            f'<td class="utp-num">{u["num_tareas"]}</td>'
            "</tr>"
        )
    return (
        '<div class="utp-tarjeta utp-tarjeta-ancha"><div class="utp-tabla-scroll">'
        '<table class="utp-tabla"><thead><tr>'
        "<th>Nombre</th><th>Correo</th><th>Rol</th><th>Estado</th>"
        '<th>Registro</th><th>Último acceso</th><th class="utp-num">Correos</th>'
        '<th class="utp-num">Tareas</th>'
        "</tr></thead><tbody>" + "".join(filas) + "</tbody></table></div></div>"
    )


# Cambiar rol y activar/desactivar, siempre con confirmación previa.
def _render_acciones_usuarios(usuarios, admin_id):
    por_id = {u["id"]: u for u in usuarios}
    with st.container(key="panel_acciones"):
        st.markdown('<div class="utp-tarjeta-titulo">Acciones</div>', unsafe_allow_html=True)
        elegido = st.selectbox(
            "Usuario",
            list(por_id),
            key="usuario_gestion",
            format_func=lambda i: f'{por_id[i]["nombre"]} · {por_id[i]["correo"]}',
        )
        usuario = por_id[elegido]
        es_yo = elegido == admin_id
        if es_yo:
            st.caption(
                "Esta es tu cuenta: no puedes quitarte el rol de administrador ni desactivarla."
            )

        # Una acción pendiente de otro usuario se descarta al cambiar la selección.
        pendiente = st.session_state.get("accion_pendiente")
        if pendiente and pendiente["usuario_id"] != elegido:
            st.session_state.pop("accion_pendiente", None)
            pendiente = None

        nombre = usuario["nombre"]
        if usuario["rol"] == "administrador":
            nuevo_rol, texto_rol = "usuario", "Quitar rol de administrador"
            pregunta_rol = f"¿Quitar el rol de administrador a {nombre}?"
        else:
            nuevo_rol, texto_rol = "administrador", "Hacer administrador"
            pregunta_rol = f"¿Dar el rol de administrador a {nombre}?"
        if usuario["activo"]:
            nuevo_activo, texto_activo = 0, "Desactivar cuenta"
            pregunta_activo = f"¿Desactivar la cuenta de {nombre}? No podrá iniciar sesión."
        else:
            nuevo_activo, texto_activo = 1, "Activar cuenta"
            pregunta_activo = f"¿Activar de nuevo la cuenta de {nombre}?"

        col_rol, col_activo = st.columns(2)
        with col_rol:
            if st.button(texto_rol, key="accion_rol", width="stretch", disabled=es_yo):
                st.session_state["accion_pendiente"] = {
                    "tipo": "rol", "usuario_id": elegido, "valor": nuevo_rol,
                    "pregunta": pregunta_rol,
                }
                st.rerun()
        with col_activo:
            if st.button(texto_activo, key="accion_activo", width="stretch", disabled=es_yo):
                st.session_state["accion_pendiente"] = {
                    "tipo": "activo", "usuario_id": elegido, "valor": nuevo_activo,
                    "pregunta": pregunta_activo,
                }
                st.rerun()

        if pendiente:
            st.warning(pendiente["pregunta"])
            col_si, col_no = st.columns(2)
            with col_si:
                confirmar = st.button(
                    "Confirmar", key="accion_confirmar", type="primary", width="stretch"
                )
            with col_no:
                cancelar = st.button("Cancelar", key="accion_cancelar", width="stretch")
            if confirmar:
                st.session_state.pop("accion_pendiente", None)
                if pendiente["tipo"] == "rol":
                    ok, texto = cambiar_rol_usuario(admin_id, pendiente["usuario_id"], pendiente["valor"])
                else:
                    ok, texto = cambiar_estado_usuario(admin_id, pendiente["usuario_id"], pendiente["valor"])
                st.session_state["flash_usuarios_ok" if ok else "flash_usuarios_error"] = texto
                st.rerun()
            if cancelar:
                st.session_state.pop("accion_pendiente", None)
                st.rerun()


# Gestión de usuarios (solo administradores).
def render_usuarios():
    requiere_admin()
    admin_id = st.session_state["usuario_id"]
    render_cabecera(meta="UTPConsult · Sistema interno")
    render_navegacion_interna("usuarios")

    with st.container(key="contenido"):
        st.markdown(
            '<div class="utp-eyebrow">Administración</div>'
            '<div class="utp-titulo">Usuarios</div>'
            '<p class="utp-subtitulo">Gestiona quién accede al sistema y con qué rol.</p>',
            unsafe_allow_html=True,
        )
        ok = st.session_state.pop("flash_usuarios_ok", None)
        if ok:
            st.success(ok)
        error = st.session_state.pop("flash_usuarios_error", None)
        if error:
            st.error(error)

        usuarios = listar_usuarios()
        activos = sum(1 for u in usuarios if u["activo"])
        st.markdown(
            _html_metricas([
                (len(usuarios), "Total de usuarios"),
                (activos, "Activos"),
                (len(usuarios) - activos, "Inactivos"),
                (sum(1 for u in usuarios if u["rol"] == "administrador"), "Administradores"),
            ]),
            unsafe_allow_html=True,
        )
        st.markdown(_html_tabla_usuarios(usuarios, admin_id), unsafe_allow_html=True)
        _render_acciones_usuarios(usuarios, admin_id)

    render_pie()


# --- Procesar correo ---
CORREO_EJEMPLO = {
    "pc_nombre": "Ana Torres",
    "pc_correo": "ana.torres@techcorp.com",
    "pc_asunto": "Avance con la propuesta",
    "pc_cuerpo": (
        "Hola equipo de UTP Consult, gracias por la propuesta. Nos interesa avanzar. "
        "¿Podríamos tener una reunión la próxima semana para discutir los detalles técnicos "
        "del módulo de pagos? Adjunto un documento con algunos requisitos iniciales. "
        "Saludos, Ana Torres de TechCorp."
    ),
}
ESTADOS_RUN = [("en_cola", "En cola"), ("en_progreso", "En progreso"),
               ("requiere_accion", "Requiere acción"), ("completado", "Completado")]
# Estados finales sin éxito: (etiqueta, pasos previos marcados como hechos).
ESTADOS_FINALES = {"fallido": ("Fallido", 2), "cancelado": ("Cancelado", 3)}
TITULOS_ACCION = {"registrar_contacto_en_crm": "Registrar contacto", "crear_tarea": "Crear tarea",
                  "agendar_reunion": "Agendar reunión"}
TIPOS_PASO = {"llamada_modelo": "Llamada al modelo", "funcion_propuesta": "Función propuesta",
              "funcion_ejecutada": "Función ejecutada", "funcion_rechazada": "Función rechazada",
              "error_validacion": "Error de validación", "respuesta_final": "Respuesta final"}
SECCIONES_RESUMEN = re.compile(
    r"^(CLIENTE|SOLICITUD|ACCIONES REALIZADAS|PENDIENTES|SIGUIENTE PASO SUGERIDO)\s*:\s*(.*)$", re.I
)


# Rellena el formulario con el correo de ejemplo (callback).
def _cargar_correo_ejemplo():
    st.session_state.update(CORREO_EJEMPLO)


# Limpia la ejecución y el formulario (callback).
def _limpiar_procesamiento():
    for clave in ("ejecucion", *CORREO_EJEMPLO):
        st.session_state.pop(clave, None)


# Indicador EN COLA → EN PROGRESO → REQUIERE ACCIÓN → COMPLETADO.
def _html_estado_run(estado):
    claves = [c for c, _ in ESTADOS_RUN]
    if estado in ESTADOS_FINALES:
        etiqueta_final, hechos = ESTADOS_FINALES[estado]
        pasos = [(e, "hecho" if i < hechos else "") for i, (_, e) in enumerate(ESTADOS_RUN[:hechos])]
        pasos.append((etiqueta_final, "actual"))
    else:
        actual = claves.index(estado)
        pasos = [(e, "actual" if i == actual else "hecho" if i < actual else "")
                 for i, (_, e) in enumerate(ESTADOS_RUN)]
    flecha = '<span class="utp-run-flecha">→</span>'
    return '<div class="utp-run">' + flecha.join(
        f'<span class="{clase}">{etiqueta}</span>' for etiqueta, clase in pasos) + "</div>"


# Llama al modelo mostrando el estado y un spinner; guarda el resultado en la sesión.
def _avanzar_con_spinner(run, funcion, *args):
    st.markdown(_html_estado_run("en_progreso"), unsafe_allow_html=True)
    with st.spinner("El asistente está analizando el correo…"):
        run = funcion(obtener_cliente_groq(), run, *args)
    st.session_state["ejecucion"] = run
    st.rerun()


def _render_formulario_correo():
    st.button("Cargar correo de ejemplo", key="pc_ejemplo", on_click=_cargar_correo_ejemplo)
    with st.form("form_correo"):
        st.markdown(
            '<div class="utp-form-titulo">Correo del cliente</div>'
            '<div class="utp-form-subtitulo">Pega el correo tal como lo recibiste.</div>',
            unsafe_allow_html=True,
        )
        col_nombre, col_correo = st.columns(2)
        nombre = col_nombre.text_input("Nombre del remitente", key="pc_nombre", max_chars=100)
        correo = col_correo.text_input("Correo del remitente", key="pc_correo", max_chars=150)
        asunto = st.text_input("Asunto", key="pc_asunto", max_chars=255)
        cuerpo = st.text_area("Cuerpo del correo", key="pc_cuerpo", height=260, max_chars=10_000)
        enviado = st.form_submit_button("Analizar correo", type="primary", width="stretch")
    if enviado:
        errores = validar_correo_entrante(nombre, correo, asunto, cuerpo)
        if errores:
            st.error("Revisa los siguientes datos:\n\n" + "\n".join(f"- {e}" for e in errores))
            return
        run = iniciar_ejecucion(st.session_state["usuario_id"], nombre.strip(),
                                correo.strip().lower(), asunto.strip(), cuerpo.strip())
        st.session_state["ejecucion"] = run
        st.markdown(_html_estado_run("en_cola"), unsafe_allow_html=True)
        _avanzar_con_spinner(run, avanzar_ejecucion)


# Quita espacios y omite los opcionales vacíos.
def _limpiar_argumentos(nombre, argumentos):
    requeridos = ESQUEMAS[nombre]["required"]
    limpios = {}
    for clave, valor in argumentos.items():
        valor = valor.strip() if isinstance(valor, str) else valor
        if valor in ("", None) and clave not in requeridos:
            continue
        limpios[clave] = valor
    return limpios


# Campos editables de una acción propuesta; devuelve los argumentos editados.
def _campos_accion(p):
    k, a, nombre = p["id"], p["argumentos"], p["nombre"]
    if nombre == "registrar_contacto_en_crm":
        c1, c2 = st.columns(2)
        datos = {
            "nombre": c1.text_input("Nombre", a.get("nombre", ""), key=f"{k}_nombre"),
            "correo": c2.text_input("Correo", a.get("correo", ""), key=f"{k}_correo"),
            "empresa": c1.text_input("Empresa", a.get("empresa", ""), key=f"{k}_empresa"),
            "cargo": c2.text_input("Cargo", a.get("cargo", ""), key=f"{k}_cargo"),
            "telefono": c1.text_input("Teléfono", a.get("telefono", ""), key=f"{k}_telefono"),
        }
        estados = ["", "prospecto", "cliente", "inactivo"]
        datos["estado"] = c2.selectbox(
            "Estado", estados, index=estados.index(a.get("estado") or ""), key=f"{k}_estado",
            format_func=lambda v: v.capitalize() if v else "Sin indicar",
        )
        datos["notas"] = st.text_area("Notas", a.get("notas", ""), key=f"{k}_notas", height=90)
    elif nombre == "crear_tarea":
        prioridades = ["baja", "media", "alta", "urgente"]
        limite = a.get("fecha_limite")
        c1, c2 = st.columns(2)
        datos = {
            "titulo": st.text_input("Título", a.get("titulo", ""), key=f"{k}_titulo", max_chars=200),
            "descripcion": st.text_area("Descripción", a.get("descripcion", ""), key=f"{k}_desc", height=90),
            "prioridad": c1.selectbox("Prioridad", prioridades, index=prioridades.index(a["prioridad"]),
                                      key=f"{k}_prioridad", format_func=str.capitalize),
        }
        fecha = c2.date_input("Fecha límite", datetime.strptime(limite, "%Y-%m-%d").date() if limite else None,
                              key=f"{k}_limite", format="YYYY-MM-DD")
        datos["fecha_limite"] = f"{fecha:%Y-%m-%d}" if fecha else ""
        datos["correo_contacto"] = st.text_input("Correo del contacto", a.get("correo_contacto", ""),
                                                 key=f"{k}_contacto")
    else:
        inicio = datetime.strptime(a["fecha_inicio"], "%Y-%m-%dT%H:%M")
        datos = {
            "titulo": st.text_input("Título", a.get("titulo", ""), key=f"{k}_titulo", max_chars=200),
            "descripcion": st.text_area("Temas a tratar", a.get("descripcion", ""), key=f"{k}_desc", height=90),
        }
        c1, c2, c3 = st.columns(3)
        fecha = c1.date_input("Fecha", inicio.date(), key=f"{k}_fecha", format="YYYY-MM-DD")
        hora = c2.time_input("Hora", inicio.time(), key=f"{k}_hora", step=900)
        datos["duracion_minutos"] = int(c3.number_input(
            "Duración (min)", 15, 240, int(a["duracion_minutos"]), 15, key=f"{k}_duracion"))
        datos["fecha_inicio"] = f"{fecha:%Y-%m-%d}T{hora:%H:%M}" if fecha and hora else ""
        modalidades = ["virtual", "presencial"]
        datos["modalidad"] = c1.selectbox("Modalidad", modalidades, index=modalidades.index(a["modalidad"]),
                                          key=f"{k}_modalidad", format_func=str.capitalize)
        datos["correo_contacto"] = st.text_input("Correo del contacto", a.get("correo_contacto", ""),
                                                 key=f"{k}_contacto")
        datos["fecha_confirmada_por_cliente"] = a["fecha_confirmada_por_cliente"]
    return _limpiar_argumentos(nombre, datos)


def _render_acciones_propuestas(run):
    with st.form("form_acciones"):
        st.markdown(
            '<div class="utp-form-titulo">Acciones propuestas</div>'
            '<div class="utp-form-subtitulo">Revisa, corrige si hace falta y aprueba o rechaza cada acción.</div>',
            unsafe_allow_html=True,
        )
        decisiones = {}
        for i, p in enumerate(run["pendientes"]):
            with st.container(key=f"accion_{i}"):
                st.markdown(f'<div class="utp-accion-tipo">{TITULOS_ACCION[p["nombre"]]}</div>',
                            unsafe_allow_html=True)
                if p["nombre"] == "agendar_reunion" and not p["argumentos"]["fecha_confirmada_por_cliente"]:
                    st.warning("Horario propuesto por el asistente, pendiente de confirmar con el cliente.")
                argumentos = _campos_accion(p)
                decision = st.radio("Decisión", ["Aprobar", "Rechazar"], horizontal=True,
                                    key=f"{p['id']}_decision")
                decisiones[p["id"]] = {"aprobado": decision == "Aprobar", "argumentos": argumentos}
        col_si, col_no = st.columns(2)
        confirmar = col_si.form_submit_button("Confirmar acciones", type="primary", width="stretch")
        cancelar = col_no.form_submit_button("Cancelar procesamiento", width="stretch")

    if cancelar:
        st.session_state["ejecucion"] = cancelar_ejecucion(run)
        st.rerun()
    if confirmar:
        errores = validar_decisiones(run, decisiones)
        if errores:
            for p in run["pendientes"]:
                if p["id"] in errores:
                    st.error(f"Revisa «{TITULOS_ACCION[p['nombre']]}»: " + " ".join(errores[p["id"]]))
            return
        _avanzar_con_spinner(run, reanudar_tras_confirmacion, decisiones)


# Escapa HTML y el $ (Streamlit lo interpreta como fórmula).
def _escapar(texto):
    return html.escape(texto or "").replace("$", "&#36;")


# Resumen del modelo con los títulos de sección destacados.
def _html_resumen(texto):
    bloques = []
    for linea in texto.splitlines():
        linea = linea.strip().replace("**", "")
        if not linea:
            continue
        seccion = SECCIONES_RESUMEN.match(linea)
        if seccion:
            bloques.append(f'<div class="utp-resumen-titulo">{seccion.group(1).upper()}</div>')
            linea = seccion.group(2)
        if linea:
            bloques.append(f"<p>{_escapar(linea)}</p>")
    return ('<div class="utp-tarjeta utp-tarjeta-ancha utp-resumen">'
            '<div class="utp-tarjeta-titulo">Resumen del asistente</div>' + "".join(bloques) + "</div>")


# Lista de lo creado (contacto, tareas y reunión).
def _html_creados(creados):
    filas = []
    for c in creados:
        a, r = c["argumentos"], c["resultado"]
        if c["nombre"] == "registrar_contacto_en_crm":
            detalle = " · ".join(html.escape(v) for v in (a.get("empresa"), a.get("correo")) if v)
            etiqueta = f'Contacto {"creado" if r.get("accion") == "creado" else "actualizado"}'
            titulo, meta = a["nombre"], f"<span>{detalle}</span>"
        elif c["nombre"] == "crear_tarea":
            vence = f'Vence {formato_fecha_corta(datetime.strptime(a["fecha_limite"], "%Y-%m-%d"))}' \
                if a.get("fecha_limite") else "Sin fecha límite"
            etiqueta, titulo = "Tarea", a["titulo"]
            meta = (f'<span class="utp-prioridad utp-prioridad-{a["prioridad"]}">{a["prioridad"]}</span>'
                    f"<span>{vence}</span>")
        else:
            inicio = datetime.strptime(a["fecha_inicio"], "%Y-%m-%dT%H:%M")
            etiqueta, titulo = "Reunión", a["titulo"]
            meta = (f"<span>{formato_fecha_hora(inicio)} · {a['duracion_minutos']} min</span>"
                    f'<span class="utp-chip">{a["modalidad"]}</span>')
        filas.append(
            f'<div class="utp-item"><div class="utp-item-fecha">{etiqueta}</div>'
            f'<div class="utp-item-titulo">{html.escape(titulo)}</div>'
            f'<div class="utp-item-meta">{meta}</div></div>'
        )
    contenido = "".join(filas) or _html_vacio("No se creó ningún registro.")
    return ('<div class="utp-tarjeta utp-tarjeta-ancha">'
            f'<div class="utp-tarjeta-titulo">Registros creados</div>{contenido}</div>')


# JSON guardado en la traza, con sangría legible.
def _json_legible(texto):
    try:
        return json.dumps(json.loads(texto), ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(texto)


# Pasos de una ejecución en orden: tipo, función, argumentos y resultado.
def _render_pasos(pasos):
    for i, paso in enumerate(pasos, 1):
        funcion = f' · {paso["nombre_funcion"]}' if paso["nombre_funcion"] else ""
        st.markdown(
            f'<div class="utp-traza-paso">{i:02d} · {TIPOS_PASO[paso["tipo"]]}{funcion}'
            f'<span>{paso["fecha"]:%H:%M:%S}</span></div>',
            unsafe_allow_html=True,
        )
        for etiqueta in ("argumentos", "resultado"):
            if paso[etiqueta]:
                st.caption(etiqueta.capitalize())
                st.code(_json_legible(paso[etiqueta]), language="json")


def _render_traza(run):
    with st.expander("Ver traza de la ejecución"):
        _render_pasos(obtener_pasos(run["ejecucion_id"], st.session_state["usuario_id"]))


def _render_completado(run):
    st.markdown(_html_resumen(run["resumen"]) + _html_creados(run["creados"]), unsafe_allow_html=True)
    _render_traza(run)
    st.button("Procesar otro correo", key="pc_otro", type="primary", on_click=_limpiar_procesamiento)


def _render_fallido(run):
    st.error(run["error"])
    col_reintentar, col_otro = st.columns(2)
    if col_reintentar.button("Reintentar", key="pc_reintentar", type="primary", width="stretch"):
        _avanzar_con_spinner(reintentar_ejecucion(run), avanzar_ejecucion)
    col_otro.button("Procesar otro correo", key="pc_otro", width="stretch", on_click=_limpiar_procesamiento)


def _render_cancelado(run):
    st.info("Procesamiento cancelado. El correo quedó guardado como pendiente.")
    st.button("Procesar otro correo", key="pc_otro", type="primary", on_click=_limpiar_procesamiento)


def render_procesar():
    render_cabecera(meta="UTPConsult · Sistema interno")
    render_navegacion_interna("procesar")
    with st.container(key="contenido"):
        st.markdown(
            '<div class="utp-eyebrow">Asistente de IA</div>'
            '<div class="utp-titulo">Procesar correo</div>'
            '<p class="utp-subtitulo">El asistente lee el correo y propone contactos, tareas y '
            "reuniones para que los apruebes.</p>",
            unsafe_allow_html=True,
        )
        run = st.session_state.get("ejecucion")
        if run is None:
            _render_formulario_correo()
        elif run["estado"] == "en_cola":
            st.markdown(_html_estado_run("en_cola"), unsafe_allow_html=True)
            _avanzar_con_spinner(run, avanzar_ejecucion)
        else:
            st.markdown(_html_estado_run(run["estado"]), unsafe_allow_html=True)
            pantallas = {"requiere_accion": _render_acciones_propuestas, "completado": _render_completado,
                         "fallido": _render_fallido, "cancelado": _render_cancelado}
            if run["estado"] in pantallas:
                pantallas[run["estado"]](run)
            else:
                st.button("Procesar otro correo", key="pc_otro", on_click=_limpiar_procesamiento)
    render_pie()


# --- Calendario ---
VISTAS_CAL = [("mes", "Mes"), ("semana", "Semana"), ("agenda", "Agenda")]
HORA_INICIO_SEM, HORA_FIN_SEM, PX_HORA = 8, 19, 48
DIAS_LARGOS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ESTADOS_EVENTO = {"confirmada": "Confirmada", "por-confirmar": "Por confirmar",
                  "realizada": "Realizada", "cancelada": "Cancelada"}
CAMPOS_REUNION = {"titulo": "título", "descripcion": "descripción", "fecha_inicio": "fecha y hora",
                  "duracion_minutos": "duración", "parámetro": "campo"}
HTML_LEYENDA = '<div class="utp-cal-leyenda">' + "".join(
    f'<span><i class="utp-ev utp-ev-{c}"></i>{t}</span>' for c, t in ESTADOS_EVENTO.items()) + "</div>"


def _hoy_lima():
    return ahora_lima().date()


def _lunes(dia):
    return dia - timedelta(days=dia.weekday())


def _inicio_dia(dia):
    return datetime.combine(dia, dtime())


def _fecha_larga(dia, anio=False):
    return f"{dia.day} de {MESES_ES[dia.month - 1]}" + (f" de {dia.year}" if anio else "")


# Rango [desde, hasta) de fechas que muestra la vista.
def _rango_vista(vista, ref):
    if vista == "mes":
        primero = ref.replace(day=1)
        ultimo = (primero + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        return _lunes(primero), _lunes(ultimo) + timedelta(days=7)
    if vista == "semana":
        return _lunes(ref), _lunes(ref) + timedelta(days=7)
    return ref, ref + timedelta(days=30)


def _titulo_periodo(vista, ref):
    if vista == "mes":
        return f"{MESES_ES[ref.month - 1].capitalize()} de {ref.year}"
    desde, hasta = _rango_vista(vista, ref)
    fin = hasta - timedelta(days=1)
    if vista == "semana":
        if desde.month == fin.month:
            return f"Semana del {desde.day} al {fin.day} de {MESES_ES[fin.month - 1]}"
        return f"Semana del {_fecha_larga(desde)} al {_fecha_larga(fin)}"
    return f"Del {_fecha_larga(desde)} al {_fecha_larga(fin, anio=True)}"


def _inicializar_calendario():
    hoy = _hoy_lima()
    st.session_state.setdefault("cal_vista", "mes")
    st.session_state.setdefault("cal_fecha", hoy)
    st.session_state.setdefault("cal_dia", hoy)


# Callbacks de navegación: -1 anterior, 0 hoy, +1 siguiente.
def _mover_calendario(paso):
    vista, ref, hoy = st.session_state["cal_vista"], st.session_state["cal_fecha"], _hoy_lima()
    if paso == 0:
        nueva = hoy
    elif vista == "mes":
        primero = ref.replace(day=1)
        nueva = ((primero + timedelta(days=32)) if paso > 0 else (primero - timedelta(days=1))).replace(day=1)
        if (nueva.year, nueva.month) == (hoy.year, hoy.month):
            nueva = hoy
    else:
        nueva = ref + timedelta(days=paso * (7 if vista == "semana" else 30))
    st.session_state["cal_fecha"] = nueva
    st.session_state["cal_dia"] = nueva


def _cambiar_vista(vista):
    st.session_state["cal_vista"] = vista


def _abrir_formulario(valor):
    st.session_state["cal_form"] = valor
    st.session_state.pop("cal_cancelar", None)


def _cerrar_formulario():
    st.session_state.pop("cal_form", None)


# Clase visual según estado y confirmación.
def _clase_evento(evento):
    if evento["estado"] != "programada":
        return evento["estado"]
    return "confirmada" if evento["confirmada_por_cliente"] else "por-confirmar"


def _recortar(texto, largo):
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def _html_mes(eventos, ref, hoy):
    desde, hasta = _rango_vista("mes", ref)
    por_dia = {}
    for e in eventos:
        por_dia.setdefault(e["fecha_inicio"].date(), []).append(e)
    celdas = [f'<div class="utp-cal-cab">{d}</div>' for d in DIAS_CORTOS_ES]
    dia = desde
    while dia < hasta:
        clases = ["utp-cal-dia"] + (["otro-mes"] if dia.month != ref.month else []) \
            + (["finde"] if dia.weekday() >= 5 else []) + (["hoy"] if dia == hoy else [])
        del_dia = por_dia.get(dia, [])
        etiquetas = "".join(
            f'<div class="utp-ev utp-ev-{_clase_evento(e)}" title="{html.escape(e["titulo"])}">'
            f'{e["fecha_inicio"]:%H:%M} {html.escape(_recortar(e["titulo"], 22))}</div>'
            for e in del_dia[:3]
        )
        if len(del_dia) > 3:
            etiquetas += f'<div class="utp-cal-mas">+{len(del_dia) - 3} más</div>'
        celdas.append(f'<div class="{" ".join(clases)}"><div class="utp-cal-num">{dia.day}</div>{etiquetas}</div>')
        dia += timedelta(days=1)
    return f'<div class="utp-cal-scroll"><div class="utp-cal-mes">{"".join(celdas)}</div></div>'


# Reparte eventos solapados del mismo día en carriles: [(evento, carril, total)].
def _carriles(eventos):
    fines, asignados = [], []
    for e in sorted(eventos, key=lambda x: x["fecha_inicio"]):
        for i, fin in enumerate(fines):
            if fin <= e["fecha_inicio"]:
                fines[i] = e["fecha_fin"]
                asignados.append((e, i))
                break
        else:
            fines.append(e["fecha_fin"])
            asignados.append((e, len(fines) - 1))
    return [(e, i, max(len(fines), 1)) for e, i in asignados]


def _html_semana(eventos, ref, hoy):
    desde, _ = _rango_vista("semana", ref)
    dias = [desde + timedelta(days=i) for i in range(7)]
    alto = (HORA_FIN_SEM - HORA_INICIO_SEM) * PX_HORA
    partes = ['<div class="utp-sem-cab"></div>'] + [
        f'<div class="utp-sem-cab{" hoy" if d == hoy else ""}">{DIAS_CORTOS_ES[i]} <strong>{d.day}</strong></div>'
        for i, d in enumerate(dias)
    ]
    horas = "".join(f'<div class="utp-sem-hora" style="top:{(h - HORA_INICIO_SEM) * PX_HORA}px">{h:02d}:00</div>'
                    for h in range(HORA_INICIO_SEM, HORA_FIN_SEM))
    partes.append(f'<div class="utp-sem-horas" style="height:{alto}px">{horas}</div>')
    for i, dia in enumerate(dias):
        base = datetime.combine(dia, dtime(HORA_INICIO_SEM))
        contenido = ""
        if i < 5:
            contenido += (f'<div class="utp-sem-laboral" style="top:{(9 - HORA_INICIO_SEM) * PX_HORA}px;'
                          f'height:{9 * PX_HORA}px"></div>')
        del_dia = [e for e in eventos if e["fecha_inicio"].date() == dia]
        for e, carril, total in _carriles(del_dia):
            inicio = max(e["fecha_inicio"], base)
            fin = min(e["fecha_fin"], datetime.combine(dia, dtime(HORA_FIN_SEM)))
            if fin <= inicio:
                continue
            top = (inicio - base).total_seconds() / 3600 * PX_HORA
            altura = max((fin - inicio).total_seconds() / 3600 * PX_HORA, 22)
            clase = _clase_evento(e)
            empresa = f'<em>{html.escape(e["contacto_empresa"])}</em>' if e["contacto_empresa"] else ""
            marca = '<b class="utp-marca-confirmar">Por confirmar</b>' if clase == "por-confirmar" else ""
            contenido += (
                f'<div class="utp-ev utp-ev-{clase} utp-sem-ev" title="{html.escape(e["titulo"])}" '
                f'style="top:{top:.0f}px;height:{altura:.0f}px;left:calc({100 * carril / total:.2f}% + 2px);'
                f'width:calc({100 / total:.2f}% - 4px)">'
                f'<span>{e["fecha_inicio"]:%H:%M}–{e["fecha_fin"]:%H:%M}</span>'
                f'<strong>{html.escape(e["titulo"])}</strong>{empresa}{marca}</div>'
            )
        partes.append(f'<div class="utp-sem-col{" finde" if i >= 5 else ""}" style="height:{alto}px">{contenido}</div>')
    return f'<div class="utp-cal-scroll"><div class="utp-cal-semana">{"".join(partes)}</div></div>'


def _html_meta_evento(e, mostrar_responsable):
    clase = _clase_evento(e)
    contacto = " · ".join(html.escape(v) for v in (e["contacto_nombre"], e["contacto_empresa"]) if v)
    partes = [f"<span>{contacto}</span>" if contacto else "",
              f'<span class="utp-chip">{e["modalidad"]}</span>',
              f'<span class="utp-chip utp-chip-{clase}">{ESTADOS_EVENTO[clase]}</span>',
              f'<span class="utp-responsable">Resp.: {html.escape(e["responsable"])}</span>' if mostrar_responsable else ""]
    return f'<div class="utp-item-meta">{"".join(partes)}</div>'


def _html_agenda(eventos, mostrar_responsable):
    if not eventos:
        return f'<div class="utp-agenda-dia">{_html_vacio("No hay reuniones en estos 30 días.")}</div>'
    grupos = {}
    for e in eventos:
        grupos.setdefault(e["fecha_inicio"].date(), []).append(e)
    bloques = []
    for dia, lista in grupos.items():
        filas = "".join(
            f'<div class="utp-agenda-fila utp-agenda-{_clase_evento(e)}">'
            f'<div class="utp-agenda-hora">{e["fecha_inicio"]:%H:%M}–{e["fecha_fin"]:%H:%M}</div>'
            f'<div><div class="utp-item-titulo">{html.escape(e["titulo"])}</div>'
            f"{_html_meta_evento(e, mostrar_responsable)}</div></div>"
            for e in lista
        )
        bloques.append(f'<div class="utp-agenda-dia"><div class="utp-agenda-fecha">'
                       f'{DIAS_LARGOS_ES[dia.weekday()].capitalize()} {_fecha_larga(dia)}</div>{filas}</div>')
    return "".join(bloques)


# Acciones de las tarjetas del detalle del día (callback). El servidor valida permisos.
def _accion_evento(accion, evento_id):
    actor = st.session_state["usuario_id"]
    if accion == "pedir_cancelar":
        st.session_state["cal_cancelar"] = evento_id
        return
    st.session_state.pop("cal_cancelar", None)
    if accion == "volver":
        return
    if accion == "confirmar":
        ok, texto = marcar_confirmada(evento_id, actor)
    elif accion == "realizada":
        ok, texto = cambiar_estado_evento(evento_id, "realizada", actor, ahora_lima())
    else:
        ok, texto = cambiar_estado_evento(evento_id, "cancelada", actor)
    st.session_state["flash_cal_ok" if ok else "flash_cal_error"] = texto


def _puede_gestionar(evento):
    return es_admin() or evento["usuario_id"] == st.session_state["usuario_id"]


def _render_tarjeta_evento(e, mostrar_responsable):
    clase, eid = _clase_evento(e), e["id"]
    etiquetas = ""
    if e["correo_id"]:
        etiquetas += '<span class="utp-chip utp-chip-ia">Creada por UTP Assistant</span>'
    if clase == "por-confirmar":
        etiquetas += '<span class="utp-marca-confirmar">Por confirmar</span>'
    lineas = [f'<div class="utp-item-fecha">{formato_fecha_corta(e["fecha_inicio"])} · '
              f'{e["fecha_inicio"]:%H:%M}–{e["fecha_fin"]:%H:%M}</div>',
              f'<div class="utp-item-titulo utp-ev-titulo-{clase}">{html.escape(e["titulo"])}</div>',
              _html_meta_evento(e, mostrar_responsable)]
    if e["descripcion"]:
        lineas.append(f'<p class="utp-cal-desc">{html.escape(e["descripcion"])}</p>')
    if e["correo_asunto"]:
        lineas.append(f'<div class="utp-cal-origen">Correo de origen: «{html.escape(e["correo_asunto"])}»</div>')
    if etiquetas:
        lineas.append(f'<div class="utp-item-meta">{etiquetas}</div>')
    with st.container(key=f"cal_ev_{eid}"):
        st.markdown("".join(lineas), unsafe_allow_html=True)
        if not (_puede_gestionar(e) and e["estado"] == "programada"):
            return
        with st.container(horizontal=True, gap="small"):
            if not e["confirmada_por_cliente"]:
                st.button("Confirmar con cliente", key=f"cal_conf_{eid}", on_click=_accion_evento, args=("confirmar", eid))
            st.button("Editar", key=f"cal_edit_{eid}", on_click=_abrir_formulario, args=(eid,))
            if e["fecha_inicio"] <= ahora_lima():
                st.button("Marcar como realizada", key=f"cal_real_{eid}", on_click=_accion_evento, args=("realizada", eid))
            st.button("Cancelar reunión", key=f"cal_canc_{eid}", on_click=_accion_evento, args=("pedir_cancelar", eid))
        if st.session_state.get("cal_cancelar") == eid:
            st.warning(f"¿Cancelar la reunión «{e['titulo']}»? Seguirá visible como cancelada.")
            with st.container(horizontal=True, gap="small"):
                st.button("Sí, cancelar reunión", key=f"cal_canc_si_{eid}", type="primary",
                          on_click=_accion_evento, args=("cancelar", eid))
                st.button("Volver", key=f"cal_canc_no_{eid}", on_click=_accion_evento, args=("volver", eid))


def _render_detalle_dia(alcance, mostrar_responsable):
    st.markdown('<div class="utp-seccion-titulo">Detalle del día</div>', unsafe_allow_html=True)
    columna, _ = st.columns([1.2, 2.8])
    with columna:
        dia = st.date_input("Ver día", key="cal_dia", format="YYYY-MM-DD")
    eventos = obtener_eventos_rango(alcance, _inicio_dia(dia), _inicio_dia(dia + timedelta(days=1)))
    st.markdown(f'<div class="utp-cal-dia-titulo">{DIAS_LARGOS_ES[dia.weekday()].capitalize()} '
                f"{_fecha_larga(dia, anio=True)}</div>", unsafe_allow_html=True)
    if not eventos:
        st.markdown(f'<div class="utp-tarjeta utp-tarjeta-ancha">{_html_vacio("No hay reuniones este día.")}</div>',
                    unsafe_allow_html=True)
    for e in eventos:
        _render_tarjeta_evento(e, mostrar_responsable)


# Formulario "Nueva reunión" / "Editar" (valida con la misma regla que agendar_reunion).
def _render_formulario_reunion():
    actor = st.session_state["usuario_id"]
    modo = st.session_state["cal_form"]
    evento = None if modo == "nuevo" else obtener_evento(modo)
    if modo != "nuevo" and (evento is None or not _puede_gestionar(evento) or evento["estado"] != "programada"):
        _cerrar_formulario()
        st.session_state["flash_cal_error"] = "No se puede editar esa reunión."
        st.rerun()

    if evento:
        responsable = evento["usuario_id"]
    elif es_admin():
        activos = {u["id"]: u["nombre"] for u in listar_usuarios_activos()}
        ids = list(activos)
        with st.container(key="cal_responsable_wrap"):
            responsable = st.selectbox("Responsable", ids, key="cal_responsable",
                                       index=ids.index(actor) if actor in ids else 0,
                                       format_func=lambda i: activos[i])
    else:
        responsable = actor
    contactos = {c["id"]: c for c in listar_contactos(responsable)}
    opciones_contacto = [None] + list(contactos)

    if evento:
        inicio = evento["fecha_inicio"]
        duracion = int((evento["fecha_fin"] - evento["fecha_inicio"]).total_seconds() // 60)
    else:
        dia = st.session_state.get("cal_dia") or _hoy_lima()
        inicio, duracion = datetime.combine(max(dia, _hoy_lima()), dtime(10)), 60
    contacto_actual = evento["contacto_id"] if evento and evento["contacto_id"] in contactos else None

    with st.form("form_reunion"):
        st.markdown(f'<div class="utp-form-titulo">{"Editar reunión" if evento else "Nueva reunión"}</div>'
                    '<div class="utp-form-subtitulo">Lunes a viernes, de 09:00 a 18:00 (hora de Lima).</div>',
                    unsafe_allow_html=True)
        titulo = st.text_input("Título", evento["titulo"] if evento else "", max_chars=200)
        descripcion = st.text_area("Descripción", (evento["descripcion"] or "") if evento else "", height=90)
        c1, c2, c3 = st.columns(3)
        fecha = c1.date_input("Fecha", inicio.date(), format="YYYY-MM-DD")
        hora = c2.time_input("Hora de inicio", inicio.time(), step=900)
        minutos = c3.number_input("Duración (min)", 15, 240, min(max(duracion, 15), 240), 15)
        c4, c5 = st.columns(2)
        modalidades = ["virtual", "presencial"]
        modalidad = c4.selectbox("Modalidad", modalidades, format_func=str.capitalize,
                                 index=modalidades.index(evento["modalidad"]) if evento else 0)
        contacto_id = c5.selectbox(
            "Contacto (opcional)", opciones_contacto, index=opciones_contacto.index(contacto_actual),
            format_func=lambda i: "Sin contacto" if i is None else " · ".join(
                v for v in (contactos[i]["nombre"], contactos[i]["empresa"]) if v))
        col_g, col_c = st.columns(2)
        guardar = col_g.form_submit_button("Guardar reunión", type="primary", width="stretch")
        cancelar = col_c.form_submit_button("Cancelar", width="stretch")

    if cancelar:
        _cerrar_formulario()
        st.rerun()
    if not guardar:
        return
    argumentos = {
        "titulo": titulo.strip(), "descripcion": descripcion.strip(),
        "fecha_inicio": f"{fecha:%Y-%m-%d}T{hora:%H:%M}" if fecha and hora else "",
        "duracion_minutos": int(minutos), "modalidad": modalidad, "fecha_confirmada_por_cliente": True,
    }
    errores = validar_argumentos("agendar_reunion", argumentos, responsable,
                                 excluir_evento_id=evento["id"] if evento else None)
    if errores:
        for campo, nombre in CAMPOS_REUNION.items():
            errores = [e.replace(campo, nombre) for e in errores]
        st.error("Revisa los siguientes datos:\n\n" + "\n".join(f"- {e}" for e in errores))
        return
    inicio = datetime.strptime(argumentos["fecha_inicio"], "%Y-%m-%dT%H:%M")
    fin = inicio + timedelta(minutes=argumentos["duracion_minutos"])
    if evento:
        ok, texto = actualizar_evento(evento["id"], actor, argumentos["titulo"], argumentos["descripcion"],
                                      inicio, fin, modalidad, contacto_id)
    else:
        ok, resultado = crear_evento_manual(actor, responsable, argumentos["titulo"], argumentos["descripcion"],
                                            inicio, fin, modalidad, contacto_id)
        texto = "Reunión creada." if ok else resultado
    st.session_state["flash_cal_ok" if ok else "flash_cal_error"] = texto
    if ok:
        _cerrar_formulario()
        st.session_state["cal_dia"] = inicio.date()
    st.rerun()


def render_calendario():
    _inicializar_calendario()
    render_cabecera(meta="UTPConsult · Sistema interno")
    render_navegacion_interna("calendario")
    with st.container(key="contenido"):
        vista, ref, hoy = st.session_state["cal_vista"], st.session_state["cal_fecha"], _hoy_lima()
        st.markdown(
            '<div class="utp-eyebrow">Agenda del equipo</div>'
            '<div class="utp-titulo">Calendario</div>'
            f'<div class="utp-cal-periodo">{_titulo_periodo(vista, ref)}</div>'
            f'<style>.st-key-cal_vistas .st-key-cal_vista_{vista} button[data-testid="stBaseButton-tertiary"]'
            "{border-bottom-color: var(--utp-rojo) !important; color: var(--utp-blanco) !important;}</style>",
            unsafe_allow_html=True,
        )
        for clave, mostrar in (("flash_cal_ok", st.success), ("flash_cal_error", st.error)):
            mensaje = st.session_state.pop(clave, None)
            if mensaje:
                mostrar(mensaje)

        if es_admin():
            _render_selector_alcance("Ver calendario de:", "alcance_calendario")
        alcance = obtener_alcance("alcance_calendario")
        mostrar_responsable = alcance is None

        with st.container(key="cal_barra", horizontal=True, vertical_alignment="center"):
            with st.container(key="cal_vistas", horizontal=True, width="content", gap=None):
                for clave, etiqueta in VISTAS_CAL:
                    st.button(etiqueta, key=f"cal_vista_{clave}", type="tertiary",
                              on_click=_cambiar_vista, args=(clave,))
            with st.container(key="cal_nav", horizontal=True, horizontal_alignment="right",
                              vertical_alignment="center", gap="small"):
                st.button("← Anterior", key="cal_ant", type="tertiary", on_click=_mover_calendario, args=(-1,))
                st.button("Hoy", key="cal_hoy", type="tertiary", on_click=_mover_calendario, args=(0,))
                st.button("Siguiente →", key="cal_sig", type="tertiary", on_click=_mover_calendario, args=(1,))
                st.button("Nueva reunión", key="cal_nueva", type="primary", on_click=_abrir_formulario,
                          args=("nuevo",))

        if st.session_state.get("cal_form"):
            _render_formulario_reunion()

        desde, hasta = _rango_vista(vista, ref)
        eventos = obtener_eventos_rango(alcance, _inicio_dia(desde), _inicio_dia(hasta))
        if vista == "mes":
            cuerpo = _html_mes(eventos, ref, hoy)
        elif vista == "semana":
            cuerpo = _html_semana(eventos, ref, hoy)
        else:
            cuerpo = _html_agenda(eventos, mostrar_responsable)
        st.markdown(f'<div class="utp-cal">{cuerpo}{HTML_LEYENDA}</div>', unsafe_allow_html=True)

        if vista != "agenda":
            _render_detalle_dia(alcance, mostrar_responsable)
    render_pie()


# --- Correos ---
POR_PAGINA = 10
ETIQUETAS_ESTADO_CORREO = {"": "Todos", "procesado": "Procesado", "pendiente": "Pendiente", "error": "Error"}
ETIQUETAS_ESTADO_TAREA = {"pendiente": "Pendiente", "en_progreso": "En progreso", "completada": "Completada"}
COLUMNAS_CSV = ["fecha", "remitente", "correo", "asunto", "estado", "resumen", "tareas", "reuniones",
                "responsable"]


def _reiniciar_pagina():
    st.session_state["co_pagina"] = 1


def _limpiar_filtros():
    for clave in ("co_texto", "co_estado", "co_desde", "co_hasta"):
        st.session_state.pop(clave, None)
    _reiniciar_pagina()


def _cambiar_pagina(paso):
    st.session_state["co_pagina"] = st.session_state.get("co_pagina", 1) + paso


def _abrir_detalle(correo_id):
    st.session_state["co_detalle"] = correo_id
    st.session_state.pop("co_confirmar", None)


def _cerrar_detalle():
    st.session_state.pop("co_detalle", None)
    st.session_state.pop("co_confirmar", None)


def _filtros_correos():
    return {"texto": st.session_state.get("co_texto", ""), "estado": st.session_state.get("co_estado", ""),
            "desde": st.session_state.get("co_desde"), "hasta": st.session_state.get("co_hasta")}


def _chip_estado_correo(estado):
    return f'<span class="utp-chip utp-co-{estado}">{ETIQUETAS_ESTADO_CORREO[estado]}</span>'


# CSV de los correos filtrados (sin paginar), en utf-8-sig para Excel.
def _csv_correos(alcance, filtros):
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(COLUMNAS_CSV)
    for c in buscar_correos(alcance, filtros, limite=None):
        escritor.writerow([f'{c["fecha_recepcion"]:%Y-%m-%d %H:%M}', c["remitente_nombre"] or "",
                           c["remitente_correo"] or "", c["asunto"] or "", c["estado"], c["resumen"] or "",
                           c["num_tareas"], c["num_reuniones"], c["responsable"]])
    return salida.getvalue().encode("utf-8-sig")


def _render_filtros_correos(alcance):
    with st.container(key="co_filtros"):
        c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])
        c1.text_input("Buscar", key="co_texto", placeholder="Asunto, remitente o contenido",
                      on_change=_reiniciar_pagina)
        c2.selectbox("Estado", list(ETIQUETAS_ESTADO_CORREO), key="co_estado",
                     format_func=ETIQUETAS_ESTADO_CORREO.get, on_change=_reiniciar_pagina)
        c3.date_input("Desde", value=None, key="co_desde", format="YYYY-MM-DD", on_change=_reiniciar_pagina)
        c4.date_input("Hasta", value=None, key="co_hasta", format="YYYY-MM-DD", on_change=_reiniciar_pagina)
        with st.container(horizontal=True, gap="small"):
            st.button("Limpiar filtros", key="co_limpiar", on_click=_limpiar_filtros)
            st.download_button("Exportar CSV", data=_csv_correos(alcance, _filtros_correos()),
                               file_name=f"correos_{_hoy_lima():%Y%m%d}.csv", mime="text/csv",
                               key="co_exportar")


def _render_fila_correo(c, mostrar_responsable):
    remitente = _escapar(c["remitente_nombre"] or "Remitente desconocido")
    correo = f'<span class="utp-co-correo">{_escapar(c["remitente_correo"])}</span>' if c["remitente_correo"] else ""
    generados = f'{c["num_tareas"]} tarea{"s" if c["num_tareas"] != 1 else ""} · ' \
                f'{c["num_reuniones"]} reunión{"es" if c["num_reuniones"] != 1 else ""}'
    meta = [_chip_estado_correo(c["estado"]), f"<span>{generados}</span>"]
    if mostrar_responsable:
        meta.append(f'<span class="utp-responsable">Resp.: {_escapar(c["responsable"])}</span>')
    with st.container(key=f"co_fila_{c['id']}"):
        texto, boton = st.columns([5, 1.2], vertical_alignment="center")
        texto.markdown(
            f'<div class="utp-item-fecha">{formato_fecha_hora(c["fecha_recepcion"])}</div>'
            f'<div class="utp-item-titulo">{remitente} {correo}</div>'
            f'<div class="utp-co-asunto-fila">{_escapar(c["asunto"] or "Sin asunto")}</div>'
            f'<div class="utp-item-meta">{"".join(meta)}</div>',
            unsafe_allow_html=True,
        )
        boton.button("Ver detalle", key=f"co_ver_{c['id']}", type="tertiary",
                     on_click=_abrir_detalle, args=(c["id"],))


def _render_listado_correos():
    if es_admin():
        _render_selector_alcance("Ver correos de:", "alcance_correos", al_cambiar=_reiniciar_pagina)
    alcance = obtener_alcance("alcance_correos")
    filtros = _filtros_correos()
    resumen = resumen_correos(alcance, filtros)
    st.markdown(_html_metricas([(resumen["total"], "Total"), (resumen["procesado"], "Procesados"),
                                (resumen["pendiente"], "Pendientes"), (resumen["error"], "Con error")]),
                unsafe_allow_html=True)
    _render_filtros_correos(alcance)
    if filtros["desde"] and filtros["hasta"] and filtros["desde"] > filtros["hasta"]:
        st.warning("La fecha «Desde» es posterior a «Hasta».")

    total = contar_correos(alcance, filtros)
    paginas = max(1, math.ceil(total / POR_PAGINA))
    pagina = min(max(st.session_state.get("co_pagina", 1), 1), paginas)
    st.session_state["co_pagina"] = pagina
    correos = buscar_correos(alcance, filtros, POR_PAGINA, (pagina - 1) * POR_PAGINA)
    if not correos:
        st.markdown(f'<div class="utp-tarjeta utp-tarjeta-ancha">'
                    f'{_html_vacio("No hay correos que coincidan con la búsqueda.")}</div>',
                    unsafe_allow_html=True)
        return
    for c in correos:
        _render_fila_correo(c, alcance is None)
    with st.container(key="co_paginacion", horizontal=True, horizontal_alignment="center",
                      vertical_alignment="center", gap="medium"):
        st.button("← Anterior", key="co_anterior", type="tertiary", disabled=pagina <= 1,
                  on_click=_cambiar_pagina, args=(-1,))
        st.markdown(f'<span class="utp-co-pagina">Página {pagina} de {paginas}</span>',
                    unsafe_allow_html=True)
        st.button("Siguiente →", key="co_siguiente", type="tertiary", disabled=pagina >= paginas,
                  on_click=_cambiar_pagina, args=(1,))


# Lleva al calendario en la fecha de la reunión (callback).
def _ver_en_calendario(dia, usuario_id):
    st.session_state.update(cal_vista="mes", cal_fecha=dia, cal_dia=dia, pagina="calendario")
    if es_admin():
        st.session_state["alcance_calendario"] = usuario_id


def _cambiar_estado_tarea(tarea_id):
    ok, texto = actualizar_estado_tarea(tarea_id, st.session_state[f"co_estado_tarea_{tarea_id}"],
                                        st.session_state["usuario_id"])
    st.session_state["flash_co_ok" if ok else "flash_co_error"] = texto


# Reprocesa el correo: nueva ejecución y a la página de procesar (callback).
def _reprocesar_correo(correo_id):
    detalle = obtener_detalle_correo(correo_id, st.session_state["usuario_id"])
    if not detalle:
        st.session_state["flash_co_error"] = "No tienes permiso para reprocesar este correo."
        return
    correo = detalle["correo"]
    run = reintentar_ejecucion({"correo_id": correo["id"], "usuario_id": correo["usuario_id"]})
    _limpiar_procesamiento()
    st.session_state.update(ejecucion=run, pagina="procesar")
    _cerrar_detalle()


def _eliminar_correo(correo_id):
    ok, texto = eliminar_correo(correo_id, st.session_state["usuario_id"])
    st.session_state["flash_co_ok" if ok else "flash_co_error"] = texto
    if ok:
        _cerrar_detalle()


def _confirmar_accion(accion):
    st.session_state["co_confirmar"] = accion


def _render_acciones_correo(detalle):
    correo = detalle["correo"]
    cid = correo["id"]
    confirmar = st.session_state.get("co_confirmar")
    with st.container(horizontal=True, gap="small"):
        if correo["estado"] in ("pendiente", "error"):
            if detalle["tareas"] or detalle["reuniones"]:
                st.button("Reprocesar", key="co_reprocesar", type="primary", on_click=_confirmar_accion,
                          args=("reprocesar",))
            else:
                st.button("Reprocesar", key="co_reprocesar", type="primary", on_click=_reprocesar_correo,
                          args=(cid,))
        st.button("Eliminar correo", key="co_eliminar", on_click=_confirmar_accion, args=("eliminar",))
    if confirmar == "reprocesar":
        st.warning("Este correo ya generó acciones. Reprocesarlo puede crear duplicados.")
        with st.container(horizontal=True, gap="small"):
            st.button("Sí, reprocesar", key="co_reprocesar_si", type="primary", on_click=_reprocesar_correo,
                      args=(cid,))
            st.button("Volver", key="co_reprocesar_no", on_click=_confirmar_accion, args=(None,))
    elif confirmar == "eliminar":
        st.warning("¿Eliminar este correo? Sus tareas, reuniones y el contacto se conservan (quedan sin "
                   "correo de origen); sus ejecuciones y la traza se eliminan. No se puede deshacer.")
        with st.container(horizontal=True, gap="small"):
            st.button("Sí, eliminar correo", key="co_eliminar_si", type="primary", on_click=_eliminar_correo,
                      args=(cid,))
            st.button("Volver", key="co_eliminar_no", on_click=_confirmar_accion, args=(None,))


def _html_contacto(contacto):
    if not contacto:
        return _html_vacio("Este correo no está vinculado a ningún contacto.")
    filas = [("Nombre", contacto["nombre"]), ("Empresa", contacto["empresa"]), ("Cargo", contacto["cargo"]),
             ("Correo", contacto["correo"]), ("Teléfono", contacto["telefono"]),
             ("Estado en el CRM", (contacto["estado"] or "").capitalize())]
    return '<div class="utp-co-datos">' + "".join(
        f"<div><span>{etiqueta}</span>{_escapar(valor)}</div>" for etiqueta, valor in filas if valor) + "</div>"


def _render_tareas_correo(tareas):
    if not tareas:
        st.markdown(f'<div class="utp-tarjeta utp-tarjeta-ancha">{_html_vacio("Este correo no generó tareas.")}</div>',
                    unsafe_allow_html=True)
        return
    for t in tareas:
        vence = f'Vence {formato_fecha_corta(t["fecha_limite"])}' if t["fecha_limite"] else "Sin fecha límite"
        with st.container(key=f"co_tarjeta_tarea_{t['id']}"):
            texto, estado = st.columns([3, 1.3])
            texto.markdown(
                f'<div class="utp-item-titulo">{_escapar(t["titulo"])}</div>'
                f'<div class="utp-item-meta"><span class="utp-prioridad utp-prioridad-{t["prioridad"]}">'
                f'{t["prioridad"]}</span><span>{vence}</span></div>'
                + (f'<p class="utp-cal-desc">{_escapar(t["descripcion"])}</p>' if t["descripcion"] else ""),
                unsafe_allow_html=True,
            )
            opciones = list(ETIQUETAS_ESTADO_TAREA)
            estado.selectbox("Estado", opciones, index=opciones.index(t["estado"]),
                             key=f"co_estado_tarea_{t['id']}", format_func=ETIQUETAS_ESTADO_TAREA.get,
                             on_change=_cambiar_estado_tarea, args=(t["id"],))


def _render_reuniones_correo(reuniones):
    if not reuniones:
        st.markdown(f'<div class="utp-tarjeta utp-tarjeta-ancha">{_html_vacio("Este correo no generó reuniones.")}</div>',
                    unsafe_allow_html=True)
        return
    for r in reuniones:
        clase = _clase_evento(r)
        marca = '<span class="utp-marca-confirmar">Por confirmar</span>' if clase == "por-confirmar" else ""
        with st.container(key=f"co_tarjeta_reu_{r['id']}"):
            texto, boton = st.columns([3, 1.3], vertical_alignment="center")
            texto.markdown(
                f'<div class="utp-item-fecha">{formato_fecha_corta(r["fecha_inicio"])} · '
                f'{r["fecha_inicio"]:%H:%M}–{r["fecha_fin"]:%H:%M}</div>'
                f'<div class="utp-item-titulo utp-ev-titulo-{clase}">{_escapar(r["titulo"])}</div>'
                f'<div class="utp-item-meta"><span class="utp-chip">{r["modalidad"]}</span>'
                f'<span class="utp-chip utp-chip-{clase}">{ESTADOS_EVENTO[clase]}</span>{marca}</div>',
                unsafe_allow_html=True,
            )
            boton.button("Ver en calendario", key=f"co_cal_{r['id']}", on_click=_ver_en_calendario,
                         args=(r["fecha_inicio"].date(), r["usuario_id"]))


def _render_detalle_correo(correo_id):
    st.button("← Volver al listado", key="co_volver", type="tertiary", on_click=_cerrar_detalle)
    detalle = obtener_detalle_correo(correo_id, st.session_state["usuario_id"])
    if not detalle:
        st.error("No tienes acceso a este correo o ya no existe.")
        return
    correo = detalle["correo"]
    remitente = " · ".join(v for v in (correo["remitente_nombre"], correo["remitente_correo"]) if v)
    st.markdown(
        f'<div class="utp-co-asunto">{_escapar(correo["asunto"] or "Sin asunto")}</div>'
        f'<div class="utp-co-cabecera">{_escapar(remitente or "Remitente desconocido")} · '
        f'{formato_fecha_hora(correo["fecha_recepcion"])} · Resp.: {_escapar(correo["responsable"])}'
        f"</div>{_chip_estado_correo(correo['estado'])}",
        unsafe_allow_html=True,
    )
    _render_acciones_correo(detalle)

    st.markdown('<div class="utp-seccion-titulo">Correo original</div>', unsafe_allow_html=True)
    with st.container(key="co_tarjeta_original"):
        st.code(correo["cuerpo"], language=None, wrap_lines=True)

    resumen = _html_resumen(correo["resumen"]) if correo["resumen"] else (
        '<div class="utp-tarjeta utp-tarjeta-ancha"><div class="utp-tarjeta-titulo">Resumen del asistente</div>'
        f'{_html_vacio("Este correo aún no tiene resumen.")}</div>')
    st.markdown(resumen, unsafe_allow_html=True)
    st.markdown('<div class="utp-tarjeta utp-tarjeta-ancha"><div class="utp-tarjeta-titulo">Contacto</div>'
                f'{_html_contacto(detalle["contacto"])}</div>', unsafe_allow_html=True)

    st.markdown('<div class="utp-seccion-titulo">Tareas generadas</div>', unsafe_allow_html=True)
    _render_tareas_correo(detalle["tareas"])
    st.markdown('<div class="utp-seccion-titulo">Reuniones generadas</div>', unsafe_allow_html=True)
    _render_reuniones_correo(detalle["reuniones"])

    st.markdown('<div class="utp-seccion-titulo">Traza de ejecución</div>', unsafe_allow_html=True)
    if not detalle["ejecuciones"]:
        st.markdown(f'<div class="utp-tarjeta utp-tarjeta-ancha">{_html_vacio("Este correo no tiene ejecuciones.")}</div>',
                    unsafe_allow_html=True)
    for ej in detalle["ejecuciones"]:
        with st.expander(f'Ejecución #{ej["id"]} · {formato_fecha_hora(ej["fecha_inicio"])} · '
                         f'{ej["estado"].replace("_", " ")} · {ej["iteraciones"]} iteraciones · {ej["modelo"]}'):
            _render_pasos(ej["pasos"])


def render_correos():
    render_cabecera(meta="UTPConsult · Sistema interno")
    render_navegacion_interna("correos")
    with st.container(key="contenido"):
        st.markdown(
            '<div class="utp-eyebrow">Historial</div>'
            '<div class="utp-titulo">Correos</div>'
            '<p class="utp-subtitulo">Todo lo que llegó de los clientes y lo que el asistente hizo con ello.</p>',
            unsafe_allow_html=True,
        )
        for clave, mostrar in (("flash_co_ok", st.success), ("flash_co_error", st.error)):
            mensaje = st.session_state.pop(clave, None)
            if mensaje:
                mostrar(mensaje)
        if st.session_state.get("co_detalle"):
            _render_detalle_correo(st.session_state["co_detalle"])
        else:
            _render_listado_correos()
    render_pie()


# --- Main ---
def main():
    aplicar_estilos()
    inicializar_sesion()
    obtener_cliente_groq()  # Solo valida la clave; no llama al modelo.
    try:
        # init_db() se ejecuta una sola vez por sesión.
        if not st.session_state.get("db_inicializada"):
            init_db()
            st.session_state["db_inicializada"] = True

        requiere_login()

        pagina = st.session_state["pagina"]
        pantallas = {
            "landing": render_landing,
            "registro": render_registro,
            "login": render_login,
            "dashboard": render_dashboard,
            "procesar": render_procesar,
            "calendario": render_calendario,
            "correos": render_correos,
            "usuarios": render_usuarios,
        }
        pantallas[pagina]()
    except ErrorBaseDatos as error:
        st.error(str(error))
        st.stop()


if __name__ == "__main__":
    main()
