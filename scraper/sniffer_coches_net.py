from playwright.sync_api import sync_playwright
import json

log_conexiones = []

def al_recibir_respuesta(response):
    url = response.url
    # Queremos escuchar las comunicaciones secretas de datos, no imágenes ni estilos
    if "google" not in url and "segment" not in url and ".js" not in url and ".css" not in url and ".png" not in url:
        try:
            # Solo guardamos cosas que vengan de la red de coches.net o subdominios
            if "coches.net" in url or "adevinta" in url:
                print(f"🔥 ¡Comunicación Interceptada! -> {url}")
                log_conexiones.append({
                    "url_endpoint": url,
                    "metodo": response.request.method,
                    "codigo_estado": response.status
                })
        except Exception:
            pass

def iniciar_rastreador_inverso():
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

        # Conectar el estetoscopio a la red: escuchamos todas las respuestas del servidor
        page.on("response", al_recibir_respuesta)
        
        print("Accediendo a Coches.net en modo escáner...")
        page.goto("https://www.coches.net/search/")
        
        print("\n" + "═"*60)
        print("🕵️‍♂️ MODO DE INGENIERÍA INVERSA ACTIVADO 🕵️‍♂️")
        print("1. Si salta el Captcha, resuélvelo tranquilamente.")
        print("2. Empieza a jugar con la web: abre los menús, elige un 'Seat', elige 'Diésel'...")
        print("3. Cambia de páginas, prueba ordenarlos de más caros a más baratos.")
        print("4. Yo estoy escondido capturando cada variable, ID y conexión oculta que usa la web.")
        print("5. Cuando te aburras o termines, CIERRA EL NAVEGADOR con la 'X'.")
        print("═"*60 + "\n")
        
        # Mantiene la ventana abierta para que operes manualmente hasta que la cierres
        page.wait_for_event("close", timeout=0)
        browser.close()

if __name__ == "__main__":
    try:
        iniciar_rastreador_inverso()
    except KeyboardInterrupt:
        pass
        
    # Volcamos todo lo que hemos averiguado a un archivo Json
    with open("diccionario_cochesnet_interceptado.json", "w", encoding="utf-8") as f:
        json.dump(log_conexiones, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ Análisis completado. He espiado {len(log_conexiones)} peticiones secretas.")
    print("Revisa el archivo 'diccionario_cochesnet_interceptado.json' para ver la estructura de URLs y IDs de su BD.")
