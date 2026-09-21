"""Pruebas unitarias de las validaciones de dominio (RF-05, RF-09, RNF-11): sin base de datos."""
import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.drivers.licenses import LICENSE_TYPES, normalize_license_type
from app.drivers.schemas import DriverCreate, DriverUpdate
from app.expenses.schemas import ExpenseCreate, ExpenseUpdate
from app.models.driver import Driver
from app.models.expense import Expense
from app.models.vehicle import Vehicle
from app.trips.schemas import TRIP_STATUSES
from app.vehicles.schemas import VehicleCreate, VehicleUpdate

MIGRATION = Path(__file__).resolve().parent.parent / "migrations" / "versions" / "d5b1f7a3c9e2_validaciones_ubicacion_peaje_anonimizacion.py"


# ----------------------------------------------------------- tipo de licencia (RF-05)
@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("E", "E"), ("e", "E"), (" e ", "E"), ("Tipo E", "E"), ("tipo e", "E"), ("Licencia C1", "C1"),
        ("c1", "C1"), ("A1", "A1"), ("D1", "D"), ("E1", "E"), ("Tipo E1", "E"), ("", None), ("   ", None), (None, None),
    ],
)
def test_normaliza_el_tipo_de_licencia(entrada, esperado):
    assert normalize_license_type(entrada) == esperado


@pytest.mark.parametrize("entrada", ["X", "H", "AB", "Tipo Z", "E2", "1", "profesional"])
def test_rechaza_un_tipo_de_licencia_inexistente(entrada):
    with pytest.raises(ValueError, match="license_type debe ser uno de"):
        normalize_license_type(entrada)


def test_el_catalogo_incluye_el_tipo_de_carga_pesada():
    assert "camiones pesados" in LICENSE_TYPES["E"]
    assert set(LICENSE_TYPES) == {"A", "A1", "B", "C", "C1", "D", "E", "F", "G"}


def test_las_restricciones_de_la_migracion_coinciden_con_el_catalogo_y_los_modelos():
    spec = importlib.util.spec_from_file_location("migracion_d5b1", MIGRATION)
    migracion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracion)
    assert set(migracion.LICENSE_TYPES) == set(LICENSE_TYPES)

    def checks(model):
        return {c.name: str(c.sqltext) for c in model.__table__.constraints if c.name and c.name.startswith("ck_")}

    assert "ck_drivers_license_type" in checks(Driver) and "ck_drivers_status" in checks(Driver)
    assert "ck_vehicles_status" in checks(Vehicle)
    assert "ck_expenses_location_only_toll" in checks(Expense)
    for code in LICENSE_TYPES:
        assert f"'{code}'" in checks(Driver)["ck_drivers_license_type"]
    for estado in migracion.VEHICLE_STATUS:
        assert f"'{estado}'" in checks(Vehicle)["ck_vehicles_status"]


def test_alta_de_conductor_normaliza_y_valida():
    d = DriverCreate(full_name="  Ana Pérez ", license_number=" 0912345678 ", license_type="Tipo E")
    assert (d.full_name, d.license_number, d.license_type) == ("Ana Pérez", "0912345678", "E")
    assert DriverCreate(full_name="A", license_number="B").license_type is None
    with pytest.raises(ValidationError, match="license_type"):
        DriverCreate(full_name="Ana", license_number="1", license_type="Z")
    with pytest.raises(ValidationError, match="no puede estar vacío"):
        DriverCreate(full_name="   ", license_number="1")
    with pytest.raises(ValidationError, match="no puede estar vacío"):
        DriverCreate(full_name="Ana", license_number="")


def test_edicion_de_conductor_permite_rectificar_la_licencia_y_valida_el_estado():
    u = DriverUpdate(license_number=" 0999 ", license_type="e1", phone="0987")
    assert u.model_dump(exclude_unset=True) == {"license_number": "0999", "license_type": "E", "phone": "0987"}
    assert DriverUpdate(status="inactivo").status == "inactivo"
    with pytest.raises(ValidationError, match="status debe ser uno de"):
        DriverUpdate(status="baja")
    with pytest.raises(ValidationError, match="no puede estar vacío"):
        DriverUpdate(full_name="  ")


# ----------------------------------------------------------- estados y kilometraje de vehículos
def test_vehiculo_solo_acepta_estados_definidos():
    assert VehicleCreate(plate="AAA-123", brand="X", model="Y", year=2020).status == "activo"
    for estado in ("activo", "mantenimiento", "inactivo"):
        assert VehicleUpdate(status=estado).status == estado
    for cls, kwargs in ((VehicleCreate, dict(plate="A", brand="X", model="Y", year=2020)), (VehicleUpdate, {})):
        with pytest.raises(ValidationError, match="status debe ser uno de"):
            cls(status="vendido", **kwargs)


def test_el_kilometraje_del_vehiculo_no_puede_ser_negativo():
    with pytest.raises(ValidationError):
        VehicleCreate(plate="A", brand="X", model="Y", year=2020, current_mileage_km=-1)
    with pytest.raises(ValidationError):
        VehicleUpdate(current_mileage_km=-5)


def test_los_estados_de_viaje_son_los_del_ciclo_de_vida():
    assert TRIP_STATUSES == {"planificado", "en_curso", "completado", "anulado"}


# ----------------------------------------------------------- gastos y ubicación del peaje (RF-09)
BASE = dict(amount=Decimal("3.50"), expense_date="2026-09-21")


def test_un_peaje_exige_ubicacion():
    with pytest.raises(ValidationError, match="location es obligatoria"):
        ExpenseCreate(type="peaje", **BASE)
    with pytest.raises(ValidationError, match="location es obligatoria"):
        ExpenseCreate(type="peaje", location="   ", **BASE)


def test_un_peaje_con_ubicacion_la_conserva_recortada():
    e = ExpenseCreate(type="peaje", location="  Peaje Nueva Esperanza ", **BASE)
    assert e.location == "Peaje Nueva Esperanza"


@pytest.mark.parametrize("tipo", ["combustible", "alimentacion"])
def test_la_ubicacion_se_descarta_en_gastos_que_no_son_peaje(tipo):
    assert ExpenseCreate(type=tipo, location="Guayaquil", **BASE).location is None


def test_la_ubicacion_tiene_un_maximo_de_120_caracteres():
    with pytest.raises(ValidationError):
        ExpenseCreate(type="peaje", location="x" * 121, **BASE)


@pytest.mark.parametrize("monto", ["0", "-1", "-0.01"])
def test_el_monto_debe_ser_positivo(monto):
    with pytest.raises(ValidationError):
        ExpenseCreate(type="combustible", amount=Decimal(monto), expense_date="2026-09-21")
    with pytest.raises(ValidationError):
        ExpenseUpdate(amount=Decimal(monto))


def test_los_litros_deben_ser_positivos_si_se_informan():
    assert ExpenseCreate(type="combustible", liters=None, **BASE).liters is None
    with pytest.raises(ValidationError):
        ExpenseCreate(type="combustible", liters=Decimal("0"), **BASE)


def test_edicion_de_gasto_recorta_la_ubicacion():
    assert ExpenseUpdate(location=" Peaje Santa Lucía ").location == "Peaje Santa Lucía"
    assert ExpenseUpdate(location="  ").location is None
