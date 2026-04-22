from flask import Flask, render_template, request, jsonify
import json
import os
import threading

from valorar_coche import (
    scrape_valoracion, buscar_ids_en_diccionario, resolver_provincias, cargar_provincias
)
from scraper.buscador import buscar_multi, FUENTES_DISPONIBLES

app = Flask(__name__)
DICCIONARIO_JSON = os.path.join("data", "diccionario_coches_net.json")

tarea = {"activa": False, "resultado": None, "error": None, "progreso": ""}

DB_OK = False
try:
    from db import init_db, guardar_busqueda, historial_busquedas, evolucion_precios, precios_por_anio_modelo, vehiculos_busqueda, PG_DISPONIBLE
    if PG_DISPONIBLE:
        DB_OK = init_db()
        if DB_OK:
            print("PostgreSQL conectado correctamente.")
        else:
            print("PostgreSQL no disponible. Funcionando sin base de datos.")
except Exception as e:
    print(f"PostgreSQL no disponible ({e}). Funcionando sin base de datos.")


def cargar_catalogo():
    if not os.path.exists(DICCIONARIO_JSON):
        return {}
    with open(DICCIONARIO_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/marcas")
def api_marcas():
    catalogo = cargar_catalogo()
    marcas = sorted([
        {"nombre": k, "make_id": v["make_id"]}
        for k, v in catalogo.items()
    ], key=lambda x: x["nombre"])
    return jsonify(marcas)


@app.route("/api/modelos/<make_id>")
def api_modelos(make_id):
    catalogo = cargar_catalogo()
    for nombre, datos in catalogo.items():
        if datos["make_id"] == make_id:
            modelos = sorted([
                {"nombre": k, "model_id": v}
                for k, v in datos.get("modelos", {}).items()
            ], key=lambda x: x["nombre"])
            return jsonify(modelos)
    return jsonify([])


UBICACIONES_JSON = os.path.join("data", "ubicaciones_coches_net.json")

def cargar_ubicaciones_json():
    if not os.path.exists(UBICACIONES_JSON):
        return None
    with open(UBICACIONES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/api/provincias")
def api_provincias():
    datos = cargar_ubicaciones_json()
    if not datos:
        return jsonify([])
    resultado = []
    for comunidad, info in datos.get("comunidades", {}).items():
        provs = info.get("provincias", {})
        ids_comunidad = "|".join(str(v) for v in provs.values())
        resultado.append({
            "nombre": comunidad,
            "id": ids_comunidad,
            "es_comunidad": True,
            "provincias": [
                {"nombre": n, "id": v} for n, v in provs.items()
            ]
        })
    resultado.sort(key=lambda x: x["nombre"])
    return jsonify(resultado)


@app.route("/api/fuentes")
def api_fuentes():
    return jsonify(FUENTES_DISPONIBLES)


# ────────── BÚSQUEDA MULTI-FUENTE ──────────

@app.route("/api/buscar", methods=["POST"])
def api_buscar():
    global tarea
    if tarea["activa"]:
        return jsonify({"error": "Ya hay una búsqueda en curso."}), 409

    data = request.json
    marca = data.get("marca", "")
    modelo = data.get("modelo", "")
    fuentes = data.get("fuentes", FUENTES_DISPONIBLES)
    anio_min = int(data["anio_min"]) if data.get("anio_min") else None
    anio_max = int(data["anio_max"]) if data.get("anio_max") else None
    km_min = int(data["km_min"]) if data.get("km_min") else None
    km_max = int(data["km_max"]) if data.get("km_max") else None
    combustible = data.get("combustible", "")
    transmision = data.get("transmision", "")
    provincias = data.get("provincias")
    solo_canarias = data.get("solo_canarias", False)
    make_id = data.get("make_id")
    model_id = data.get("model_id")

    tarea = {"activa": True, "resultado": None, "error": None, "progreso": "Iniciando búsqueda multi-fuente..."}

    def ejecutar():
        global tarea
        try:
            def on_progreso(msg):
                tarea["progreso"] = msg

            resultado = buscar_multi(
                marca=marca, modelo=modelo, fuentes=fuentes,
                km_max=km_max, km_min=km_min,
                anio_min=anio_min, anio_max=anio_max,
                combustible=combustible, transmision=transmision,
                provincias=provincias, solo_canarias=solo_canarias,
                max_paginas=20, on_progreso=on_progreso,
            )

            if DB_OK and resultado.get("todos"):
                try:
                    bid = guardar_busqueda(
                        {"marca": marca, "modelo": modelo, "anio_min": anio_min,
                         "anio_max": anio_max, "km_min": km_min, "km_max": km_max,
                         "combustible": combustible, "transmision": transmision,
                         "fuentes": fuentes},
                        resultado["todos"],
                        resultado.get("estudio_mercado", {}),
                    )
                    resultado["busqueda_id"] = bid
                except Exception as e:
                    resultado["db_error"] = str(e)

            tarea["resultado"] = resultado
            tarea["progreso"] = "Completado"
        except Exception as e:
            tarea["error"] = str(e)
            tarea["progreso"] = "Error"
        finally:
            tarea["activa"] = False

    threading.Thread(target=ejecutar, daemon=True).start()
    return jsonify({"ok": True, "mensaje": "Búsqueda iniciada"})


# ────────── BÚSQUEDA SOLO COCHES.NET (legacy) ──────────

@app.route("/api/valorar", methods=["POST"])
def api_valorar():
    global tarea
    if tarea["activa"]:
        return jsonify({"error": "Ya hay una valoración en curso."}), 409

    data = request.json
    marca = data.get("marca", "")
    modelo = data.get("modelo", "")
    make_id = data.get("make_id")
    model_id = data.get("model_id")
    anio_min = int(data["anio_min"]) if data.get("anio_min") else None
    anio_max = int(data["anio_max"]) if data.get("anio_max") else None
    km_min = int(data["km_min"]) if data.get("km_min") else None
    km_max = int(data["km_max"]) if data.get("km_max") else None
    provincias = data.get("provincias")

    tarea = {"activa": True, "resultado": None, "error": None, "progreso": "Iniciando..."}

    def ejecutar():
        global tarea
        try:
            def actualizar_progreso(msg):
                tarea["progreso"] = msg

            resultado = scrape_valoracion(
                marca=marca, modelo=modelo,
                anio_min=anio_min, anio_max=anio_max,
                km_min=km_min, km_max=km_max,
                make_id=make_id, model_id=model_id,
                provincias=provincias,
                on_progreso=actualizar_progreso,
            )
            if resultado:
                del resultado["detalle_coches"]
                tarea["resultado"] = resultado
                tarea["progreso"] = "Completado"
            else:
                tarea["error"] = "No se pudieron obtener resultados."
                tarea["progreso"] = "Error"
        except Exception as e:
            tarea["error"] = str(e)
            tarea["progreso"] = "Error"
        finally:
            tarea["activa"] = False

    threading.Thread(target=ejecutar, daemon=True).start()
    return jsonify({"ok": True, "mensaje": "Valoración iniciada"})


@app.route("/api/estado")
def api_estado():
    return jsonify({
        "activa": tarea["activa"],
        "progreso": tarea["progreso"],
        "resultado": tarea["resultado"],
        "error": tarea["error"],
    })


# ────────── HISTORIAL Y ANÁLISIS ──────────

@app.route("/api/historial")
def api_historial():
    if not DB_OK:
        return jsonify({"error": "Base de datos no disponible"}), 503
    marca = request.args.get("marca")
    modelo = request.args.get("modelo")
    return jsonify(historial_busquedas(marca, modelo))


@app.route("/api/evolucion")
def api_evolucion():
    if not DB_OK:
        return jsonify({"error": "Base de datos no disponible"}), 503
    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    if not marca or not modelo:
        return jsonify({"error": "marca y modelo requeridos"}), 400
    return jsonify(evolucion_precios(marca, modelo))


@app.route("/api/precios_anio")
def api_precios_anio():
    if not DB_OK:
        return jsonify({"error": "Base de datos no disponible"}), 503
    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    if not marca or not modelo:
        return jsonify({"error": "marca y modelo requeridos"}), 400
    return jsonify(precios_por_anio_modelo(marca, modelo))


@app.route("/api/db_status")
def api_db_status():
    return jsonify({"disponible": DB_OK})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
