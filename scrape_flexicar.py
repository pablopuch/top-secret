import json
import time
import urllib.request
import urllib.error

API_URL = "https://services.flexicar.es/api/v1/vehicles"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.flexicar.es/",
}


def fetch_page(page: int) -> dict:
    url = f"{API_URL}?page={page}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def scrape_flexicar():
    print("Consultando API de Flexicar...", flush=True)
    primera = fetch_page(1)
    total = primera["total"]
    pages = primera["pages"]
    print(f"  Total: {total} vehículos en {pages} páginas", flush=True)

    todos = []
    for p in range(1, pages + 1):
        if p == 1:
            data = primera
        else:
            intentos = 0
            while True:
                try:
                    data = fetch_page(p)
                    break
                except (urllib.error.URLError, TimeoutError) as e:
                    intentos += 1
                    if intentos >= 3:
                        print(f"  ERROR en página {p} tras 3 intentos: {e}")
                        data = {"results": []}
                        break
                    time.sleep(2)

        for v in data.get("results", []):
            todos.append({
                "concesionario": "Flexicar",
                "id": v.get("id"),
                "marca": v.get("brand", ""),
                "modelo": v.get("model", ""),
                "version": v.get("version", ""),
                "precio": v.get("price"),
                "precio_anterior": v.get("previousPrice"),
                "precio_retail": v.get("retailPrice"),
                "cuota_mensual": v.get("quotaPrice"),
                "anio": v.get("year"),
                "km": v.get("km"),
                "combustible": v.get("fuel", ""),
                "transmision": v.get("transmission", ""),
                "etiqueta_eco": v.get("ecoSticker", ""),
                "concesionario_local": v.get("carDealership", ""),
                "iva_deducible": v.get("taxDeductible", False),
                "oferta": v.get("offer", False),
                "reservado": v.get("reserved", False),
                "url": f"https://www.flexicar.es/{v['slug']}/" if v.get("slug") else "",
                "imagen": v.get("image", ""),
            })

        if p % 100 == 0 or p == pages:
            print(f"  Página {p}/{pages} — {len(todos)} vehículos acumulados", flush=True)

        if not data.get("hasNext", False) and p > 1:
            break

        time.sleep(0.15)

    return todos


if __name__ == "__main__":
    inventario = scrape_flexicar()
    with open("flexicar.json", "w", encoding="utf-8") as f:
        json.dump(inventario, f, indent=4, ensure_ascii=False)
    print(f"\nTotal: {len(inventario)} vehículos guardados en flexicar.json")
