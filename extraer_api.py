from playwright.sync_api import sync_playwright
import time
import os

def run():
    os.makedirs("responses", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        def handle_response(response):
            if "json" in response.headers.get("content-type", ""):
                url = response.url
                if "ms.coches.net" in url or "api" in url or "graphql" in url:
                    try:
                        text = response.text()
                        if "make" in text.lower() or "marca" in text.lower() or "models" in text.lower():
                            safe_name = url.split("?")[0].replace("https://", "").replace("/", "_")
                            safe_name = safe_name + "_" + str(int(time.time() * 1000)) + ".json"
                            with open(os.path.join("responses", safe_name), "w", encoding="utf-8") as f:
                                f.write(text)
                            print(f"Intercepted useful JSON: {url}")
                    except Exception as e:
                        pass
        
        page.on("response", handle_response)
        page.goto("https://www.coches.net/search/", wait_until="networkidle", timeout=60000)
        
        # let's try to click multiple things to trigger data
        time.sleep(3)
        try:
             page.click("button:has-text('Aceptar y cerrar')", timeout=3000)
        except:
             pass
        time.sleep(2)
        try:
             page.click("text=Marca y modelo", timeout=3000)
        except:
            pass
        try:
             page.click("text=Marca", timeout=3000)
        except:
            pass

        time.sleep(5)
        browser.close()

if __name__ == "__main__":
    run()
