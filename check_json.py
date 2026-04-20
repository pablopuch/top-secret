import json

def buscar_modelos(archivo):
    with open(archivo, "r", encoding="utf-8") as f:
        data = json.load(f)
    hay_algoritmo = sum(len(v.get("modelos", {})) for v in data.values())
    print(f"Total modelos extraídos en todo el JSON: {hay_algoritmo}")

if __name__ == "__main__":
    buscar_modelos("diccionario_coches_net.json")
