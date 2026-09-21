"""Pruebas unitarias de la política de alertas de mantenimiento (RF-13):
no requieren el stack levantado ni la base de datos."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.maintenance import policy
from app.maintenance.policy import MaintenancePolicy

BASE = MaintenancePolicy(version="t", estado="prueba", procedencia="prueba", proximo_km=1500)
DEFAULT_PATH = Path(policy.__file__).with_name("maintenance_policy.json")


@pytest.mark.parametrize(
    "remaining, esperado",
    [(None, "normal"), (-100, "vencido"), (0, "vencido"), (1, "proximo"), (1500, "proximo"), (1501, "normal")],
)
def test_clasificacion_en_los_limites(remaining, esperado):
    assert policy.classify(remaining, "frenos", BASE) == esperado


def test_un_tipo_con_umbral_propio_usa_ese_umbral():
    pol = MaintenancePolicy("t", "prueba", "prueba", proximo_km=1500, proximo_km_por_tipo={"frenos": 3000})
    assert policy.classify(2500, "frenos", pol) == "proximo"
    assert policy.classify(2500, "aceite", pol) == "normal"
    assert policy.threshold_for("frenos", pol) == 3000 and policy.threshold_for("aceite", pol) == 1500


def test_km_restantes():
    assert policy.km_remaining(50_000, 48_800) == 1200
    assert policy.km_remaining(50_000, 51_000) == -1000
    assert policy.km_remaining(None, 48_800) is None


def _registro(status, scheduled, mtype="frenos"):
    return SimpleNamespace(status=status, scheduled_mileage_km=scheduled, maintenance_type=mtype)


def test_assess_de_un_pendiente_programado():
    assert policy.assess(_registro("pendiente", 50_000), 48_800, BASE) == (1200, "proximo")
    assert policy.assess(_registro("pendiente", 50_000), 50_000, BASE) == (0, "vencido")
    assert policy.assess(_registro("pendiente", 60_000), 48_800, BASE) == (11_200, "normal")


def test_assess_de_un_pendiente_sin_kilometraje_programado_es_normal():
    assert policy.assess(_registro("pendiente", None), 48_800, BASE) == (None, "normal")


def test_un_mantenimiento_completado_no_tiene_urgencia():
    assert policy.assess(_registro("completado", 40_000), 48_800, BASE) == (None, None)


def test_la_politica_entregada_carga_y_declara_su_procedencia():
    pol = policy.load_policy()
    assert pol.version and pol.estado and pol.procedencia and pol.proximo_km > 0


def _write(tmp_path, data):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "mutate, mensaje",
    [
        (lambda d: d.update(proximo_km=0), "fuera de"),
        (lambda d: d.update(proximo_km=-5), "fuera de"),
        (lambda d: d.update(proximo_km="1500"), "entero"),
        (lambda d: d.update(proximo_km=1500.5), "entero"),
        (lambda d: d.pop("proximo_km"), "entero"),
        (lambda d: d.update(estado=""), "estado"),
        (lambda d: d.pop("procedencia"), "procedencia"),
        (lambda d: d.update(proximo_km_por_tipo={"radiador": 2000}), "desconocido"),
        (lambda d: d.update(proximo_km_por_tipo={"frenos": 0}), "fuera de"),
        (lambda d: d.update(proximo_km_por_tipo=[1, 2]), "objeto"),
    ],
)
def test_una_politica_invalida_detiene_la_carga(tmp_path, mutate, mensaje):
    data = copy.deepcopy(json.loads(DEFAULT_PATH.read_text(encoding="utf-8")))
    mutate(data)
    with pytest.raises(ValueError, match=mensaje):
        policy.load_policy(_write(tmp_path, data))


def test_la_variable_de_entorno_reemplaza_la_politica(tmp_path, monkeypatch):
    data = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    data.update(estado="expertos_n=3", proximo_km=2000, proximo_km_por_tipo={"frenos": 3000})
    monkeypatch.setenv("MAINTENANCE_POLICY_PATH", str(_write(tmp_path, data)))
    pol = policy.load_policy()
    assert pol.estado == "expertos_n=3" and pol.proximo_km == 2000 and pol.proximo_km_por_tipo == {"frenos": 3000}
