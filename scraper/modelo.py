"""Modelo unificado de vehículo para todas las fuentes."""
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime


@dataclass
class Vehiculo:
    fuente: str
    marca: str
    modelo: str
    version: str = ""
    precio: Optional[int] = None
    precio_financiado: Optional[int] = None
    cuota_mensual: Optional[int] = None
    anio: Optional[int] = None
    km: Optional[int] = None
    combustible: str = ""
    transmision: str = ""
    cv: Optional[int] = None
    provincia: str = ""
    vendedor: str = ""
    url: str = ""
    url_imagen: str = ""
    reservado: bool = False
    fecha_scraping: str = ""

    def __post_init__(self):
        if not self.fecha_scraping:
            self.fecha_scraping = datetime.now().isoformat()
        self.marca = self.marca.strip().upper()
        self.modelo = self.modelo.strip().upper()
        self.combustible = _normalizar_combustible(self.combustible)
        self.transmision = _normalizar_transmision(self.transmision)

    def to_dict(self):
        return asdict(self)


def _normalizar_combustible(raw: str) -> str:
    r = raw.lower().strip()
    if not r:
        return ""
    if "diesel" in r or "diésel" in r:
        return "Diésel"
    if "gasolina" in r:
        return "Gasolina"
    if "eléctrico" in r or "electrico" in r or "electric" in r:
        return "Eléctrico"
    if "híbrido" in r or "hibrido" in r or "hybrid" in r:
        if "enchuf" in r or "plug" in r:
            return "Híbrido enchufable"
        return "Híbrido"
    if "glp" in r:
        return "GLP"
    if "gnc" in r:
        return "GNC"
    return raw.strip()


def _normalizar_transmision(raw: str) -> str:
    r = raw.lower().strip()
    if not r:
        return ""
    if "autom" in r:
        return "Automático"
    if "manual" in r:
        return "Manual"
    return raw.strip()
