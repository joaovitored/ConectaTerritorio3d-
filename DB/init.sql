-- =====================================================================
-- Conecta Território 3D - estrutura inicial do banco (PostgreSQL + PostGIS)
-- Executado automaticamente pelo Docker na PRIMEIRA vez que o banco é criado
-- (ver o volume ./db/init.sql no compose.yaml).
-- Para recriar do zero:  docker compose down -v  &&  docker compose up -d
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------- Fontes de dados ----------
CREATE TABLE public.fontes_dados (
    id               bigserial PRIMARY KEY,
    nome             varchar(150) NOT NULL,
    descricao        text,
    url_fonte        text,
    licenca          varchar(150),
    data_coleta      date,
    status_qualidade varchar(50),
    criado_em        timestamp DEFAULT CURRENT_TIMESTAMP
);

-- ---------- Territórios (município, bairro, setor) ----------
CREATE TABLE public.territorios (
    id              bigserial PRIMARY KEY,
    nome            varchar(150) NOT NULL,
    tipo_territorio varchar(50)  NOT NULL,
    codigo          varchar(100),
    descricao       text,
    geometria       geometry(MultiPolygon, 4326),
    criado_em       timestamp DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_territories_geom ON public.territorios USING gist (geometria);

-- ---------- Camadas ----------
CREATE TABLE public.camadas (
    id             bigserial PRIMARY KEY,
    fonte_dados_id bigint REFERENCES public.fontes_dados(id),
    nome           varchar(150) NOT NULL,
    tipo_camada    varchar(80)  NOT NULL,
    descricao      text,
    status         varchar(30) DEFAULT 'active',
    escala         varchar(100),
    estilo         jsonb,
    publico        boolean DEFAULT true,
    criado_em      timestamp DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_layers_source ON public.camadas USING btree (fonte_dados_id);

-- ---------- Lotes ----------
CREATE TABLE public.lotes (
    id             bigserial PRIMARY KEY,
    territorio_id  bigint REFERENCES public.territorios(id),
    fonte_dados_id bigint REFERENCES public.fontes_dados(id),
    codigo         varchar(100) UNIQUE,
    endereco       text,
    area_m2        numeric(14,2),
    uso_solo       varchar(100),
    zoneamento     varchar(100),
    geometria      geometry(MultiPolygon, 4326),
    criado_em      timestamp DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_parcels_geom      ON public.lotes USING gist (geometria);
CREATE INDEX idx_parcels_territory ON public.lotes USING btree (territorio_id);

-- ---------- Edificações ----------
CREATE TABLE public.edificacoes (
    id              bigserial PRIMARY KEY,
    lote_id         bigint REFERENCES public.lotes(id),
    fonte_dados_id  bigint REFERENCES public.fontes_dados(id),
    nome            varchar(150),
    tipo_edificacao varchar(100),
    pavimentos      integer,
    altura_m        numeric(10,2),
    area_m2         numeric(14,2),
    geometria       geometry(MultiPolygon, 4326),
    criado_em       timestamp DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_buildings_geom   ON public.edificacoes USING gist (geometria);
CREATE INDEX idx_buildings_parcel ON public.edificacoes USING btree (lote_id);

-- ---------- Indicadores ----------
CREATE TABLE public.indicadores (
    id                 bigserial PRIMARY KEY,
    territorio_id      bigint REFERENCES public.territorios(id),
    fonte_dados_id     bigint REFERENCES public.fontes_dados(id),
    nome               varchar(150) NOT NULL,
    categoria          varchar(100),
    valor              numeric(18,4),
    unidade            varchar(50),
    periodo_referencia varchar(30),
    descricao          text,
    criado_em          timestamp DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_indicators_territory ON public.indicadores USING btree (territorio_id);

-- ---------- Importações ----------
CREATE TABLE public.importacoes (
    id                    bigserial PRIMARY KEY,
    fonte_dados_id        bigint REFERENCES public.fontes_dados(id),
    camada_id             bigint REFERENCES public.camadas(id),
    nome_arquivo          varchar(255),
    status                varchar(30) NOT NULL DEFAULT 'pending',
    registros_processados integer DEFAULT 0,
    mensagem_erro         text,
    iniciado_em           timestamp,
    finalizado_em         timestamp,
    criado_em             timestamp DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_imports_status ON public.importacoes USING btree (status);

-- ---------- Dados de teste ----------
INSERT INTO public.territorios (nome, tipo_territorio, codigo, descricao) VALUES
    ('Olinda', 'municipio', '2609600', 'Município de Pernambuco'),
    ('Recife', 'municipio', '2611606', 'Capital de Pernambuco');

-- =====================================================================
-- DADOS DE TESTE GEOESPACIAIS (coordenadas APROXIMADAS, só para desenvolvimento)
-- Troque pelos dados reais quando a fonte oficial for importada.
-- Geometrias: MultiPolygon, SRID 4326 (longitude, latitude em graus).
-- =====================================================================

-- Fonte e camada
INSERT INTO public.fontes_dados (nome, descricao, licenca, data_coleta, status_qualidade) VALUES
    ('Dados de teste', 'Geometrias aproximadas criadas à mão para desenvolvimento', 'uso interno', CURRENT_DATE, 'teste');

INSERT INTO public.camadas (fonte_dados_id, nome, tipo_camada, descricao)
SELECT id, 'Lotes (teste)', 'cadastral', 'Lotes de exemplo em Olinda'
FROM public.fontes_dados WHERE nome = 'Dados de teste';

-- Contorno aproximado dos municípios (retângulos de teste)
UPDATE public.territorios SET geometria = ST_Multi(ST_GeomFromText(
    'POLYGON((-34.885 -8.040, -34.825 -8.040, -34.825 -7.960, -34.885 -7.960, -34.885 -8.040))', 4326))
WHERE codigo = '2609600';   -- Olinda

UPDATE public.territorios SET geometria = ST_Multi(ST_GeomFromText(
    'POLYGON((-34.960 -8.150, -34.870 -8.150, -34.870 -8.000, -34.960 -8.000, -34.960 -8.150))', 4326))
WHERE codigo = '2611606';   -- Recife

-- Lotes de exemplo em Olinda (cada um dentro do contorno de Olinda)
INSERT INTO public.lotes (territorio_id, fonte_dados_id, codigo, endereco, area_m2, uso_solo, zoneamento, geometria)
SELECT t.id, f.id, v.codigo, v.endereco, v.area, v.uso, v.zona, ST_Multi(ST_GeomFromText(v.wkt, 4326))
FROM public.territorios t, public.fontes_dados f,
(VALUES
  ('OL-001', 'Rua do Sol, 10',        300.00, 'residencial', 'ZUR-1', 'POLYGON((-34.8560 -8.0100, -34.8555 -8.0100, -34.8555 -8.0095, -34.8560 -8.0095, -34.8560 -8.0100))'),
  ('OL-002', 'Rua do Sol, 20',        320.00, 'residencial', 'ZUR-1', 'POLYGON((-34.8554 -8.0100, -34.8549 -8.0100, -34.8549 -8.0095, -34.8554 -8.0095, -34.8554 -8.0100))'),
  ('OL-003', 'Av. Principal, 100',    500.00, 'comercial',   'ZC-2',  'POLYGON((-34.8560 -8.0094, -34.8554 -8.0094, -34.8554 -8.0088, -34.8560 -8.0088, -34.8560 -8.0094))'),
  ('OL-004', 'Praça Central, 5',      450.00, 'misto',       'ZM-1',  'POLYGON((-34.8553 -8.0094, -34.8547 -8.0094, -34.8547 -8.0088, -34.8553 -8.0088, -34.8553 -8.0094))'),
  ('OL-005', 'Rua da Igreja, 40',     280.00, 'institucional','ZI-1', 'POLYGON((-34.8546 -8.0100, -34.8541 -8.0100, -34.8541 -8.0095, -34.8546 -8.0095, -34.8546 -8.0100))')
) AS v(codigo, endereco, area, uso, zona, wkt)
WHERE t.codigo = '2609600' AND f.nome = 'Dados de teste';

-- Edificações de exemplo (cada uma dentro do seu lote)
INSERT INTO public.edificacoes (lote_id, fonte_dados_id, nome, tipo_edificacao, pavimentos, altura_m, area_m2, geometria)
SELECT l.id, f.id, v.nome, v.tipo, v.pav, v.altura, v.area, ST_Multi(ST_GeomFromText(v.wkt, 4326))
FROM public.lotes l, public.fontes_dados f,
(VALUES
  ('OL-001', 'Casa 10',         'residencial', 1,  3.50, 120.00, 'POLYGON((-34.85590 -8.01000, -34.85565 -8.01000, -34.85565 -8.00975, -34.85590 -8.00975, -34.85590 -8.01000))'),
  ('OL-003', 'Loja Principal',  'comercial',   2,  7.00, 300.00, 'POLYGON((-34.85590 -8.00935, -34.85550 -8.00935, -34.85550 -8.00895, -34.85590 -8.00895, -34.85590 -8.00935))'),
  ('OL-004', 'Edifício Praça',  'misto',       5, 15.00, 250.00, 'POLYGON((-34.85520 -8.00935, -34.85480 -8.00935, -34.85480 -8.00895, -34.85520 -8.00895, -34.85520 -8.00935))'),
  ('OL-005', 'Paróquia',        'institucional',1, 9.00, 200.00, 'POLYGON((-34.85450 -8.00995, -34.85420 -8.00995, -34.85420 -8.00960, -34.85450 -8.00960, -34.85450 -8.00995))')
) AS v(codigo_lote, nome, tipo, pav, altura, area, wkt)
WHERE l.codigo = v.codigo_lote AND f.nome = 'Dados de teste';