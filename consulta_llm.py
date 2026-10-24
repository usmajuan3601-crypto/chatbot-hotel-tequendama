"""Módulo de integración con Groq LLM y cliente HTTP para FastAPI (Hotel Tequendama).
Sin dependencias externas (solo urllib y json).
"""

import json
import os
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

# URL base de la FastAPI local
API_FASTAPI = os.getenv("CHATBOT_API_URL", "http://127.0.0.1:8011").rstrip("/")

# Operaciones que modifican la base de datos y requieren confirmación explícita
ESCRITURA = ["crear_reserva", "modificar_reserva", "cancelar_reserva"]

# Declaración de herramientas para Groq Tool-Calling
HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "listar_servicios",
            "description": "Obtiene la lista de servicios y habitaciones disponibles en el hotel junto con sus precios.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_disponibilidad",
            "description": "Consulta los horarios disponibles para un servicio específico en una fecha determinada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "servicio": {
                        "type": "string",
                        "description": "Nombre del servicio (ej. masaje, spa, habitacion)",
                    },
                    "fecha": {
                        "type": "string",
                        "description": "Fecha en formato YYYY-MM-DD",
                    },
                },
                "required": ["servicio", "fecha"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_reserva",
            "description": "Crea una nueva reserva para un cliente en un servicio, fecha y hora especificados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente": {
                        "type": "string",
                        "description": "Nombre completo del cliente",
                    },
                    "servicio": {
                        "type": "string",
                        "description": "Nombre del servicio",
                    },
                    "fecha": {
                        "type": "string",
                        "description": "Fecha en formato YYYY-MM-DD",
                    },
                    "hora": {
                        "type": "string",
                        "description": "Hora en formato HH:MM (ej. 10:00)",
                    },
                },
                "required": ["cliente", "servicio", "fecha", "hora"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modificar_reserva",
            "description": "Modifica el servicio, fecha u hora de una reserva existente por su ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_reserva": {
                        "type": "integer",
                        "description": "ID numérico de la reserva",
                    },
                    "servicio": {
                        "type": "string",
                        "description": "Nuevo servicio",
                    },
                    "fecha": {
                        "type": "string",
                        "description": "Nueva fecha YYYY-MM-DD",
                    },
                    "hora": {
                        "type": "string",
                        "description": "Nueva hora HH:MM",
                    },
                },
                "required": ["id_reserva"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancelar_reserva",
            "description": "Cancela una reserva existente dado su ID numérico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_reserva": {
                        "type": "integer",
                        "description": "ID numérico de la reserva a cancelar",
                    }
                },
                "required": ["id_reserva"],
            },
        },
    },
]


def consultar_groq(*args, **kwargs):
    """Consulta la API de Groq resolviendo parámetros dinámicos y evitando bucles de herramientas."""
    clave_api = os.getenv("GROQ_API_KEY", "")
    modelo = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    mensajes = []

    if len(args) == 4:
        clave_api, modelo, mensajes = args[0], args[1], args[2]
    elif len(args) == 3:
        if isinstance(args[0], list):
            mensajes, clave_api, modelo = args[0], args[1], args[2]
        else:
            clave_api, modelo, mensajes = args[0], args[1], args[2]
    elif len(args) == 2:
        if isinstance(args[0], list):
            mensajes, clave_api = args[0], args[1]
        else:
            clave_api, modelo = args[0], args[1]
    elif len(args) == 1:
        mensajes = args[0] if isinstance(args[0], list) else [{"role": "user", "content": str(args[0])}]

    if "clave" in kwargs and kwargs["clave"]:
        clave_api = kwargs["clave"]
    if "clave_api" in kwargs and kwargs["clave_api"]:
        clave_api = kwargs["clave_api"]
    if "modelo" in kwargs and kwargs["modelo"]:
        modelo = kwargs["modelo"]
    if "historial" in kwargs and kwargs["historial"] is not None:
        mensajes = kwargs["historial"]
    if "mensajes" in kwargs and kwargs["mensajes"] is not None:
        mensajes = kwargs["mensajes"]

    clave_limpia = str(clave_api or "").replace("\r", "").strip()
    modelo_limpio = str(modelo or "qwen/qwen3.8-27b").replace("\r", "").strip()

    if not isinstance(mensajes, list):
        mensajes = [{"role": "user", "content": str(mensajes)}]

    tiene_respuesta_tool = any(
        isinstance(m, dict) and m.get("role") == "tool" for m in mensajes
    )

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {clave_limpia}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    payload = {
        "model": modelo_limpio,
        "messages": mensajes,
        "temperature": 0.2,
    }

    if tiene_respuesta_tool:
        payload["tool_choice"] = "none"
    else:
        payload["tools"] = HERRAMIENTAS
        payload["tool_choice"] = "auto"

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data_bytes, headers=headers, method="POST"
    )

    with urllib.request.urlopen(req) as resp:
        contenido = resp.read().decode("utf-8")
        res_json = json.loads(contenido)

    try:
        choices = res_json.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            if not msg.get("tool_calls"):
                content = msg.get("content")
                if not content or str(content).strip() == "" or str(content) == "null":
                    reasoning = msg.get("reasoning_content") or msg.get("reasoning")
                    if reasoning and str(reasoning).strip():
                        msg["content"] = str(reasoning)
                    else:
                        msg["content"] = "Con gusto te ayudo. ¿Qué información sobre habitaciones, servicios o reservas del Hotel Tequendama deseas consultar?"
    except Exception:
        pass

    return res_json


consultar_llm = consultar_groq


def ejecutar_http(metodo, ruta, datos=None):
    """Realiza peticiones HTTP a la API local de FastAPI."""
    url = f"{API_FASTAPI}{ruta}"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    data_bytes = json.dumps(datos).encode("utf-8") if datos else None

    req = urllib.request.Request(
        url, data=data_bytes, headers=headers, method=metodo
    )
    with urllib.request.urlopen(req) as resp:
        res_text = resp.read().decode("utf-8")
        return json.loads(res_text)


def ejecutar(plan, confirmar=False):
    """Ejecuta la función seleccionada por el LLM contra el backend de FastAPI."""
    nombre = plan.get("funcion")
    args = plan.get("argumentos", {})

    if nombre in ESCRITURA and not confirmar:
        return {
            "tipo": "confirmacion",
            "mensaje": f"⚠️ Se requiere confirmación para ejecutar **{nombre}** con estos datos:\n\n```json\n{json.dumps(args, ensure_ascii=False, indent=2)}\n```\n\nHaz clic en **Confirmar operación** para proceder.",
        }

    if nombre == "listar_servicios":
        res = ejecutar_http("GET", "/servicios")
        return {"tipo": "resultado", "datos": res}
    elif nombre == "consultar_disponibilidad":
        servicio = args.get("servicio", "")
        fecha = args.get("fecha", "")
        ruta = f"/disponibilidad?servicio={urllib.parse.quote(servicio)}&fecha={urllib.parse.quote(fecha)}"
        res = ejecutar_http("GET", ruta)
        return {"tipo": "resultado", "datos": res}
    elif nombre == "crear_reserva":
        res = ejecutar_http("POST", "/reservas", args)
        return {"tipo": "resultado", "datos": res}
    elif nombre == "modificar_reserva":
        id_res = args.get("id_reserva")
        res = ejecutar_http("PUT", f"/reservas/{id_res}", args)
        return {"tipo": "resultado", "datos": res}
    elif nombre == "cancelar_reserva":
        id_res = args.get("id_reserva")
        res = ejecutar_http("DELETE", f"/reservas/{id_res}")
        return {"tipo": "resultado", "datos": res}
    else:
        return {"tipo": "error", "mensaje": f"Función desconocida: {nombre}"}