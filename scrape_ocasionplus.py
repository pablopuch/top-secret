import json
import time
import urllib.request
import urllib.error

API_URL = "https://zeus.ocasionplus.com/vehicles/search/CAR"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.ocasionplus.com/",
}


def fetch_page(page: int) -> dict:
    url = f"{API_URL}?page={page}&searchType=organic"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def scrape_ocasionplus():
    print("Consultando API de OcasionPlus (Zeus)...", flush=True)
    primera = fetch_page(1)
    page_info = primera["page"]
    total = page_info["totalSize"]
    pages = page_info["total"]
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
                        data = {"data": []}
                        break
                    time.sleep(2)

        for v in data.get("data", []):
            precio_obj = v.get("price", {})
            motor = v.get("characteristics", {}).get("engine", {})
            dealer = v.get("dealer", {})
            finance = v.get("finance", {})
            chars = v.get("characteristics", {})
            desc = v.get("description", {})
            images = v.get("images", [])

            slug = v.get("slug", "")
            url_vehiculo = f"https://www.ocasionplus.com/coches-segunda-mano/{slug}" if slug else ""

            todos.append({
                "concesionario": "OcasionPlus",
                "id": v.get("id"),
                "id_crm": v.get("idCRM"),
                "marca": v.get("brand", ""),
                "modelo": v.get("model", ""),
                "version": desc.get("short", ""),
                "carroceria": v.get("bodyStyle", ""),
                "precio": precio_obj.get("cash"),
                "precio_financiado": precio_obj.get("withFinancing"),
                "descuento_financiacion": precio_obj.get("financedDiscount"),
                "descuento_porcentaje": precio_obj.get("discountPercentageTotal"),
                "iva_deducible": precio_obj.get("deductibleVat", 0) == 100,
                "cuota_mensual": finance.get("quote"),
                "plazo_maximo": finance.get("maximumTerm"),
                "anio": chars.get("registrationDate", "")[:4] if chars.get("registrationDate") else "",
                "fecha_matriculacion": chars.get("registrationDate", ""),
                "km": chars.get("kms"),
                "combustible": motor.get("fuel", ""),
                "transmision": motor.get("transmission", ""),
                "tipo_motor": motor.get("motorType", ""),
                "cv": motor.get("cv"),
                "etiqueta_ambiental": chars.get("environmentalLabel", ""),
                "propietarios": chars.get("owners"),
                "libro_revisiones": chars.get("maintenanceBook", ""),
                "tiene_360": chars.get("has360", False),
                "entrega_rapida": v.get("fastDelivery", False),
                "oferta_flash": v.get("flashOffers", False),
                "condicion": v.get("condition", ""),
                "centro": dealer.get("shortname", ""),
                "provincia": dealer.get("province", ""),
                "ciudad": dealer.get("city", ""),
                "whatsapp": dealer.get("whatsapp", ""),
                "imagen": images[0].get("thumb", "") if images else "",
                "url": url_vehiculo,
            })

        if p % 50 == 0 or p == pages:
            print(f"  Página {p}/{pages} — {len(todos)} vehículos acumulados", flush=True)

        if p < pages:
            time.sleep(0.15)

    return todos


if __name__ == "__main__":
    inventario = scrape_ocasionplus()
    with open("ocasionplus.json", "w", encoding="utf-8") as f:
        json.dump(inventario, f, indent=4, ensure_ascii=False)
    print(f"\nTotal: {len(inventario)} vehículos guardados en ocasionplus.json")
