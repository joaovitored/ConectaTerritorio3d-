# Conecta Território 3D 

API em Django REST Framework da plataforma 3D georreferenciada de dados territoriais (projeto Takeoff, Squad 31).

## Tecnologias

- Python 3.14 e Django 6.0
- Django REST Framework
- drf-spectacular (documentação OpenAPI/Swagger)
- django-cors-headers
- SQLite (por enquanto; PostgreSQL + PostGIS entra com o modelo geoespacial)

## Como rodar

```bash
# 1. Criar e ativar o ambiente virtual
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/macOS

# 2. Instalar as dependências
python -m pip install -r requirements.txt

# 3. Criar o banco local
python manage.py migrate

# 4. Criar um usuário administrador
python manage.py createsuperuser

# 5. Subir o servidor
python manage.py runserver
```

Links locais:

- Admin: http://127.0.0.1:8000/admin/
- Documentação da API (Swagger): http://127.0.0.1:8000/api/docs/

O banco `db.sqlite3` não é versionado: cada pessoa cria o seu com o `migrate`.

Como inserir dados no PostgreSQL
# 1. Acessar o banco de dados pelo Docker
docker compose exec db psql -U conecta_user -d conecta_territorio

# 2. Inserir dados na tabela territorios
INSERT INTO territorios (nome, tipo_territorio, codigo, descricao)
VALUES ('Olinda', 'municipio', '2609600', 'Município de Pernambuco');

# 3. Visualizar os dados inseridos
SELECT * FROM territorios;

# 4. Visualizar todas as tabelas
\dt

Observação: para inserir dados em outras tabelas, utilize o comando INSERT INTO com o nome da tabela, as colunas e os valores correspondentes.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/layers/` | Camadas de dados (filtro `?category=`) |
| GET | `/api/territories/` | Territórios (filtros `type`, `code`, `name`, `parent`) |
| GET | `/api/indicators/` | Indicadores (filtros `territory`, `category`, `period`) |
| GET | `/api/search/?q=` | Busca unificada por território e camada |
| GET | `/api/features/` | Feições geográficas (em desenvolvimento) |
| GET | `/api/tilesets/` | Tilesets 3D (em desenvolvimento) |
| POST | `/api/imports/` | Cria um job de importação (somente administrador) |
| POST | `/api/ai/query/` | Pergunta em linguagem natural sobre os dados |

Todas as listas são paginadas (20 por página). Há limite de requisições: 60 por minuto sem login, 300 com login e 10 por minuto na IA. Ao exceder, a API responde `429`.

## Estrutura do projeto

```
ProjetoResidencia/
├── api/                      App principal: toda a lógica da API
│   ├── migrations/           Histórico de alterações do banco (versionado)
│   │   └── 0001_initial.py   Cria as tabelas Source, Layer, Territory, Indicator e ImportJob
│   ├── admin.py              Registra os models no painel /admin/
│   ├── ai.py                 Interpreta a pergunta da IA (categoria e território) por regras
│   ├── apps.py               Configuração do app `api` no Django
│   ├── models.py             Tabelas do banco (fontes, camadas, territórios, indicadores, importações)
│   ├── serializers.py        Convertem os models em JSON (e validam o corpo do POST da IA)
│   ├── tests.py              Testes automatizados (35)
│   ├── urls.py               Rotas da API (/api/layers/, /api/search/, ...)
│   └── views.py              Lógica de cada endpoint (filtros, busca, IA, importação)
├── core/                     Configuração do projeto Django
│   ├── settings.py           Banco, apps instalados, CORS, permissões, limites e Swagger
│   ├── urls.py               Rotas principais: /admin/, /api/, /api/docs/
│   ├── asgi.py               Ponto de entrada para servidores ASGI (produção)
│   └── wsgi.py               Ponto de entrada para servidores WSGI (produção)
├── manage.py                 Comando do Django (runserver, migrate, test, ...)
├── requirements.txt          Dependências do projeto
├── README.MD                 Este arquivo
├── .gitignore                Arquivos que o Git não versiona (banco local, cache, venv)
└── .gitattributes            Configuração de fim de linha do Git
```

> `db.sqlite3` é o banco local de cada pessoa. Ele é criado pelo `migrate` e **não** vai para o Git.

## Models (tabelas do banco)

| Model | Para que serve |
|---|---|
| `Source` | Fonte de um dado (nome, licença, data de coleta) |
| `Layer` | Camada de dados exibida no mapa, com categoria e fonte |
| `Territory` | Município, bairro ou setor, com hierarquia (um território pode ter um "pai") |
| `Indicator` | Valor de um indicador de um território, com unidade, período e fonte |
| `ImportJob` | Registro de uma importação de dados (status, versão, erros) |

## Endpoints e onde cada um está

| Rota | View (em `api/views.py`) |
|---|---|
| `/api/layers/` | `LayerViewSet` |
| `/api/territories/` | `TerritoryViewSet` |
| `/api/indicators/` | `IndicatorViewSet` |
| `/api/search/` | `SearchView` |
| `/api/imports/` | `ImportJobViewSet` |
| `/api/ai/query/` | `AIQueryView` (usa `api/ai.py`) |
| `/api/features/`, `/api/tilesets/` | `FeatureListView`, `FeatureDetailView`, `TilesetListView` (em desenvolvimento) |
| `/api/docs/` | Swagger (configurado em `core/urls.py`) |

## Testes

```bash
python manage.py test
```

## Status

- [x] Endpoints base, busca e documentação Swagger
- [x] Endpoint de IA com tratamento de "sem dados" e pergunta incompleta
- [x] PostGIS, lotes e edificações com geometria
- [ ] `/api/features/` com GeoJSON
- [ ] Importação real de dados (ETL)
- [ ] Integração com LLM