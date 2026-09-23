# --- Imports y configuración de página ---
import html
import json
import math
import re
import time
from datetime import date, datetime

import streamlit as st

from assistant import (
    ESQUEMAS, avanzar_ejecucion, cancelar_ejecucion, iniciar_ejecucion, obtener_cliente_groq,
    reanudar_tras_confirmacion, reintentar_ejecucion, validar_correo_entrante, validar_decisiones,
)
from auth import (
    autenticar_usuario, registrar_acceso, registrar_usuario, validar_login, validar_registro,
)
from db import (
    ErrorBaseDatos, cambiar_estado_usuario, cambiar_rol_usuario, cargar_datos_ejemplo,
    contar_contactos, contar_correos_procesados, contar_reuniones_proximas,
    contar_tareas_pendientes, init_db, listar_usuarios, listar_usuarios_activos,
    obtener_actividad_reciente, obtener_estado_usuario, obtener_pasos, obtener_proximas_reuniones,
    obtener_tareas_pendientes, tiene_datos,
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
def obtener_alcance():
    if not es_admin():
        return st.session_state["usuario_id"]
    elegido = st.session_state.get("alcance_admin")
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
        "<div>Calendario <span>· Fase 4</span></div>"
        "<div>Correos <span>· Fase 5</span></div>"
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


# Selector 'Ver datos de:' (solo admin; por defecto todo el equipo).
def _render_selector_alcance():
    activos = listar_usuarios_activos()
    nombres = {u["id"]: u["nombre"] for u in activos}
    opciones = [None] + list(nombres)
    # Si el usuario elegido ya no está activo, se vuelve a "Todo el equipo".
    if st.session_state.get("alcance_admin") not in opciones:
        st.session_state["alcance_admin"] = None
    with st.container(key="selector_alcance"):
        columna, _ = st.columns([1.4, 2.6])
        with columna:
            st.selectbox(
                "Ver datos de:",
                opciones,
                key="alcance_admin",
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
            bloques.append(f"<p>{html.escape(linea)}</p>")
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


def _render_traza(run):
    with st.expander("Ver traza de la ejecución"):
        for i, paso in enumerate(obtener_pasos(run["ejecucion_id"], st.session_state["usuario_id"]), 1):
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
        else:
            st.markdown(_html_estado_run(run["estado"]), unsafe_allow_html=True)
            pantallas = {"requiere_accion": _render_acciones_propuestas, "completado": _render_completado,
                         "fallido": _render_fallido, "cancelado": _render_cancelado}
            if run["estado"] in pantallas:
                pantallas[run["estado"]](run)
            else:
                st.button("Procesar otro correo", key="pc_otro", on_click=_limpiar_procesamiento)
    render_pie()


# Página de marcador para módulos pendientes.
def render_modulo_pendiente(pagina, titulo, fase, descripcion):
    render_cabecera(meta="UTPConsult · Sistema interno")
    render_navegacion_interna(pagina)
    with st.container(key="contenido"):
        st.markdown(
            f'<div class="utp-eyebrow">Fase {fase}</div>'
            f'<div class="utp-titulo">{titulo}</div>'
            f'<p class="utp-lead">Este módulo estará disponible en la fase {fase}.</p>'
            f'<p class="utp-panel-texto">{descripcion}</p>',
            unsafe_allow_html=True,
        )
    render_pie()


# Módulos pendientes: página → (título, número, descripción).
MODULOS_PENDIENTES = {
    "calendario": ("Calendario", 4,
                   "Consulta y gestiona las reuniones agendadas a partir de los correos."),
    "correos": ("Correos", 5,
                "Historial de los correos procesados con su resumen y los elementos creados."),
}


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
            "usuarios": render_usuarios,
        }
        if pagina in MODULOS_PENDIENTES:
            render_modulo_pendiente(pagina, *MODULOS_PENDIENTES[pagina])
        else:
            pantallas[pagina]()
    except ErrorBaseDatos as error:
        st.error(str(error))
        st.stop()


if __name__ == "__main__":
    main()
