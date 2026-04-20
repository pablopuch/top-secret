from playwright.sync_api import sync_playwright
import time
import sys

def run():
    print("Iniciando Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,  # Running headlessly so it runs in background
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("Cargando web...")
        page.goto("https://www.coches.net/search/", wait_until="domcontentloaded")
        time.sleep(3)
        
        try:
             page.click("button:has-text('Aceptar y cerrar')", timeout=3000)
        except:
             pass
        
        print("Abriendo menú Marca y modelo...")
        try:
            page.click("text=Marca y modelo", timeout=3000)
        except:
            try:
                page.click("text=Marca", timeout=3000)
            except:
                print("No se pudo abrir el menú. Volcando HTML...")
                with open("error_page.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                sys.exit(1)
        
        time.sleep(2)
        
        btn = page.locator('button[id="header-4"]')
        if btn.count() == 0:
            print("No se encontró AUDI.")
            sys.exit(1)
            
        print("Abriendo AUDI...")
        btn.scroll_into_view_if_needed()
        btn.click()
        time.sleep(2)
        
        panel = page.locator("id=panel-4")
        print("Obteniendo HTML de AUDI:")
        print(panel.inner_html()[:2500])
        
        browser.close()

if __name__ == "__main__":
    run()
