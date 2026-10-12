# Conecta Território 3D 

API em Django REST Framework da plataforma 3D georreferenciada de dados territoriais (projeto Takeoff, Squad 31).

## Tecnologias

- Python 3.14 e Django 6.0
- Django REST Framework
- drf-spectacular (documentação OpenAPI/Swagger)
- django-cors-headers
- SQLite (banco que a API usa hoje)
- PostgreSQL + PostGIS 16 em Docker (banco geoespacial, ainda não conectado à API; veja a seção abaixo)

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

## Banco geoespacial (PostgreSQL + PostGIS no Docker)

O banco geoespacial roda num container Docker, definido no arquivo `compose.yaml`. Ele é **separado** do `db.sqlite3` que a API usa hoje.

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

Entre no banco pelo terminal (pode ser o terminal do VS Code):

```bash
docker compose exec db psql -U conecta_user -d conecta_territorio
```

Dentro do `psql`:

```sql
-- Inserir um território
INSERT INTO territorios (nome, tipo_territorio, codigo, descricao)
VALUES ('Olinda', 'municipio', '2609600', 'Município de Pernambuco');

-- Ver os dados inseridos
SELECT * FROM territorios;

-- Listar todas as tabelas
\dt

-- Sair
\q
```

Para inserir em outras tabelas, use `INSERT INTO <tabela> (colunas) VALUES (valores);`. Para ver as colunas de uma tabela: `\d nome_da_tabela`.

### Importante: cada pessoa tem o seu banco

O Docker **não compartilha** o banco entre computadores. Quando cada pessoa roda `docker compose up -d`, cria um banco próprio e vazio na sua máquina. Dados inseridos num PC **não aparecem** nos outros.

Para o time testar o mesmo banco, existem duas saídas:

1. Quem criou as tabelas deixa o script SQL no repositório (por exemplo `db/init.sql`), para todos criarem as mesmas tabelas e dados de teste.
2. Quem tem o banco deixa o computador ligado e acessível na rede para os outros se conectarem (só funciona com todos na mesma rede).

> **Pendência:** as tabelas foram criadas direto pelo terminal e o script de criação ainda não está no repositório. Quem subir o container pela primeira vez terá um banco **sem tabelas** até o script ser adicionado.

### Estado atual da integração

- A API (Django) ainda usa **SQLite**. As tabelas do PostGIS ainda não são lidas por ela.
- A conexão do Django com o PostGIS e os models com geometria são a próxima etapa.

## Quando alguém adicionar algo novo no projeto

Depois de um `git pull`, rode o que se aplica:

| Mudou o quê | O que rodar |
|---|---|
| `requirements.txt` | `python -m pip install -r requirements.txt` |
| Pasta `api/migrations/` (novo model ou campo) | `python manage.py migrate` |
| `compose.yaml` (Docker) | `docker compose up -d` |
| Qualquer código | `python manage.py test` (precisa passar antes de subir) |

Antes de commitar: `python manage.py test`, e se mudou um model, `python manage.py makemigrations` e comite o arquivo gerado.

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
├── compose.yaml              Sobe o PostgreSQL + PostGIS em Docker
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
- [x] Container PostgreSQL + PostGIS (Docker) e tabela `territorios` criada
- [ ] Script SQL das tabelas versionado no repositório
- [ ] Conectar o Django ao PostGIS e criar models de lotes e edificações com geometria
- [ ] `/api/features/` com GeoJSON
- [ ] Importação real de dados (ETL)
- [ ] Integração com LLM