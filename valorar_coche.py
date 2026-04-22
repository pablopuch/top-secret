from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import json
import time
import random
import statistics
import argparse
import os
from urllib.parse import urlencode

JS_TOTAL_RESULTADOS = r"""() => {
    const h1 = document.querySelector('h1');
    if (!h1) return null;
    const texto = h1.textContent.trim();
    const match = texto.match(/^(\d[\d.]*)\s/);
    if (match) return {total: parseInt(match[1].replace(/\./g, ''), 10), texto: texto};
    return {total: null, texto: texto};
}"""

JS_EXTRAER = r"""() => {
    const tarjetas = document.querySelectorAll('.mt-CardBasic, .mt-CardAd, [class*="CardAd"], article[class*="card"]');
    const resultados = [];

    for (const card of tarjetas) {
        let enlaceEl = card.querySelector('h2 a');
        if (!enlaceEl) enlaceEl = card.querySelector('a[href*=".aspx"]');
        if (!enlaceEl) continue;
        
        const href = enlaceEl.getAttribute('href') || '';
        const titulo = enlaceEl.textContent?.trim() || '';
        const inner = card.innerText || '';
        const lineas = inner.split('\n').map(l => l.trim()).filter(Boolean);

        let precio = null;
        let precio_financiado = null;
        let cuota = null;
        let anio = '';
        let km = null;
        let combustible = '';
        let cv = null;
        let provincia = '';
        let vendedor = '';

        for (let i = 0; i < lineas.length; i++) {
            const linea = lineas[i];
            const ctx2 = ((lineas[i-1] || '') + ' ' + (lineas[i-2] || '') + ' ' + linea).toLowerCase();
            
            if (linea.includes('€') && !linea.includes('/mes')) {
                const val = parseInt(linea.replace(/[^\d]/g, ''), 10);
                if (val <= 500) continue;
                const esFinanciacion = ctx2.includes('financiado') || ctx2.includes('entrada') 
                    || ctx2.includes('desde') || ctx2.includes('sin entrada');
                if (esFinanciacion) {
                    precio_financiado = precio_financiado || val;
                } else if (!precio) {
                    precio = val;
                } else if (!precio_financiado) {
                    precio_financiado = val;
                }
            }
            if (linea.includes('€/mes') || (linea.includes('€') && lineas[i+1] && lineas[i+1].includes('/mes'))) {
                cuota = parseInt(linea.replace(/[^\d]/g, ''), 10);
            }
            
            if (/^20\d{2}$/.test(linea) || /^19\d{2}$/.test(linea)) anio = linea;
            if (/km$/i.test(linea)) km = parseInt(linea.replace(/[^\d]/g, ''), 10);
            if (/cv$/i.test(linea)) cv = parseInt(linea.replace(/[^\d]/g, ''), 10);
            if (/Gasolina|Diésel|Eléctrico|Híbrido|GLP|GNC/i.test(linea)) combustible = linea;
            
            if (linea.includes('Profesional') || linea.includes('Particular')) {
                vendedor = linea;
                if (i > 0 && !lineas[i-1].includes('Envío') && !lineas[i-1].includes('Garantía')) {
                    provincia = lineas[i-1];
                } else if (i > 1 && !lineas[i-2].includes('Envío') && !lineas[i-2].includes('Garantía')) {
                    provincia = lineas[i-2];
                }
            }
        }

        resultados.push({
            titulo: titulo,
            precio: precio,
            precio_financiado: precio_financiado,
            cuota_mensual: cuota,
            anio: anio,
            km: km,
            combustible: combustible,
            cv: cv,
            provincia: provincia,
            vendedor: vendedor,
            url: href.startsWith('http') ? href : 'https://www.coches.net' + href
        });
    }
    return resultados;
}"""


def fmt_tiempo(segundos):
    mins = int(segundos // 60)
    secs = round(segundos % 60, 1)
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"


UBICACIONES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ubicaciones_coches_net.json")

PROVINCIAS_FALLBACK = {
    "alava": 1, "albacete": 2, "alicante": 3, "almeria": 4, "asturias": 33,
    "avila": 5, "badajoz": 6, "barcelona": 8, "burgos": 9, "caceres": 10,
    "cadiz": 11, "cantabria": 39, "castellon": 12, "ciudad real": 13,
    "cordoba": 14, "coruña": 15, "a coruña": 15, "cuenca": 16,
    "girona": 17, "granada": 18, "guadalajara": 19, "guipuzcoa": 20,
    "huelva": 21, "huesca": 22, "jaen": 23, "leon": 24, "lleida": 25,
    "lugo": 27, "madrid": 28, "malaga": 29, "murcia": 30, "navarra": 31,
    "ourense": 32, "palencia": 34, "las palmas": 35, "pontevedra": 36,
    "la rioja": 26, "salamanca": 37, "santa cruz de tenerife": 38,
    "tenerife": 38, "segovia": 40, "sevilla": 41, "soria": 42,
    "tarragona": 43, "teruel": 44, "toledo": 45, "valencia": 46,
    "valladolid": 47, "vizcaya": 48, "zamora": 49, "zaragoza": 50,
    "ceuta": 51, "melilla": 52, "baleares": 7, "gran canaria": 35,
    "canarias": "35|38",
}


def cargar_provincias():
    """Carga ubicaciones desde JSON (formato comunidades>provincias), con fallback."""
    if os.path.exists(UBICACIONES_JSON):
        with open(UBICACIONES_JSON, "r", encoding="utf-8") as f:
            datos = json.load(f)
        provincias = {}
        for comunidad, info in datos.get("comunidades", {}).items():
            ids_comunidad = []
            for nombre_prov, pid in info.get("provincias", {}).items():
                provincias[nombre_prov.lower().strip()] = pid
                ids_comunidad.append(str(pid))
            provincias[comunidad.lower().strip()] = "|".join(ids_comunidad)
        return provincias
    return PROVINCIAS_FALLBACK


PROVINCIAS = cargar_provincias()

FUEL_MAP = {
    "diesel": 1, "diésel": 1,
    "gasolina": 2,
    "eléctrico": 3, "electrico": 3,
    "híbrido": 4, "hibrido": 4,
    "híbrido enchufable": 5, "hibrido enchufable": 5, "enchufable": 5, "phev": 5,
    "glp": 6, "gas licuado": 6,
    "gnc": 7, "gas natural": 7, "cng": 7,
}

TRANS_MAP = {
    "automático": 1, "automatico": 1, "auto": 1,
    "manual": 2,
}


def construir_url(make_id, model_id, anio_min=None, anio_max=None, km_min=None, km_max=None,
                  provincias=None, combustible=None, transmision=None, pagina=1):
    params = {
        "MakeIds[0]": make_id,
        "ModelIds[0]": model_id,
    }
    if anio_min:
        params["MinYear"] = anio_min
    if anio_max:
        params["MaxYear"] = anio_max
    if km_min:
        params["MinKms"] = km_min
    if km_max:
        params["MaxKms"] = km_max
    if provincias:
        params["arrProvince"] = provincias
    if combustible:
        fuel_id = FUEL_MAP.get(combustible.lower().strip())
        if fuel_id:
            params["Fueltype2List"] = fuel_id
    if transmision:
        trans_id = TRANS_MAP.get(transmision.lower().strip())
        if trans_id:
            params["TransmissionTypeId"] = trans_id
    if pagina > 1:
        params["pg"] = pagina
    return f"https://www.coches.net/search/?{urlencode(params)}"


def resolver_provincias(texto_provincias):
    """Convierte nombres de provincias a IDs separados por |."""
    if not texto_provincias:
        return None
    ids = []
    for nombre in texto_provincias.split(","):
        nombre = nombre.strip().lower()
        if nombre.isdigit():
            ids.append(nombre)
        elif nombre in PROVINCIAS:
            val = PROVINCIAS[nombre]
            if isinstance(val, str):
                ids.extend(val.split("|"))
            else:
                ids.append(str(val))
        else:
            print(f"  AVISO: Provincia '{nombre}' no reconocida, ignorada.")
    return "|".join(ids) if ids else None


DICCIONARIO_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "diccionario_coches_net.json")

def buscar_ids_en_diccionario(marca_texto, modelo_texto):
    """Busca MakeId y ModelId en el diccionario local."""
    if not os.path.exists(DICCIONARIO_JSON):
        return None, None
    
    with open(DICCIONARIO_JSON, "r", encoding="utf-8") as f:
        catalogo = json.load(f)
    
    marca_texto = marca_texto.lower().strip()
    modelo_texto = modelo_texto.lower().strip()
    
    make_id = None
    modelos = {}
    for nombre_marca, datos in catalogo.items():
        if marca_texto in nombre_marca.lower() or nombre_marca.lower() in marca_texto:
            make_id = datos["make_id"]
            modelos = datos.get("modelos", {})
            break
    
    if not make_id:
        return None, None
    
    model_id = None
    for nombre_modelo, mid in modelos.items():
        if modelo_texto in nombre_modelo.lower() or nombre_modelo.lower() in modelo_texto:
            model_id = mid
            break
    
    return make_id, model_id


def _es_captcha(page):
    titulo = page.title()
    url = page.url
    return ("Ups" in titulo or "Parece que algo" in titulo
            or "captcha" in titulo.lower() or "challenge" in url.lower()
            or "blocked" in titulo.lower())


def esperar_captcha(page, max_intentos=120, on_progreso=None):
    """Detecta CAPTCHA/bloqueo y espera a que se resuelva manualmente."""
    if not _es_captcha(page):
        return True
    msg = "CAPTCHA detectado. Resuélvelo en el navegador..."
    print(f"  ⚠ {msg}")
    if on_progreso:
        on_progreso(msg)
    for i in range(max_intentos):
        time.sleep(5)
        if not _es_captcha(page):
            print(f"  ✓ CAPTCHA resuelto tras {(i+1)*5}s")
            if on_progreso:
                on_progreso("CAPTCHA resuelto. Continuando...")
            time.sleep(2)
            return True
        if on_progreso and i % 6 == 5:
            on_progreso(f"Esperando CAPTCHA... ({(i+1)*5}s)")
    print("  ✗ Timeout esperando CAPTCHA (10 min)")
    return False


def normalizar(texto):
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', texto.lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

def filtrar_por_titulo(resultados, marca, modelo):
    """Descarta anuncios promocionados que no corresponden a la marca buscada."""
    marca_n = normalizar(marca)
    filtrados = []
    descartados = 0
    for r in resultados:
        titulo_n = normalizar(r["titulo"])
        if marca_n in titulo_n:
            filtrados.append(r)
        else:
            descartados += 1
    if descartados:
        print(f"  (Descartados {descartados} anuncios promocionados de otras marcas)")
    return filtrados


def filtrar_resultados(resultados, anio_min=None, anio_max=None, km_min=None, km_max=None):
    filtrados = []
    for r in resultados:
        if r["precio"] is None:
            continue
        if anio_min or anio_max:
            try:
                anio_coche = int(r["anio"]) if r["anio"] else 0
            except ValueError:
                continue
            if anio_min and anio_coche < anio_min:
                continue
            if anio_max and anio_coche > anio_max:
                continue
        if km_min and r["km"] is not None and r["km"] < km_min:
            continue
        if km_max and r["km"] is not None and r["km"] > km_max:
            continue
        filtrados.append(r)
    return filtrados


def calcular_estadisticas(resultados):
    precios = [r["precio"] for r in resultados if r["precio"]]
    if not precios:
        return None

    precios_ordenados = sorted(precios)
    q1_idx = len(precios_ordenados) // 4
    q3_idx = 3 * len(precios_ordenados) // 4
    iqr = precios_ordenados[q3_idx] - precios_ordenados[q1_idx] if len(precios_ordenados) > 4 else float('inf')
    limite_bajo = precios_ordenados[q1_idx] - 1.5 * iqr
    limite_alto = precios_ordenados[q3_idx] + 1.5 * iqr
    precios_limpios = [p for p in precios if limite_bajo <= p <= limite_alto]

    if not precios_limpios:
        precios_limpios = precios

    return {
        "total_anuncios": len(resultados),
        "anuncios_con_precio": len(precios),
        "precio_medio": round(statistics.mean(precios_limpios)),
        "precio_mediana": round(statistics.median(precios_limpios)),
        "precio_min": min(precios_limpios),
        "precio_max": max(precios_limpios),
        "desviacion_tipica": round(statistics.stdev(precios_limpios)) if len(precios_limpios) > 1 else 0,
        "precios_usados_calculo": len(precios_limpios),
        "outliers_eliminados": len(precios) - len(precios_limpios),
    }


def scrape_valoracion(marca, modelo, anio_min=None, anio_max=None, km_min=None, km_max=None,
                      max_paginas=20, make_id=None, model_id=None, provincias=None,
                      combustible=None, transmision=None, on_progreso=None):
    todos_resultados = []
    tiempos_peticion = []

    # Buscar IDs en el diccionario local si no se proporcionaron
    if not make_id or not model_id:
        print(f"Buscando IDs en {DICCIONARIO_JSON}...")
        auto_make, auto_model = buscar_ids_en_diccionario(marca, modelo)
        if auto_make:
            make_id = make_id or auto_make
        if auto_model:
            model_id = model_id or auto_model
        if make_id and model_id:
            print(f"  MakeId={make_id}, ModelId={model_id}")
        else:
            print(f"  No encontrado. Usa --make-id y --model-id manualmente.")
            return None

    SELECTOR_TARJETAS = '.mt-CardBasic, .mt-CardAd, article[class*="card"]'
    MEDIA_PESADO = {"media", "font"}
    DOMINIOS_TRACKING = ["google-analytics", "doubleclick", "facebook.net", "hotjar", "taboola", "outbrain"]

    def delay_humano(media=1.8, desviacion=0.5, minimo=0.8):
        """Delay con distribucion gaussiana (mas realista que uniform)."""
        d = max(minimo, random.gauss(media, desviacion))
        time.sleep(d)

    def scroll_humano(page):
        """Scroll progresivo con variacion, simula lectura humana."""
        viewport_h = page.evaluate("window.innerHeight")
        doc_h = page.evaluate("document.body.scrollHeight")
        pos = 0
        while pos < doc_h - viewport_h:
            salto = random.randint(int(viewport_h * 0.4), int(viewport_h * 0.8))
            pos = min(pos + salto, doc_h)
            page.evaluate(f"window.scrollTo(0, {pos})")
            time.sleep(random.uniform(0.1, 0.3))
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(0.15, 0.3))

    def actividad_raton(page):
        """Mueve el raton a posiciones aleatorias para simular presencia."""
        for _ in range(random.randint(1, 3)):
            x = random.randint(200, 1000)
            y = random.randint(150, 600)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.05, 0.15))

    def filtrar_recurso(route):
        req = route.request
        if req.resource_type in MEDIA_PESADO:
            route.abort()
            return
        url_lower = req.url.lower()
        if any(d in url_lower for d in DOMINIOS_TRACKING):
            route.abort()
            return
        route.continue_()

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale="es-ES",
            extra_http_headers={
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }
        )
        page = context.new_page()

        page.route("**/*", filtrar_recurso)

        t_inicio_global = time.time()

        url_inicio = construir_url(make_id, model_id, anio_min, anio_max, km_min, km_max, provincias, combustible, transmision)

        print(f"\n{'='*60}")
        print(f"  VALORACION DE MERCADO - coches.net")
        print(f"  Marca: {marca.upper()} (ID:{make_id})  |  Modelo: {modelo.upper()} (ID:{model_id})")
        if anio_min and anio_max:
            print(f"  Año: {anio_min} - {anio_max}")
        elif anio_min:
            print(f"  Año: Desde {anio_min}")
        elif anio_max:
            print(f"  Año: Hasta {anio_max}")
        if km_min or km_max:
            km_str = ""
            if km_min and km_max:
                km_str = f"{km_min:,} - {km_max:,} km"
            elif km_min:
                km_str = f"Desde {km_min:,} km"
            else:
                km_str = f"Hasta {km_max:,} km"
            print(f"  Km: {km_str}")
        if provincias:
            print(f"  Provincias: {provincias}")
        print(f"  URL: {url_inicio}")
        print(f"{'='*60}\n")

        def cargar_y_esperar(url):
            """Carga URL y espera a tarjetas o CAPTCHA. Retorna True si OK."""
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_selector(f'{SELECTOR_TARJETAS}, h1', timeout=8000)
            except Exception:
                pass
            if not esperar_captcha(page, on_progreso=on_progreso):
                return False
            try:
                page.wait_for_selector(SELECTOR_TARJETAS, timeout=6000)
            except Exception:
                time.sleep(2)
                try:
                    page.wait_for_selector(SELECTOR_TARJETAS, timeout=4000)
                except Exception:
                    return False
            return True

        t_req = time.time()
        if not cargar_y_esperar(url_inicio):
            print("  No se encontraron resultados en la primera página.")

        total_web = None
        try:
            info = page.evaluate(JS_TOTAL_RESULTADOS)
            if info and info.get("total"):
                total_web = info["total"]
                print(f"  coches.net dice: {info['texto']}")
                print(f"  Total según web: {total_web} coches\n")
        except:
            pass

        tiempos_peticion.append(time.time() - t_req)

        try:
            for pagina in range(1, max_paginas + 1):
                t_req = time.time()

                if pagina > 1:
                    url_pagina = construir_url(make_id, model_id, anio_min, anio_max, km_min, km_max, provincias, combustible, transmision, pagina)
                    if not cargar_y_esperar(url_pagina):
                        print(f"  Sin resultados en página {pagina}. Fin del scraping.")
                        break

                actividad_raton(page)
                scroll_humano(page)

                coches = page.evaluate(JS_EXTRAER)
                t_pagina = time.time() - t_req
                tiempos_peticion.append(t_pagina)

                if not coches:
                    print(f"  Página {pagina}: 0 resultados. Fin.")
                    break

                todos_resultados.extend(coches)
                t_acum = time.time() - t_inicio_global
                msg = f"Pág {pagina}: {len(coches)} coches | Acumulado: {len(todos_resultados)} | {fmt_tiempo(t_acum)}"
                print(f"  {msg}")
                if on_progreso:
                    on_progreso(msg)

                delay_humano(media=1.8, desviacion=0.6, minimo=0.9)

        except KeyboardInterrupt:
            print("\nDetenido por el usuario.")
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            t_total = time.time() - t_inicio_global
            browser.close()

    # Deduplicar por URL
    vistos = set()
    unicos = []
    for r in todos_resultados:
        url = r.get("url", "")
        if url and url not in vistos:
            vistos.add(url)
            unicos.append(r)
    if len(todos_resultados) != len(unicos):
        print(f"  Duplicados eliminados: {len(todos_resultados) - len(unicos)}")
    todos_resultados = unicos

    todos_resultados = filtrar_por_titulo(todos_resultados, marca, modelo)
    filtrados = filtrar_resultados(todos_resultados, anio_min, anio_max, km_min, km_max)

    stats = calcular_estadisticas(filtrados)

    tiempos_solo_paginas = tiempos_peticion[1:] if len(tiempos_peticion) > 1 else tiempos_peticion
    metricas_tiempo = {
        "tiempo_total": fmt_tiempo(t_total),
        "paginas_scrapeadas": len(tiempos_peticion) - 1,
        "tiempo_medio_por_pagina": fmt_tiempo(statistics.mean(tiempos_solo_paginas)) if tiempos_solo_paginas else "0s",
        "pagina_mas_rapida": fmt_tiempo(min(tiempos_solo_paginas)) if tiempos_solo_paginas else "0s",
        "pagina_mas_lenta": fmt_tiempo(max(tiempos_solo_paginas)) if tiempos_solo_paginas else "0s",
        "peticiones_por_minuto": round(60 / statistics.mean(tiempos_solo_paginas), 1) if tiempos_solo_paginas and statistics.mean(tiempos_solo_paginas) > 0 else 0,
        "delay_entre_peticiones": "~1.8s gaussiano",
    }

    # Desglose por año
    desglose_anio = {}
    for r in filtrados:
        anio = r.get("anio", "?") or "?"
        if anio not in desglose_anio:
            desglose_anio[anio] = {"cantidad": 0, "precios": []}
        desglose_anio[anio]["cantidad"] += 1
        if r.get("precio"):
            desglose_anio[anio]["precios"].append(r["precio"])
    
    for anio, d in desglose_anio.items():
        d["precio_medio"] = round(statistics.mean(d["precios"])) if d["precios"] else None
        del d["precios"]

    return {
        "busqueda": {
            "marca": marca, "modelo": modelo,
            "make_id": make_id, "model_id": model_id,
            "anio_min": anio_min, "anio_max": anio_max,
            "km_min": km_min, "km_max": km_max, "provincias": provincias,
        },
        "total_segun_web": total_web,
        "resultados_brutos": len(todos_resultados),
        "resultados_filtrados": len(filtrados),
        "desglose_por_anio": desglose_anio,
        "estadisticas_precio": stats,
        "metricas_tiempo": metricas_tiempo,
        "detalle_coches": filtrados,
    }


def imprimir_informe(datos):
    b = datos["busqueda"]
    s = datos["estadisticas_precio"]
    t = datos["metricas_tiempo"]

    print(f"\n{'='*60}")
    print(f"  INFORME DE VALORACION")
    print(f"{'='*60}")
    print(f"  {b['marca'].upper()} {b['modelo'].upper()}", end="")
    if b.get("anio_min") and b.get("anio_max"):
        print(f" | Año {b['anio_min']}-{b['anio_max']}", end="")
    elif b.get("anio_min"):
        print(f" | Año desde {b['anio_min']}", end="")
    elif b.get("anio_max"):
        print(f" | Año hasta {b['anio_max']}", end="")
    if b.get("km_min") or b.get("km_max"):
        if b.get("km_min") and b.get("km_max"):
            print(f" | {b['km_min']:,}-{b['km_max']:,} km", end="")
        elif b.get("km_min"):
            print(f" | >={b['km_min']:,} km", end="")
        else:
            print(f" | <={b['km_max']:,} km", end="")
    if b.get("provincias"):
        print(f" | Provincias: {b['provincias']}", end="")
    print()

    if datos.get("total_segun_web"):
        print(f"\n  Total según coches.net:  {datos['total_segun_web']}")
    print(f"  Anuncios scrapeados:     {datos['resultados_brutos']}")
    print(f"  Tras filtrar año/km:     {datos['resultados_filtrados']}")

    desglose = datos.get("desglose_por_anio", {})
    if desglose:
        print(f"\n  --- DESGLOSE POR AÑO ---")
        for anio in sorted(desglose.keys()):
            d = desglose[anio]
            precio_str = f"{d['precio_medio']:>8,} €" if d.get("precio_medio") else "    s/d"
            print(f"  {anio}: {d['cantidad']:>3} coches | Media: {precio_str}")

    if s:
        print(f"\n  --- PRECIO DE MERCADO ---")
        print(f"  Precio medio:      {s['precio_medio']:>10,} €")
        print(f"  Mediana:           {s['precio_mediana']:>10,} €")
        print(f"  Mínimo:            {s['precio_min']:>10,} €")
        print(f"  Máximo:            {s['precio_max']:>10,} €")
        print(f"  Desviación típica: {s['desviacion_tipica']:>10,} €")
        print(f"  (Outliers eliminados: {s['outliers_eliminados']})")
    else:
        print("\n  No hay datos suficientes para calcular estadísticas.")

    print(f"\n  --- METRICAS DE TIEMPO ---")
    print(f"  Tiempo total:           {t['tiempo_total']:>12}")
    print(f"  Páginas scrapeadas:     {t['paginas_scrapeadas']:>12}")
    print(f"  Tiempo medio/página:    {t['tiempo_medio_por_pagina']:>12}")
    print(f"  Página más rápida:      {t['pagina_mas_rapida']:>12}")
    print(f"  Página más lenta:       {t['pagina_mas_lenta']:>12}")
    print(f"  Peticiones/minuto:      {t['peticiones_por_minuto']:>12}")
    print(f"  Delay entre peticiones: {t['delay_entre_peticiones']:>12}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Valorar un coche en coches.net",
        epilog="Ejemplo: python valorar_coche.py fiat 500 --anio-min 2019 --km 100000 --provincias canarias"
    )
    parser.add_argument("marca", help="Marca (ej: seat, volkswagen, fiat)")
    parser.add_argument("modelo", help="Modelo (ej: leon, golf, 500)")
    parser.add_argument("--anio-min", type=int, default=None, help="Año mínimo (desde)")
    parser.add_argument("--anio-max", type=int, default=None, help="Año máximo (hasta)")
    parser.add_argument("--km-min", type=int, default=None, help="Kilómetros mínimos")
    parser.add_argument("--km-max", type=int, default=None, help="Kilómetros máximos")
    parser.add_argument("--provincias", default=None, help="Provincias separadas por coma (ej: canarias, madrid, 'las palmas,tenerife')")
    parser.add_argument("--paginas", type=int, default=20, help="Máximo de páginas (default: 20)")
    parser.add_argument("--make-id", type=int, default=None, help="ID de marca (ej: 14=Fiat)")
    parser.add_argument("--model-id", type=int, default=None, help="ID de modelo (ej: 598=500)")
    args = parser.parse_args()

    provincias_ids = resolver_provincias(args.provincias)

    datos = scrape_valoracion(
        marca=args.marca,
        modelo=args.modelo,
        anio_min=args.anio_min,
        anio_max=args.anio_max,
        km_min=args.km_min,
        km_max=args.km_max,
        max_paginas=args.paginas,
        make_id=args.make_id,
        model_id=args.model_id,
        provincias=provincias_ids,
    )

    if datos:
        imprimir_informe(datos)
        archivo = f"valoracion_{args.marca}_{args.modelo}.json"
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
        print(f"Datos guardados en {archivo}")
