-- Aislamiento de los esquemas por servicio.
--
-- Si los tres servicios se conectaran con el mismo usuario (el superusuario de la instancia), la separación
-- entre esquemas sería solo una convención: cualquier servicio podría leer y escribir las tablas de otro.
-- Por eso cada servicio que usa la base de datos tiene su propio rol, dueño de su esquema y sin
-- ningún permiso sobre el del otro:
--
--     auth-service        ->  flota_auth   ->  esquema auth
--     fleet-core-service  ->  flota_fleet  ->  esquema fleet
--     reporting-service   ->  (no usa la base de datos: obtiene los datos de fleet-core por HTTP)
--
-- El superusuario de la instancia (POSTGRES_USER) queda solo para administrar: ningún servicio lo usa.
--
-- Es idempotente: sirve tanto para una base nueva (lo invoca infra/postgres/init.sh la primera vez que
-- arranca el volumen) como para una base que ya existe (scripts/apply_db_roles.py), donde además transfiere
-- a cada rol la propiedad de las tablas y secuencias que hoy son del superusuario.
--
-- Se ejecuta con psql conectado a la base de datos de la aplicación, con las variables
-- auth_password y fleet_password definidas (-v o \set).
\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------- roles
SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'flota_auth') AS crear_auth \gset
\if :crear_auth
  CREATE ROLE flota_auth LOGIN;
\endif
SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'flota_fleet') AS crear_fleet \gset
\if :crear_fleet
  CREATE ROLE flota_fleet LOGIN;
\endif
ALTER ROLE flota_auth  WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'auth_password';
ALTER ROLE flota_fleet WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'fleet_password';

-- ---------------------------------------------------------------------------- esquemas
CREATE SCHEMA IF NOT EXISTS auth  AUTHORIZATION flota_auth;
CREATE SCHEMA IF NOT EXISTS fleet AUTHORIZATION flota_fleet;
ALTER SCHEMA auth  OWNER TO flota_auth;
ALTER SCHEMA fleet OWNER TO flota_fleet;

-- Las tablas, vistas y secuencias que ya existan (base creada antes de esta separación) pasan a su dueño;
-- los índices y restricciones acompañan a su tabla. Sin esto, Alembic no podría alterarlas con el nuevo rol.
DO $$
DECLARE
  objeto record;
  tipo text;
BEGIN
  FOR objeto IN
    SELECT n.nspname AS esquema, c.relname AS nombre, c.relkind AS clase,
           CASE n.nspname WHEN 'auth' THEN 'flota_auth' ELSE 'flota_fleet' END AS dueno
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname IN ('auth', 'fleet') AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
      -- una secuencia de una columna serial/identidad cambia de dueño junto con su tabla
      AND NOT (c.relkind = 'S' AND EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype IN ('a', 'i')))
  LOOP
    tipo := CASE objeto.clase WHEN 'S' THEN 'SEQUENCE' WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW' ELSE 'TABLE' END;
    EXECUTE format('ALTER %s %I.%I OWNER TO %I', tipo, objeto.esquema, objeto.nombre, objeto.dueno);
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------- permisos
-- Cada esquema solo lo ven y lo usan su dueño y el superusuario.
REVOKE ALL ON SCHEMA auth  FROM PUBLIC;
REVOKE ALL ON SCHEMA fleet FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA auth  TO flota_auth;
GRANT USAGE, CREATE ON SCHEMA fleet TO flota_fleet;
REVOKE ALL ON SCHEMA auth  FROM flota_fleet;
REVOKE ALL ON SCHEMA fleet FROM flota_auth;

-- Nadie crea objetos sueltos en el esquema público, y solo los roles de la aplicación se conectan.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SELECT current_database() AS base \gset
REVOKE CONNECT ON DATABASE :"base" FROM PUBLIC;
GRANT  CONNECT ON DATABASE :"base" TO flota_auth, flota_fleet;

-- ---------------------------------------------------------------------------- limpieza
-- El esquema "reporting" se creó para un uso futuro que no llegó: reporting-service no tiene tablas.
-- Se elimina solo si está vacío (DROP SCHEMA sin CASCADE falla si tiene objetos).
SELECT EXISTS (SELECT FROM pg_namespace WHERE nspname = 'reporting') AS hay_reporting \gset
\if :hay_reporting
  DROP SCHEMA reporting;
\endif
