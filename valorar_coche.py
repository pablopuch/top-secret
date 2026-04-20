from playwright.sync_api import sync_playwright
import json
import time
import statistics
import argparse
import os
from urllib.parse import urlencode

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
            
            if (linea.includes('€') && !linea.includes('/mes')) {
                const val = parseInt(linea.replace(/[^\d]/g, ''), 10);
                if (!precio && val > 500) {
                    precio = val;
                } else if (val > 500) {
                    const ctx = (lineas[i-1] || '') + ' ' + (lineas[i-2] || '');
                    if (ctx.includes('financiado')) {
                        precio_financiado = val;
                    }
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


def construir_url(make_id, model_id, anio=None, km_max=None, tolerancia=1, pagina=1):
    """Genera URL de búsqueda con IDs reales de coches.net y filtros de año/km."""
    params = {
        "MakeIds[0]": make_id,
        "ModelIds[0]": model_id,
        "hasPhoto": "false",
        "wwa": "false",
    }
    if anio:
        params["MinYear"] = anio - tolerancia
        params["MaxYear"] = anio + tolerancia
    if km_max:
        params["MaxKms"] = km_max
    if pagina > 1:
        params["pg"] = pagina
    return f"https://www.coches.net/search/?{urlencode(params)}"


JS_DESCUBRIR_MARCAS = r"""() => {
    const opciones = [];
    // Buscar en selectores nativos
    document.querySelectorAll('select').forEach(sel => {
        const name = (sel.name || sel.id || '').toLowerCase();
        if (name.includes('make') || name.includes('marca') || name.includes('brand')) {
            Array.from(sel.options).forEach(o => {
                if (o.value && o.value !== '0' && o.value !== '')
                    opciones.push({id: o.value, nombre: o.textContent.trim()});
            });
        }
    });
    if (opciones.length) return opciones;

    // Buscar en dropdowns custom con data attributes
    document.querySelectorAll('[data-make-id], [data-value]').forEach(el => {
        const id = el.dataset.makeId || el.dataset.value;
        const nombre = el.textContent.trim();
        if (id && nombre && nombre.length < 30) opciones.push({id, nombre});
    });
    if (opciones.length) return opciones;

    // Buscar en listas de filtros (role=option)
    document.querySelectorAll('[role="option"], [role="listbox"] li').forEach(el => {
        const id = el.dataset.value || el.dataset.id || el.getAttribute('value');
        const nombre = el.textContent.trim();
        if (id && nombre) opciones.push({id, nombre});
    });
    return opciones;
}"""


def descubrir_ids(page, marca_texto, modelo_texto):
    """Intenta descubrir MakeId y ModelId desde el DOM de la página de búsqueda."""
    marca_texto = marca_texto.lower().strip()
    modelo_texto = modelo_texto.lower().strip()

    marcas = page.evaluate(JS_DESCUBRIR_MARCAS)
    if not marcas:
        return None, None

    make_id = None
    for m in marcas:
        if marca_texto in m["nombre"].lower():
            make_id = m["id"]
            break
    if not make_id:
        return None, None

    # Seleccionar la marca en la UI para que cargue los modelos (si aplica)
    # Intentar navegar con solo MakeId para obtener modelos
    page.goto(f"https://www.coches.net/search/?MakeIds%5B0%5D={make_id}", wait_until="domcontentloaded")
    time.sleep(3)

    modelos = page.evaluate(JS_DESCUBRIR_MARCAS.replace('make', 'model').replace('marca', 'modelo').replace('brand', 'model'))
    model_id = None
    for m in modelos:
        if modelo_texto in m["nombre"].lower():
            model_id = m["id"]
            break

    return make_id, model_id


def filtrar_por_titulo(resultados, marca, modelo):
    """Descarta anuncios promocionados que no corresponden a la marca/modelo buscado."""
    marca_l = marca.lower()
    modelo_l = modelo.lower()
    filtrados = []
    descartados = 0
    for r in resultados:
        titulo = r["titulo"].lower()
        if marca_l in titulo and modelo_l in titulo:
            filtrados.append(r)
        else:
            descartados += 1
    if descartados:
        print(f"  (Descartados {descartados} anuncios promocionados de otros modelos)")
    return filtrados


def filtrar_resultados(resultados, anio_objetivo=None, km_max=None, tolerancia_anio=1):
    filtrados = []
    for r in resultados:
        if r["precio"] is None:
            continue
        if anio_objetivo:
            try:
                anio_coche = int(r["anio"]) if r["anio"] else 0
            except ValueError:
                continue
            if abs(anio_coche - anio_objetivo) > tolerancia_anio:
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


def scrape_valoracion(marca, modelo, anio=None, km_max=None, max_paginas=20,
                      tolerancia_anio=1, make_id=None, model_id=None):
    todos_resultados = []
    tiempos_peticion = []

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

        t_inicio_global = time.time()

        # --- Fase de descubrimiento de IDs (si no se proporcionaron) ---
        if not make_id or not model_id:
            print("Navegando a coches.net para descubrir IDs de marca/modelo...")
            page.goto("https://www.coches.net/search/", wait_until="domcontentloaded")
            print("Esperando 15s por protección anti-bot (resuelve el CAPTCHA si aparece)...")
            time.sleep(15)

            auto_make, auto_model = descubrir_ids(page, marca, modelo)
            if auto_make and auto_model:
                make_id = auto_make
                model_id = auto_model
                print(f"  IDs descubiertos: MakeId={make_id}, ModelId={model_id}")
            else:
                print("  No se pudieron descubrir los IDs automáticamente.")
                print("  Usa --make-id y --model-id para proporcionarlos manualmente.")
                print("  Puedes encontrar los IDs buscando en coches.net y mirando la URL resultante.")
                print("  Ejemplo: MakeIds[0]=39 → Seat, ModelIds[0]=410 → León")
                browser.close()
                return None

        url_inicio = construir_url(make_id, model_id, anio, km_max, tolerancia_anio)

        print(f"\n{'='*60}")
        print(f"  VALORACION DE MERCADO - coches.net")
        print(f"  Marca: {marca.upper()} (ID:{make_id})  |  Modelo: {modelo.upper()} (ID:{model_id})")
        if anio:
            print(f"  Año: {anio - tolerancia_anio} - {anio + tolerancia_anio}")
        if km_max:
            print(f"  Km máximo: {km_max:,} km")
        print(f"  URL: {url_inicio}")
        print(f"{'='*60}\n")

        t_req = time.time()
        page.goto(url_inicio, wait_until="domcontentloaded")

        if not (make_id and model_id):
            print("Esperando 15s por protección anti-bot...")
            time.sleep(15)
        else:
            time.sleep(4)

        tiempos_peticion.append(time.time() - t_req)

        try:
            for pagina in range(1, max_paginas + 1):
                t_req = time.time()

                if pagina > 1:
                    url_pagina = construir_url(make_id, model_id, anio, km_max, tolerancia_anio, pagina)
                    try:
                        page.goto(url_pagina, wait_until="domcontentloaded", timeout=60000)
                    except Exception:
                        print(f"Timeout en página {pagina}. Parando.")
                        break
                    time.sleep(4)

                try:
                    page.wait_for_selector('.mt-CardBasic, .mt-CardAd, article[class*="card"]', timeout=10000)
                except Exception:
                    time.sleep(10)
                    try:
                        page.wait_for_selector('.mt-CardBasic, .mt-CardAd, article[class*="card"]', timeout=5000)
                    except Exception:
                        print(f"Sin resultados en página {pagina}. Fin del scraping.")
                        break

                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 1500)")
                    time.sleep(0.5)

                coches = page.evaluate(JS_EXTRAER)
                t_pagina = time.time() - t_req
                tiempos_peticion.append(t_pagina)

                if not coches:
                    print(f"Página {pagina}: 0 resultados. Fin.")
                    break

                todos_resultados.extend(coches)
                t_acum = time.time() - t_inicio_global
                print(f"Pág {pagina:>3}: {len(coches):>2} coches | {fmt_tiempo(t_pagina)} | Acumulado: {len(todos_resultados)} | Total: {fmt_tiempo(t_acum)}")

                time.sleep(3)

        except KeyboardInterrupt:
            print("\nDetenido por el usuario.")
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            t_total = time.time() - t_inicio_global
            browser.close()

    # --- Filtro por título (descarta anuncios de otros modelos) ---
    todos_resultados = filtrar_por_titulo(todos_resultados, marca, modelo)

    # --- Filtro por año/km ---
    filtrados = filtrar_resultados(todos_resultados, anio, km_max, tolerancia_anio)

    stats = calcular_estadisticas(filtrados)

    tiempos_solo_paginas = tiempos_peticion[1:] if len(tiempos_peticion) > 1 else tiempos_peticion
    metricas_tiempo = {
        "tiempo_total": fmt_tiempo(t_total),
        "paginas_scrapeadas": len(tiempos_peticion) - 1,
        "tiempo_medio_por_pagina": fmt_tiempo(statistics.mean(tiempos_solo_paginas)) if tiempos_solo_paginas else "0s",
        "pagina_mas_rapida": fmt_tiempo(min(tiempos_solo_paginas)) if tiempos_solo_paginas else "0s",
        "pagina_mas_lenta": fmt_tiempo(max(tiempos_solo_paginas)) if tiempos_solo_paginas else "0s",
        "peticiones_por_minuto": round(60 / statistics.mean(tiempos_solo_paginas), 1) if tiempos_solo_paginas and statistics.mean(tiempos_solo_paginas) > 0 else 0,
        "delay_entre_peticiones": "3s",
    }

    return {
        "busqueda": {
            "marca": marca, "modelo": modelo,
            "make_id": make_id, "model_id": model_id,
            "anio_objetivo": anio, "tolerancia_anio": tolerancia_anio,
            "km_max": km_max,
        },
        "resultados_brutos": len(todos_resultados),
        "resultados_filtrados": len(filtrados),
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
    if b["anio_objetivo"]:
        print(f" | Año {b['anio_objetivo'] - b['tolerancia_anio']}-{b['anio_objetivo'] + b['tolerancia_anio']}", end="")
    if b["km_max"]:
        print(f" | ≤{b['km_max']:,} km", end="")
    print()

    print(f"\n  Anuncios del modelo:  {datos['resultados_brutos']}")
    print(f"  Tras filtrar año/km: {datos['resultados_filtrados']}")

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
        epilog="Ejemplo: python valorar_coche.py seat leon --anio 2019 --km 100000 --make-id 39 --model-id 410"
    )
    parser.add_argument("marca", help="Marca (ej: seat, volkswagen, bmw)")
    parser.add_argument("modelo", help="Modelo (ej: leon, golf, serie-3)")
    parser.add_argument("--anio", type=int, default=None, help="Año objetivo")
    parser.add_argument("--km", type=int, default=None, help="Kilómetros máximos")
    parser.add_argument("--paginas", type=int, default=20, help="Máximo de páginas (default: 20)")
    parser.add_argument("--tolerancia", type=int, default=1, help="Tolerancia de años ±N (default: 1)")
    parser.add_argument("--make-id", type=int, default=None, help="ID interno de la marca en coches.net (ej: 39=Seat)")
    parser.add_argument("--model-id", type=int, default=None, help="ID interno del modelo en coches.net (ej: 410=León)")
    args = parser.parse_args()

    datos = scrape_valoracion(
        marca=args.marca,
        modelo=args.modelo,
        anio=args.anio,
        km_max=args.km,
        max_paginas=args.paginas,
        tolerancia_anio=args.tolerancia,
        make_id=args.make_id,
        model_id=args.model_id,
    )

    if datos:
        imprimir_informe(datos)
        archivo = f"valoracion_{args.marca}_{args.modelo}.json"
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
        print(f"Datos guardados en {archivo}")
