from playwright.sync_api import sync_playwright
import time
import json

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.coches.net/search/", wait_until="domcontentloaded")
        
        try:
            page.click("button:has-text('Aceptar y cerrar')", timeout=3000)
        except:
            pass

        time.sleep(2)
        print("Clicking 'Marca y modelo' filter...")
        try:
            # coches.net frequently changes text, let's use multiple strategies
            try:
                page.click("text=Marca y modelo", timeout=3000)
            except:
                page.click("text=Marca", timeout=3000)
            time.sleep(2)
        except Exception as e:
            print("Couldn't click main filter:", e)
            
        print("Obteniendo marcas del menú...")
        headers = page.locator('button[id^="header-"]')
        count = headers.count()
        print(f"Marcas encontradas: {count}")
        
        catalogo = {}
        for i in range(count):
            btn = headers.nth(i)
            make_id = btn.get_attribute("id").replace("header-", "")
            
            try:
                marca_name = btn.locator(".mt-FilterBasicLegacy-singleSelectionItemLabel").inner_text(timeout=2000).strip()
            except:
                marca_name = btn.inner_text().strip().split("\n")[0]
            
            print(f"Analizando {marca_name} (ID: {make_id})")
            
            btn.scroll_into_view_if_needed()
            btn.click()
            time.sleep(1.5) # wait for models
            
            panel_id = f"panel-{make_id}"
            panel = page.locator(f"id={panel_id}")
            
            modelos_dict = {}
            # Models inside panel are often checkboxes or buttons. 
            items = panel.locator(".sui-AtomCheckbox, .mt-FilterBasicLegacy-singleSelectionItemLabel, input[type='checkbox']")
            
            print(f"  Elementos encontrados en el panel: {items.count()}")
            # let's just dump the panel HTML for the first brand to understand 
            if i == 0:
                with open("panel_dump.html", "w", encoding="utf-8") as f:
                    f.write(panel.inner_html())
            
            # Collapse again
            btn.scroll_into_view_if_needed()
            btn.click()
            time.sleep(0.5)
            
            if i >= 3:
                break
        
        browser.close()

if __name__ == "__main__":
    run()
