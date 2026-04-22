"""Buscador unificado multi-fuente."""
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from .modelo import Vehiculo


FUENTES_DISPONIBLES = ["coches.net", "flexicar", "ocasionplus", "domingo_alonso"]


def buscar_multi(marca: str, modelo: str, fuentes: list[str] = None,
                 km_max: int = None, km_min: int = None,
                 anio_min: int = None, anio_max: int = None,
                 combustible: str = "", transmision: str = "",
                 provincias: str = None, solo_canarias: bool = False,
                 max_paginas: int = 20, on_progreso=None) -> dict:
    """Lanza búsquedas en paralelo en las fuentes seleccionadas."""
    if fuentes is None:
        fuentes = FUENTES_DISPONIBLES

    resultados_por_fuente = {}
    errores = {}

    def _buscar_fuente(nombre_fuente):
        try:
            if nombre_fuente == "coches.net":
                from . import adapter_coches_net
                vehiculos, stats = adapter_coches_net.buscar(
                    marca=marca, modelo=modelo,
                    km_max=km_max, km_min=km_min,
                    anio_min=anio_min, anio_max=anio_max,
                    combustible=combustible, transmision=transmision,
                    provincias=provincias, max_paginas=max_paginas,
                    on_progreso=on_progreso,
                )
                return nombre_fuente, vehiculos, stats

            elif nombre_fuente == "flexicar":
                from . import adapter_flexicar
                vehiculos = adapter_flexicar.buscar(
                    marca=marca, modelo=modelo,
                    km_max=km_max, km_min=km_min,
                    anio_min=anio_min, anio_max=anio_max,
                    combustible=combustible, transmision=transmision,
                    solo_canarias=solo_canarias,
                    on_progreso=on_progreso,
                )
                return nombre_fuente, vehiculos, {}

            elif nombre_fuente == "ocasionplus":
                from . import adapter_ocasionplus
                vehiculos = adapter_ocasionplus.buscar(
                    marca=marca, modelo=modelo,
                    km_max=km_max, km_min=km_min,
                    anio_min=anio_min, anio_max=anio_max,
                    combustible=combustible, transmision=transmision,
                    solo_canarias=solo_canarias,
                    on_progreso=on_progreso,
                )
                return nombre_fuente, vehiculos, {}

            elif nombre_fuente == "domingo_alonso":
                from . import adapter_domingo_alonso
                vehiculos = adapter_domingo_alonso.buscar(
                    marca=marca, modelo=modelo,
                    km_max=km_max, km_min=km_min,
                    anio_min=anio_min, anio_max=anio_max,
                    combustible=combustible, transmision=transmision,
                    on_progreso=on_progreso,
                )
                return nombre_fuente, vehiculos, {}

        except Exception as e:
            return nombre_fuente, [], {"error": str(e)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        for f in fuentes:
            futures[pool.submit(_buscar_fuente, f)] = f

        for future in as_completed(futures):
            nombre, vehiculos, stats = future.result()
            if isinstance(stats, dict) and "error" in stats:
                errores[nombre] = stats["error"]
                resultados_por_fuente[nombre] = {"vehiculos": [], "stats": {}}
            else:
                resultados_por_fuente[nombre] = {"vehiculos": vehiculos, "stats": stats}

    todos = []
    for f_data in resultados_por_fuente.values():
        todos.extend(f_data["vehiculos"])

    return {
        "total": len(todos),
        "por_fuente": {
            nombre: {
                "total": len(data["vehiculos"]),
                "vehiculos": [v.to_dict() for v in data["vehiculos"]],
                "stats": data["stats"],
            }
            for nombre, data in resultados_por_fuente.items()
        },
        "todos": [v.to_dict() for v in todos],
        "estudio_mercado": _generar_estudio(todos),
        "errores": errores,
    }


def _generar_estudio(vehiculos: list[Vehiculo]) -> dict:
    if not vehiculos:
        return {}

    precios_validos = [v for v in vehiculos if v.precio and v.precio > 0]
    if not precios_validos:
        return {}

    precios = [v.precio for v in precios_validos]

    por_anio = {}
    for v in precios_validos:
        a = v.anio or 0
        if a not in por_anio:
            por_anio[a] = {"precios": [], "fuentes": set()}
        por_anio[a]["precios"].append(v.precio)
        por_anio[a]["fuentes"].add(v.fuente)

    desglose_anio = {}
    for anio, data in sorted(por_anio.items()):
        if anio == 0:
            continue
        p = data["precios"]
        desglose_anio[str(anio)] = {
            "cantidad": len(p),
            "precio_medio": round(statistics.mean(p)),
            "precio_mediana": round(statistics.median(p)),
            "precio_min": min(p),
            "precio_max": max(p),
            "fuentes": list(data["fuentes"]),
        }

    por_fuente = {}
    for v in precios_validos:
        if v.fuente not in por_fuente:
            por_fuente[v.fuente] = []
        por_fuente[v.fuente].append(v.precio)

    resumen_fuentes = {}
    for fuente, p in por_fuente.items():
        resumen_fuentes[fuente] = {
            "cantidad": len(p),
            "precio_medio": round(statistics.mean(p)),
            "precio_mediana": round(statistics.median(p)),
        }

    return {
        "total_vehiculos": len(precios_validos),
        "precio_medio_global": round(statistics.mean(precios)),
        "precio_mediana_global": round(statistics.median(precios)),
        "precio_min_global": min(precios),
        "precio_max_global": max(precios),
        "desglose_por_anio": desglose_anio,
        "resumen_por_fuente": resumen_fuentes,
    }
