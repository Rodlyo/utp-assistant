# Asistente de IA: cliente de Groq y validación de GROQ_API_KEY.
import streamlit as st
from openai import OpenAI

# Modelo de Groq (todavía no se usa).
MODELO_GROQ = "openai/gpt-oss-120b"


# Crea (una sola vez) el cliente de Groq usando la librería openai.
@st.cache_resource(show_spinner=False)
def _crear_cliente_groq(api_key):
    return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)


# Valida GROQ_API_KEY en secrets.toml y devuelve el cliente (cacheado).
def obtener_cliente_groq():
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
