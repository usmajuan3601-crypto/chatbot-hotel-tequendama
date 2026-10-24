import os
from cliente import HERRAMIENTAS, consultar_groq, ejecutar

# Configura tu clave de Groq (o usa os.environ["GROQ_API_KEY"])
GROQ_API_KEY = "tu_groq_api_key_aqui"
MODELO = "llama3-8b-8192"

mensajes = [
    {"role": "system", "content": "Eres un asistente del Hotel Tequendama. Ayuda al cliente a consultar servicios o hacer reservas."},
    {"role": "user", "content": "¿Qué servicios tienen disponibles?"}
]

print("1. Enviando pregunta a Groq...")
respuesta = consultar_groq(GROQ_API_KEY, MODELO, mensajes, herramientas=HERRAMIENTAS)

mensaje_groq = respuesta["choices"][0]["message"]

# Verificar si Groq quiere llamar a una herramienta (tool call)
if "tool_calls" in mensaje_groq and mensaje_groq["tool_calls"]:
    herramienta = mensaje_groq["tool_calls"][0]["function"]
    import json
    plan = {
        "accion": herramienta["name"],
        "argumentos": json.loads(herramienta["arguments"])
    }
    print(f"2. Groq decidió ejecutar la acción: {plan['accion']} con argumentos {plan['argumentos']}")
    
    # Ejecutar contra FastAPI
    resultado = ejecutar(plan, confirmar=True)
    print("3. Resultado del servidor backend:")
    print(resultado["mensaje"])
else:
    print("Respuesta directa de Groq:")
    print(mensaje_groq["content"])