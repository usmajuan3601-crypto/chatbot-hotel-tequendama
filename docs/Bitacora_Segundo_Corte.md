---
tipo: bitacora-corte
curso: electiva ll
periodo: EAM-2026II
equipo: Andres Hernandez_Juan Usma
corte: 2
proyecto: Chatbot del Hotel Tequendama
estado: Borrador — completar los campos [COMPLETAR]
---

# Bitácora — Segundo corte: Chatbot del Hotel Tequendama

> **Cómo leer este documento.** Los campos marcados **[COMPLETAR]** dependen de datos que solo el equipo conoce (fechas reales, capturas, quién hizo qué). Todo lo demás se verificó contra el código entregado.

## 1. Contexto y alcance

**Problema.** Un hotel recibe solicitudes de reserva de sus servicios (masaje, spa, cena romántica, sala de reuniones y tour) y necesita atenderlas por chat sin que dos reservas se crucen.

**Solución.** Un chatbot en español que conversa con el usuario, consulta la disponibilidad real y gestiona reservas. El usuario siempre confirma antes de que se escriba algo en la base de datos.

**Alcance del corte**

| Incluye | No incluye |
|---|---|
| Chat de varios turnos con memoria | Reserva de noches de habitación (solo se consultan como información) |
| Crear, consultar, modificar y cancelar reservas de servicios | Autenticación de usuarios y pagos |
| Validación de horario, duración y cruces | Varias agendas en paralelo (una sola agenda para todo el hotel) |
| Persistencia en SQLite | Despliegue en un servidor público |
| Confirmación obligatoria de las escrituras | |

**Integrantes:** Andres David Hernandez · Juan Jose Usma

## 2. Arquitectura y archivos

```
Usuario ─▶ Gradio (:7860) ─▶ Groq (LLM + herramientas)
               │                    │
               ▼                    ▼
        "Confirmar operación" ─▶ FastAPI (:8011) ─▶ SQLite (reservas.db)
```

| Archivo | Responsabilidad |
|---|---|
| `app_gradio.py` | Interfaz web; estado por sesión; botones Enviar, Confirmar, Descartar y Reiniciar. |
| `chatbot_memoria.py` | Prompt de sistema, historial y ciclo de cada turno (`procesar_turno`). |
| `consulta_llm.py` | Definición de las 6 herramientas, cliente de Groq y cliente HTTP hacia la API; guardrail `ESCRITURA`. |
| `main.py` | API FastAPI con las rutas `/api/...` y la traducción de errores a HTTP 404/409/422. |
| `almacen_sqlite.py` | Clase `AgendaSQLite`: tabla `reservas`, validaciones y transacciones. |
| `negocio.json` | Catálogo de habitaciones y servicios con precio y duración. |
| `test_bot.py` | Prueba de humo contra la API real. |
| `diagnostico_groq.py` | Diagnóstico paso a paso de la conexión con Groq. |

**Qué hace cada capa.** Gradio es la pantalla; Groq interpreta el texto del usuario y decide qué herramienta usar; FastAPI recibe esas operaciones y aplica las reglas del negocio; SQLite guarda los datos aunque se apague el programa.

## 3. Consumo del modelo (Groq)

| Elemento | Valor |
|---|---|
| Endpoint | `POST https://api.groq.com/openai/v1/chat/completions` |
| Modelo | `openai/gpt-oss-20b` (configurable con `GROQ_MODEL`) |
| Cliente | `urllib` de la biblioteca estándar (sin dependencias externas) |
| Headers | `Authorization: Bearer <GROQ_API_KEY>`, `Content-Type: application/json`, `User-Agent: Mozilla/5.0` |
| Payload | `model`, `messages` (historial completo), `temperature: 0.2`, `tools`, `tool_choice: "auto"` |
| Timeout | 60 s hacia Groq, 20 s hacia la API |

**Herramientas expuestas al modelo (tool-calling):** `listar_servicios`, `consultar_disponibilidad`, `consultar_reserva`, `crear_reserva`, `modificar_reserva`, `cancelar_reserva`.

**Prompt de sistema** (resumen de `nuevo_historial()`): asistente oficial del Hotel Tequendama; responde en español, amable y breve; conoce la fecha de hoy para interpretar "mañana"; debe consultar `listar_servicios` para usar los identificadores exactos; debe consultar la disponibilidad antes de proponer; pide los datos que falten antes de escribir; nunca afirma que algo ya quedó hecho (el usuario debe confirmar); nunca inventa códigos ni horarios.

**Seguridad de la clave.** `GROQ_API_KEY` se lee solo de la variable de entorno. Los lanzadores `.ps1` la piden sin mostrarla.

## 4. Conversación

- **Roles.** El historial es una lista de mensajes `system`, `user`, `assistant` y `tool`, que se reenvía completa a Groq en cada turno.
- **Ciclo de un turno** (`procesar_turno`): se agrega el mensaje del usuario; se llama a Groq; si el modelo pide herramientas de **lectura**, se ejecutan contra la API y su resultado vuelve al modelo (hasta 6 vueltas); si pide una herramienta de **escritura**, el turno se detiene y se genera un resumen para confirmar.
- **Estado por sesión.** `gr.State` guarda `historial`, `pantalla` y `pendiente`, de modo que cada pestaña del navegador tiene su propia conversación.
- **Confirmación.** Mientras hay una operación pendiente no se aceptan mensajes nuevos: hay que **Confirmar operación** o **Descartar solicitud**. Al confirmar, la acción se envía a la API con `confirmar=True`.
- **Reinicio.** El botón *Reiniciar conversación* (o limpiar el chat) crea un estado nuevo y vacío.
- **Guardrail doble.** (1) `ejecutar()` devuelve `tipo: "confirmacion"` y no llama a la API si la acción está en `ESCRITURA` y no se confirmó. (2) La API rechaza `POST /api/reservas` si `confirmada` es falso.

## 5. API y persistencia

| Método | Ruta | Descripción | Errores |
|---|---|---|---|
| GET | `/api/servicios` | Hotel, habitaciones y servicios | — |
| GET | `/api/disponibilidad` | Horas libres de un servicio en una fecha | 422 |
| GET | `/api/reservas` | Lista todas las reservas | — |
| GET | `/api/reservas/{codigo}` | Consulta una reserva | 404 |
| POST | `/api/reservas` | Crea una reserva | 400, 409, 422 |
| PUT | `/api/reservas/{codigo}` | Modifica servicio, fecha y hora | 404, 409, 422 |
| DELETE | `/api/reservas/{codigo}` | Cancela la reserva | 404, 409 |

**Tabla `reservas`:** `codigo` (clave primaria, 8 caracteres hexadecimales), `cliente`, `servicio`, `fecha`, `hora`, `duracion_minutos` (> 0) y `estado` (`activa` o `cancelada`), con un índice sobre `(fecha, estado)`.

**Cancelar no borra:** la fila pasa a estado `cancelada`, lo que conserva el historial y libera el horario.

## 6. Disponibilidad

- **Horario:** 08:00 a 20:00, todos los días, en pasos de 30 minutos.
- **Duración:** viene de `negocio.json` (masaje 60, spa 90, cena 120, sala 120, tour 180 min). La atención debe terminar antes del cierre.
- **Cruce de intervalos:** dos intervalos se cruzan si `inicio < fin_existente` y `fin > inicio_existente`. Como hay una sola agenda, ningún par de reservas activas puede cruzarse, aunque sean de servicios distintos. Una reserva que empieza justo cuando otra termina es válida.
- **Transacción:** al escribir se usa `BEGIN IMMEDIATE`, así la comprobación de disponibilidad y el guardado ocurren en la misma transacción. Dos solicitudes simultáneas no pueden ocupar el mismo horario; si hay error se hace `rollback`.
- **Modificar** excluye la propia reserva al buscar cruces, para poder mover una reserva sin chocar consigo misma.

## 7. Resultados

### 7.1 Evolución del proyecto

| # | Fecha | Avance | Qué cambió | Participó | Dificultad y solución | Cómo se comprobó |
|---|---|---|---|---|---|---|
| 1 | 2026-09-12 (Clase 02) | Chatbot en **Flowise + Groq** con FastAPI y `hotel.json` | Primer flujo con memoria por `sessionId` y Custom Tools | Andres (API), Juan (conversación) | El bot decía que modificó la reserva pero el JSON no cambiaba: el payload no coincidía con el esquema Pydantic. Se corrigieron las claves. | Pruebas de memoria y revisión de `hotel.json` |
| 2 | 2026-10-19 (Clase 04) | **Gradio + Groq** con tool-calling en Python | Se reemplazó Flowise por código propio: `app_gradio.py`, `consulta_llm.py` | Andres (cliente y depuración), Juan (backend base) | Errores HTTP 403 (Cloudflare, se añadió `User-Agent`), 404 `model_not_found` (había `\r` en la variable de entorno) y `ImportError` de `ESCRITURA`. | Respuesta 200 de Groq y chat funcionando en `:7860` |
| 3 | [COMPLETAR] | **SQLite** y disponibilidad | `almacen_sqlite.py` reemplaza el almacenamiento en JSON; reglas de horario y cruces | [COMPLETAR] | [COMPLETAR] | Pruebas de la sección 7.2 |
| 4 | [COMPLETAR] | Historial y confirmación | `chatbot_memoria.py` y botones Confirmar/Descartar | [COMPLETAR] | [COMPLETAR] | [COMPLETAR] |

### 7.2 Pruebas

**A. Capa de reservas (SQLite).** Ejecutadas con las reglas reales del hotel (08:00–20:00, pasos de 30 min) sobre una base temporal.

| # | Prueba | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|:-:|
| 1 | Crear masaje mañana 10:00 | Reserva `activa` con código | Reserva creada | ✅ |
| 2 | Otra reserva exactamente a las 10:00 | Rechazo por cruce | `ConflictoReserva`: el intervalo se cruza | ✅ |
| 3 | Spa (90 min) a las 10:30 | Rechazo por cruce parcial | `ConflictoReserva` | ✅ |
| 4 | Masaje a las 11:00 (pegado al anterior) | Permitido | Reserva creada | ✅ |
| 5 | Cena (120 min) a las 19:00 | Rechazo: termina después del cierre | "debe terminar dentro del horario" | ✅ |
| 6 | Hora 12:15 | Rechazo: fuera de pasos de 30 min | "pasos de 30 minutos" | ✅ |
| 7 | Fecha pasada | Rechazo | "No se puede reservar en una fecha pasada" | ✅ |
| 8 | Servicio inexistente | Rechazo | "Servicio desconocido" | ✅ |
| 9 | Nombre vacío | Rechazo | "Indica el nombre del cliente" | ✅ |
| 10 | Modificar a spa 14:00 | Reserva actualizada | Reserva actualizada | ✅ |
| 11 | Cancelar y consultar disponibilidad | El horario queda libre | 10:00 vuelve a aparecer | ✅ |
| 12 | Cancelar dos veces | Rechazo | "La reserva ya está cancelada" | ✅ |
| 13 | Modificar una cancelada | Rechazo | "La reserva ya no está activa" | ✅ |
| 14 | Consultar código inexistente | Error 404 | `ReservaNoEncontrada` | ✅ |
| 15 | Reutilizar el horario liberado | Permitido | Reserva creada | ✅ |
| 16 | Reiniciar la agenda (nueva conexión) | Las filas se conservan | 3 filas antes y 3 después | ✅ |

**B. API completa y chat.** Requieren Groq y la API encendida; el equipo debe ejecutarlas y adjuntar evidencia.

| # | Prueba | Resultado esperado | Resultado obtenido | Evidencia |
|---|---|---|---|---|
| 17 | `python test_bot.py` | Todas las líneas `OK` y "Todo bien." | [COMPLETAR] | [COMPLETAR captura] |
| 18 | Conversación de varios turnos: pedir un masaje dando los datos por partes | El bot recuerda los datos ya dichos y pide solo lo que falta | [COMPLETAR] | [COMPLETAR captura] |
| 19 | Dos pestañas del navegador | Cada una conserva su propia conversación | [COMPLETAR] | [COMPLETAR captura] |
| 20 | Reiniciar conversación | El chat y el historial quedan vacíos | [COMPLETAR] | [COMPLETAR captura] |
| 21 | Crear → Confirmar | Aparece el resumen, y solo tras confirmar se guarda | [COMPLETAR] | [COMPLETAR captura] |
| 22 | Crear → Descartar | No se guarda nada | [COMPLETAR] | [COMPLETAR captura] |
| 23 | Intentar enviar un mensaje con una operación pendiente | Error "Confirma o descarta…" | [COMPLETAR] | [COMPLETAR captura] |
| 24 | Modificar y cancelar por código desde el chat | Reserva cambiada y luego `cancelada` | [COMPLETAR] | [COMPLETAR captura] |
| 25 | Pedir un horario ocupado desde el chat | El bot informa que no hay cupo (error 409) | [COMPLETAR] | [COMPLETAR captura] |
| 26 | Reiniciar la API y listar `/api/reservas` | Las reservas siguen ahí | [COMPLETAR] | [COMPLETAR captura] |
| 27 | Apagar la API y enviar un mensaje | Mensaje de error claro, sin caerse | [COMPLETAR] | [COMPLETAR captura] |

### 7.3 Errores resueltos durante el corte

| Error | Causa | Solución |
|---|---|---|
| HTTP 403 de Groq | Cloudflare bloquea el `User-Agent` por defecto de `urllib` | Header `User-Agent: Mozilla/5.0` |
| HTTP 404 `model_not_found` | Modelo no asignado a la clave y `\r` oculto en la variable | `.replace("\r", "").strip()` y modelo `openai/gpt-oss-20b` |
| `ImportError: ESCRITURA` | La constante no estaba expuesta en `consulta_llm.py` | Se declaró a nivel de módulo |
| Reserva "modificada" que no cambiaba el JSON (Flowise) | Payload distinto al esquema Pydantic | Se alinearon las claves; la lógica pasó a SQLite |

### 7.4 Comparación con la versión de Flowise + JSON

| Aspecto | Flowise + `hotel.json` (corte 1) | Gradio + FastAPI + SQLite (corte 2) |
|---|---|---|
| Control del flujo | Nodos visuales; menos visibilidad del prompt y del historial | Código propio: se ve y se prueba cada paso |
| Interfaz | Chat de Flowise | Gradio con Confirmar, Descartar y Reiniciar |
| Persistencia | Archivo JSON reescrito | SQLite con transacciones |
| Disponibilidad | Marcas `disponible: true/false` por habitación | Intervalos con duración, horario y detección de cruces |
| Seguridad de escrituras | Dependía del prompt | Guardrail en código + confirmación del usuario + validación en la API |
| Qué se reserva | Noches de habitación | Servicios del hotel por franja horaria |
| Facilidad inicial | Más rápido de montar | Más trabajo, pero más control y mejores pruebas |

### 7.5 Limitaciones y mejoras pendientes

- Las habitaciones solo se consultan; no se reservan noches (check-in/check-out).
- Una sola agenda: un servicio a la vez en todo el hotel. Mejora: una agenda o capacidad por servicio.
- El estado de la conversación vive en memoria; si se reinicia Gradio se pierde (las reservas no).
- No hay autenticación: cualquiera con un código puede modificar o cancelar esa reserva.
- No hay pruebas automáticas del flujo del LLM; solo la prueba de humo `test_bot.py`.
- [COMPLETAR] Casos que fallaron en las pruebas B y su estado actual.

## 8. Uso de inteligencia artificial

| Herramienta | Objetivo | Qué se utilizó | Cómo se verificó | Qué se modificó |
|---|---|---|---|---|
| Gemini AI | Depurar errores HTTP 403/404 y reestructurar `consulta_llm.py` | Parches y script de diagnóstico | Terminal de VS Code y pruebas en el navegador | Headers, limpieza de `\r`, lanzadores `.ps1` |
| ChatGPT | Guía para ejecutar FastAPI | Pasos de arranque | [COMPLETAR] | [COMPLETAR] |
| Claude | Redactar README, bitácora y presentación a partir del código | Borradores de documentación y pruebas de la capa SQLite | Contraste con el código fuente | [COMPLETAR] |

## 9. Aprendizajes

1. Las protecciones como Cloudflare descartan peticiones sin un `User-Agent` de navegador.
2. Las variables de entorno en Windows pueden traer `\r`; hay que limpiarlas.
3. Una regla importante no debe depender solo del prompt: la confirmación se impone en el código.
4. Comprobar y guardar dentro de la misma transacción evita reservas duplicadas.

## 10. Revisión antes de entregar

- [ ] README, bitácora y PDF describen la misma versión (archivos, puertos, reglas).
- [ ] Se completaron todos los campos **[COMPLETAR]** y las capturas están en `docs/evidencias/`.
- [ ] No hay claves reales en el repositorio (ni en la bitácora) y `.gitignore` excluye `.venv/`, `__pycache__/` y `reservas.db`.
- [ ] El repositorio se probó desde una copia nueva siguiendo el README.
- [ ] Todos los integrantes pueden explicar el recorrido de una solicitud: chat → Groq → API → SQLite.
