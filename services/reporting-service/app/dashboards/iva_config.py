"""Tarifas de IVA por rubro de costo y modo de presentación 'bruto' / 'neto'.

Los montos se registran tal como se pagaron (con IVA): eso es el modo 'bruto', el predeterminado,
correcto cuando la empresa no recupera el IVA de sus compras (p. ej. el transporte de carga
vende con tarifa 0 %, Art. 56 LRTI, y por eso no genera crédito tributario). El modo 'neto' quita
el IVA para las empresas que sí lo recuperan.

Las tarifas viven en iva_config.json (o en la ruta de IVA_CONFIG_PATH), que declara su `estado` y su
`procedencia`, igual que ahp_config.json y maintenance_policy.json. Un archivo inválido detiene el arranque.
"""
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.dashboards.cost_model import ALL_ITEMS, VARIABLE_ITEMS

MODES = ("bruto", "neto")
_DEFAULT_PATH = Path(__file__).with_name("iva_config.json")


@dataclass(frozen=True)
class IvaConfig:
    version: str
    estado: str
    procedencia: str
    default_mode: str
    rates: dict[str, Decimal]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"iva_config inválida: {message}")


def load_config(path: str | os.PathLike | None = None) -> IvaConfig:
    source = Path(path or os.getenv("IVA_CONFIG_PATH") or _DEFAULT_PATH)
    raw = json.loads(source.read_text(encoding="utf-8"))
    for key in ("version", "estado", "procedencia"):
        _require(isinstance(raw.get(key), str) and raw[key].strip(), f"falta '{key}'")
    mode = raw.get("modo_por_defecto")
    _require(mode in MODES, f"modo_por_defecto debe ser uno de {MODES}, se recibió {mode!r}")
    rates_raw = raw.get("tarifas")
    _require(isinstance(rates_raw, dict), "tarifas debe ser un objeto")
    for item in rates_raw:
        _require(item in ALL_ITEMS, f"rubro desconocido en tarifas: {item}")
    for item in VARIABLE_ITEMS:
        _require(item in rates_raw, f"falta la tarifa del rubro '{item}'")
    rates: dict[str, Decimal] = {}
    for item, value in rates_raw.items():
        _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"tarifas.{item} debe ser un número")
        _require(0 <= value <= 0.25, f"tarifas.{item}={value} fuera de [0, 0.25]")
        rates[item] = Decimal(str(value))
    return IvaConfig(raw["version"], raw["estado"], raw["procedencia"], mode, rates)


CONFIG = load_config()
