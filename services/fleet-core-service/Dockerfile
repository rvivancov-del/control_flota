FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY migrations ./migrations

EXPOSE 8000

# Aplica migraciones pendientes antes de arrancar el servidor.
# Procesos de uvicorn por contenedor; la prueba de carga (12_RESULTADOS_OBTENIDOS/prueba_de_carga_tablero.md)
# mide 1, 2 y 4. Las migraciones y la siembra corren una sola vez, antes de arrancar los procesos.
ENV UVICORN_WORKERS=2
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
