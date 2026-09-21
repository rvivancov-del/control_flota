"""Pruebas de la configuración externa del AHP (ahp_config.json): la carga
debe ser estricta, porque un juicio mal escrito no puede pasar en silencio."""
import copy
import json
from pathlib import Path

import pytest

from app.dashboards import ahp

DEFAULT_PATH = Path(ahp.__file__).with_name("ahp_config.json")


def _base() -> dict:
    return json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))


def _write(tmp_path, data: dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_la_configuracion_entregada_carga_y_declara_su_procedencia():
    cfg = ahp.load_config()
    assert cfg.version and cfg.estado and cfg.procedencia
    assert set(ahp.CRITERIA) == {"seguridad", "urgencia", "costo"}
    assert "otro" in cfg.criticidad_seguridad and "otro" in cfg.costo.respaldo_usd


def test_la_matriz_se_arma_reciproca_desde_las_tres_comparaciones():
    m = ahp.load_config().matrix
    for i in range(3):
        assert m[i][i] == 1.0
        for j in range(3):
            assert m[i][j] * m[j][i] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "mutate, mensaje",
    [
        (lambda d: d["comparaciones_saaty"].update(seguridad_vs_urgencia=9, seguridad_vs_costo=1 / 9, urgencia_vs_costo=1),
         "inconsistente"),
        (lambda d: d["comparaciones_saaty"].update(seguridad_vs_urgencia=10), "fuera de"),
        (lambda d: d["comparaciones_saaty"].pop("urgencia_vs_costo"), "numérico"),
        (lambda d: d["criticidad_seguridad"].pop("otro"), "otro"),
        (lambda d: d["criticidad_seguridad"].update(frenos=1.5), "fuera de"),
        (lambda d: d["costo"].update(direccion="cualquiera"), "direccion"),
        (lambda d: d["costo"]["respaldo_usd"].pop("otro"), "otro"),
        (lambda d: d["urgencia"].update(sin_urgencia_multiplo=1.0), "fuera de"),
        (lambda d: d["urgencia"].pop("sin_urgencia_multiplo"), "numérico"),
        (lambda d: d["urgencia"].update(puntaje_en_proximo=1.5), "fuera de"),
        (lambda d: d.update(criterios=["seguridad", "costo", "urgencia"]), "criterios"),
        (lambda d: d.update(estado=""), "estado"),
    ],
)
def test_una_configuracion_invalida_detiene_la_carga(tmp_path, mutate, mensaje):
    data = copy.deepcopy(_base())
    mutate(data)
    with pytest.raises(ValueError, match=mensaje):
        ahp.load_config(_write(tmp_path, data))


def test_la_variable_de_entorno_reemplaza_el_archivo_por_defecto(tmp_path, monkeypatch):
    data = _base()
    data["estado"] = "expertos_n=3"
    data["comparaciones_saaty"].update(seguridad_vs_urgencia=5, seguridad_vs_costo=7, urgencia_vs_costo=3)
    monkeypatch.setenv("AHP_CONFIG_PATH", str(_write(tmp_path, data)))
    cfg = ahp.load_config()
    assert cfg.estado == "expertos_n=3"
    pesos = ahp.compute_ahp_weights(cfg.matrix)
    assert pesos.seguridad > ahp.compute_ahp_weights().seguridad  # más peso a seguridad que la provisional
