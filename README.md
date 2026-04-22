# Estudio de Mercado de Coches de Ocasión

Herramienta de scraping multi-fuente para analizar precios de coches de segunda mano en España, con foco especial en Canarias (IGIC vs IVA).

Extrae datos en tiempo real de **4 plataformas** y los unifica en una interfaz web con estadísticas, gráficos y filtros avanzados.

## Fuentes de datos

| Fuente | Método | Filtros servidor | Cobertura |
|---|---|---|---|
| **coches.net** | Playwright + stealth | Marca, modelo, provincia, combustible, transmisión, km, año | Nacional |
| **Flexicar** | API REST | Provincia | Nacional (188 concesionarios) |
| **OcasionPlus** | API REST | Marca, provincia, market, combustible, transmisión | Nacional |
| **Domingo Alonso** | Playwright + AJAX intercept | Isla (URL) | Solo Canarias |

## Estructura del proyecto

```
├── app.py                  # Backend Flask (API + servidor web)
├── valorar_coche.py        # Scraper core de coches.net (Playwright)
├── db.py                   # Capa PostgreSQL (opcional)
├── requirements.txt
│
├── data/                   # Bases de conocimiento (JSON)
│   ├── diccionario_coches_net.json      # Marcas/modelos con IDs
│   ├── ubicaciones_coches_net.json      # Provincias con IDs
│   ├── filtros_coches_net.json          # Documentación params URL
│   ├── diccionario_flexicar.json        # Catálogo completo
│   ├── diccionario_ocasionplus.json     # Catálogo completo
│   └── diccionario_domingo_alonso.json  # Catálogo completo
│
├── scraper/
│   ├── modelo.py               # Dataclass Vehiculo (modelo unificado)
│   ├── buscador.py             # Orquestador multi-fuente
│   ├── adapter_coches_net.py   # Adaptador coches.net
│   ├── adapter_flexicar.py     # Adaptador Flexicar
│   ├── adapter_ocasionplus.py  # Adaptador OcasionPlus
│   └── adapter_domingo_alonso.py  # Adaptador Domingo Alonso
│
└── templates/
    └── index.html              # Frontend (HTML/JS/Chart.js)
```

## Requisitos

- **Python 3.11+**
- **Chromium** (se instala automáticamente con Playwright)
- **PostgreSQL 14+** (opcional, para persistencia histórica)

## Instalación

```bash
# 1. Clonar e instalar dependencias
cd top-secret
pip install -r requirements.txt

# 2. Instalar navegador para Playwright
playwright install chromium

# 3. (Opcional) Configurar PostgreSQL
#    Variables de entorno o valores por defecto:
#    PG_HOST=localhost  PG_PORT=5432  PG_DB=coches_mercado
#    PG_USER=postgres   PG_PASSWORD=postgres
```

## Ejecución

```bash
python app.py
```

Abre **http://localhost:5000** en el navegador.

## Uso

1. Selecciona **marca y modelo** (catálogo de coches.net)
2. Activa las **fuentes** que quieras consultar
3. Aplica filtros: año, km, combustible, transmisión, provincia
4. Marca **"Solo Canarias (IGIC)"** para buscar solo en las islas
5. Pulsa **Buscar** — el scraping se ejecuta en paralelo
6. Revisa los resultados: estadísticas, gráficos por año, comparación entre fuentes

## API Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/marcas` | Lista de marcas (coches.net) |
| GET | `/api/modelos/<make_id>` | Modelos de una marca |
| GET | `/api/provincias` | Provincias agrupadas por CCAA |
| GET | `/api/fuentes` | Fuentes de datos disponibles |
| POST | `/api/buscar` | Búsqueda multi-fuente |
| GET | `/api/estado` | Estado de la búsqueda en curso |
| GET | `/api/historial` | Historial de búsquedas (requiere DB) |
| GET | `/api/evolucion?marca=X&modelo=Y` | Evolución de precios (requiere DB) |
| GET | `/api/precios_anio?marca=X&modelo=Y` | Precios desglosados por año (requiere DB) |

### Ejemplo POST `/api/buscar`

```json
{
  "marca": "Fiat",
  "modelo": "500",
  "fuentes": ["coches.net", "flexicar", "ocasionplus", "domingo_alonso"],
  "anio_min": 2018,
  "anio_max": 2023,
  "km_max": 100000,
  "combustible": "gasolina",
  "transmision": "automatico",
  "solo_canarias": true
}
```

## Bases de conocimiento

Los archivos en `data/` contienen los catálogos de cada fuente extraídos por scraping. Incluyen:

- **Marcas y modelos** con IDs internos de cada plataforma
- **Provincias/ubicaciones** con los valores exactos que acepta cada API
- **Combustibles y transmisiones** con los formatos correctos (ej: OcasionPlus requiere `Diésel` con acento)
- **Documentación de filtros** que funcionan a nivel servidor vs filtrado local

## Consideraciones

- **Anti-bot**: coches.net y Domingo Alonso usan detección de bots. El scraper incluye `playwright-stealth`, comportamiento humano simulado y manejo de CAPTCHA.
- **Rate limiting**: Flexicar y OcasionPlus son APIs públicas sin autenticación. Se usa un delay de 100ms entre peticiones.
- **IGIC/IVA**: Los resultados indican el régimen fiscal basándose en la ubicación del concesionario (Canarias = IGIC, Península = IVA).
- **PostgreSQL opcional**: Sin base de datos la app funciona normalmente, solo no persiste el historial de búsquedas.
