# UniTramite AI — Chatbot de Atención a Estudiantes

Prototipo académico para demostrar flujos de atención estudiantil inspirados en el documento UniTramite AI. Incluye una interfaz web interactiva, validaciones deterministas con datos ficticios y seguimiento de solicitudes mediante tickets.

> **Aviso:** este proyecto es una demostración. No está conectado a sistemas reales de la universidad, no valida identidades reales y no emite documentos oficiales. Los requisitos implementados son ilustrativos y deben contrastarse con las normas institucionales antes de cualquier uso real.

## 1. ¿Qué hace?

- Permite conversar con el chatbot desde una interfaz web.
- Simula solicitudes de récord académico y certificación de estudio.
- Comprueba requisitos usando registros ficticios.
- Genera un ticket y permite consultar su estado.
- Permite registrar estudiantes ficticios y muestra un panel de solicitudes, guardados en SQLite (local) o PostgreSQL/Supabase (nube).
- Incluye un webhook inicial para planificar la futura conexión con WhatsApp Business; **WhatsApp no está conectado en esta versión**.

## 2. Datos: procedencia y significado

Los estudiantes de prueba están en `data/students.json` y fueron creados artificialmente para este prototipo. Al iniciar la app por primera vez se copian a la tabla `students` de la base de datos. No provienen de la UASD ni contienen datos personales reales.

| Matrícula ficticia | Matrícula activa | Paz y salvo | Caso de prueba |
|---|---:|---:|---|
| `2024-1001` | Sí | Sí | Cumple los requisitos ilustrativos del récord |
| `2024-1002` | Sí | No | Tiene paz y salvo pendiente |
| `2023-2040` | No | Sí | Matrícula inactiva |

Las reglas están definidas en `core.py`:
- Récord académico: matrícula activa y paz y salvo.
- Certificación de estudio: matrícula activa.

Estas reglas son ejemplos de desarrollo, no una afirmación sobre los requisitos oficiales vigentes de una universidad.

La base de datos tiene dos tablas:

- `students`: estudiantes. Se llena con los tres casos de prueba y con los que registres en «Registro de estudiantes».
- `requests`: solicitudes (tickets). Cada una apunta a un estudiante registrado.

Dónde se guardan:

- **Sin configurar nada:** en el archivo local `unitramite.db` (SQLite), que se crea automáticamente al iniciar la aplicación.
- **Con la variable `DATABASE_URL`:** en PostgreSQL en la nube (recomendado: Supabase). Las tablas y la secuencia de tickets se crean solas al arrancar. Ver la sección 9.

## 3. Requisitos

Elige **una** de las dos formas de ejecutarla:

- **Opción A — Docker (un solo comando):** [Docker Desktop](https://www.docker.com/products/docker-desktop/). No necesitas instalar Python ni PostgreSQL.
- **Opción B — uv:** [uv](https://docs.astral.sh/uv/getting-started/installation/), el gestor de paquetes de Python. uv descarga por su cuenta la versión de Python del proyecto (3.12), así que no hace falta instalarla aparte.

Para instalar uv:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Descarga o clona el repositorio y entra en la carpeta del proyecto antes de seguir.

## 4. Opción A: todo con Docker (app + PostgreSQL)

```bash
docker compose up --build
```

Abre `http://localhost:8501`. Este comando levanta dos contenedores: la app y una base PostgreSQL local, la misma tecnología que usa Supabase. Los datos se guardan en un volumen de Docker y no se pierden al reiniciar.

- Detener: `Ctrl+C`, o `docker compose down` si lo arrancaste con `-d`.
- Borrar también los datos de la base local: `docker compose down -v`.
- Usar Supabase en lugar de la base local: crea un archivo `.env` junto a `docker-compose.yml` con la línea `DATABASE_URL=postgresql://...` (ver sección 9) y vuelve a ejecutar `docker compose up --build`.

## 5. Opción B: ejecutar con uv

```bash
uv sync
uv run streamlit run app.py
```

`uv sync` crea el entorno virtual `.venv` e instala exactamente las versiones de `uv.lock`. `uv run` ejecuta dentro de ese entorno, sin tener que activarlo. Abre la dirección que muestra Streamlit, normalmente `http://localhost:8501`.

Sin configurar nada, los datos se guardan en el archivo local `unitramite.db` (SQLite). Para usar Supabase, consulta la sección 9.

Para agregar una dependencia usa `uv add nombre-paquete`. No edites `requirements.txt` a mano: se genera desde `uv.lock` y solo existe para las plataformas de publicación que lo piden (ver sección 9):

```bash
uv export --no-hashes --format requirements-txt --no-emit-project -o requirements.txt
```

### Guion de demostración en clase

1. En «Conversar con el chatbot», escribe: `Necesito un récord académico`.
2. Cuando lo solicite, escribe la matrícula ficticia `2024-1001`. Debe registrar una solicitud y mostrar un ticket.
3. Repite el proceso con `2024-1002`; debe dejar la solicitud pendiente de revisión porque el paz y salvo figura pendiente.
4. En «Consultar una solicitud», consulta el ticket que acabas de recibir.
5. En «Panel de solicitudes», muestra el registro.
6. En «Registro de estudiantes», registra la matrícula `2025-0001` sin paz y salvo. Vuelve al chatbot, escribe `Necesito un récord académico, mi matrícula es 2025-0001` y verifica que queda pendiente de revisión.
7. Prueba una pregunta frecuente, por ejemplo: `¿El chatbot emite documentos oficiales?`.

Los identificadores de tickets se generan en ejecución; usa el ticket que muestra la aplicación en lugar de asumir que tendrá siempre un número determinado.

## 6. Ejecutar pruebas automatizadas

```bash
uv run python -m unittest discover -s tests -v
```

Las pruebas verifican algunas funciones de validación y el formato de ticket. No sustituyen una evaluación completa del chatbot ni prueban una integración con WhatsApp.

## 7. Estructura del proyecto

```text
UniTramiteAI/
├── app.py
├── core.py
├── whatsapp_webhook.py
├── pyproject.toml        # dependencias (uv)
├── uv.lock               # versiones exactas (uv)
├── requirements.txt      # generado desde uv.lock para Streamlit Cloud
├── Dockerfile
├── docker-compose.yml    # app + PostgreSQL con un solo comando
├── README.md
├── data/
│   └── students.json
└── tests/
    └── test_core.py
```

## 8. Publicarlo en GitHub

1. Crea un repositorio vacío en GitHub, por ejemplo `unitramite-ai`.
2. Abre la terminal en la carpeta del proyecto.
3. Ejecuta:

```bash
git init
git add .
git commit -m "Entrega inicial del prototipo UniTramite AI"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/unitramite-ai.git
git push -u origin main
```

Sustituye `TU_USUARIO` por tu usuario real de GitHub y usa la URL que GitHub asigne a tu repositorio. No subas contraseñas, tokens ni archivos `.env`.

## 9. Publicar la demo

### Dónde se publica cada parte

| Parte | Dónde | Costo |
|---|---|---|
| Frontend + lógica (la app Streamlit) | **Streamlit Community Cloud** (recomendado) | Gratis |
| Base de datos | **Supabase** | Gratis |

En Streamlit el frontend y el backend son el mismo programa de Python, así que se publican juntos. **Vercel, Netlify o GitHub Pages no sirven**: solo alojan páginas estáticas o funciones cortas, y Streamlit necesita un servidor de Python encendido todo el tiempo. Supabase tampoco aloja la app, solo la base de datos.

Alternativas si Streamlit Cloud no te sirve, ambas usando el `Dockerfile` del proyecto:

- **Hugging Face Spaces** (gratis): crea un Space de tipo *Docker*. Spaces espera el puerto `7860`, así que hay que indicarle `app_port: 8501` en la cabecera del README del Space.
- **Render** (plan gratis): crea un *Web Service* desde el repositorio con entorno *Docker*. En el plan gratis se duerme sin uso y tarda en despertar.

En las dos, define `DATABASE_URL` en sus variables de entorno o *secrets*.

### Streamlit Community Cloud

1. Sube el repositorio a GitHub.
2. Entra en Streamlit Community Cloud y conecta tu cuenta de GitHub.
3. Selecciona el repositorio, la rama `main` y el archivo principal `app.py`.
4. Despliega la aplicación.
5. Abre la URL pública y repite el guion de demostración.

### Guardar los datos en Supabase (recomendado)

En Streamlit Community Cloud el archivo SQLite se borra cada vez que la app se reinicia o se vuelve a desplegar. Para que estudiantes y solicitudes no se pierdan, usa Supabase (PostgreSQL gestionado, con plan gratuito):

1. Crea una cuenta en [Supabase](https://supabase.com) y un proyecto nuevo. Guarda la contraseña de la base de datos que te pide.
2. En el proyecto pulsa **Connect** y copia la cadena de conexión del **Session pooler** (puerto `5432`). Tiene esta forma:
   `postgresql://postgres.xxxxxxxx:[TU-CONTRASEÑA]@aws-0-us-east-1.pooler.supabase.com:5432/postgres`
   Usa el *pooler* y no la «Direct connection»: la conexión directa solo funciona por IPv6 y Streamlit Cloud usa IPv4.
3. Sustituye `[TU-CONTRASEÑA]` por tu contraseña. Si tiene símbolos como `@`, `#` o `/`, cámbiala por una solo con letras y números o codifícala para URL.
4. En Streamlit Community Cloud abre tu app → **Settings → Secrets** y añade:

   ```toml
   DATABASE_URL = "postgresql://postgres.xxxxxxxx:contraseña@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
   ```

5. Reinicia la app. Al arrancar crea las tablas `students` y `requests` y carga los estudiantes de prueba. Compruébalo en **Table Editor** de Supabase.

**Seguridad:** Supabase publica las tablas del esquema `public` mediante su API REST con una clave pública (`anon`). Por eso la app activa *Row Level Security* en las dos tablas sin crear políticas: la API pública no puede leerlas ni modificarlas, mientras que la app, que se conecta como dueña de las tablas, sí. No desactives RLS. Si en el futuro quieres usar la API de Supabase o Supabase Auth, crea políticas específicas antes.

En el plan gratuito, Supabase pausa el proyecto tras una semana sin actividad; se reactiva desde su panel. Cualquier otro PostgreSQL (Neon, por ejemplo) también funciona con la misma variable `DATABASE_URL`.

Para usar la base en la nube desde tu computadora, crea el archivo `.streamlit/secrets.toml` con la misma línea, o define la variable de entorno `DATABASE_URL` antes de `streamlit run app.py`. Ese archivo está en `.gitignore`: **nunca subas la contraseña a GitHub**.

Las pruebas usan SQLite temporal. Para repetirlas también contra PostgreSQL, define `TEST_DATABASE_URL` apuntando a una base **de pruebas**, nunca a la de la demo (las pruebas borran las tablas `students` y `requests`):

```bash
TEST_DATABASE_URL="postgresql://..." uv run python -m unittest discover -s tests -v
```

La disponibilidad del servicio y los pasos de la plataforma pueden cambiar. Antes de presentar, verifica que la URL pública abra correctamente.

## 10. Limitaciones conocidas y próximos pasos

- La aplicación web es el canal que funciona en esta versión.
- El webhook de WhatsApp es solo una estructura inicial: no envía respuestas ni tiene validación de firma completa.
- La matrícula ficticia sirve para demostrar el flujo, no para autenticar a una persona.
- El estado académico y el paz y salvo se consultan en datos de prueba que se cargan a mano en «Registro de estudiantes»; esa sección no tiene autenticación.
- El LLM/RAG, la base de conocimiento institucional y la integración real están pendientes.
- Para producción hacen falta autenticación, autorización, protección de datos, manejo seguro de credenciales, auditoría y pruebas de seguridad.

## 11. Relación con el documento original

El documento de UniTramite AI propone atención mediante LLM y WhatsApp Business, y describe gestión de récords, certificaciones y seguimiento de solicitudes. Esta implementación es un **MVP académico parcial**: demuestra esos flujos mediante una interfaz web, reglas simples y datos simulados. Las decisiones de tecnología, datos de prueba y validaciones son nuevas decisiones del prototipo.
