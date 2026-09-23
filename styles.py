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
.st-key-nav_usuario button[data-testid="stBaseButton-tertiary"] {
    padding: 0.7rem 1.1rem !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    color: var(--utp-sobre-fondo) !important;
    text-decoration: none !important;
}
.st-key-nav_dashboard button[data-testid="stBaseButton-tertiary"] { padding-left: 0 !important; }
.st-key-nav_usuario button[data-testid="stBaseButton-tertiary"] { padding-right: 0 !important; }
.st-key-nav_enlaces button p, .st-key-nav_usuario button p {
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
}
.st-key-nav_enlaces button[data-testid="stBaseButton-tertiary"]:hover,
.st-key-nav_usuario button[data-testid="stBaseButton-tertiary"]:hover {
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
.utp-panel-texto {
    font-size: 1.02rem;
    line-height: 1.6;
    color: var(--utp-sobre-fondo);
    max-width: 600px;
    margin-bottom: 2.2rem;
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
