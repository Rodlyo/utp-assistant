# UTP Assistant

Sistema interno de UTPConsult. Incluye landing page, registro, login, dashboard con métricas, gestión de usuarios, procesamiento de correos con IA, calendario de reuniones e historial de correos.

## 1. Iniciar MySQL en XAMPP

1. Abre el **XAMPP Control Panel**.
2. Pulsa **Start** en la fila de **MySQL** (debe quedar en verde, puerto 3306).
3. La base de datos `assistantutpdb` y sus tablas (`usuarios`, `contactos`, `correos`, `tareas`, `eventos`) se crean solas al abrir la app (también `ejecuciones` y `pasos_ejecucion`).
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

## Procesar correo (asistente de IA)

Página **Procesar correo**: pegas el correo de un cliente y el asistente (Groq, modelo `openai/gpt-oss-120b`) propone contactos, tareas y reuniones.

1. El correo se guarda como `pendiente` y se crea una ejecución (`en_cola`).
2. El modelo analiza el correo (`en_progreso`). Las consultas de solo lectura (`buscar_contacto`, `consultar_disponibilidad`) se ejecutan solas.
3. Las acciones de escritura (`registrar_contacto_en_crm`, `crear_tarea`, `agendar_reunion`) **no se ejecutan** hasta que las apruebas (`requiere_accion`). Puedes editarlas o rechazarlas.
4. Con la respuesta final, el correo pasa a `procesado` con su resumen y la ejecución a `completado`.

Reglas: máximo 6 llamadas al modelo por ejecución; reuniones de lunes a viernes entre 09:00 y 18:00 (America/Lima) sin cruces; todo se valida en el servidor. Cada paso queda en `pasos_ejecucion` y se puede ver en **Ver traza de la ejecución**.

> El contenido de los correos se envía a Groq para analizarlo. No pegues información que no deba salir de la empresa.

## Calendario

Página **Calendario** con tres vistas (**Mes**, **Semana** y **Agenda** de 30 días), navegación Anterior / Hoy / Siguiente y un **detalle del día** con las reuniones en tarjetas.

- Estados: confirmada (negro), **por confirmar** con el cliente (borde discontinuo, propuesta por el asistente), realizada (gris) y cancelada (tachada).
- Acciones: nueva reunión, editar, confirmar con cliente, marcar como realizada (si ya empezó) y cancelar (con confirmación).
- Mismas reglas que el asistente: lunes a viernes, de 09:00 a 18:00 (America/Lima), en el futuro y sin cruces con otra reunión programada.
- Cada usuario gestiona sus reuniones; el administrador ve **"Ver calendario de:"** y puede gestionar las de todo el equipo. Los permisos se validan en la base de datos.

## Correos (historial)

Página **Correos** con todo lo que llegó de los clientes:

- Métricas (total, procesados, pendientes, con error) que respetan los filtros.
- Filtros: búsqueda de texto (asunto, cuerpo, remitente y su correo; `%` y `_` se buscan como texto; no distingue tildes), estado y rango de fechas. El administrador elige **"Ver correos de:"**. **Limpiar filtros** y **Exportar CSV** (los correos filtrados, en UTF-8 para Excel).
- Listado de 10 correos por página con fecha, remitente, asunto, estado, tareas y reuniones generadas.
- **Ver detalle**: correo original (siempre como texto plano), resumen del asistente, contacto, tareas (con cambio de estado), reuniones (con **Ver en calendario**) y la traza de cada ejecución.
- **Reprocesar** (correos pendientes o con error; avisa si puede duplicar acciones) y **Eliminar correo**: las tareas, reuniones y contactos se conservan; sus ejecuciones y la traza se borran.

## Módulos del sistema

| Módulo | Qué hace | Quién lo usa |
|---|---|---|
| Landing, registro y login | Página pública, alta de cuentas (el primer usuario es administrador) y acceso con bloqueo tras 5 intentos | Todos |
| Dashboard | Métricas, próximas reuniones, tareas pendientes y actividad reciente | Usuarios y administradores (equipo completo o por persona) |
| Procesar correo | El asistente de IA (Groq) propone contactos, tareas y reuniones; el usuario aprueba, edita o rechaza | Usuarios y administradores |
| Calendario | Vistas mes, semana y agenda; crear, editar, confirmar, marcar como realizada y cancelar reuniones | Usuarios (las suyas) y administradores (todas) |
| Correos | Historial con filtros, detalle, traza, reprocesar, eliminar y exportar CSV | Usuarios (los suyos) y administradores (todos) |
| Usuarios | Roles, activar/desactivar cuentas, siempre con al menos un administrador activo | Solo administradores |

## Archivos del proyecto

Todos en la misma carpeta (sin subcarpetas ni paquetes). Se ejecuta con `streamlit run utp_assistant.py`.

| Archivo | Qué contiene |
|---|---|
| `utp_assistant.py` | Interfaz y navegación: configuración de página, sesión, permisos (`requiere_login`, `requiere_admin`, `obtener_alcance`), cabecera, barra de navegación, todas las pantallas y `main()`. |
| `db.py` | Conexión a MySQL, `init_db()` con tablas y migraciones, consultas del dashboard, gestión de usuarios y datos de ejemplo. No dibuja interfaz. |
| `auth.py` | Hash y verificación de contraseñas, validaciones de registro y login, `registrar_usuario()` y `autenticar_usuario()`. No dibuja interfaz. |
| `assistant.py` | Asistente de IA: cliente de Groq, prompt de sistema, herramientas (function calling), validación en servidor y ciclo de ejecución. No dibuja interfaz. |
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
