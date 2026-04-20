from playwright.sync_api import sync_playwright
import json
import time
import re
from urllib.parse import urlparse, parse_qs

ARCHIVO_SALIDA = "mapa_filtros_coches_net.json"

api_responses = []
url_changes = []


def interceptar_respuesta(response):
    """Captura respuestas de API que contengan datos de filtros (marcas, modelos, etc.)."""
    url = response.url
    content_type = response.headers.get("content-type", "")

    if not ("json" in content_type or "api" in url.lower()):
        return
    if response.status != 200:
        return

    ruido = [".js", ".css", ".png", ".jpg", ".svg", ".woff", "google", "segment",
             "datadome", "facebook", "doubleclick", "analytics", "adsystem"]
    if any(r in url.lower() for r in ruido):
        return

    try:
        body = response.json()
    except Exception:
        return

    tiene_datos_filtro = False
    body_str = json.dumps(body)[:5000].lower()
    palabras_clave = ["make", "model", "brand", "marca", "modelo", "year", "fuel",
                      "province", "km", "price", "bodytype", "gearbox", "transmission"]
    for kw in palabras_clave:
        if kw in body_str:
            tiene_datos_filtro = True
            break

    if not tiene_datos_filtro:
        return

    entrada = {
        "url": url,
        "metodo": response.request.method,
        "body_preview": body if isinstance(body, (list, dict)) else str(body)[:2000],
    }
    api_responses.append(entrada)
    print(f"  [API] {response.request.method} {url[:120]}")


def extraer_params_url(url):
    """Parsea los parámetros de una URL de búsqueda de coches.net."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return {k: v[0] if len(v) == 1 else v for k, v in params.items()}


JS_EXTRAER_FILTROS_DOM = r"""() => {
    const resultado = {selects: [], inputs: [], dropdowns: [], dataAttributes: [], urlActual: window.location.href};

    // 1. Select nativos
    document.querySelectorAll('select').forEach(sel => {
        const opciones = Array.from(sel.options).slice(0, 200).map(o => ({
            value: o.value, text: o.textContent.trim(), selected: o.selected
        }));
        if (opciones.length > 1) {
            resultado.selects.push({
                name: sel.name || null, id: sel.id || null,
                classes: sel.className || null, opciones
            });
        }
    });

    // 2. Inputs de filtro
    document.querySelectorAll('input[type="text"], input[type="number"], input[type="search"], input[name*="km" i], input[name*="year" i], input[name*="price" i]').forEach(inp => {
        resultado.inputs.push({
            name: inp.name || null, id: inp.id || null,
            type: inp.type, value: inp.value,
            placeholder: inp.placeholder || null,
            classes: inp.className || null
        });
    });

    // 3. Dropdowns custom (elementos clickeables con listas de opciones)
    document.querySelectorAll('[role="listbox"], [class*="Dropdown" i], [class*="dropdown" i], [class*="FilterSelect" i], [class*="filterSelect" i]').forEach(dd => {
        const items = Array.from(dd.querySelectorAll('[role="option"], li, [class*="option" i], [class*="Option" i]')).slice(0, 200);
        if (items.length > 0) {
            resultado.dropdowns.push({
                classes: dd.className || null,
                role: dd.getAttribute('role'),
                items: items.map(el => ({
                    text: el.textContent.trim().substring(0, 60),
                    value: el.dataset.value || el.dataset.id || el.getAttribute('value') || null,
                    dataAttrs: {...el.dataset},
                    selected: el.classList.contains('selected') || el.getAttribute('aria-selected') === 'true'
                }))
            });
        }
    });

    // 4. Elementos con data attributes relevantes
    const patrones = ['make', 'model', 'brand', 'year', 'km', 'fuel', 'price', 'body', 'gear', 'province'];
    document.querySelectorAll('[data-value], [data-id], [data-filter]').forEach(el => {
        const attrs = {...el.dataset};
        const attrStr = JSON.stringify(attrs).toLowerCase();
        for (const p of patrones) {
            if (attrStr.includes(p) || el.className.toLowerCase().includes(p)) {
                resultado.dataAttributes.push({
                    tag: el.tagName, text: el.textContent.trim().substring(0, 60),
                    classes: el.className, dataAttrs: attrs
                });
                break;
            }
        }
    });

    return resultado;
}"""


JS_EXTRAER_NEXT_DATA = r"""() => {
    const datos = {};
    // Next.js / frameworks que inyectan datos en el HTML
    if (window.__NEXT_DATA__) datos.__NEXT_DATA__ = window.__NEXT_DATA__;
    if (window.__INITIAL_STATE__) datos.__INITIAL_STATE__ = window.__INITIAL_STATE__;
    if (window.__PRELOADED_STATE__) datos.__PRELOADED_STATE__ = window.__PRELOADED_STATE__;

    // Buscar scripts JSON embebidos en el HTML
    document.querySelectorAll('script[type="application/json"], script[type="application/ld+json"]').forEach((s, i) => {
        try {
            const parsed = JSON.parse(s.textContent);
            datos[`script_json_${i}`] = parsed;
        } catch(e) {}
    });

    // Buscar variables globales que contengan datos de filtros
    const globales = {};
    const skip = new Set(['chrome', 'performance', 'navigator', 'location', 'document', 'window', 'self', 'top', 'parent', 'frames']);
    for (const key of Object.getOwnPropertyNames(window)) {
        if (skip.has(key) || key.startsWith('_') && !key.startsWith('__')) continue;
        try {
            const val = window[key];
            if (val && typeof val === 'object' && !Array.isArray(val) && !(val instanceof HTMLElement)) {
                const str = JSON.stringify(val).substring(0, 3000).toLowerCase();
                if (str.includes('makeid') || str.includes('modelid') || str.includes('marca') ||
                    str.includes('"makes"') || str.includes('"models"') || str.includes('"filters"')) {
                    globales[key] = val;
                }
            }
        } catch(e) {}
    }
    if (Object.keys(globales).length) datos.globales_con_filtros = globales;

    return datos;
}"""


def explorar_pagina(page, nombre_paso):
    """Hace una foto del estado actual del DOM y la URL."""
    print(f"\n--- Escaneando: {nombre_paso} ---")

    params_url = extraer_params_url(page.url)
    if params_url:
        print(f"  Parámetros URL: {json.dumps(params_url, indent=2)}")

    filtros_dom = page.evaluate(JS_EXTRAER_FILTROS_DOM)
    datos_framework = page.evaluate(JS_EXTRAER_NEXT_DATA)

    return {
        "paso": nombre_paso,
        "url": page.url,
        "params_url": params_url,
        "filtros_dom": filtros_dom,
        "datos_framework": datos_framework,
    }


def ejecutar():
    mapa = {
        "meta": {"fecha": time.strftime("%Y-%m-%d %H:%M"), "descripcion": "Mapa de filtros internos de coches.net"},
        "exploraciones": [],
        "api_interceptadas": [],
        "parametros_url_detectados": {},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.on("response", interceptar_respuesta)

        # --- Fase 1: Carga inicial ---
        print("Accediendo a coches.net/search/ ...")
        page.goto("https://www.coches.net/search/", wait_until="domcontentloaded")
        print("Esperando 15s (resuelve el CAPTCHA si aparece)...")
        time.sleep(15)

        mapa["exploraciones"].append(explorar_pagina(page, "carga_inicial"))

        # --- Fase 2: Dejar al usuario interactuar y monitorizar cambios ---
        print("\n" + "=" * 60)
        print("  MODO EXPLORACIÓN DE FILTROS")
        print("=" * 60)
        print("  1. Resuelve el CAPTCHA si salió.")
        print("  2. Juega con los filtros: selecciona marca, modelo, año, km...")
        print("  3. Cada vez que la URL cambie capturo automáticamente el estado.")
        print("  4. Cuando termines, CIERRA EL NAVEGADOR con la X.")
        print("=" * 60 + "\n")

        ultima_url = page.url
        num_capturas = 0

        try:
            while True:
                try:
                    page.wait_for_timeout(2000)
                except Exception:
                    break

                try:
                    url_actual = page.url
                except Exception:
                    break

                if url_actual != ultima_url:
                    num_capturas += 1
                    params = extraer_params_url(url_actual)
                    print(f"\n  [Cambio #{num_capturas}] URL actualizada:")
                    print(f"    {url_actual[:150]}")
                    if params:
                        for k, v in params.items():
                            print(f"    {k} = {v}")
                            mapa["parametros_url_detectados"][k] = v

                    mapa["exploraciones"].append(explorar_pagina(page, f"cambio_filtro_{num_capturas}"))
                    ultima_url = url_actual

        except KeyboardInterrupt:
            print("\nDetenido por el usuario.")
        except Exception:
            pass

        # --- Fase 3: Captura final ---
        try:
            mapa["exploraciones"].append(explorar_pagina(page, "estado_final"))
        except Exception:
            pass

        try:
            browser.close()
        except Exception:
            pass

    mapa["api_interceptadas"] = api_responses

    # --- Resumen ---
    print(f"\n{'=' * 60}")
    print(f"  RESUMEN DE EXPLORACIÓN")
    print(f"{'=' * 60}")
    print(f"  Cambios de URL capturados:  {num_capturas}")
    print(f"  Respuestas API capturadas:  {len(api_responses)}")
    print(f"  Parámetros URL detectados:")
    for k, v in mapa["parametros_url_detectados"].items():
        print(f"    {k} = {v}")

    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        json.dump(mapa, f, indent=4, ensure_ascii=False, default=str)
    print(f"\n  Mapa completo guardado en: {ARCHIVO_SALIDA}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    ejecutar()
