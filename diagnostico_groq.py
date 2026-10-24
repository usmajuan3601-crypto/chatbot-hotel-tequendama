"""Prueba paso a paso la conexión con Groq y muestra el error exacto."""
import getpass, json, os, sys, urllib.error, urllib.request
from consulta_llm import HERRAMIENTAS

BASE = "https://api.groq.com/openai/v1"
clave = (os.getenv("GROQ_API_KEY") or getpass.getpass("API key de Groq (no se ve al pegar): ")).strip()
modelo = (os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile").strip()
print(f"\nModelo a probar: {modelo!r}")
print(f"Largo de la clave: {len(clave)} caracteres, empieza por {clave[:4]!r}")


def llamar(metodo, ruta, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(BASE + ruta, data=datos, method=metodo, headers={
        "Authorization": f"Bearer {clave}", "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace") or "(cuerpo vacío)"
    except Exception as e:
        return None, repr(e)


print("\n[1] Pidiendo la lista de modelos de tu cuenta...")
estado, datos = llamar("GET", "/models")
print("   estado:", estado)
if estado == 200:
    ids = sorted(m["id"] for m in datos["data"])
    print("   modelos disponibles:\n    - " + "\n    - ".join(ids))
    if modelo not in ids:
        print(f"\n   >>> {modelo!r} NO está en tu lista. Usa uno de arriba con $env:GROQ_MODEL")
else:
    print("   respuesta:", datos)
    print("   >>> Problema con la API key (401/403) o con la red. Crea otra clave.")
    sys.exit(1)

print("\n[2] Mensaje simple, sin herramientas...")
estado, datos = llamar("POST", "/chat/completions", {
    "model": modelo, "messages": [{"role": "user", "content": "Responde solo: hola"}]})
print("   estado:", estado)
print("   respuesta:", datos["choices"][0]["message"]["content"] if estado == 200 else datos)

print("\n[3] Mensaje con las herramientas del hotel...")
estado, datos = llamar("POST", "/chat/completions", {
    "model": modelo, "temperature": 0.2, "tools": HERRAMIENTAS, "tool_choice": "auto",
    "messages": [{"role": "system", "content": "Eres el asistente del Hotel Tequendama."},
                 {"role": "user", "content": "¿Qué servicios tienen?"}]})
print("   estado:", estado)
print("   respuesta:", json.dumps(datos, ensure_ascii=False)[:600] if estado == 200 else datos)
print("\nListo. Copia todo este resultado y mándamelo.")
