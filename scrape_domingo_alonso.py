from playwright.sync_api import sync_playwright
import json
import sys

URL_BASE = "https://domingoalonsoocasion.com/coches/"

JS_EXTRAER = r"""() => {
    const tarjetas = document.querySelectorAll('ul.flex.flex-wrap > li');
    const resultados = [];

    for (const li of tarjetas) {
        const enlace = li.querySelector('h3 a[href]');
        if (!enlace) continue;

        const href = enlace.getAttribute('href') || '';
        const marca = (li.querySelector('h3 a span.text-sm') || {}).textContent?.trim() || '';
        const modelo = (li.querySelector('h3 a strong.text-black') || {}).textContent?.trim() || '';
        const precioEl = li.querySelector('strong.text-blue-400');
        if (!precioEl) continue;

        const precioTexto = precioEl.textContent.trim();
        const precioNum = parseInt(precioTexto.replace(/[^\d]/g, ''), 10);
        if (!precioNum) continue;

        // Precio anterior (tachado)
        const anteriorEl = li.querySelector('del, .line-through, s');
        let precioAnterior = null;
        if (anteriorEl) {
            precioAnterior = parseInt(anteriorEl.textContent.replace(/[^\d]/g, ''), 10) || null;
        }
        // A veces el precio anterior está en el span dentro del div gris
        if (!precioAnterior) {
            const spanGris = li.querySelector('.text-gray-700.text-sm.text-right span');
            if (spanGris) {
                const val = parseInt(spanGris.textContent.replace(/[^\d]/g, ''), 10);
                if (val > precioNum) precioAnterior = val;
            }
        }

        const specs = li.querySelectorAll('.flex.flex-wrap.truncate.text-xs span');
        const especsList = Array.from(specs).map(s => s.textContent.trim()).filter(Boolean);

        let anio = '', km = '', combustible = '', transmision = '';
        for (const spec of especsList) {
            if (/^20\d{2}$/.test(spec)) anio = spec;
            else if (/km/i.test(spec)) km = spec;
            else if (/gasolina|di[eé]sel|el[eé]ctrico|h[ií]brido|glp/i.test(spec)) combustible = spec;
            else if (/autom|manual|sin caja/i.test(spec)) transmision = spec;
        }

        const reservado = !!li.querySelector('[class*="reserv"], .bg-red');
        const textoCompleto = li.innerText || '';
        const esReservado = reservado || /reservado/i.test(textoCompleto);

        resultados.push({
            concesionario: 'Domingo Alonso',
            marca: marca,
            modelo: modelo,
            precio: precioNum,
            precio_anterior: precioAnterior,
            anio: anio,
            km: km,
            combustible: combustible,
            transmision: transmision,
            reservado: esReservado,
            url: href.startsWith('http') ? href : 'https://domingoalonsoocasion.com' + href
        });
    }
    return resultados;
}"""


def scrape_domingo_alonso(max_paginas=100):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Accediendo a Domingo Alonso...")
        page.goto(URL_BASE, wait_until="networkidle")
        page.wait_for_timeout(3000)

        total_previo = 0
        reintentos = 0
        pagina = 0

        while pagina < max_paginas:
            coches = page.evaluate(JS_EXTRAER)
            total_actual = len(coches)

            if total_actual > total_previo:
                pagina += 1
                reintentos = 0
                print(f"  Página {pagina}: {total_actual} vehículos (+{total_actual - total_previo} nuevos)")
                total_previo = total_actual
            elif reintentos < 3:
                reintentos += 1
                page.wait_for_timeout(4000)
                continue
            else:
                break

            boton_visible = page.evaluate("""() => {
                const btn = document.querySelector('button[onclick*="nextPage"]');
                return btn && btn.offsetParent !== null;
            }""")
            if not boton_visible:
                print("  No hay más páginas.")
                break

            # Scroll al botón y click nativo
            page.evaluate("""() => {
                const btn = document.querySelector('button[onclick*="nextPage"]');
                btn.scrollIntoView({ behavior: 'instant', block: 'center' });
            }""")
            page.wait_for_timeout(500)
            page.evaluate("document.querySelector('button[onclick*=\"nextPage\"]').click()")

            try:
                page.wait_for_response(
                    lambda r: "getSearchModuleParams" in r.url,
                    timeout=15000
                )
            except Exception:
                page.wait_for_timeout(3000)
            page.wait_for_timeout(2000)

        browser.close()
        return coches


if __name__ == "__main__":
    inventario = scrape_domingo_alonso()
    with open("coches.json", "w", encoding="utf-8") as f:
        json.dump(inventario, f, indent=4, ensure_ascii=False)
    print(f"\nTotal: {len(inventario)} vehículos guardados en coches.json")
