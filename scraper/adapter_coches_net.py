"""Adaptador coches.net — reutiliza el scraper mejorado con stealth."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from valorar_coche import scrape_valoracion, buscar_ids_en_diccionario, resolver_provincias
from .modelo import Vehiculo


def buscar(marca: str = "", modelo: str = "", km_max: int = None, km_min: int = None,
           anio_min: int = None, anio_max: int = None, combustible: str = "",
           transmision: str = "", provincias: str = None,
           max_paginas: int = 20, on_progreso=None) -> tuple[list[Vehiculo], dict]:
    """Busca en coches.net y devuelve (vehiculos, estadisticas)."""
    make_id, model_id = buscar_ids_en_diccionario(marca, modelo)
    if not make_id or not model_id:
        return [], {}

    datos = scrape_valoracion(
        marca=marca, modelo=modelo,
        anio_min=anio_min, anio_max=anio_max,
        km_min=km_min, km_max=km_max,
        max_paginas=max_paginas,
        make_id=make_id, model_id=model_id,
        provincias=provincias,
        combustible=combustible or None,
        transmision=transmision or None,
        on_progreso=on_progreso,
    )

    if not datos:
        return [], {}

    vehiculos = []
    for c in datos.get("detalle_coches", []):
        anio_val = int(c["anio"]) if c.get("anio") and str(c["anio"]).isdigit() else None
        vehiculos.append(Vehiculo(
            fuente="coches.net",
            marca=marca,
            modelo=modelo,
            precio=c.get("precio"),
            precio_financiado=c.get("precio_financiado"),
            cuota_mensual=c.get("cuota_mensual"),
            anio=anio_val,
            km=c.get("km"),
            combustible=c.get("combustible", ""),
            cv=c.get("cv"),
            provincia=c.get("provincia", ""),
            vendedor=c.get("vendedor", ""),
            url=c.get("url", ""),
        ))

    stats = datos.get("estadisticas_precio", {})
    stats["total_segun_web"] = datos.get("total_segun_web")
    stats["desglose_por_anio"] = datos.get("desglose_por_anio", {})
    stats["metricas_tiempo"] = datos.get("metricas_tiempo", {})

    return vehiculos, stats
