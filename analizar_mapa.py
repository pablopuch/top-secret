import json

with open('mapa_filtros_coches_net.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

def find_models(obj, path=""):
    if isinstance(obj, dict):
        # Look for structures that look like a brand/model list
        if "makeId" in obj or "modelId" in obj or "makes" in obj or "models" in obj:
            print(f"Found keys at {path}: {list(obj.keys())[:10]}")
        for k, v in obj.items():
            find_models(v, path=path+"."+str(k))
    elif isinstance(obj, list):
        if len(obj) > 0 and isinstance(obj[0], dict):
            keys = set(obj[0].keys())
            if "makeId" in obj[0] or "id" in obj[0] and "models" in obj[0]:
                 print(f"Found list of models at {path}")
        for i, v in enumerate(obj):
            find_models(v, path=path+f"[{i}]")

find_models(data)
