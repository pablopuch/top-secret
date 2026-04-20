from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.coches.net/search/", wait_until="domcontentloaded")
        
        # Omitimos consentimos si aparece
        try:
            page.click("button:has-text('Aceptar y cerrar')", timeout=3000)
        except:
            pass

        time.sleep(2)

        # Clic en "Marca y modelo" o el input correspondiente si no está visible el popover
        print("Buscando el filtro de marcas...")
        try:
             # Click the visually hidden input label or form input to trigger popover
             page.click("label[for='input-search-filter-vehicle-id'], input#input-search-filter-vehicle-id", timeout=5000)
             time.sleep(1)
        except Exception as e:
             print("No se pudo hacer clic en el filtro de marcas:", e)

        # Buscar el botón de SEAT (ID 39)
        selector_seat = "button#header-39"
        try:
            page.wait_for_selector(selector_seat, timeout=5000)
            print("Clic en SEAT...")
            page.evaluate(f"document.querySelector('{selector_seat}').click()")
            time.sleep(2)
            
            panel_html = page.evaluate("document.querySelector('#panel-39').innerHTML")
            with open("panel_seat.html", "w", encoding="utf-8") as f:
                f.write(panel_html)
            print("HTML del panel SEAT guardado en panel_seat.html")
        except Exception as e:
            print("Error al encontrar/extraer SEAT:", e)
            html = page.content()
            with open("page_dump.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Page dump saved")

        browser.close()

if __name__ == "__main__":
    run()
