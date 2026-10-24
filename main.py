"""API del Hotel Tequendama con almacenamiento en SQLite (reservas.db)."""

import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from almacen_sqlite import AgendaSQLite, ConflictoReserva, ReservaNoEncontrada

BASE = Path(__file__).resolve().parent
NEGOCIO = json.loads((BASE / "negocio.json").read_text(encoding="utf-8-sig"))
SERVICIOS = NEGOCIO["servicios"]

agenda = AgendaSQLite(
    BASE / "reservas.db",
    SERVICIOS,
    apertura="08:00",
    cierre="20:00",
    dias=(0, 1, 2, 3, 4, 5, 6),  # el hotel atiende todos los días
    paso=30,
)

app = FastAPI(title="API Hotel Tequendama")


class ReservaNueva(BaseModel):
    cliente: str = Field(min_length=2)
    servicio: str
    fecha: date
    hora: str
    confirmada: bool = True


class CambioReserva(BaseModel):
    servicio: str
    fecha: date
    hora: str


def responder(funcion, *args):
    try:
        return funcion(*args)
    except ReservaNoEncontrada as error:
        raise HTTPException(404, str(error)) from error
    except ConflictoReserva as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/servicios")
def obtener_servicios():
    return {
        "hotel": NEGOCIO["hotel"],
        "habitaciones": NEGOCIO["habitaciones"],
        "servicios": SERVICIOS,
    }


@app.get("/api/disponibilidad")
def consultar_disponibilidad(fecha: date, servicio: str):
    return responder(agenda.disponibilidad, fecha.isoformat(), servicio)


@app.get("/api/reservas")
def listar_reservas():
    return agenda.listar()


@app.get("/api/reservas/{codigo}")
def consultar_reserva(codigo: str):
    return responder(agenda.consultar, codigo)


@app.post("/api/reservas", status_code=201)
def crear_reserva(datos: ReservaNueva):
    if not datos.confirmada:
        raise HTTPException(400, "La operación debe estar confirmada")
    return responder(agenda.crear, datos.cliente, datos.servicio,
                     datos.fecha.isoformat(), datos.hora)


@app.put("/api/reservas/{codigo}")
def modificar_reserva(codigo: str, datos: CambioReserva):
    return responder(agenda.modificar, codigo, datos.servicio,
                     datos.fecha.isoformat(), datos.hora)


@app.delete("/api/reservas/{codigo}")
def cancelar_reserva(codigo: str):
    return responder(agenda.cancelar, codigo)
