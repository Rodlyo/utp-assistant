# UTP Assistant · Fase 1

Sistema interno de UTPConsult. Esta fase incluye landing page, registro, login y panel provisional.

## 1. Iniciar MySQL en XAMPP

1. Abre el **XAMPP Control Panel**.
2. Pulsa **Start** en la fila de **MySQL** (debe quedar en verde, puerto 3306).
3. La base de datos `assistantutpdb` y la tabla `usuarios` se crean solas al abrir la app.
   Si lo prefieres, puedes importar `schema.sql` desde phpMyAdmin.

## 2. Instalar dependencias

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## 3. Configurar secrets.toml

Copia el ejemplo y rellena tu clave de Groq:

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

```toml
GROQ_API_KEY = "gsk_..."

[mysql]
host = "localhost"
port = 3306
user = "root"
password = ""
database = "assistantutpdb"
```

`secrets.toml` está en `.gitignore`: nunca lo subas al repositorio.

## 4. Ejecutar

```bash
streamlit run utp_assistant.py
```

## Fondo

La imagen de fondo está en `assets/fondo.jpg` (foto libre de [Unsplash](https://unsplash.com), licencia Unsplash). Puedes reemplazarla por otra con el mismo nombre.
La oscuridad y el desenfoque se ajustan en las variables `--utp-oscuridad` y `--utp-desenfoque` del CSS en `utp_assistant.py`.

## Seguridad

- `.streamlit/secrets.toml` (clave de Groq y datos de MySQL) está en `.gitignore` y **no se sube** al repositorio.
- Cada persona que clone el proyecto debe crear su propio `secrets.toml` a partir de `secrets.toml.example`.
- Las contraseñas de los usuarios se guardan con PBKDF2-HMAC-SHA256 y salt aleatorio; nunca en texto plano.
