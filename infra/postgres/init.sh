#!/bin/sh
# Se ejecuta una sola vez, cuando PostgreSQL arranca por primera vez con un volumen vacío
# (/docker-entrypoint-initdb.d). Crea un rol por servicio y los esquemas auth y fleet con sus permisos:
# ver roles.sql. Las contraseñas de los roles llegan por variables de entorno del contenedor.
set -e

: "${AUTH_DB_PASSWORD:?Falta AUTH_DB_PASSWORD}"
: "${FLEET_DB_PASSWORD:?Falta FLEET_DB_PASSWORD}"

# El comando \set de psql las recibe entre comillas simples: una contraseña con comilla simple o salto de línea lo rompería.
for valor in "$AUTH_DB_PASSWORD" "$FLEET_DB_PASSWORD"; do
  case "$valor" in
    *"'"*|*"
"*) echo "Las contraseñas de los roles no pueden llevar comillas simples ni saltos de línea." >&2; exit 1 ;;
  esac
done

# Las contraseñas se pasan por la entrada estándar, no como argumentos: así no quedan en la lista de procesos.
{
  printf "\\\\set auth_password '%s'\n" "$AUTH_DB_PASSWORD"
  printf "\\\\set fleet_password '%s'\n" "$FLEET_DB_PASSWORD"
  cat /opt/flota/roles.sql
} | psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"
