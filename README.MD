# Conecta Território 3D 

API em Django REST Framework da plataforma 3D georreferenciada de dados territoriais (projeto Takeoff, Squad 31).

## Tecnologias

- Python 3.14 e Django 6.0
- Django REST Framework + **GeoDjango**
- drf-spectacular (documentação OpenAPI/Swagger)
- django-cors-headers
- PostgreSQL 16 + PostGIS 3.5 (banco único da API), em Docker

Arquitetura (conforme o documento *Plataforma 3D – Arquitetura Tecnológica*):
`CesiumJS → API Django/GeoDjango → PostgreSQL/PostGIS`. O front nunca acessa o banco.

## Como rodar (Docker — recomendado)

O GeoDjango precisa das bibliotecas GDAL/GEOS/PROJ. Elas já vêm na imagem da API, então
o jeito mais simples é rodar tudo no Docker:

```bash
# 1. (opcional) copiar as variáveis de ambiente e ajustar
copy .env.example .env          # Windows  (cp no Linux/macOS)

# 2. Subir banco + API (a API roda o migrate sozinha ao subir)
docker compose up -d --build

# 3. Criar um usuário administrador
docker compose exec api python manage.py createsuperuser

# 4. Carregar dados
docker compose exec api python manage.py importar_geojson dados_geograficos/malha-pe-2025-v3.geojson --target territory --fonte "IBGE - Malha Municipal PE 2025" --versao 2025-v3
docker compose exec api python manage.py carregar_demo      # lotes/edificações de teste em Olinda

# 5. Rodar os testes
docker compose exec api python manage.py test
```

Links locais:

- Admin (com mapa para editar geometrias): http://127.0.0.1:8000/admin/
- Documentação da API (Swagger): http://127.0.0.1:8000/api/docs/

Rodar fora do Docker também funciona, desde que GDAL esteja instalado na máquina
(no Windows: OSGeo4W ou conda) e o `.env` aponte para `POSTGRES_HOST=localhost` e `POSTGRES_PORT=5433`.

### Variáveis de ambiente

Veja `.env.example`. Em produção, `DJANGO_DEBUG=0` exige `DJANGO_SECRET_KEY`; nenhum segredo fica no código.

## Banco geoespacial (PostgreSQL + PostGIS no Docker)

O banco geoespacial roda num container Docker, definido no arquivo `compose.yaml`. É o banco único da API (o SQLite não é mais usado).

### Pré-requisito

Ter o **Docker Desktop** instalado e aberto (no Windows, ele precisa estar rodando antes de qualquer comando `docker`). Para conferir: `docker --version`.

### Dados de conexão

| Item | Valor |
|---|---|
| Imagem | `postgis/postgis:16-3.5` |
| Container | `conecta_territorio_db` |
| Host | `localhost` |
| Porta (no seu PC) | `5433` (a porta 5432 fica livre para outro Postgres) |
| Banco | `conecta_territorio` |
| Usuário | `conecta_user` |
| Senha | `conecta_dev_123` (somente desenvolvimento local) |

Para abrir em DBeaver, pgAdmin ou outra ferramenta, use esses mesmos dados.

### Comandos do dia a dia

```bash
# Subir o banco em segundo plano (na pasta onde está o compose.yaml)
docker compose up -d

# Ver se está rodando e saudável
docker compose ps

# Ver os logs do banco
docker compose logs db

# Desligar o banco (os dados continuam salvos no volume)
docker compose down

# Desligar E APAGAR todos os dados do banco (cuidado)
docker compose down -v
```

### Como inserir e consultar dados

O jeito recomendado é pela **API** (importação de GeoJSON) ou pelo **admin** (`/admin/`, com mapa para desenhar geometrias).
Para olhar o banco direto:

```bash
docker compose exec db psql -U conecta_user -d conecta_territorio
```

Dentro do `psql`:

```sql
-- Listar as tabelas (as da API começam com api_)
\dt

-- Municípios cadastrados
SELECT id, name, code, type FROM api_territory;

-- Sair
\q
```

Não crie nem altere tabelas pelo `psql`: a estrutura é das migrations do Django (`makemigrations` + `migrate`).

### Importante: cada pessoa tem o seu banco

O Docker **não compartilha** o banco entre computadores. Quando cada pessoa roda `docker compose up -d`, cria um banco próprio na sua máquina. Dados inseridos num PC **não aparecem** nos outros.

Para todos terem os mesmos dados, cada pessoa roda os mesmos comandos de carga (`importar_geojson` com a malha do repositório e `carregar_demo`), descritos em "Como rodar".

## Testes de dados geoespaciais

Verificações manuais para conferir o banco e o GeoJSON entregue ao CesiumJS (os testes automáticos ficam em `api/tests.py`).

### 1. Containers rodando

```powershell
docker compose ps
```

**Resultado esperado:** `db` e `api` com status `running` (o `db` como `healthy`).

### 2. PostGIS instalado

```powershell
docker compose exec db psql -U conecta_user -d conecta_territorio -c "SELECT PostGIS_Version();"
```

### 3. Geometrias municipais válidas e em EPSG:4326

```powershell
docker compose exec db psql -U conecta_user -d conecta_territorio -c "SELECT count(*) AS total, count(*) FILTER (WHERE ST_IsValid(geometry)) AS validas, min(ST_SRID(geometry)) AS srid FROM api_territory WHERE type = 'municipio';"
```

**Resultado esperado após importar a malha de PE:** `total = 185`, `validas = 185`, `srid = 4326`.

### 4. GeoJSON pela API

```powershell
$geo = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/features/?kind=territory&territory=2609600"
$geo.type
$geo.features | Select-Object @{N="Municipio";E={$_.properties.name}}, @{N="Codigo";E={$_.properties.code}}, @{N="Geometria";E={$_.geometry.type}}
```

**Resultado esperado:** `FeatureCollection`, com Olinda (`2609600`) e geometria `MultiPolygon`.

### 5. Arquivos geográficos

```text
ConectaTerritorio3d-/
├── dados_geograficos/
│   ├── malha-pe-2025-v3.geojson   malha municipal original de PE (185 municípios)
│   └── municipios.geojson         Olinda e Recife exportados para testes do front
└── DB/
    └── init.sql                   só habilita o PostGIS
```

A integração visual com o CesiumJS deve ser testada no front: estes testes validam o banco e a API, não o globo 3D.

## Quando alguém adicionar algo novo no projeto

Depois de um `git pull`, rode o que se aplica:

| Mudou o quê | O que rodar |
|---|---|
| `requirements.txt` | `python -m pip install -r requirements.txt` |
| Pasta `api/migrations/` (novo model ou campo) | `python manage.py migrate` |
| `compose.yaml` (Docker) | `docker compose up -d` |
| Qualquer código | `docker compose exec api python manage.py test` (precisa passar antes de subir) |
| `Dockerfile` | `docker compose up -d --build` |

Antes de commitar: rode os testes, e se mudou um model, `docker compose exec api python manage.py makemigrations` e comite o arquivo gerado.

## Endpoints

Versão atual: **`/api/v1/`**. O prefixo `/api/` continua funcionando como alias da v1 (para não quebrar o front) e será removido na v2.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/layers/` | Catálogo de camadas (filtros `category`, `kind`). Camadas privadas só com login |
| GET | `/api/v1/territories/` | Territórios (filtros `type`, `code`, `name`, `parent`, `bbox`, `contains=lon,lat`). Cada item traz `bbox` para enquadrar a câmera |
| GET | `/api/v1/territories/{id}/summary/` | Agregação espacial: área (km², em metros reais), nº de lotes e edificações, uso do solo, indicadores |
| GET | `/api/v1/indicators/` | Indicadores (filtros `territory`, `parcel`, `category`, `period`, `period_from`, `period_to`) |
| GET | `/api/v1/search/?q=` | Busca por território, camada, código de lote, endereço, edificação ou coordenada `lon,lat` |
| GET | `/api/v1/features/` | **GeoJSON** de `kind=territory\|parcel\|building` ou `layer=<id>`. Filtros: `bbox`, `territory`, `near`+`radius`, `land_use`, `zoning`, `use`, `min_height`, `limit`, `simplify` |
| POST | `/api/v1/features/query/` | Feições que intersectam um polígono desenhado no mapa |
| GET | `/api/v1/features/{kind}/{id}/` | Detalhe da feição clicada (geometria, atributos, indicadores) |
| GET | `/api/v1/tilesets/` | URLs/metadados de 3D Tiles e raster (arquivos ficam em storage/CDN) |
| GET/POST | `/api/v1/imports/` | Importação de GeoJSON com validação, reprojeção e proveniência (somente administrador) |
| POST | `/api/v1/ai/query/` | Pergunta em linguagem natural sobre os dados |
| POST | `/api/v1/auth/login/` · `logout/` · GET `me/` | Login por token |

Listas REST são paginadas (20 por página). `/features/` devolve no máximo 1000 feições (padrão 200) e indica
`truncated: true` quando há mais; `bbox` maior que 1 grau² é recusado (400), para proteger o banco e o front.
Limite de requisições: 60/min sem login, 300/min com login, 10/min na IA e no login. Ao exceder, a API responde `429`.

### Exemplos para o CesiumJS

```text
GET /api/v1/features/?kind=building&bbox=-34.86,-8.02,-34.85,-8.00     → extrudar por properties.height_m
GET /api/v1/features/?kind=territory&type=municipio&simplify=0.001     → limites em zoom distante
GET /api/v1/features/parcel/12/                                         → painel do objeto clicado (id "parcel.12")
```

### Importar dados (ETL)

`POST /api/v1/imports/` (multipart) com `source`, `target` (`territory`, `parcel` ou `building`), `file` (.geojson até 50 MB)
e, opcionalmente, `layer`. O processamento:

1. lê o CRS do arquivo e **reprojeta para EPSG:4326** (SRID oficial do projeto);
2. **corrige geometrias inválidas** (`make_valid`) e converte Polygon → MultiPolygon;
3. reconhece nomes de atributo comuns (`codigo`, `cod_munici`, `nome`, `endereco`, `altura`...);
4. atualiza pelo código (reimportar não duplica) e liga lotes/edificações ao território que os contém;
5. registra quantas feições entraram e falharam, os erros e a fonte (proveniência), e grava na **auditoria**.

Pelo terminal: `python manage.py importar_geojson <arquivo> --target territory|parcel|building`.

## Estrutura do projeto

```
ConectaTerritorio3d-/
├── api/                      App principal: toda a lógica da API
│   ├── management/commands/  importar_geojson (ETL pelo terminal) e carregar_demo (dados de teste)
│   ├── migrations/           Histórico de alterações do banco (versionado)
│   ├── admin.py              Painel /admin/ (com mapa nas tabelas geográficas)
│   ├── ai.py                 Interpreta a pergunta da IA (categoria e território) por regras
│   ├── auth.py               Login/logout por token e /auth/me/
│   ├── etl.py                Importação de GeoJSON: validação, reprojeção, proveniência
│   ├── geo.py                Consultas espaciais, visibilidade de camadas e montagem do GeoJSON
│   ├── models.py             Tabelas do banco (fontes, camadas, territórios, lotes, edificações...)
│   ├── schema.py             Ajustes do Swagger (documenta só /api/v1/)
│   ├── serializers.py        Convertem os models em JSON e validam as entradas
│   ├── tests.py              Testes automatizados
│   ├── urls.py               Rotas da API
│   └── views.py              Lógica de cada endpoint
├── core/                     Configuração do projeto Django
│   ├── settings.py           Banco (por variáveis de ambiente), CORS, permissões, limites, logs, Swagger
│   └── urls.py               Rotas principais: /admin/, /api/v1/, /api/, /api/docs/
├── dados_geograficos/        GeoJSON de origem (malha municipal de PE)
├── DB/init.sql               Habilita o PostGIS na criação do banco
├── Dockerfile                Imagem da API com GDAL/GEOS/PROJ
├── compose.yaml              Sobe PostGIS (db) + API (api)
├── .env.example              Modelo das variáveis de ambiente
├── manage.py                 Comando do Django (runserver, migrate, test, ...)
├── requirements.txt          Dependências do projeto
└── README.MD                 Este arquivo
```

## Models (tabelas do banco)

Todas as geometrias são `MultiPolygon` em **EPSG:4326**, com índice espacial GiST.

| Model | Para que serve |
|---|---|
| `Source` | Fonte de um dado (licença, data de coleta, método de importação, versão, qualidade) |
| `Layer` | Catálogo de camadas: categoria, tipo (`kind`), estilo, escala, responsável, pública/privada |
| `Territory` | Município, bairro ou setor, com hierarquia e geometria |
| `Parcel` | Lote/imóvel: código cadastral, endereço, área, uso do solo, zoneamento, geometria |
| `Building` | Edificação: uso, pavimentos, altura, área, lote, geometria |
| `Indicator` | Valor de um indicador de um território (ou lote), com unidade, período e fonte |
| `Tileset` | Referência a 3D Tiles/raster publicados em storage/CDN |
| `ImportJob` | Importação: status, arquivo, destino, registros processados/com erro, log |
| `AuditLog` | Auditoria de operações críticas (importações) |

## Endpoints e onde cada um está

| Rota | View (em `api/views.py`) |
|---|---|
| `/api/v1/layers/` | `LayerViewSet` |
| `/api/v1/territories/` e `/{id}/summary/` | `TerritoryViewSet` |
| `/api/v1/indicators/` | `IndicatorViewSet` |
| `/api/v1/search/` | `SearchView` |
| `/api/v1/features/` | `FeatureListView` (usa `api/geo.py`) |
| `/api/v1/features/query/` | `FeatureQueryView` |
| `/api/v1/features/{kind}/{id}/` | `FeatureDetailView` |
| `/api/v1/tilesets/` | `TilesetViewSet` |
| `/api/v1/imports/` | `ImportJobViewSet` (usa `api/etl.py`) |
| `/api/v1/ai/query/` | `AIQueryView` (usa `api/ai.py`) |
| `/api/v1/auth/...` | `LoginView`, `MeView`, `LogoutView` (em `api/auth.py`) |
| `/api/docs/` | Swagger (configurado em `core/urls.py`) |

## Testes

```bash
python manage.py test
```

## Status

- [x] Endpoints base, busca e documentação Swagger
- [x] Endpoint de IA com tratamento de "sem dados" e pergunta incompleta
- [x] Container PostgreSQL + PostGIS (Docker)
- [x] Django conectado ao PostGIS (GeoDjango); tabelas criadas por migrations
- [x] Models de lotes e edificações com geometria
- [x] `/api/v1/features/` com GeoJSON, filtros espaciais e limites
- [x] Importação real de dados (ETL) com validação, reprojeção e proveniência
- [x] API versionada, camadas públicas/privadas, auditoria, segredos por variável de ambiente
- [ ] Integração com LLM (hoje o `/ai/query/` usa regras)
- [ ] Fase de escala: Celery para importações grandes, Redis para cache, geração de 3D Tiles
