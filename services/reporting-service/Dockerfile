# Etapa de compilación: instala las dependencias en el HOME del usuario ("pip install --user"), sin
# dejar la caché de pip ni las herramientas de compilación en la imagen final.
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Etapa final: solo el intérprete, las dependencias ya instaladas y el código de la aplicación.
FROM python:3.12-slim
# El proceso corre sin privilegios de administrador (RNF-02): un contenedor comprometido no debería
# poder escribir fuera de lo que este usuario ya puede tocar. Este servicio no tiene base de datos
# propia (agrega datos de fleet-core-service por HTTP), así que no hay migraciones que aplicar.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser
WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser app ./app
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER appuser

EXPOSE 8000

# El orquestador (docker compose, Cloud Run) usa esto para saber si el contenedor sirve tráfico; no
# depende de curl, que la imagen slim no trae.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

# Procesos de uvicorn por contenedor; la prueba de carga (12_RESULTADOS_OBTENIDOS/prueba_de_carga_tablero.md)
# mide 1, 2 y 4.
ENV UVICORN_WORKERS=2
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
