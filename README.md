# Chatbot del Hotel Tequendama

Asistente conversacional para consultar los servicios de un hotel y **crear, consultar, modificar y cancelar reservas** de esos servicios (masaje, spa, cena romántica, sala de reuniones y tour por la ciudad). Proyecto de la Electiva II (EAM-2026II), segundo corte.

**Integrantes:** Andres David Hernandez · Juan Jose Usma

**Documentación del corte:**
- [Bitácora del segundo corte](docs/Bitacora_Segundo_Corte.md)
- [Presentación (PDF)](docs/Presentacion_Segundo_Corte.pdf)
- Evidencias (capturas): `docs/evidencias/`

## Cómo funciona (resumen)

```
Usuario ─▶ Gradio (chat, :7860) ─▶ Groq (LLM con herramientas)
                │                         │ decide qué herramienta usar
                ▼                         ▼
        botón "Confirmar"  ───────▶ FastAPI (:8011) ─▶ SQLite (reservas.db)
```

| Pieza | Función |
|---|---|
| **Gradio** (`app_gradio.py`) | Interfaz web de chat. Crear, modificar o cancelar exige pulsar **Confirmar operación**. |
| **Groq** (`consulta_llm.py`, `chatbot_memoria.py`) | Modelo de lenguaje con *tool-calling*; mantiene el historial y el prompt. |
| **FastAPI** (`main.py`) | Expone las operaciones del negocio (`/api/...`). |
| **SQLite** (`almacen_sqlite.py`) | Guarda las reservas y valida horarios y cruces. |

## Requisitos

- Python 3.10 o superior (probado con 3.12).
- Una API key de Groq (https://console.groq.com).
- Dependencias: `fastapi`, `uvicorn`, `gradio>=6,<7` (ver `requirements.txt`).

## Instalación

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        Linux/Mac:  source .venv/bin/activate
pip install -r requirements.txt
```

## Variables de entorno

| Variable | Obligatoria | Valor por defecto | Uso |
|---|:-:|---|---|
| `GROQ_API_KEY` | Sí | — | Clave de Groq. **Nunca** se escribe en el código ni se sube al repositorio. |
| `GROQ_MODEL` | No | `openai/gpt-oss-20b` | Modelo de Groq a usar. |
| `CHATBOT_API_URL` | No | `http://127.0.0.1:8011` | Dirección de la FastAPI. |

Ejemplos (Windows PowerShell / Linux o Mac):

```powershell
$env:GROQ_API_KEY = "tu_clave"
```
```bash
export GROQ_API_KEY="tu_clave"
```

## Ejecución

Se necesitan **dos terminales** y la API debe encenderse primero.

**Terminal 1 — API** (http://127.0.0.1:8011/docs):
```bash
python -m uvicorn main:app --reload --port 8011
```

**Terminal 2 — Chat** (http://127.0.0.1:7860):
```bash
python app_gradio.py
```

En Windows también puedes hacer doble clic en `iniciar_api.bat` y luego en `iniciar_chatbot.bat` (crean el entorno `.venv` la primera vez y piden la clave de Groq sin mostrarla).

La base de datos `reservas.db` se crea sola al iniciar la API; no hay que prepararla a mano.

## Prueba inicial

Con la API encendida (no necesita Groq):

```bash
python test_bot.py
```

Resultado esperado: una línea `OK` por prueba y al final `Todo bien.` Si falla alguna, el programa termina con código 1.

Prueba del chat: abre http://127.0.0.1:7860 y escribe *"¿Qué servicios tienen?"*. Debe responder con la lista de servicios y precios.

## Reglas del negocio

- Atención todos los días, de **08:00 a 20:00**, con horas en pasos de **30 minutos**.
- Cada servicio tiene su duración (`negocio.json`): el servicio debe terminar dentro del horario.
- No se permiten fechas pasadas.
- **Una sola agenda:** dos reservas activas no pueden cruzarse en el tiempo, sin importar el servicio. Reservas pegadas (una termina cuando empieza la otra) sí se permiten.
- Una reserva cancelada libera su horario.

## Endpoints de la API

| Método | Ruta | Acción |
|---|---|---|
| GET | `/api/servicios` | Hotel, habitaciones y servicios |
| GET | `/api/disponibilidad?fecha=AAAA-MM-DD&servicio=spa` | Horas libres |
| GET | `/api/reservas` | Lista todas las reservas |
| GET | `/api/reservas/{codigo}` | Consulta una reserva |
| POST | `/api/reservas` | Crea una reserva (exige `confirmada: true`) |
| PUT | `/api/reservas/{codigo}` | Modifica servicio, fecha y hora |
| DELETE | `/api/reservas/{codigo}` | Cancela (estado `cancelada`; la fila se conserva) |

Códigos de error: `404` reserva inexistente, `409` cruce de horario o estado inválido, `422` datos inválidos.

## Estructura del proyecto

```
├── main.py               API FastAPI
├── almacen_sqlite.py     Reservas en SQLite y validación de horarios
├── consulta_llm.py       Herramientas del LLM, cliente Groq y cliente HTTP
├── chatbot_memoria.py    Prompt, historial y ciclo de cada turno
├── app_gradio.py         Interfaz de chat
├── negocio.json          Habitaciones y servicios (datos ficticios)
├── test_bot.py           Prueba de humo contra la API
├── diagnostico_groq.py   Diagnóstico de la conexión con Groq
├── iniciar_*.bat / .ps1  Lanzadores para Windows
├── requirements.txt
└── docs/                 Bitácora, presentación y evidencias
```

## Errores frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Configura GROQ_API_KEY y GROQ_MODEL` | Falta la clave | Define `GROQ_API_KEY` y reinicia el chat. |
| `No pude conectar con Groq o FastAPI` | La API no está encendida o el puerto no coincide | Inicia la API en el puerto 8011 o ajusta `CHATBOT_API_URL`. |
| HTTP 403 desde Groq | Cloudflare bloquea el `User-Agent` por defecto de Python | Ya está resuelto en el código (`User-Agent: Mozilla/5.0`). |
| HTTP 404 `model_not_found` | Modelo no disponible para tu clave, o `\r` oculto en la variable | Ejecuta `diagnostico.bat` (o `python diagnostico_groq.py`) y usa un modelo de la lista. |
| `Confirma o descarta la solicitud pendiente primero` | Hay una operación esperando | Pulsa **Confirmar operación** o **Descartar solicitud**. |

## Seguridad

- La clave de Groq se lee solo de la variable de entorno. Si alguna vez se escribió en un archivo, **revócala** en https://console.groq.com y crea otra.
- El `.gitignore` debe excluir `.venv/`, `__pycache__/` y `reservas.db`.
- Todos los datos del proyecto son ficticios.

## Limitaciones conocidas

- La interfaz reserva **servicios**, no noches de habitación; las habitaciones solo se consultan como información.
- Hay una única agenda para todo el hotel (un servicio a la vez).
- El estado de la conversación vive en memoria de Gradio: se pierde al reiniciar el chat (las reservas sí persisten en SQLite).
- No hay autenticación de usuarios.
