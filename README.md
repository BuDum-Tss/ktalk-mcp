# ktalk-mcp-apikey

MCP-сервер для Контур.Толк (ktalk.ru): записи, транскрипты, саммари — через
официальный публичный API Толка с авторизацией по API-ключу (`X-Auth-Token`),
без браузерного session-токена.

Основан на официальной OpenAPI-спецификации Толка (endpoints для
`/api/recordings/*` и `/api/Domain/recordings*`) — session-token-инструменты
вроде [mdemyanov/ktalk-cli](https://github.com/mdemyanov/ktalk-cli) и
[mainpart/ktalk-mcp](https://github.com/mainpart/ktalk-mcp) используют
внутренний недокументированный контур и не подходят, если у вас именно
API-ключ, а не сессия браузера.

## Инструменты

| Инструмент | Эндпоинт | Назначение |
|---|---|---|
| `get_recording` | `GET /api/Recordings/{key}` | Детали записи |
| `get_transcript` | `GET /api/recordings/{key}/transcript` | Транскрипт по спикерам |
| `get_summary` | `GET /api/recordings/v2/{key}/summary` или `/summary/{type}` | Краткий пересказ / протокол |
| `download_recording` | `GET /api/Recordings/{key}/file/{quality}` | Скачать видеофайл |
| `list_recordings` | `GET /api/Domain/recordings/v2` | Список записей пространства (нужен **доменный** ключ, не личный) |
| `auth_status` | — | Проверить, что ключ вообще принимается |

**Важно про личный API-ключ:** по документации Толка личный ключ даёт доступ
только к тем данным, которые видит сам пользователь. `list_recordings` при
этом почти наверняка вернёт 403 — доменный листинг требует ключ,
выпущенный администратором пространства со scope "Просмотр списка записей".
Если у вас только личный ключ, `recording_key` придётся брать из самого Толка
(ссылка на запись) и передавать в `get_recording` / `get_transcript` /
`get_summary` напрямую.

Это не проверено вживую — сначала вызовите `auth_status`, а затем один из
read-инструментов с реальным `recording_key` и посмотрите на ответ.

## Установка

Требуется Python 3.12+ и [uv](https://docs.astral.sh/uv/).

```bash
cd C:\MyProjects\ktalk-mcp
uv sync
```

## Настройка

```bash
copy .env.example .env
```

Откройте `.env` и заполните сами (в чат ключ вставлять не нужно):

- `KTALK_SPACE_URL` — адрес вашего пространства, например `https://mycompany.ktalk.ru`.
- `KTALK_API_KEY` — API-ключ. Личный: аватар → «Настройки» → «API ключи» →
  «Выпустить ключ». Доменный (если нужен `list_recordings`): «Управление» →
  «API-ключи» → «Добавить» — этот делает администратор пространства.

## Проверка

```bash
uv run ktalk-mcp-apikey
```

Сервер запустится на stdio (это нормально — он ждёт MCP-клиента, а не
печатает лог и не завершается). Для быстрой проверки ключа без Claude можно
временно добавить в `server.py` ручной вызов `auth_status()`, либо
подключить сервер к Claude Code (см. ниже) и вызвать `auth_status` оттуда.

## Подключение к Claude Code

```bash
copy .mcp.json.example .mcp.json
```

Впишите свои `KTALK_SPACE_URL` и `KTALK_API_KEY` в `.mcp.json` (файл в
`.gitignore` не входит — не коммитьте его с реальным ключом) либо, лучше,
оставьте `env` пустым и полагайтесь на `.env` — тогда добавьте загрузку
`.env` в `server.py` через `python-dotenv`, если понадобится.

## Структура

```
src/ktalk_mcp_apikey/
  client.py   — HTTP-клиент: base_url, заголовок X-Auth-Token, GET/download
  server.py   — FastMCP-сервер и сами инструменты
```
