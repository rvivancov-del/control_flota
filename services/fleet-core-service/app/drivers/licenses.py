"""Tipos de licencia de conducir vigentes en Ecuador (RF-05).

Fuente: Agencia Nacional de Tránsito (ANT), guía oficial de trámites de licencias en
gob.ec (tipos profesionales A1, C, C1, D, E y G; no profesionales A y B) y el listado de
tipos de la ANT, que añade el tipo F (especial, vehículos adaptados para personas con
discapacidad). Los tipos históricos D1 y E1 se convirtieron en D y E por la Resolución
028-DE-ANT-2021 (título publicado por la ANT; no se pudo abrir el texto completo), así que
se aceptan como entrada y se guardan como D y E.

Para una flota de carga pesada el tipo relevante es E (camiones pesados y extrapesados de
más de 3,5 t, con o sin remolque, tráileres, volquetas y tanqueros).
"""
import re
from typing import Optional

LICENSE_TYPES: dict[str, str] = {
    "A": "No profesional: motocicletas, ciclomotores, tricar y cuadrones",
    "A1": "Profesional: motocicletas y similares de servicio comercial",
    "B": "No profesional: automóviles y camionetas",
    "C": "Profesional: taxis, camionetas de hasta 3,5 t y transporte de hasta 25 pasajeros",
    "C1": "Profesional: vehículos oficiales y de emergencia",
    "D": "Profesional: transporte de pasajeros de más de 25 asientos",
    "E": "Profesional: camiones pesados y extrapesados (más de 3,5 t), con o sin remolque",
    "F": "Especial: vehículos adaptados para personas con discapacidad",
    "G": "Profesional: maquinaria agrícola y de construcción",
}
# Tipos históricos convertidos por la Resolución 028-DE-ANT-2021.
_HISTORICAL = {"D1": "D", "E1": "E"}


def normalize_license_type(value: Optional[str]) -> Optional[str]:
    """Devuelve el código canónico ('Tipo E' -> 'E', 'e1' -> 'E'); None si viene vacío.
    Lanza ValueError si no es un tipo de licencia vigente."""
    if value is None:
        return None
    code = re.sub(r"^(TIPO|LICENCIA)\s+", "", value.strip().upper()).replace(" ", "")
    if not code:
        return None
    code = _HISTORICAL.get(code, code)
    if code not in LICENSE_TYPES:
        raise ValueError(f"license_type debe ser uno de: {', '.join(LICENSE_TYPES)}")
    return code
