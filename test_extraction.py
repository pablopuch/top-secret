from playwright.sync_api import sync_playwright
import time
import json

JS_DESCUBRIR_MARCAS = r"""() => {
    const opciones = [];
    document.querySelectorAll('[role="option"], [role="listbox"] li').forEach(el => {
        const id = el.dataset.value || el.dataset.id || el.getAttribute('value');
        const nombre = el.textContent.trim();
        if (id && nombre) opciones.push({id, nombre});
    });
    
    // Y probemos también lo del usuario: panel-39 etc. Si ya están en el DOM.
    return opciones;
}"""

JS_EXTRACT_POPOVER = r"""() => {
    let results = {};
    const headers = document.querySelectorAll('button[id^="header-"]');
    headers.forEach(h => {
        const makeId = h.id.replace('header-', '');
        const makeName = h.querySelector('.mt-FilterBasicLegacy-singleSelectionItemLabel')?.innerText;
        results[makeName] = { make_id: makeId, modelos: {} };
    });
    return results;
}"""

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.coches.net/search/?MakeIds[0]=39", wait_until="domcontentloaded")
        time.sleep(4)
        
        # Test 1: use the sidebar dropdown logic
        modelos_dropdown = page.evaluate(JS_DESCUBRIR_MARCAS.replace('make', 'model').replace('marca', 'modelo').replace('brand', 'model'))
        print("Modelos dropdown approach:", len(modelos_dropdown), "encontrados")
        
        # Test 2: see if the big popover is actually there
        popover_brands = page.evaluate(JS_EXTRACT_POPOVER)
        print("Marcas popover approach:", len(popover_brands), "encontradas")
        
        with open("test_results.json", "w") as f:
            json.dump({"dropdown": modelos_dropdown, "popover": popover_brands}, f, indent=2)

        browser.close()

if __name__ == "__main__":
    run()
