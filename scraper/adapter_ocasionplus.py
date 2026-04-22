"""Adaptador OcasionPlus — API REST (Zeus).

Realidad de la API (verificado):
- brand: funciona (CASE-SENSITIVE: "Fiat" sí, "FIAT" no)
- model: IGNORADO por la API
- market: funciona ("canarias", "peninsula")
- province: funciona ("Las Palmas", "Madrid", etc.)
- fuel: funciona (case-insensitive: "Gasolina", "Diésel", etc.)
- transmission: funciona ("AUTO", "MANUAL")
- year/km: NO disponibles como params
"""
import json
import time
import urllib.request
import urllib.error
from urllib.parse import urlencode, quote
from .modelo import Vehiculo

API_URL = "https://zeus.ocasionplus.com/vehicles/search/CAR"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.ocasionplus.com/",
}

FUEL_MAP = {
    "gasolina": "Gasolina",
    "diésel": "Diésel", "diesel": "Diésel",
    "eléctrico": "Eléctrico", "electrico": "Eléctrico",
    "híbrido": "Híbrido", "hibrido": "Híbrido",
    "glp": "GLP",
}

TRANS_MAP = {
    "automático": "AUTO", "automatico": "AUTO", "auto": "AUTO",
    "manual": "MANUAL",
}


def _fetch(params: dict) -> dict:
    parts = []
    for k, v in params.items():
        parts.append(f"{k}={quote(str(v))}")
    url = f"{API_URL}?{'&'.join(parts)}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def buscar(marca: str = "", modelo: str = "", km_max: int = None, km_min: int = None,
           anio_min: int = None, anio_max: int = None, combustible: str = "",
           transmision: str = "", solo_canarias: bool = False, provincia_op: str = "",
           max_paginas: int = 200, on_progreso=None) -> list[Vehiculo]:
    """
    Filtros server-side: brand, market, province, fuel, transmission.
    Filtros client-side: model, year, km.
    """
    params = {"page": 1, "searchType": "organic"}

    # Brand (case-sensitive: primera mayúscula)
    if marca:
        params["brand"] = marca.strip().title()

    # Market / Province
    if solo_canarias:
        params["market"] = "canarias"
    elif provincia_op:
        params["province"] = provincia_op

    # Fuel
    if combustible:
        fuel_key = combustible.lower().strip()
        params["fuel"] = FUEL_MAP.get(fuel_key, combustible)

    # Transmission
    if transmision:
        trans_key = transmision.lower().strip()
        params["transmission"] = TRANS_MAP.get(trans_key, transmision.upper())

    modelo_f = modelo.upper().strip()
    vehiculos = []
    total_raw = 0

    for p in range(1, max_paginas + 1):
        params["page"] = p
        try:
            data = _fetch(params)
        except (urllib.error.URLError, TimeoutError) as e:
            if on_progreso:
                on_progreso(f"OcasionPlus: error pág {p}: {e}")
            break

        page_info = data.get("page", {})
        total_pages = page_info.get("total", 1)

        for v in data.get("data", []):
            total_raw += 1
            v_model = (v.get("model") or "").upper()
            chars = v.get("characteristics", {})
            motor = chars.get("engine", {})
            dealer = v.get("dealer", {})
            precio_obj = v.get("price", {})
            images = v.get("images", [])
            slug = v.get("slug", "")

            # Filtro local: modelo (la API lo ignora)
            if modelo_f and modelo_f not in v_model and v_model not in modelo_f:
                continue

            # Filtro local: año
            reg_date = chars.get("registrationDate", "") or ""
            anio_str = reg_date[:4]
            anio = int(anio_str) if anio_str.isdigit() else None
            if anio_min and anio and anio < anio_min:
                continue
            if anio_max and anio and anio > anio_max:
                continue

            # Filtro local: km
            v_km = chars.get("kms")
            if km_min and v_km and v_km < km_min:
                continue
            if km_max and v_km and v_km > km_max:
                continue

            market = v.get("market", "")
            regimen = "IGIC" if market == "canarias" else "IVA"

            vehiculos.append(Vehiculo(
                fuente="OcasionPlus",
                marca=v.get("brand", ""),
                modelo=v.get("model", ""),
                version=v.get("description", {}).get("short", ""),
                precio=precio_obj.get("cash"),
                precio_financiado=precio_obj.get("withFinancing"),
                cuota_mensual=v.get("finance", {}).get("quote"),
                anio=anio,
                km=v_km,
                combustible=motor.get("fuel", ""),
                transmision=motor.get("transmission", ""),
                cv=motor.get("cv"),
                provincia=f"{dealer.get('province', '')} ({regimen})",
                vendedor=dealer.get("shortname", ""),
                url=f"https://www.ocasionplus.com/coches-segunda-mano/{slug}" if slug else "",
                url_imagen=images[0].get("thumb", "") if images else "",
            ))

        if on_progreso:
            on_progreso(f"OcasionPlus: pág {p}/{total_pages} — {len(vehiculos)} filtrados de {total_raw}")

        if p >= total_pages:
            break
        time.sleep(0.12)

    return vehiculos
