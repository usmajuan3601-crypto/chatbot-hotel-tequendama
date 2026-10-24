"""Memoria de la conversación y procesamiento de cada turno."""

import json
from datetime import date

from consulta_llm import ESCRITURA, HERRAMIENTAS, consultar_groq, ejecutar

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def nuevo_historial():
    hoy = date.today()
    sistema = (
        "Eres el asistente virtual oficial del Hotel Tequendama. Ayudas a consultar servicios, "
        "ver disponibilidad y gestionar reservas. Responde siempre en español, de forma amable, clara y breve. "
        f"Hoy es {DIAS[hoy.weekday()]} {hoy.isoformat()}; usa esa fecha para interpretar 'mañana' o 'el viernes'. "
        "Reglas: (1) usa listar_servicios para conocer los identificadores exactos de los servicios; "
        "(2) antes de proponer una reserva consulta la disponibilidad real; "
        "(3) si falta el nombre, servicio, fecha u hora, pídelos antes de usar herramientas de escritura; "
        "(4) fechas AAAA-MM-DD y horas HH:MM de 24 horas; "
        "(5) las reservas, cambios y cancelaciones NO se ejecutan al instante: al llamar la herramienta el "
        "usuario verá un resumen y debe pulsar 'Confirmar operación'. Nunca digas que algo ya quedó hecho; "
        "(6) nunca inventes códigos ni horarios libres."
    )
    return [{"role": "system", "content": sistema}]


def _limpio(mensaje):
    """Deja solo los campos que Groq acepta al reenviar un mensaje del asistente."""
    return {"role": "assistant", "content": mensaje.get("content") or "",
            "tool_calls": [{"id": l["id"], "type": "function",
                            "function": {"name": l["function"]["name"],
                                         "arguments": l["function"]["arguments"]
                                         if isinstance(l["function"]["arguments"], str)
                                         else json.dumps(l["function"]["arguments"])}}
                           for l in mensaje["tool_calls"]]}


def _argumentos(llamada):
    crudos = llamada["function"].get("arguments") or "{}"
    return json.loads(crudos) if isinstance(crudos, str) else crudos


def _resumen(plan):
    a = plan["argumentos"]
    if plan["accion"] == "crear_reserva":
        return (f"Voy a **crear** esta reserva:\n\n"
                f"Cliente: {a['cliente']}\n"
                f"Servicio: {a['servicio']}\n"
                f"Fecha: {a['fecha']}\n"
                f"Hora: {a['hora']}\n\n"
                "¿Confirmas? Pulsa **Confirmar operación** o **Descartar solicitud**.")
    
    if plan["accion"] == "modificar_reserva":
        return (f"Voy a **modificar** la reserva {a.get('codigo', 'desconocido')}:\n\n"
                f"Servicio: {a['servicio']}\n"
                f"Fecha: {a['fecha']}\n"
                f"Hora: {a['hora']}\n\n"
                "¿Confirmas? Pulsa **Confirmar operación** o **Descartar solicitud**.")
    
    return (f"Voy a **cancelar** la reserva {a.get('codigo', 'desconocido')}.\n\n"
            "¿Confirmas? Pulsa **Confirmar operación** o **Descartar solicitud**.")

def procesar_turno(mensaje, historial, clave, modelo):
    """Devuelve (resultado, historial_nuevo, plan_pendiente)."""
    historial = list(historial) + [{"role": "user", "content": mensaje}]
    for _ in range(6):
        respuesta = consultar_groq(clave, modelo, historial, HERRAMIENTAS)
        mensaje_modelo = respuesta["choices"][0]["message"]
        llamadas = mensaje_modelo.get("tool_calls") or []

        if not llamadas:
            texto = mensaje_modelo.get("content") or ""
            historial.append({"role": "assistant", "content": texto})
            return {"tipo": "respuesta", "mensaje": texto}, historial, None

        escritura = next((l for l in llamadas if l["function"]["name"] in ESCRITURA), None)
        if escritura is not None:
            plan = {"accion": escritura["function"]["name"], "argumentos": _argumentos(escritura)}
            try:
                texto = _resumen(plan)
            except KeyError:
                texto = "Me faltan datos para preparar la operación. ¿Puedes indicármelos?"
                historial.append({"role": "assistant", "content": texto})
                return {"tipo": "respuesta", "mensaje": texto}, historial, None
            historial.append({"role": "assistant", "content": texto})
            return {"tipo": "confirmacion", "mensaje": texto}, historial, plan

        historial.append(_limpio(mensaje_modelo))
        for llamada in llamadas:
            try:
                resultado = ejecutar({"accion": llamada["function"]["name"],
                                      "argumentos": _argumentos(llamada)})
                contenido = resultado["datos"]
            except KeyError as error:
                contenido = {"error": f"Falta el argumento {error}"}
            historial.append({"role": "tool", "tool_call_id": llamada["id"],
                              "content": json.dumps(contenido, ensure_ascii=False)})
    raise ValueError("El modelo no produjo una respuesta final")
