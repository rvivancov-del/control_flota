# Prueba de carga del tablero

Comprueba RNF-01 (consultas en menos de 2 s con hasta 10 usuarios concurrentes) con
[k6](https://k6.io). `dashboard.js` simula usuarios administradores que abren el tablero: cada uno
dispara en paralelo las 13 consultas que hace el navegador, espera 5 s y repite (ver la cabecera del
script). Falla si el p95 de alguna consulta, o el de la carga completa, pasa de 2 s, o si más de 1 %
de las peticiones falla.

**Córrala contra la pila de verificación, no contra la base de trabajo**: solo lee datos, pero el
inicio de sesión y la carga la ensucian con registros de acceso y ocupan la pila viva.

```bash
# pila de verificación con la base piloto (ver scripts/README.md)
python scripts/make_verif_nginx.py
docker compose -p flota_verif -f docker-compose.yml -f infra/docker-compose.verif.yml up -d
docker compose -p flota_verif exec -T postgres psql -U flota -d flota_db -v ON_ERROR_STOP=1 -q < scripts/seed/pilot_dataset.sql
docker compose -p flota_verif -f docker-compose.yml -f infra/docker-compose.verif.yml restart gateway
python scripts/seed_costos_ejemplo.py --project flota_verif --db flota_db     # costos fijos y de personal de ejemplo

# k6 en un contenedor; en Git Bash de Windows anteponga MSYS_NO_PATHCONV=1
docker run --rm -e BASE_URL=http://host.docker.internal:18080/api \
  -v "$PWD/scripts/loadtest:/scripts" -v "$PWD/salida:/out" \
  grafana/k6 run --summary-export=/out/k6.json /scripts/dashboard.js
```

Variables (`-e`): `BASE_URL`, `LOAD_USER` y `LOAD_PASSWORD` (por defecto el administrador de desarrollo),
`VUS` (10), `DURATION` (60s), `THINK_SECONDS` (5), `DATE_FROM` y `DATE_TO` (por defecto, el mes en curso).

Para comparar configuraciones (p. ej. el número de procesos por servicio, `UVICORN_WORKERS`), guarde
un resumen por corrida con `--summary-export` en `12_RESULTADOS_OBTENIDOS/prueba_de_carga/` con los
nombres que espera `informe.py` y regenere el informe:

```bash
python scripts/loadtest/informe.py     # escribe 12_RESULTADOS_OBTENIDOS/prueba_de_carga_tablero.md
```

Las cifras del informe salen de esos archivos; no se escriben a mano.
