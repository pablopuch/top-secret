"""Adaptador Domingo Alonso — Playwright con intercepción de API.

El endpoint /hooks/getModelList/ solo responde a requests originados desde
el JavaScript del propio sitio (framework SPA). Llamadas directas dan 404.
Estrategia: click botón "siguiente" + interceptar respuesta JSON + parsear HTML.
"""
from playwright.sync_api import sync_playwright
import json
import re
from .modelo import Vehiculo

URL_BASE = "https://domingoalonsoocasion.com/ocasion/"

URLS_ISLA = {
    "tenerife": "https://domingoalonsoocasion.com/tenerife/",
    "las palmas": "https://domingoalonsoocasion.com/las-palmas/",
    "gran canaria": "https://domingoalonsoocasion.com/las-palmas/",
    "fuerteventura": "https://domingoalonsoocasion.com/fuerteventura/",
    "lanzarote": "https://domingoalonsoocasion.com/lanzarote/",
    "la palma": "https://domingoalonsoocasion.com/la-palma/",
}

BLOCK_TYPES = {"media", "font"}
BLOCK_DOMAINS = ["google-analytics", "facebook", "doubleclick", "hotjar", "segment"]

JS_EXTRAER = r"""() => {
    const tarjetas = document.querySelectorAll('ul.flex.flex-wrap > li');
    const resultados = [];
    for (const li of tarjetas) {
        const enlace = li.querySelector('h3 a[href]');
        if (!enlace) continue;
        const href = enlace.getAttribute('href') || '';
        if (!href || href === '#') continue;
        const marca = (li.querySelector('h3 a span.text-sm') || {}).textContent?.trim() || '';
        const modelo = (li.querySelector('h3 a strong.text-black') || {}).textContent?.trim() || '';
        const precioEl = li.querySelector('strong.text-blue-400');
        if (!precioEl) continue;
        const precio = parseInt(precioEl.textContent.replace(/[^\d]/g, ''), 10);
        if (!precio) continue;
        const specs = li.querySelectorAll('.flex.flex-wrap.truncate.text-xs span');
        const especsList = Array.from(specs).map(s => s.textContent.trim()).filter(Boolean);
        let anio = '', km = '', combustible = '', transmision = '';
        for (const spec of especsList) {
            if (/^20\d{2}$/.test(spec)) anio = spec;
            else if (/km/i.test(spec)) km = spec;
            else if (/gasolina|di[eé]sel|el[eé]ctrico|h[ií]brido|glp/i.test(spec)) combustible = spec;
            else if (/autom|manual/i.test(spec)) transmision = spec;
        }
        const texto = li.innerText || '';
        let isla = 'Canarias';
        if (/tenerife|santa\s*cruz/i.test(texto)) isla = 'Sta. C. Tenerife';
        else if (/gran\s*canaria|las\s*palmas/i.test(texto)) isla = 'Las Palmas';
        else if (/fuerteventura|lanzarote/i.test(texto)) isla = 'Las Palmas';
        resultados.push({marca, modelo, precio, anio, km, combustible, transmision, isla, url: href.startsWith('http') ? href : 'https://domingoalonsoocasion.com' + href});
    }
    return resultados;
}"""


def buscar(marca: str = "", modelo: str = "", km_max: int = None, km_min: int = None,
           anio_min: int = None, anio_max: int = None, combustible: str = "",
           transmision: str = "", isla: str = "",
           max_paginas: int = 50, on_progreso=None) -> list[Vehiculo]:

    url_inicio = URL_BASE
    if isla:
        isla_key = isla.lower().strip()
        url_inicio = URLS_ISLA.get(isla_key, URL_BASE)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        def filtrar_recurso(route):
            req = route.request
            if req.resource_type in BLOCK_TYPES:
                route.abort()
                return
            if any(d in req.url.lower() for d in BLOCK_DOMAINS):
                route.abort()
                return
            route.continue_()

        page.route("**/*", filtrar_recurso)

        if on_progreso:
            on_progreso("Domingo Alonso: cargando...")

        page.goto(url_inicio, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        # Extraer primera página directamente del DOM
        all_raw = page.evaluate(JS_EXTRAER)
        pagina = 1
        if on_progreso:
            on_progreso(f"Domingo Alonso: pág {pagina} — {len(all_raw)} vehículos")

        total_previo = len(all_raw)
        reintentos = 0

        while pagina < max_paginas:
            boton_visible = page.evaluate("""() => {
                const btn = document.querySelector('button[onclick*="nextPage"]');
                return btn && btn.offsetParent !== null;
            }""")
            if not boton_visible:
                break

            page.evaluate("""() => {
                const btn = document.querySelector('button[onclick*="nextPage"]');
                btn.scrollIntoView({behavior: 'instant', block: 'center'});
            }""")
            page.wait_for_timeout(200)
            page.evaluate("document.querySelector('button[onclick*=\"nextPage\"]').click()")

            try:
                page.wait_for_response(
                    lambda r: "getModelList" in r.url, timeout=10000
                )
            except Exception:
                page.wait_for_timeout(2000)
            page.wait_for_timeout(800)

            coches = page.evaluate(JS_EXTRAER)
            total_actual = len(coches)

            if total_actual > total_previo:
                pagina += 1
                reintentos = 0
                all_raw = coches
                if on_progreso:
                    on_progreso(f"Domingo Alonso: pág {pagina} — {total_actual} vehículos")
                total_previo = total_actual
            elif reintentos < 2:
                reintentos += 1
                continue
            else:
                break

        browser.close()

    # Filtrado local
    marca_f = marca.upper().strip()
    modelo_f = modelo.upper().strip()
    comb_f = combustible.lower().strip()
    trans_f = transmision.lower().strip()

    vehiculos = []
    for c in all_raw:
        m_upper = c["marca"].upper()
        mod_upper = c["modelo"].upper()

        if marca_f and marca_f not in m_upper and m_upper not in marca_f:
            continue
        if modelo_f and modelo_f not in mod_upper and mod_upper not in modelo_f:
            continue

        c_fuel = c.get("combustible", "").lower()
        if comb_f and comb_f not in c_fuel and c_fuel not in comb_f:
            continue

        c_trans = c.get("transmision", "").lower()
        if trans_f and trans_f not in c_trans and c_trans not in trans_f:
            continue

        anio_val = int(c["anio"]) if c["anio"] and c["anio"].isdigit() else None
        if anio_min and anio_val and anio_val < anio_min:
            continue
        if anio_max and anio_val and anio_val > anio_max:
            continue

        km_val = None
        if c.get("km"):
            digits = re.sub(r"[^\d]", "", c["km"])
            km_val = int(digits) if digits else None
        if km_max and km_val and km_val > km_max:
            continue
        if km_min and km_val and km_val < km_min:
            continue

        isla = c.get("isla", "Canarias")

        vehiculos.append(Vehiculo(
            fuente="Domingo Alonso",
            marca=c["marca"],
            modelo=c["modelo"],
            precio=c["precio"],
            anio=anio_val,
            km=km_val,
            combustible=c.get("combustible", ""),
            transmision=c.get("transmision", ""),
            provincia=f"{isla} (IGIC)",
            url=c["url"],
        ))

    if on_progreso:
        on_progreso(f"Domingo Alonso: {len(vehiculos)} filtrados de {len(all_raw)}")

    return vehiculos
