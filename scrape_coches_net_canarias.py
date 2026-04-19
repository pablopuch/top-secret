from playwright.sync_api import sync_playwright
import json
import time

# URL acotada exclusivamente a Canarias (Provincias 35 y 38)
URL_BASE = "https://www.coches.net/search/?hasPhoto=false&wwa=false&arrProvince=35%7C38"

# Script JS que se inyectará en la página para leer las tarjetas
JS_EXTRAER = r"""() => {
    const tarjetas = document.querySelectorAll('.mt-CardBasic, .mt-CardAd, [class*="CardAd"], article[class*="card"]');
    const resultados = [];

    for (const card of tarjetas) {
        // Enlace y título
        let enlaceEl = card.querySelector('h2 a');
        if (!enlaceEl) enlaceEl = card.querySelector('a[href*=".aspx"]');
        if (!enlaceEl) continue;
        
        const href = enlaceEl.getAttribute('href') || '';
        const titulo = enlaceEl.textContent?.trim() || '';

        // El texto interno de la tarjeta tiene toda la información visible
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
            
            // Extracción de Precios
            if (linea.includes('€') && !linea.includes('/mes')) {
                const val = parseInt(linea.replace(/[^\d]/g, ''), 10);
                if (!precio && val > 500) {
                    precio = val;
                } else if (val > 500) {
                    // Es probable que si hay otro precio sea el financiado, comprobamos contexto
                    const ctx = (lineas[i-1] || '') + ' ' + (lineas[i-2] || '');
                    if (ctx.includes('financiado')) {
                        precio_financiado = val;
                    }
                }
            }
            if (linea.includes('€/mes') || (linea.includes('€') && lineas[i+1] && lineas[i+1].includes('/mes'))) {
                cuota = parseInt(linea.replace(/[^\d]/g, ''), 10);
            }
            
            // Extracción de Características
            if (/^20\d{2}$/.test(linea) || /^19\d{2}$/.test(linea)) anio = linea;
            if (/km$/i.test(linea)) km = parseInt(linea.replace(/[^\d]/g, ''), 10);
            if (/cv$/i.test(linea)) cv = parseInt(linea.replace(/[^\d]/g, ''), 10);
            if (/Gasolina|Diésel|Eléctrico|Híbrido|GLP|GNC/i.test(linea)) combustible = linea;
            
            // Vendedor y Localización
            if (linea.includes('Profesional') || linea.includes('Particular')) {
                vendedor = linea;
                // La provincia suele estar justo arriba del vendedor, saltando "Envío disponible"
                if (i > 0 && !lineas[i-1].includes('Envío') && !lineas[i-1].includes('Garantía')) {
                    provincia = lineas[i-1];
                } else if (i > 1 && !lineas[i-2].includes('Envío') && !lineas[i-2].includes('Garantía')) {
                    provincia = lineas[i-2];
                }
            }
        }

        resultados.push({
            concesionario: 'Coches.net',
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

def scrape_coches_net_canarias(max_paginas=5, pagina_inicio=1, resultados_previos=None):
    resultados = resultados_previos if resultados_previos is not None else []
    
    with sync_playwright() as p:
        # ESENCIAL: Evitar que nos detecten como bot de automatización
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
        
        # Ocultar propiedad webdriver
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("Accediendo a Coches.net (Filtro Canarias)...")
        page.goto(URL_BASE)
        
        print("⏳ Esperando 15 segundos por si salta la protección anti-bot (DataDome/Cloudflare)...")
        print("❗ SI VES UN CAPTCHA, RESUÉLVELO AHORA DIRECTAMENTE EN EL NAVEGADOR EMERGENTE")
        time.sleep(15)

        try:
            for pagina in range(pagina_inicio, max_paginas + 1):
                if pagina > 1:
                    # Añadido arrProvince=35|38 a la paginación dinámica
                    url_pagina = f"https://www.coches.net/search/?Section1Id=2500&pg={pagina}&hasPhoto=false&wwa=false&arrProvince=35%7C38"
                    try:
                        # Timeout extendido a 60 segundos por si hay lag en la red o salta el anti-bot
                        page.goto(url_pagina, wait_until="domcontentloaded", timeout=60000)
                    except Exception as e:
                        print(f"\n❌ Error de red (Timeout) intentando cargar la página {pagina}.")
                        print("Deteniendo el proceso de forma segura para no perder los datos ya extraídos...")
                        break
                        
                    time.sleep(4) # Esperar a que asiente el HTML

                try:
                    # Esperamos a que el contenedor de tarjetas exista
                    page.wait_for_selector('.mt-CardBasic, .mt-CardAd, article[class*="card"]', timeout=10000)
                except Exception:
                    print(f"⚠️ No se encontraron tarjetas en la página {pagina}. Reintentando...")
                    time.sleep(10) # Damos margen por si nos han saltado captcha de nuevo entre páginas
                    try:
                        page.wait_for_selector('.mt-CardBasic, .mt-CardAd, article[class*="card"]', timeout=5000)
                    except:
                        print("❌ Definitivamente no hay tarjetas o el bot nos bloqueó. Deteniendo...")
                        break
                
                # Hacemos scroll por la página un par de veces para cargar imágenes y HTML perezoso
                for _ in range(4):
                    page.evaluate("window.scrollBy(0, 1500)")
                    time.sleep(1)

                coches = page.evaluate(JS_EXTRAER)
                print(f"✔️ Página {pagina}: extraídos {len(coches)} vehículos")
                
                if not coches:
                    break
                    
                resultados.extend(coches)
                
                # GUARDADO DE SEGURIDAD PROGRESIVO
                if pagina % 5 == 0:
                    with open("coches_net_canarias_seguridad.json", "w", encoding="utf-8") as f:
                        json.dump(resultados, f, indent=4, ensure_ascii=False)
                
                # Delay aleatorio para no ser agresivos y que nos pillen
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\n🛑 Proceso detenido manualmente por el usuario. Guardando lo recolectado...")
        except Exception as e:
            print(f"\n💥 Error inesperado masivo: {e}")
            print("Guardando los datos recolectados para que no se pierdan...")
        finally:
            browser.close()
            return resultados

import os

if __name__ == "__main__":
    print("Iniciando scraper exclusivo para coches.net CANARIAS...")
    
    # Trabajamos sobre un archivo totalmente independiente
    archivo_json = "coches_net_canarias.json"
    inventario_previo = []
    
    # Carga de seguridad por si se detiene a medias
    if os.path.exists(archivo_json):
        try:
            with open(archivo_json, "r", encoding="utf-8") as f:
                inventario_previo = json.load(f)
                print(f"♻️ Cargados {len(inventario_previo)} vehículos de la sesión anterior.")
        except Exception:
            print("⚠️ No se pudo cargar el archivo anterior, empezando de cero.")

    # Lanzar configurado para 407 páginas (Canarias), empezando en la 1 por defecto
    inventario = scrape_coches_net_canarias(max_paginas=407, pagina_inicio=1, resultados_previos=inventario_previo) 
    
    with open(archivo_json, "w", encoding="utf-8") as f:
        json.dump(inventario, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ Total final: {len(inventario)} vehículos de Canarias guardados en {archivo_json}")
