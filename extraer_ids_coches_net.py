from playwright.sync_api import sync_playwright
import json
import time
import os
import random

ARCHIVO_SALIDA = "diccionario_coches_net.json"
ARCHIVO_PROGRESO = "progreso_modelos.json"
DELAY_MIN = 4
DELAY_MAX = 7
MAX_MAKE_ID = 1500
MAX_MODEL_ID = 2000
MAX_VACIOS = 50

MARCAS = {
    "ABARTH": "1330", "AIWAYS": "1408", "AIXAM": "158", "ALFA ROMEO": "1",
    "ALPINE": "1377", "ARO": "238", "ASIA": "1326", "ASIA MOTORS": "2",
    "ASTON MARTIN": "3", "AUDI": "4", "AUSTIN": "111", "AUVERLAND": "1321",
    "BAIC": "1441", "BELLIER": "1331", "BENTLEY": "6", "BERTONE": "241",
    "BESTUNE": "1437", "BMW": "7", "BUGATTI": "1345", "BUNKER-TRIKE": "1332",
    "BYD": "1352", "CADILLAC": "8", "CASALINI": "1333", "CENNTRO": "1415",
    "CHANGAN": "1444", "CHATENET": "161", "CHEVROLET": "9", "CHRYSLER": "10",
    "CITROEN": "11", "CORVETTE": "1327", "CUPRA": "1400", "DACIA": "1011",
    "DAEWOO": "12", "DAF": "102", "DAIHATSU": "13", "DAIMLER": "145",
    "DFSK": "1351", "DODGE": "173", "DONGFENG": "1431",
    "DR AUTOMOBILES": "1401", "DS": "1358", "DSK": "1429", "EBRO": "210",
    "ERAD": "1334", "ESTRIMA BIRO": "1398", "EVO": "1410", "EVUM": "1416",
    "FARIZON": "1436", "FERRARI": "146", "FIAT": "14", "FISKER": "1383",
    "FORD": "15", "FOTON": "1430", "FUSO": "1397", "GALLOPER": "16",
    "GME": "191", "GRECAV": "1335", "GREEN TOUR": "1406", "HERKO": "1442",
    "HONDA": "69", "HONGQI": "1423", "HUMMER": "234", "HYUNDAI": "18",
    "ICH-X": "1438", "INEOS": "1409", "INFINITI": "1025", "INNOCENTI": "185",
    "ISUZU": "19", "ITAL CAR": "1336", "IVECO": "126", "IVECO-PEGASO": "103",
    "JAECOO": "1434", "JAGUAR": "20", "JDM": "159", "JEEP": "21",
    "KGM": "1427", "KIA": "22", "KTM": "1349", "LADA": "153",
    "LAMBORGHINI": "243", "LANCIA": "23", "LAND-ROVER": "24", "LDV": "128",
    "LEAPMOTOR": "1432", "LEVC": "1407", "LEXUS": "25", "LIGIER": "163",
    "LIVAN": "1439", "LOTUS": "147", "LYNK & CO": "1404", "MAHINDRA": "246",
    "MAN": "104", "MASERATI": "26", "MAXUS": "1403", "MAYBACH": "1323",
    "MAZDA": "27", "MCLAREN": "1347", "MEGA": "1337", "MELEX": "1338",
    "MERCEDES-BENZ": "28", "MG": "29", "M-HERO": "1428", "MICRO": "1433",
    "MICROCAR": "162", "MINI": "222", "MITSUBISHI": "30", "MOBILIZE": "1440",
    "MORGAN": "149", "MW MOTORS": "1419", "NEXTEM": "1417", "NISSAN": "31",
    "OMODA": "1420", "OPEL": "32", "PEUGEOT": "33", "PGO SCOOTERS": "1339",
    "PIAGGIO": "87", "POLARIS": "1340", "POLESTAR": "1402", "PONTIAC": "112",
    "PORSCHE": "34", "QOROS": "1348", "QUOVIS": "1341", "RAM": "1372",
    "RENAULT": "35", "RENAULT V.I.": "1329", "ROLLS-ROYCE": "36",
    "ROVER": "37", "SAAB": "38", "SAIC": "1399", "SANTANA": "1328",
    "SEAT": "39", "SERES": "1422", "SHINERAY": "1443", "SKODA": "40",
    "SKYWELL": "1425", "SMART": "41", "SPORTEQUIPE": "1446",
    "SSANGYONG": "42", "SUBARU": "43", "SUZUKI": "44", "SWM": "1411",
    "TALBOT": "156", "TASSO": "1342", "TATA": "45", "TESLA": "1354",
    "TIGER": "1445", "TOYOTA": "46", "TWIKE": "1350", "UMM": "1324",
    "VAZ": "1325", "VIDI": "1343", "VOLKSWAGEN": "47", "VOLVO": "48",
    "VOYAH": "1426", "WARTBURG": "186", "XPENG": "1435", "YUDO": "1421",
    "ZEST": "1344", "ZHIDOU": "1418",
}


def lanzar_browser(playwright):
    browser = playwright.chromium.launch(
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
    return browser, context, page


def detectar_captcha(page):
    titulo = page.title()
    if "Ups" in titulo or "Parece que algo" in titulo:
        print("\n  !!! CAPTCHA - Resuélvelo en el navegador !!!")
        for _ in range(60):
            time.sleep(5)
            if "Ups" not in page.title():
                print("  Resuelto.\n")
                time.sleep(3)
                return True
        return False
    return True


def extraer_modelo_de_titulo(titulo, nombre_marca):
    """Extrae nombre del modelo del title de la página.
    Ejemplo: 'SEAT Ibiza de segunda mano y ocasión | coches.net' -> 'Ibiza'
    """
    if not titulo or "coches.net" not in titulo:
        return None
    parte = titulo.split("|")[0].strip()
    # Quitar "de segunda mano y ocasión" etc
    for corte in [" de segunda", " segunda mano", " ocasión", " en "]:
        if corte in parte:
            parte = parte.split(corte)[0].strip()
    # Quitar nombre de marca al inicio
    marca_upper = nombre_marca.upper().replace("-", " ")
    parte_upper = parte.upper()
    if parte_upper.startswith(marca_upper):
        modelo = parte[len(nombre_marca):].strip()
        if modelo:
            return modelo
    # A veces el título no tiene la marca
    if parte and parte.upper() != marca_upper and len(parte) < 40:
        return parte
    return None


def cargar_progreso():
    if os.path.exists(ARCHIVO_PROGRESO):
        with open(ARCHIVO_PROGRESO, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_progreso(progreso):
    with open(ARCHIVO_PROGRESO, "w", encoding="utf-8") as f:
        json.dump(progreso, f, indent=2, ensure_ascii=False)


def guardar_catalogo(catalogo):
    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, indent=2, ensure_ascii=False)


def ejecutar():
    t_inicio = time.time()

    # Cargar catálogo
    catalogo = {}
    if os.path.exists(ARCHIVO_SALIDA):
        with open(ARCHIVO_SALIDA, "r", encoding="utf-8") as f:
            try:
                catalogo = json.load(f)
            except Exception:
                catalogo = {}

    for nombre, make_id in MARCAS.items():
        if nombre not in catalogo:
            catalogo[nombre] = {"make_id": make_id, "modelos": {}}
    guardar_catalogo(catalogo)

    progreso = cargar_progreso()

    with sync_playwright() as p:
        browser, _, page = lanzar_browser(p)

        try:
            print("Cargando coches.net...")
            page.goto("https://www.coches.net/search/", wait_until="domcontentloaded", timeout=90000)
            time.sleep(10)
            detectar_captcha(page)
            print("OK\n")

            # === FASE 1: Descubrir marcas por URL (MakeIds 1-1500) ===
            fase1_ultimo = progreso.get("__fase1__", 0)
            if fase1_ultimo < MAX_MAKE_ID:
                print(f"=== FASE 1: Marcas (MakeId {fase1_ultimo+1}-{MAX_MAKE_ID}) ===\n")
                vacios = 0
                for make_id in range(fase1_ultimo + 1, MAX_MAKE_ID + 1):
                    url = f"https://www.coches.net/search/?MakeIds%5B0%5D={make_id}"
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(1.5)
                    except Exception:
                        time.sleep(3)
                        continue

                    if not detectar_captcha(page):
                        break

                    titulo = page.title()
                    nombre_marca = None
                    if titulo and "coches.net" in titulo:
                        parte = titulo.split("|")[0].strip()
                        for corte in [" de segunda", " segunda mano", " ocasión", " en "]:
                            if corte in parte:
                                parte = parte.split(corte)[0].strip()
                        if parte and parte.upper() not in ["COCHES.NET", "COCHES", ""]:
                            nombre_marca = parte.strip()

                    if nombre_marca:
                        ya = any(d["make_id"] == str(make_id) for d in catalogo.values())
                        if not ya:
                            catalogo[nombre_marca] = {"make_id": str(make_id), "modelos": {}}
                            print(f"  MakeId {make_id:5d} = {nombre_marca} (NUEVA)")
                        else:
                            print(f"  MakeId {make_id:5d} = {nombre_marca}")
                        vacios = 0
                    else:
                        vacios += 1

                    progreso["__fase1__"] = make_id
                    if make_id % 50 == 0:
                        guardar_progreso(progreso)
                        guardar_catalogo(catalogo)
                        print(f"  ... MakeId {make_id} ({len(catalogo)} marcas)")

                    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

                progreso["__fase1__"] = MAX_MAKE_ID
                guardar_progreso(progreso)
                guardar_catalogo(catalogo)
                print(f"\n  Fase 1 completa: {len(catalogo)} marcas\n")

            # === FASE 2: Modelos por marca (ModelIds 1-2000) ===
            pendientes = []
            for nombre in sorted(catalogo.keys()):
                ultimo = progreso.get(nombre, 0)
                if ultimo >= MAX_MODEL_ID:
                    continue
                pendientes.append(nombre)

            if not pendientes:
                print("Todas las marcas ya tienen modelos.")
            else:
                print(f"=== FASE 2: Modelos ({len(pendientes)} marcas, ModelId 1-{MAX_MODEL_ID}) ===")
                print(f"  Delay: {DELAY_MIN}-{DELAY_MAX}s | Corte: {MAX_VACIOS} vacíos\n")

                for idx_marca, nombre in enumerate(pendientes):
                    make_id = catalogo[nombre]["make_id"]
                    desde = progreso.get(nombre, 0) + 1
                    modelos = catalogo[nombre].get("modelos", {})
                    vacios = 0

                    print(f"[{idx_marca+1}/{len(pendientes)}] {nombre} (MakeId={make_id}) desde ModelId={desde}")

                    for model_id in range(desde, MAX_MODEL_ID + 1):
                        url = f"https://www.coches.net/search/?MakeIds%5B0%5D={make_id}&ModelIds%5B0%5D={model_id}"
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            time.sleep(1.5)
                        except Exception:
                            time.sleep(3)
                            continue

                        if not detectar_captcha(page):
                            break

                        titulo = page.title()
                        modelo = extraer_modelo_de_titulo(titulo, nombre)

                        if modelo:
                            modelos[modelo] = str(model_id)
                            print(f"  ModelId {model_id:5d} = {modelo}")
                            vacios = 0
                        else:
                            vacios += 1

                        progreso[nombre] = model_id
                        catalogo[nombre]["modelos"] = modelos

                        if model_id % 50 == 0:
                            guardar_progreso(progreso)
                            guardar_catalogo(catalogo)
                            print(f"  ... ModelId {model_id} ({len(modelos)} modelos) [{vacios} vacíos]")

                        if vacios >= MAX_VACIOS:
                            print(f"  {MAX_VACIOS} vacíos seguidos, siguiente marca")
                            progreso[nombre] = MAX_MODEL_ID
                            break

                        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

                    guardar_progreso(progreso)
                    guardar_catalogo(catalogo)
                    print(f"  >> {nombre}: {len(modelos)} modelos\n")

        except KeyboardInterrupt:
            print("\nDetenido.")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        finally:
            guardar_progreso(progreso)
            guardar_catalogo(catalogo)
            try:
                browser.close()
            except Exception:
                pass

    imprimir_resumen(catalogo, t_inicio)


def imprimir_resumen(catalogo, t_inicio):
    t_total = time.time() - t_inicio
    total_modelos = sum(len(v.get("modelos", {})) for v in catalogo.values())
    con_modelos = sum(1 for v in catalogo.values() if v.get("modelos"))

    print(f"\n{'='*60}")
    print(f"  Marcas:        {len(catalogo)}")
    print(f"  Con modelos:   {con_modelos}")
    print(f"  Total modelos: {total_modelos}")
    print(f"  Tiempo:        {int(t_total//60)}m {t_total%60:.0f}s")
    print(f"  Archivo:       {ARCHIVO_SALIDA}")
    print(f"{'='*60}")

    for marca, datos in sorted(catalogo.items()):
        mods = datos.get("modelos", {})
        if mods:
            print(f"  {marca} ({len(mods)}): {', '.join(list(mods.keys())[:5])}")


if __name__ == "__main__":
    ejecutar()
