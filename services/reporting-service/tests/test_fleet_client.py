"""Pruebas del cliente de fleet-core con un transporte simulado de httpx: un solo pool de
conexiones para todo el proceso, el token de cada usuario en cada llamada (nunca en el pool), reintentos
con espera creciente solo cuando tiene sentido reintentar, y errores del cliente que se propagan tal cual.
No requieren red ni el stack."""
import httpx
import pytest

from app.core import fleet_client
from app.core.fleet_client import FleetClient


class Servidor:
    """Transporte simulado: responde según una lista de respuestas o excepciones y guarda las peticiones."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.peticiones = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.peticiones.append(request)
        actual = self.respuestas.pop(0) if len(self.respuestas) > 1 else self.respuestas[0]
        if isinstance(actual, Exception):
            raise actual
        return httpx.Response(actual, json=[{"ok": True}] if actual < 400 else {"detail": "x"})


class Esperas(list):
    """Lista de las esperas pedidas entre reintentos; `instalar` pone un servidor simulado en el pool.
    Si el código reintentara sin fin, falla la prueba en vez de colgarla."""

    def instalar(self, *respuestas):
        raise NotImplementedError  # lo define el fixture, que conoce monkeypatch

    def registrar(self, segundos: float) -> None:
        self.append(segundos)
        if len(self) > 10:
            raise AssertionError("más reintentos de los permitidos: el máximo no se está respetando")


@pytest.fixture
def esperas(monkeypatch):
    """Sustituye el pool por un transporte simulado y registra las esperas entre reintentos sin dormir."""
    registradas = Esperas()
    monkeypatch.setattr(fleet_client, "_sleep", registradas.registrar)

    def instalar(*respuestas):
        servidor = Servidor(*respuestas)
        monkeypatch.setattr(
            fleet_client, "_client", httpx.Client(base_url="http://fleet", transport=httpx.MockTransport(servidor))
        )
        return servidor

    registradas.instalar = instalar
    return registradas


def test_una_respuesta_correcta_no_reintenta_ni_espera(esperas):
    servidor = esperas.instalar(200)
    assert FleetClient("t").list_vehicles() == [{"ok": True}]
    assert len(servidor.peticiones) == 1 and esperas == []


def test_el_token_de_cada_usuario_va_en_cada_llamada_y_el_pool_es_uno_solo(esperas):
    servidor = esperas.instalar(200)
    FleetClient("token-de-ana").list_vehicles()
    FleetClient("token-de-beto").list_drivers()
    assert [r.headers["authorization"] for r in servidor.peticiones] == ["Bearer token-de-ana", "Bearer token-de-beto"]
    assert fleet_client._http() is fleet_client._http()


def test_reintenta_un_503_con_espera_creciente_y_termina_bien(esperas):
    servidor = esperas.instalar(503, 503, 200)
    assert FleetClient("t").list_vehicles() == [{"ok": True}]
    assert len(servidor.peticiones) == 3
    assert esperas == [0.2, 0.4]


def test_si_el_503_persiste_lo_propaga_tras_los_reintentos(esperas):
    servidor = esperas.instalar(503)
    with pytest.raises(httpx.HTTPStatusError) as error:
        FleetClient("t").list_vehicles()
    assert error.value.response.status_code == 503  # el router lo reenvía como 503
    assert len(servidor.peticiones) == 1 + fleet_client.MAX_RETRIES
    assert esperas == [0.2, 0.4]


@pytest.mark.parametrize("codigo", [401, 403, 404, 422, 500])
def test_un_error_del_cliente_o_un_500_no_se_reintenta(esperas, codigo):
    servidor = esperas.instalar(codigo)
    with pytest.raises(httpx.HTTPStatusError) as error:
        FleetClient("t").list_vehicles()
    assert error.value.response.status_code == codigo
    assert len(servidor.peticiones) == 1 and esperas == []


def test_reintenta_una_conexion_rechazada_y_sigue_cuando_fleet_core_vuelve(esperas):
    servidor = esperas.instalar(httpx.ConnectError("rechazada"), httpx.ConnectError("rechazada"), 200)
    assert FleetClient("t").list_vehicles() == [{"ok": True}]
    assert len(servidor.peticiones) == 3 and esperas == [0.2, 0.4]


def test_si_fleet_core_no_vuelve_propaga_el_error_de_red(esperas):
    servidor = esperas.instalar(httpx.ConnectError("rechazada"))
    with pytest.raises(httpx.ConnectError):
        FleetClient("t").list_vehicles()
    assert len(servidor.peticiones) == 1 + fleet_client.MAX_RETRIES


def test_reintenta_una_conexion_que_el_servidor_ya_habia_cerrado(esperas):
    servidor = esperas.instalar(httpx.RemoteProtocolError("Server disconnected"), 200)
    assert FleetClient("t").list_vehicles() == [{"ok": True}]
    assert len(servidor.peticiones) == 2


def test_no_reintenta_un_tiempo_de_espera_de_lectura(esperas):
    """Reintentarlo duplicaría la espera del usuario (10 s + 10 s) y la carga sobre un servicio lento."""
    servidor = esperas.instalar(httpx.ReadTimeout("lento"))
    with pytest.raises(httpx.ReadTimeout):
        FleetClient("t").list_vehicles()
    assert len(servidor.peticiones) == 1 and esperas == []


def test_los_mantenimientos_de_toda_la_flota_son_una_sola_peticion_sin_parametros(esperas):
    servidor = esperas.instalar(200)
    FleetClient("t").list_maintenance_records()
    assert len(servidor.peticiones) == 1
    assert servidor.peticiones[0].url.path == "/maintenance" and servidor.peticiones[0].url.query == b""


def test_los_filtros_de_mantenimiento_viajan_como_parametros(esperas):
    servidor = esperas.instalar(200)
    FleetClient("t").list_maintenance_records("veh-1", "pendiente")
    assert dict(servidor.peticiones[0].url.params) == {"vehicle_id": "veh-1", "status_filter": "pendiente"}


def test_cerrar_el_pool_lo_libera_y_el_siguiente_uso_crea_otro(monkeypatch):
    monkeypatch.setattr(fleet_client, "_client", None)
    primero = fleet_client._http()
    fleet_client.close()
    assert fleet_client._client is None and primero.is_closed
    segundo = fleet_client._http()
    assert segundo is not primero
    fleet_client.close()


def test_los_tiempos_de_espera_son_finitos():
    """Un fleet-core colgado no debe dejar colgado también a reporting-service."""
    assert 0 < fleet_client.CONNECT_TIMEOUT_S <= 5 and 0 < fleet_client.READ_TIMEOUT_S <= 30
