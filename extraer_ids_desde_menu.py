from playwright.sync_api import sync_playwright
import time
import json
import os

ARCHIVO_JSON = "diccionario_coches_net.json"

def run():
    print("Iniciando Playwright...")
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
        page.goto("https://www.coches.net/search/", wait_until="domcontentloaded")
        
        print("\n" + "="*70)
        print(" ACCIÓN MANUAL REQUERIDA (Anti-bloqueos)")
        print("="*70)
        print("1. En el navegador que se acaba de abrir, acepta las cookies.")
        print("2. Abre el filtro de 'Marca y modelo' para que se despliegue")
        print("   el panel derecho con la lista de marcas.")
        print("3. No hace falta que despliegues ninguna marca, solo que la lista sea visible.")
        print("="*70)
        input(">> Presiona ENTER aquí en la consola cuando el panel esté abierto visible... <<")
        
        print("\nEmpezando escaneo iterativo del menú...")
        
        # Cargar diccionario anterior si existe, o crear uno nuevo
        if os.path.exists(ARCHIVO_JSON):
            with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
                catalogo = json.load(f)
        else:
            catalogo = {}

        # Encontrar el contenedor del popover (del HTML proporcionado)
        headers = page.locator('button[id^="header-"]')
        total_marcas = headers.count()
        print(f"He encontrado {total_marcas} marcas en el panel.")
        
        for i in range(total_marcas):
            btn = headers.nth(i)
            # Asegurarse de que el botón esté visible en la lista
            btn.scroll_into_view_if_needed()
            
            make_id = btn.get_attribute("id").replace("header-", "")
            
            try:
                marca_name = btn.locator(".mt-FilterBasicLegacy-singleSelectionItemLabel").inner_text(timeout=2000).strip()
                # Quitar contadores si los tiene, ej: "SEAT (1)"
                marca_name = marca_name.split('(')[0].strip()
            except:
                marca_name = btn.inner_text().split("\n")[0].strip()
                
            print(f"[{i+1}/{total_marcas}] Analizando {marca_name} (ID: {make_id})...", end="", flush=True)
            
            if marca_name not in catalogo:
                catalogo[marca_name] = {"make_id": make_id, "modelos": {}}
                
            # Expandir el panel de modelos
            btn.click()
            
            panel = page.locator(f"id=panel-{make_id}")
            
            # Esperar activamente a que aparezca al menos un elemento hijo (los modelos tardan en cargar)
            try:
                # Buscamos cualquier tipo de hijo que parezca un item
                panel.locator("label, li, button[id^='header-'], .mt-FilterBasicLegacy-singleSelectionItem, input").first.wait_for(timeout=4000)
            except:
                pass # Puede que no haya o que la estructura sea muy diferente
            
            # Buscar los elementos individuales de modelo usando JavaScript para evitar elementos solapados
            modelos_dict = panel.evaluate("""(panelHTML) => {
                let dict = {};
                
                // Estrategia 1: Acordeones anidados (por si acaso alguna vista móvil los usa)
                panelHTML.querySelectorAll('button[id^="header-"]').forEach(btn => {
                    let id = btn.id.replace('header-', '');
                    let name = btn.innerText.split('\\n')[0].split('(')[0].trim();
                    if (id && name && name.toLowerCase() !== "todos los modelos") dict[name] = id;
                });
                if (Object.keys(dict).length > 0) return dict;
                
                // Estrategia 2: Checkboxes (Donde el ID está directamente en los atributos 'id' o 'name')
                panelHTML.querySelectorAll('input[type="checkbox"], input[type="radio"]').forEach(el => {
                    let id = el.id || el.name || el.value || el.dataset.value || el.dataset.id;
                    
                    // Si el ID es texto puro, "allOptions", on/off etc, lo ignoramos
                    if (!id || id === "allOptions" || id === "on" || id === "true" || id.includes("Checkbox")) return;
                    
                    let container = el.closest('li, .mt-FilterBasicLegacy-multiSelectionItem, .mt-FilterBasicLegacy-singleSelectionItem, label');
                    if (!container) return;
                    
                    let nameNode = container.querySelector('.mt-FilterBasicLegacy-multiSelectionItemLabel, .mt-FilterBasicLegacy-singleSelectionItemLabel');
                    let name = nameNode ? nameNode.innerText : container.innerText;
                    name = name.split('\\n')[0].split('(')[0].trim();
                    
                    if (name.toLowerCase() !== "todos los modelos" && name) {
                        dict[name] = id;
                    }
                });
                
                return dict;
            }""")
            
            if modelos_dict and len(modelos_dict) > 0:
                print(f" -> Encontrados {len(modelos_dict)} modelos.")
                catalogo[marca_name]["modelos"] = modelos_dict
            else:
                print(" -> [DEBUG HTML] Sin modelos. Volcando TODO el panel a debug_panel.html...")
                with open("debug_panel.html", "w", encoding="utf-8") as f:
                    f.write(panel.inner_html())
            
            # Colapsar el panel de esta marca
            try:
                btn.scroll_into_view_if_needed()
                btn.click()
            except:
                pass
            time.sleep(0.1)
            
            # Guardamos progreso a menudo por si falla
            if i % 5 == 0:
                 with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
                     json.dump(catalogo, f, indent=2, ensure_ascii=False)
        
        # Guardado final
        with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
            json.dump(catalogo, f, indent=2, ensure_ascii=False)
            
        print("\n¡Catálogo extraído con éxito y guardado en", ARCHIVO_JSON)
        browser.close()

if __name__ == "__main__":
    run()
