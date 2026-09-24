# Estilos: CSS de la aplicación y función que lo inyecta.
import base64
from pathlib import Path

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Libre+Franklin:ital,wght@0,400;0,500;0,600;0,700;0,800;0,900;1,400&display=swap');

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
    --utp-verde: #00B491;         /* verde de utp.edu.pe (estados correctos) */
    /* Textos y líneas que van directamente sobre el fondo oscuro */
    --utp-sobre-fondo: rgba(255, 255, 255, 0.78);
    --utp-linea-fondo: rgba(255, 255, 255, 0.22);
    /* Ajustes del fondo */
    --utp-oscuridad: 0.60;        /* opacidad de la capa negra (0 = sin capa, 1 = negro) */
    --utp-desenfoque: 6px;        /* desenfoque de la imagen (0px = nítida) */
    --f-base: 'Libre Franklin', 'Helvetica Neue', Arial, sans-serif;
}

/* Base: imagen desenfocada + capa negra */
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

/* Ocultar elementos por defecto de Streamlit */
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

/* Contenedor principal (máx. 900px) */
.block-container, [data-testid="stMainBlockContainer"] {
    max-width: 900px !important;
    padding: 0 1.25rem !important;
    margin: 0 auto;
}

/* Barra superior */
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

/* Landing */
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
/* Zonas de contenido (empujan el pie al fondo) */
[data-testid="stAppViewContainer"] { overflow-x: hidden; }
.st-key-contenido, .st-key-contenido_auth { min-height: calc(100vh - 290px); }
/* Login y registro: formulario centrado vertical y horizontalmente */
.st-key-contenido_auth { justify-content: center; padding: 2.5rem 0; }

/* Pie de página (gris oscuro UTP, a todo el ancho) */
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
.utp-pie-lista span.utp-pie-activo { color: var(--utp-verde); }
.utp-pie-legal {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    padding: 1.1rem 0 1.4rem 0;
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.55);
}

/* Botones de Streamlit */
button[data-testid^="stBaseButton-"] {
    border-radius: 0 !important;
    min-height: 2.9rem;
    padding: 0.6rem 1.6rem !important;
    box-shadow: none !important;
    transition: background-color .15s ease, border-color .15s ease, color .15s ease;
}
button[data-testid^="stBaseButton-"] p { font-weight: 600 !important; font-size: 0.92rem !important; }
/* Primario: rojo UTP */
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
    background: var(--utp-rojo) !important;
    border: 1px solid var(--utp-rojo) !important;
    color: var(--utp-blanco) !important;
}
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background: var(--utp-rojo-oscuro) !important;
    border-color: var(--utp-rojo-oscuro) !important;
}
/* Secundario: borde blanco sobre el fondo oscuro, se rellena al pasar el ratón */
button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-secondaryFormSubmit"] {
    background: transparent !important;
    border: 1px solid var(--utp-blanco) !important;
    color: var(--utp-blanco) !important;
}
button[data-testid="stBaseButton-secondary"]:hover,
button[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
    background: var(--utp-blanco) !important;
    color: var(--utp-negro) !important;
}
/* Terciario: enlace de texto */
button[data-testid="stBaseButton-tertiary"] {
    background: transparent !important;
    border: none !important;
    min-height: auto;
    padding: 0.2rem 0 !important;
    color: var(--utp-sobre-fondo) !important;
}
button[data-testid="stBaseButton-tertiary"] p { font-size: 0.85rem !important; font-weight: 500 !important; }
button[data-testid="stBaseButton-tertiary"]:hover {
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

/* Formularios (tarjeta) */
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

/* Inputs */
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

/* Alertas */
[data-testid="stAlert"], [data-testid="stAlertContainer"] { border-radius: 0 !important; }
/* Fondo blanco sólido para que las alertas se lean sobre la imagen */
[data-testid="stAlertContainer"] { background-color: var(--utp-blanco) !important; }

/* Barra de navegación interna */
.st-key-barra_interna {
    border-bottom: 1px solid var(--utp-linea-fondo);
    padding: 0.2rem 0;
}
/* Líneas verticales finas entre enlaces */
.st-key-nav_procesar, .st-key-nav_calendario, .st-key-nav_correos, .st-key-nav_usuarios {
    border-left: 1px solid var(--utp-linea-fondo);
}
.st-key-nav_enlaces button[data-testid="stBaseButton-tertiary"],
.st-key-nav_usuario button[data-testid="stBaseButton-tertiary"],
.st-key-cal_barra button[data-testid="stBaseButton-tertiary"] {
    padding: 0.7rem 1.1rem !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    color: var(--utp-sobre-fondo) !important;
    text-decoration: none !important;
}
.st-key-nav_dashboard button[data-testid="stBaseButton-tertiary"] { padding-left: 0 !important; }
.st-key-nav_usuario button[data-testid="stBaseButton-tertiary"] { padding-right: 0 !important; }
.st-key-nav_enlaces button p, .st-key-nav_usuario button p, .st-key-cal_barra button p {
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
}
.st-key-nav_enlaces button[data-testid="stBaseButton-tertiary"]:hover,
.st-key-nav_usuario button[data-testid="stBaseButton-tertiary"]:hover,
.st-key-cal_barra button[data-testid="stBaseButton-tertiary"]:hover {
    color: var(--utp-blanco) !important;
}
.st-key-nav_usuario button[data-testid="stBaseButton-tertiary"]:hover { color: var(--utp-rojo-claro) !important; }
.utp-nav-usuario {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--utp-blanco);
}

/* Saludo y textos del dashboard */
.utp-saludo {
    font-weight: 800;
    font-size: clamp(2.2rem, 5vw, 3.2rem);
    letter-spacing: -0.03em;
    color: var(--utp-blanco);
    margin: 3rem 0 0.4rem 0;
}
.utp-saludo span { color: var(--utp-rojo-claro); }
.utp-fecha-hoy {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--utp-sobre-fondo);
    margin-bottom: 2rem;
}

/* Franja de métricas */
.utp-metricas {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    border-top: 1px solid var(--utp-linea-fondo);
    border-bottom: 1px solid var(--utp-linea-fondo);
    margin-bottom: 1.2rem;
}
.utp-metrica { padding: 1.3rem 1.2rem 1.4rem 1.2rem; }
.utp-metrica:first-child { padding-left: 0; }
.utp-metrica + .utp-metrica { border-left: 1px solid var(--utp-linea-fondo); }
.utp-metrica-numero {
    font-weight: 800;
    font-size: 2.8rem;
    line-height: 1;
    letter-spacing: -0.03em;
    color: var(--utp-blanco);
}
.utp-metrica-etiqueta {
    margin-top: 0.6rem;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--utp-sobre-fondo);
}

/* Aviso de datos de ejemplo (discreto) */
.utp-demo-texto { font-size: 0.85rem; font-style: italic; color: var(--utp-sobre-fondo); }
.st-key-cargar_demo button p { color: var(--utp-rojo-claro); text-decoration: underline; text-underline-offset: 4px; }

/* Tarjetas del dashboard */
.utp-dash-columnas {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin: 1rem 0;
}
.utp-tarjeta {
    background: var(--utp-blanco);
    border-top: 3px solid var(--utp-rojo);
    padding: 1.3rem 1.4rem 0.6rem 1.4rem;
    color: var(--utp-texto);
}
.utp-tarjeta-ancha { margin-bottom: 1rem; }
.utp-tarjeta-titulo {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--utp-negro);
    padding-bottom: 0.8rem;
    border-bottom: 1px solid var(--utp-negro);
}
.utp-item { padding: 0.85rem 0; border-bottom: 1px solid var(--utp-linea); }
.utp-item:last-child, .utp-actividad-fila:last-child { border-bottom: none; }
.utp-item-fila { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.8rem; }
.utp-item-fecha {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--utp-rojo);
    white-space: nowrap;
}
.utp-item-titulo { font-weight: 700; font-size: 0.95rem; color: var(--utp-negro); margin: 0.2rem 0; }
.utp-item-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.82rem;
    color: var(--utp-gris);
}
.utp-vencida { color: var(--utp-rojo); font-weight: 600; }
.utp-chip, .utp-prioridad, .utp-estado {
    display: inline-block;
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.2rem 0.5rem;
    border: 1px solid var(--utp-gris-claro);
    color: var(--utp-gris);
    white-space: nowrap;
}
/* Prioridades: urgente y alta resaltadas en rojo */
.utp-prioridad-urgente { background: var(--utp-rojo); border-color: var(--utp-rojo); color: var(--utp-blanco); }
.utp-prioridad-alta { border-color: var(--utp-rojo); color: var(--utp-rojo); }
/* Estados de correo */
.utp-estado-procesado { border-color: var(--utp-verde); color: #00866B; }
.utp-estado-error { border-color: var(--utp-rojo); color: var(--utp-rojo); }

/* Actividad reciente: remitente · asunto · estado · fecha */
.utp-actividad-fila {
    display: grid;
    grid-template-columns: 1.1fr 2fr auto auto;
    align-items: center;
    gap: 1rem;
    padding: 0.8rem 0;
    border-bottom: 1px solid var(--utp-linea);
}
.utp-actividad-asunto {
    font-size: 0.88rem;
    color: var(--utp-texto);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Estados vacíos */
.utp-vacio {
    font-style: italic;
    font-size: 0.95rem;
    color: var(--utp-gris);
    padding: 1.2rem 0 1rem 0;
    margin: 0;
}

/* Roles */
.utp-badge-admin {
    display: inline-block;
    margin-left: 0.6rem;
    padding: 0.15rem 0.45rem;
    background: var(--utp-rojo);
    color: var(--utp-blanco);
    font-size: 0.6rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    vertical-align: 1px;
}
.utp-responsable { font-size: 0.78rem; color: var(--utp-gris); }
.utp-rol-admin { border-color: var(--utp-rojo); color: var(--utp-rojo); }
.utp-tu { font-size: 0.75rem; color: var(--utp-gris); font-weight: 400; }
.utp-subtitulo {
    font-style: italic;
    font-size: 1.05rem;
    color: var(--utp-sobre-fondo);
    margin: -0.6rem 0 2rem 0;
}

/* Selectores (estilo discreto, esquinas rectas) */
[data-testid="stSelectbox"] [data-baseweb="select"] > div {
    border-radius: 0 !important;
    border: 1px solid var(--utp-gris-claro) !important;
    background: var(--utp-blanco) !important;
    box-shadow: none !important;
    min-height: 2.4rem;
}
[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
    border-color: var(--utp-rojo) !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] * { color: var(--utp-texto); }
/* "Ver datos de:" sobre el fondo oscuro */
.st-key-selector_alcance [data-testid="stWidgetLabel"] p {
    color: var(--utp-sobre-fondo) !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
}
.st-key-selector_alcance { margin-bottom: 0.4rem; }

/* Tabla de usuarios */
.utp-tabla-scroll { overflow-x: auto; padding-bottom: 0.6rem; }
.utp-tabla { width: 100%; border-collapse: collapse; font-size: 0.85rem; color: var(--utp-texto); }
.utp-tabla th {
    text-align: left;
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--utp-negro);
    padding: 0.9rem 0.7rem 0.6rem 0;
    border-bottom: 1px solid var(--utp-negro);
    white-space: nowrap;
}
.utp-tabla td {
    padding: 0.75rem 0.7rem 0.75rem 0;
    border-bottom: 1px solid var(--utp-linea);
    vertical-align: middle;
}
.utp-tabla tr:last-child td { border-bottom: none; }
.utp-tabla .utp-num { text-align: right; padding-right: 0; font-variant-numeric: tabular-nums; }
.utp-nowrap { white-space: nowrap; }

/* Panel de acciones (tarjeta blanca) */
.st-key-panel_acciones {
    background: var(--utp-blanco);
    border-top: 3px solid var(--utp-rojo);
    padding: 1.3rem 1.4rem 1.4rem 1.4rem;
    margin-bottom: 1rem;
}
.st-key-panel_acciones button[data-testid="stBaseButton-secondary"] {
    border-color: var(--utp-negro) !important;
    color: var(--utp-negro) !important;
}
.st-key-panel_acciones button[data-testid="stBaseButton-secondary"]:hover {
    background: var(--utp-negro) !important;
    color: var(--utp-blanco) !important;
}
.st-key-panel_acciones button:disabled {
    opacity: 0.35 !important;
    cursor: not-allowed !important;
}

/* Procesar correo: estado de la ejecución */
.utp-run {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.7rem;
    padding: 0.9rem 0;
    margin-bottom: 1.2rem;
    border-top: 1px solid var(--utp-linea-fondo);
    border-bottom: 1px solid var(--utp-linea-fondo);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.38);
}
.utp-run .hecho { color: var(--utp-sobre-fondo); }
.utp-run .actual { color: var(--utp-rojo-claro); border-bottom: 2px solid var(--utp-rojo-claro); padding-bottom: 2px; }
.utp-run-flecha { color: rgba(255, 255, 255, 0.3); }
[data-testid="stSpinner"], [data-testid="stSpinner"] * { color: var(--utp-sobre-fondo) !important; }

/* Tarjetas de acciones propuestas */
[class*="st-key-accion_"] {
    border: 1px solid var(--utp-negro);
    background: var(--utp-blanco);
    padding: 1rem 1.1rem;
    margin-bottom: 0.6rem;
}
.utp-accion-tipo {
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--utp-rojo);
}
[data-testid="stForm"] button[data-testid="stBaseButton-secondaryFormSubmit"] {
    border-color: var(--utp-negro) !important;
    color: var(--utp-negro) !important;
}
[data-testid="stForm"] button[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
    background: var(--utp-negro) !important;
    color: var(--utp-blanco) !important;
}

/* Área de texto, fecha, hora y número */
[data-testid="stTextArea"] [data-baseweb="textarea"],
[data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stTimeInput"] [data-baseweb="select"] > div {
    border: 1px solid var(--utp-gris-claro) !important;
    border-radius: 0 !important;
    background: var(--utp-blanco) !important;
    box-shadow: none !important;
}
[data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within,
[data-testid="stDateInput"] [data-baseweb="input"]:focus-within,
[data-testid="stNumberInput"] [data-baseweb="input"]:focus-within,
[data-testid="stTimeInput"] [data-baseweb="select"] > div:focus-within {
    border-color: var(--utp-rojo) !important;
}
[data-testid="stTextArea"] textarea, [data-testid="stDateInput"] input, [data-testid="stNumberInput"] input {
    background: var(--utp-blanco) !important;
    color: var(--utp-texto) !important;
    caret-color: var(--utp-rojo);
}
[data-testid="stNumberInput"] button { border-radius: 0 !important; }

/* Resumen del asistente */
.utp-resumen p { margin: 0.2rem 0 0.5rem 0; font-size: 0.92rem; line-height: 1.55; color: var(--utp-texto); }
.utp-resumen-titulo {
    margin-top: 1rem;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--utp-rojo);
}
.utp-resumen { padding-bottom: 1rem; }

/* Traza de la ejecución */
[data-testid="stExpander"] details {
    background: var(--utp-blanco) !important;
    border: 1px solid var(--utp-linea) !important;
    border-radius: 0 !important;
}
[data-testid="stExpander"] summary p { color: var(--utp-negro) !important; font-weight: 700 !important; }
.utp-traza-paso {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin-top: 0.4rem;
    padding-top: 0.6rem;
    border-top: 1px solid var(--utp-linea);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--utp-negro);
}
.utp-traza-paso span { color: var(--utp-gris); font-weight: 600; }

/* Calendario: encabezado y barra */
.utp-cal-periodo {
    font-weight: 800;
    font-size: clamp(1.5rem, 4vw, 2.3rem);
    letter-spacing: -0.02em;
    color: var(--utp-rojo-claro);
    margin: -0.8rem 0 1.4rem 0;
}
.st-key-cal_barra {
    border-top: 1px solid var(--utp-linea-fondo);
    border-bottom: 1px solid var(--utp-linea-fondo);
    padding: 0.2rem 0;
    margin-bottom: 0.8rem;
}
.st-key-cal_vista_semana, .st-key-cal_vista_agenda { border-left: 1px solid var(--utp-linea-fondo); }
.st-key-cal_vista_mes button[data-testid="stBaseButton-tertiary"] { padding-left: 0 !important; }
.st-key-cal_nueva button { min-height: 2.4rem; padding: 0.4rem 1rem !important; }
.st-key-cal_responsable_wrap [data-testid="stWidgetLabel"] p,
.st-key-cal_dia [data-testid="stWidgetLabel"] p { color: var(--utp-sobre-fondo) !important; }

/* Calendario: contenedor y eventos */
.utp-cal { background: var(--utp-blanco); border: 1px solid var(--utp-negro); color: var(--utp-texto); margin-bottom: 0.6rem; }
.utp-cal-scroll { overflow-x: auto; }
.utp-ev {
    display: block;
    font-size: 0.66rem;
    line-height: 1.3;
    padding: 0.12rem 0.3rem;
    margin-bottom: 0.2rem;
    border: 1px solid var(--utp-negro);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.utp-ev-confirmada { background: var(--utp-negro); color: var(--utp-blanco); }
.utp-ev-por-confirmar { background: var(--utp-blanco); color: var(--utp-negro); border-style: dashed; border-left: 3px solid var(--utp-rojo); }
.utp-ev-realizada { background: var(--utp-fondo-suave); color: #8D8D8D; border-color: var(--utp-gris-claro); }
.utp-ev-cancelada { background: var(--utp-blanco); color: var(--utp-gris-claro); border-color: var(--utp-linea); text-decoration: line-through; }
.utp-marca-confirmar {
    display: inline-block;
    font-size: 0.58rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--utp-rojo);
}

/* Vista mes */
.utp-cal-mes { display: grid; grid-template-columns: repeat(7, minmax(88px, 1fr)); min-width: 640px; }
.utp-cal-cab, .utp-sem-cab {
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--utp-negro);
    padding: 0.6rem 0.5rem;
    border-bottom: 1px solid var(--utp-negro);
}
.utp-cal-dia { min-height: 104px; padding: 0.35rem; border-right: 1px solid var(--utp-linea); border-bottom: 1px solid var(--utp-linea); }
.utp-cal-dia:nth-child(7n) { border-right: none; }
.utp-cal-dia.finde, .utp-sem-col.finde { background-color: #F7F7F7; }
.utp-cal-num { font-size: 0.8rem; font-weight: 700; color: var(--utp-negro); margin-bottom: 0.25rem; }
.utp-cal-dia.otro-mes .utp-cal-num, .utp-cal-dia.otro-mes .utp-ev { opacity: 0.35; }
.utp-cal-dia.hoy .utp-cal-num, .utp-sem-cab.hoy { color: var(--utp-rojo); }
.utp-cal-dia.hoy .utp-cal-num { text-decoration: underline; text-underline-offset: 3px; }
.utp-cal-mas { font-size: 0.64rem; font-weight: 700; color: var(--utp-gris); }

/* Vista semana */
.utp-cal-semana { display: grid; grid-template-columns: 52px repeat(7, minmax(92px, 1fr)); min-width: 720px; }
.utp-sem-cab strong { font-size: 0.85rem; }
.utp-sem-horas { position: relative; border-right: 1px solid var(--utp-linea); }
.utp-sem-hora { position: absolute; right: 0.4rem; margin-top: 2px; font-size: 0.6rem; color: var(--utp-gris); }
.utp-sem-col {
    position: relative;
    border-right: 1px solid var(--utp-linea);
    background-image: repeating-linear-gradient(to bottom, var(--utp-linea) 0, var(--utp-linea) 1px, transparent 1px, transparent 48px);
}
.utp-sem-col:last-child { border-right: none; }
.utp-sem-laboral {
    position: absolute;
    left: 0;
    right: 0;
    background: rgba(211, 5, 45, 0.045);
    border-top: 1px dashed rgba(211, 5, 45, 0.35);
    border-bottom: 1px dashed rgba(211, 5, 45, 0.35);
}
.utp-sem-ev { position: absolute; z-index: 1; margin: 0; white-space: normal; }
.utp-sem-ev span, .utp-sem-ev strong, .utp-sem-ev em { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.utp-sem-ev span { font-weight: 700; }
.utp-sem-ev em { font-style: normal; opacity: 0.8; }

/* Vista agenda */
.utp-agenda-dia { padding: 0.9rem 1.2rem; border-bottom: 1px solid var(--utp-linea); }
.utp-agenda-fecha { font-weight: 800; font-size: 1.15rem; letter-spacing: -0.01em; color: var(--utp-negro); margin-bottom: 0.3rem; }
.utp-agenda-fila { display: grid; grid-template-columns: 110px 1fr; gap: 1rem; padding: 0.55rem 0; border-top: 1px solid var(--utp-linea); }
.utp-agenda-hora { font-size: 0.75rem; font-weight: 700; color: var(--utp-rojo); padding-top: 0.2rem; }
.utp-agenda-realizada { opacity: 0.55; }
.utp-agenda-cancelada .utp-item-titulo, .utp-ev-titulo-cancelada { text-decoration: line-through; color: var(--utp-gris-claro); }
.utp-chip-por-confirmar { border-color: var(--utp-rojo); color: var(--utp-rojo); border-style: dashed; }
.utp-chip-confirmada { border-color: var(--utp-negro); color: var(--utp-negro); }
.utp-chip-ia { border-color: var(--utp-rojo); color: var(--utp-rojo); }

/* Leyenda */
.utp-cal-leyenda {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1.2rem;
    padding: 0.7rem 1rem;
    border-top: 1px solid var(--utp-negro);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--utp-gris);
}
.utp-cal-leyenda i { display: inline-block; width: 16px; height: 10px; padding: 0; margin: 0 0.4rem -1px 0; }

/* Detalle del día */
.utp-seccion-titulo {
    margin: 1.8rem 0 0.2rem 0;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--utp-blanco);
}
.utp-cal-dia-titulo { font-weight: 800; font-size: 1.4rem; letter-spacing: -0.02em; color: var(--utp-blanco); margin: 0.2rem 0 0.8rem 0; }
[class*="st-key-cal_ev_"] { background: var(--utp-blanco); border: 1px solid var(--utp-negro); padding: 1rem 1.1rem; margin-bottom: 0.6rem; }
[class*="st-key-cal_ev_"] button[data-testid="stBaseButton-secondary"] { border-color: var(--utp-negro) !important; color: var(--utp-negro) !important; min-height: 2.3rem; padding: 0.35rem 0.9rem !important; }
[class*="st-key-cal_ev_"] button[data-testid="stBaseButton-secondary"]:hover { background: var(--utp-negro) !important; color: var(--utp-blanco) !important; }
.utp-cal-desc { font-size: 0.88rem; line-height: 1.5; color: var(--utp-texto); margin: 0.5rem 0 0.3rem 0; }
.utp-cal-origen { font-size: 0.8rem; color: var(--utp-gris); font-style: italic; margin: 0.2rem 0; }

/* Correos: filtros */
.st-key-co_filtros {
    background: var(--utp-blanco);
    border-top: 3px solid var(--utp-rojo);
    padding: 1.1rem 1.3rem 1.2rem 1.3rem;
    margin-bottom: 1rem;
}
.st-key-co_filtros button[data-testid^="stBaseButton-secondary"] {
    border-color: var(--utp-negro) !important;
    color: var(--utp-negro) !important;
    min-height: 2.4rem;
    padding: 0.4rem 1rem !important;
}
.st-key-co_filtros button[data-testid^="stBaseButton-secondary"]:hover {
    background: var(--utp-negro) !important;
    color: var(--utp-blanco) !important;
}

/* Correos: listado */
[class*="st-key-co_fila_"] {
    background: var(--utp-blanco);
    border-bottom: 1px solid var(--utp-linea);
    padding: 0.8rem 1.2rem;
    margin: 0 !important;
}
[class*="st-key-co_fila_"]:first-of-type { border-top: 3px solid var(--utp-rojo); }
[class*="st-key-co_fila_"] button[data-testid="stBaseButton-tertiary"] { color: var(--utp-negro) !important; }
[class*="st-key-co_fila_"] button[data-testid="stBaseButton-tertiary"]:hover { color: var(--utp-rojo) !important; }
.utp-co-correo { font-weight: 400; font-size: 0.82rem; color: var(--utp-gris); margin-left: 0.3rem; }
.utp-co-asunto-fila { font-size: 0.9rem; color: var(--utp-texto); margin: 0.1rem 0 0.35rem 0; }
.utp-co-procesado { background: var(--utp-negro); border-color: var(--utp-negro); color: var(--utp-blanco); }
.utp-co-pendiente { border-style: dashed; border-color: var(--utp-negro); color: var(--utp-negro); }
.utp-co-error { background: var(--utp-rojo); border-color: var(--utp-rojo); color: var(--utp-blanco); }
.st-key-co_paginacion { margin: 0.8rem 0 1rem 0; }
.utp-co-pagina {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--utp-sobre-fondo);
}

/* Correos: detalle */
.utp-co-asunto {
    font-weight: 800;
    font-size: clamp(1.6rem, 4vw, 2.4rem);
    line-height: 1.1;
    letter-spacing: -0.02em;
    color: var(--utp-blanco);
    margin: 0.6rem 0 0.5rem 0;
}
.utp-co-cabecera {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--utp-sobre-fondo);
    margin-bottom: 0.6rem;
}
[class*="st-key-co_tarjeta_"] {
    background: var(--utp-blanco);
    border: 1px solid var(--utp-negro);
    padding: 1rem 1.1rem;
    margin-bottom: 0.6rem;
}
[class*="st-key-co_tarjeta_"] button[data-testid="stBaseButton-secondary"] {
    border-color: var(--utp-negro) !important;
    color: var(--utp-negro) !important;
}
[class*="st-key-co_tarjeta_"] button[data-testid="stBaseButton-secondary"]:hover {
    background: var(--utp-negro) !important;
    color: var(--utp-blanco) !important;
}
.st-key-co_tarjeta_original [data-testid="stCode"] pre { background: var(--utp-blanco) !important; }
.utp-co-datos { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.8rem 1.4rem; padding: 0.9rem 0 1.1rem 0; }
.utp-co-datos div { font-size: 0.92rem; color: var(--utp-texto); }
.utp-co-datos span {
    display: block;
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--utp-gris);
    margin-bottom: 0.15rem;
}

/* Móvil */
@media (max-width: 640px) {
    .utp-pasos, .utp-dash-columnas { grid-template-columns: 1fr; gap: 1.2rem; }
    .utp-metricas { grid-template-columns: 1fr 1fr; }
    .utp-metrica:nth-child(3) { border-left: none; padding-left: 0; }
    .utp-metrica:nth-child(n+3) { border-top: 1px solid var(--utp-linea-fondo); }
    .utp-actividad-fila { grid-template-columns: 1fr auto; }
    .utp-actividad-asunto { grid-column: 1 / -1; grid-row: 2; white-space: normal; }
    .st-key-nav_enlaces button[data-testid="stBaseButton-tertiary"] { padding: 0.6rem 0.6rem !important; }
    .utp-eyebrow { margin-top: 2.5rem; }
    .utp-nav-meta { display: none; }
    .utp-pie-columnas { grid-template-columns: 1fr; gap: 1.4rem; }
    .utp-pie-legal { flex-direction: column; }
    .st-key-contenido, .st-key-contenido_auth { min-height: auto; }
}
</style>
"""


RUTA_FONDO = Path(__file__).parent / "assets" / "fondo.jpg"


# Fondo en base64 (cacheado); sin imagen, degradado oscuro.
@st.cache_data(show_spinner=False)
def _fondo_css():
    try:
        datos = base64.b64encode(RUTA_FONDO.read_bytes()).decode("ascii")
        return f'url("data:image/jpeg;base64,{datos}")'
    except OSError:
        return "linear-gradient(135deg, #2b2b2b 0%, #111111 100%)"


# Inyecta el CSS global de la aplicación.
def aplicar_estilos():
    st.markdown(CSS.replace("__FONDO__", _fondo_css()), unsafe_allow_html=True)
