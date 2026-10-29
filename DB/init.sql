-- =====================================================================
-- Conecta Território 3D - preparação do banco (PostgreSQL + PostGIS)
-- Executado automaticamente pelo Docker na PRIMEIRA vez que o banco é criado.
--
-- As tabelas NÃO são criadas aqui: quem cria e altera a estrutura são as
-- migrations do Django (python manage.py migrate), que o container "api"
-- roda ao subir. Os dados de teste são carregados com:
--   docker compose exec api python manage.py carregar_demo
-- e a malha real de municípios com:
--   docker compose exec api python manage.py importar_geojson dados_geograficos/malha-pe-2025-v3.geojson --target territory
--
-- Para recriar do zero:  docker compose down -v  &&  docker compose up -d
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
