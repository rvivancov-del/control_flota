-- Se ejecuta una sola vez, al crear el volumen de datos por primera vez.
-- Cada microservicio vive en su propio esquema dentro de la misma instancia
-- de PostgreSQL (ver Lámina D-01 del documento de arquitectura).
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS fleet;
CREATE SCHEMA IF NOT EXISTS reporting;
