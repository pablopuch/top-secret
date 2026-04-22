"""Adaptador Flexicar — API REST.

Realidad de la API (verificado):
- province: FUNCIONA (slug: "las-palmas", "santa-cruz-tenerife", "madrid", etc.)
- brand, model, fuel, yearMin, kmMax: IGNORADOS por la API
- carDealership: funciona para peninsula, NO para Canarias

Canarias:
  province=las-palmas → 257 coches (Gran Canaria - Miller Bajo, Gran Canaria - PI El Goro)
  province=santa-cruz-tenerife → 291 coches (Tenerife Norte, Tenerife Sur, Tenerife - Taco)
"""
import json
import time
import urllib.request
import urllib.error
from .modelo import Vehiculo

API_URL = "https://services.flexicar.es/api/v1/vehicles"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.flexicar.es/",
}

PROVINCIAS_CANARIAS = ["las-palmas", "santa-cruz-tenerife"]


def _fetch(page: int, province: str = None) -> dict:
    url = f"{API_URL}?page={page}"
    if province:
        url += f"&province={province}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def buscar(marca: str = "", modelo: str = "", km_max: int = None, km_min: int = None,
           anio_min: int = None, anio_max: int = None, combustible: str = "",
           transmision: str = "", solo_canarias: bool = False,
           max_paginas: int = 200, on_progreso=None) -> list[Vehiculo]:
    """
    Si solo_canarias=True, consulta las-palmas + santa-cruz-tenerife (~550 coches).
    Si no, recorre todo el inventario (~24,000+ coches, lento).
    Brand/model/km/año/combustible/transmision siempre en local.
    """
    provinces = PROVINCIAS_CANARIAS if solo_canarias else [None]
    todos_raw = []

    for prov in provinces:
        ctx = f" ({prov})" if prov else ""
        page = 1
        while page <= max_paginas:
            try:
                data = _fetch(page, prov)
            except (urllib.error.URLError, TimeoutError) as e:
                if on_progreso:
                    on_progreso(f"Flexicar{ctx}: error pág {page}: {e}")
                break

            resultados = data.get("results", [])
            if not resultados:
                break

            todos_raw.extend(resultados)

            if on_progreso and (page % 20 == 0 or not data.get("hasNext", False)):
                on_progreso(f"Flexicar{ctx}: pág {page} — {len(todos_raw)} acumulados")

            if not data.get("hasNext", False):
                break

            page += 1
            time.sleep(0.12)

    marca_f = marca.upper().strip()
    modelo_f = modelo.upper().strip()
    comb_f = combustible.lower().strip()
    trans_f = transmision.lower().strip()

    vehiculos = []
    for v in todos_raw:
        v_marca = (v.get("brand") or "").upper()
        v_modelo = (v.get("model") or "").upper()
        v_fuel = (v.get("fuel") or "").lower()
        v_trans = (v.get("transmission") or "").lower()
        v_year = v.get("year")
        v_km = v.get("km")

        if marca_f and marca_f not in v_marca and v_marca not in marca_f:
            continue
        if modelo_f and modelo_f not in v_modelo and v_modelo not in modelo_f:
            continue
        if comb_f and comb_f not in v_fuel and v_fuel not in comb_f:
            continue
        if trans_f and trans_f not in v_trans and v_trans not in trans_f:
            continue
        if anio_min and v_year and v_year < anio_min:
            continue
        if anio_max and v_year and v_year > anio_max:
            continue
        if km_min and v_km and v_km < km_min:
            continue
        if km_max and v_km and v_km > km_max:
            continue

        dealer_name = v.get("carDealership", "")
        es_canarias = any(x in dealer_name.lower() for x in
                          ["gran canaria", "tenerife", "miller", "goro", "taco",
                           "lanzarote", "fuerteventura", "palmas", "canaria"])

        vehiculos.append(Vehiculo(
            fuente="Flexicar",
            marca=v.get("brand", ""),
            modelo=v.get("model", ""),
            version=v.get("version", ""),
            precio=v.get("cashPrice") or v.get("price"),
            precio_financiado=v.get("retailPrice"),
            cuota_mensual=v.get("quotaPrice"),
            anio=v_year,
            km=v_km,
            combustible=v.get("fuel", ""),
            transmision=v.get("transmission", ""),
            provincia=f"{dealer_name} ({'IGIC' if es_canarias else 'IVA'})",
            url=f"https://www.flexicar.es/{v['slug']}/" if v.get("slug") else "",
            url_imagen=(v.get("images") or [""])[0] if isinstance(v.get("images"), list) else v.get("image", ""),
            reservado=v.get("reserved", False),
        ))

    if on_progreso:
        on_progreso(f"Flexicar: {len(vehiculos)} vehículos tras filtrar (de {len(todos_raw)} totales)")

    return vehiculos
