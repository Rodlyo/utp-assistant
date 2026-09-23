# UTP Assistant

Sistema interno de UTPConsult. Incluye landing page, registro, login y dashboard con métricas (fases 1 y 2).

## 1. Iniciar MySQL en XAMPP

1. Abre el **XAMPP Control Panel**.
2. Pulsa **Start** en la fila de **MySQL** (debe quedar en verde, puerto 3306).
3. La base de datos `assistantutpdb` y sus tablas (`usuarios`, `contactos`, `correos`, `tareas`, `eventos`) se crean solas al abrir la app.
   Si lo prefieres, puedes importar `schema.sql` desde phpMyAdmin.
4. Importar `schema.sql` crea también dos cuentas por defecto (se inicia sesión con el correo):

   | Correo | Contraseña |
   |---|---|
   | `admin@utpconsult.com` | `admin123` |
   | `usuario@utpconsult.com` | `usuario123` |

   Son cuentas de prueba: cambia o elimina estas contraseñas antes de usar el sistema con datos reales.

## Roles y primer administrador

Hay dos roles: **usuario** (solo ve sus propios datos) y **administrador** (ve los datos de todo el equipo, puede filtrar por usuario y gestiona las cuentas en la página *Usuarios*).

- **Primer administrador:** la primera persona que se registra cuando todavía no existe ningún administrador queda como `administrador`. Todos los registros posteriores se crean como `usuario`. El formulario de registro nunca permite elegir el rol.
- **Bases de la fase 1:** al arrancar, la app añade las columnas `rol`, `activo` y `ultimo_acceso` si faltan. Si hay usuarios pero ninguno es administrador, promueve al de **id más bajo**.
- **Cuentas por defecto de `schema.sql`:** `admin@utpconsult.com` se crea como administrador y `usuario@utpconsult.com` como usuario.
- **Gestión:** un administrador puede cambiar roles y activar o desactivar cuentas (siempre con confirmación). No puede quitarse su propio rol ni desactivarse, y el sistema nunca se queda sin un administrador activo.
- Una cuenta desactivada no puede iniciar sesión. Si se desactiva mientras está conectada, su sesión se cierra en la siguiente carga de página.

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

## Archivos del proyecto

Todos en la misma carpeta (sin subcarpetas ni paquetes). Se ejecuta con `streamlit run utp_assistant.py`.

| Archivo | Qué contiene |
|---|---|
| `utp_assistant.py` | Interfaz y navegación: configuración de página, sesión, permisos (`requiere_login`, `requiere_admin`, `obtener_alcance`), cabecera, barra de navegación, todas las pantallas y `main()`. |
| `db.py` | Conexión a MySQL, `init_db()` con tablas y migraciones, consultas del dashboard, gestión de usuarios y datos de ejemplo. No dibuja interfaz. |
| `auth.py` | Hash y verificación de contraseñas, validaciones de registro y login, `registrar_usuario()` y `autenticar_usuario()`. No dibuja interfaz. |
| `assistant.py` | Cliente de Groq (IA) y validación de `GROQ_API_KEY`. En la fase 3 tendrá el prompt de sistema y las llamadas al modelo. |
| `styles.py` | Todo el CSS y la función que lo inyecta. |
| `schema.sql` | Esquema completo y cuentas por defecto, para importar desde phpMyAdmin. |

Dependencias entre archivos: `utp_assistant.py` → `auth.py` → `db.py`; `styles.py` y `assistant.py` son independientes.

## Fondo

La imagen de fondo está en `assets/fondo.jpg` (foto libre de [Unsplash](https://unsplash.com), licencia Unsplash). Puedes reemplazarla por otra con el mismo nombre.
La oscuridad y el desenfoque se ajustan en las variables `--utp-oscuridad` y `--utp-desenfoque` del CSS en `styles.py`.

## Seguridad

- `.streamlit/secrets.toml` (clave de Groq y datos de MySQL) está en `.gitignore` y **no se sube** al repositorio.
- Cada persona que clone el proyecto debe crear su propio `secrets.toml` a partir de `secrets.toml.example`.
- Las contraseñas de los usuarios se guardan con PBKDF2-HMAC-SHA256 y salt aleatorio; nunca en texto plano.
