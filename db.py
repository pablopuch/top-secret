"""Capa de base de datos PostgreSQL para el estudio de mercado."""
import os
import json
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
    PG_DISPONIBLE = True
except ImportError:
    PG_DISPONIBLE = False

DB_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": int(os.environ.get("PG_PORT", 5432)),
    "dbname": os.environ.get("PG_DB", "coches_mercado"),
    "user": os.environ.get("PG_USER", "postgres"),
    "password": os.environ.get("PG_PASSWORD", "postgres"),
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vehiculos (
    id SERIAL PRIMARY KEY,
    fuente VARCHAR(50) NOT NULL,
    marca VARCHAR(100) NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    version VARCHAR(200) DEFAULT '',
    precio INTEGER,
    precio_financiado INTEGER,
    cuota_mensual INTEGER,
    anio INTEGER,
    km INTEGER,
    combustible VARCHAR(50) DEFAULT '',
    transmision VARCHAR(50) DEFAULT '',
    cv INTEGER,
    provincia VARCHAR(100) DEFAULT '',
    vendedor VARCHAR(200) DEFAULT '',
    url TEXT DEFAULT '',
    url_imagen TEXT DEFAULT '',
    reservado BOOLEAN DEFAULT FALSE,
    fecha_scraping TIMESTAMP NOT NULL DEFAULT NOW(),
    busqueda_id INTEGER REFERENCES busquedas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS busquedas (
    id SERIAL PRIMARY KEY,
    marca VARCHAR(100) NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    anio_min INTEGER,
    anio_max INTEGER,
    km_min INTEGER,
    km_max INTEGER,
    combustible VARCHAR(50),
    transmision VARCHAR(50),
    fuentes TEXT,
    total_resultados INTEGER DEFAULT 0,
    precio_medio INTEGER,
    precio_mediana INTEGER,
    fecha TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vehiculos_marca_modelo ON vehiculos(marca, modelo);
CREATE INDEX IF NOT EXISTS idx_vehiculos_fuente ON vehiculos(fuente);
CREATE INDEX IF NOT EXISTS idx_vehiculos_anio ON vehiculos(anio);
CREATE INDEX IF NOT EXISTS idx_vehiculos_busqueda ON vehiculos(busqueda_id);
CREATE INDEX IF NOT EXISTS idx_busquedas_fecha ON busquedas(fecha);
"""


def get_conn():
    if not PG_DISPONIBLE:
        raise RuntimeError("psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    return psycopg2.connect(**DB_CONFIG)


def _pg_accesible():
    """Comprueba si el puerto de PostgreSQL está abierto."""
    import socket
    try:
        s = socket.create_connection((DB_CONFIG["host"], DB_CONFIG["port"]), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def init_db():
    """Crea la base de datos si no existe y ejecuta el schema."""
    if not PG_DISPONIBLE:
        return False

    if not _pg_accesible():
        print(f"PostgreSQL no accesible en {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        return False

    try:
        conn = psycopg2.connect(
            host=DB_CONFIG["host"], port=DB_CONFIG["port"],
            user=DB_CONFIG["user"], password=DB_CONFIG["password"],
            dbname="postgres"
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_CONFIG["dbname"],))
        if not cur.fetchone():
            cur.execute(f"CREATE DATABASE {DB_CONFIG['dbname']}")
            print(f"Base de datos '{DB_CONFIG['dbname']}' creada.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error creando BD: {e}")
        return False

    try:
        conn = get_conn()
        cur = conn.cursor()
        # busquedas primero (vehiculos referencia busquedas)
        for stmt in SCHEMA_SQL.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except Exception:
                    pass
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error inicializando schema: {e}")
        return False


def guardar_busqueda(params: dict, vehiculos: list[dict], stats: dict) -> int:
    """Guarda una búsqueda y sus vehículos. Retorna el ID de búsqueda."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO busquedas (marca, modelo, anio_min, anio_max, km_min, km_max,
                               combustible, transmision, fuentes, total_resultados,
                               precio_medio, precio_mediana)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        params.get("marca", ""), params.get("modelo", ""),
        params.get("anio_min"), params.get("anio_max"),
        params.get("km_min"), params.get("km_max"),
        params.get("combustible", ""), params.get("transmision", ""),
        ",".join(params.get("fuentes", [])),
        len(vehiculos),
        stats.get("precio_medio_global"),
        stats.get("precio_mediana_global"),
    ))
    busqueda_id = cur.fetchone()[0]

    if vehiculos:
        values = []
        for v in vehiculos:
            values.append((
                v.get("fuente", ""), v.get("marca", ""), v.get("modelo", ""),
                v.get("version", ""), v.get("precio"), v.get("precio_financiado"),
                v.get("cuota_mensual"), v.get("anio"), v.get("km"),
                v.get("combustible", ""), v.get("transmision", ""),
                v.get("cv"), v.get("provincia", ""), v.get("vendedor", ""),
                v.get("url", ""), v.get("url_imagen", ""),
                v.get("reservado", False),
                v.get("fecha_scraping", datetime.now().isoformat()),
                busqueda_id,
            ))
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO vehiculos (fuente, marca, modelo, version, precio, precio_financiado,
                                   cuota_mensual, anio, km, combustible, transmision, cv,
                                   provincia, vendedor, url, url_imagen, reservado,
                                   fecha_scraping, busqueda_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, values, page_size=500)

    conn.commit()
    cur.close()
    conn.close()
    return busqueda_id


def historial_busquedas(marca: str = None, modelo: str = None, limit: int = 50) -> list:
    """Devuelve el historial de búsquedas, opcionalmente filtrado."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    sql = "SELECT * FROM busquedas"
    params = []
    where = []
    if marca:
        where.append("UPPER(marca) = UPPER(%s)")
        params.append(marca)
    if modelo:
        where.append("UPPER(modelo) = UPPER(%s)")
        params.append(modelo)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY fecha DESC LIMIT %s"
    params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def evolucion_precios(marca: str, modelo: str) -> list:
    """Devuelve la evolución de precios medios por fecha de búsqueda."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT fecha::date as fecha, precio_medio, precio_mediana, total_resultados
        FROM busquedas
        WHERE UPPER(marca) = UPPER(%s) AND UPPER(modelo) = UPPER(%s)
        ORDER BY fecha
    """, (marca, modelo))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def precios_por_anio_modelo(marca: str, modelo: str) -> list:
    """Devuelve precio medio por año de matriculación (todas las búsquedas acumuladas)."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT anio,
               COUNT(*) as cantidad,
               ROUND(AVG(precio)) as precio_medio,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio)::int as precio_mediana,
               MIN(precio) as precio_min,
               MAX(precio) as precio_max
        FROM vehiculos
        WHERE UPPER(marca) = UPPER(%s) AND UPPER(modelo) = UPPER(%s)
          AND precio IS NOT NULL AND precio > 0 AND anio IS NOT NULL
        GROUP BY anio
        ORDER BY anio
    """, (marca, modelo))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def vehiculos_busqueda(busqueda_id: int) -> list:
    """Devuelve los vehículos de una búsqueda específica."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM vehiculos WHERE busqueda_id = %s ORDER BY precio ASC NULLS LAST
    """, (busqueda_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]
