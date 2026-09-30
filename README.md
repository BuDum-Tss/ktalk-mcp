# ktalk-mcp-apikey

MCP-сервер для Контур.Толк (ktalk.ru): записи, транскрипты, саммари, история
встреч, чат — с двумя взаимозаменяемыми режимами авторизации.

## Два режима авторизации

| | `session` (рекомендуется) | `api_key` |
|---|---|---|
| Что это | Токен вашей браузерной сессии Толка | Личный или доменный API-ключ (`X-Auth-Token`) |
| Ограничения по scope | Нет — видит всё, что видите вы сами в интерфейсе | Личный ключ: жёстко ограничен фиксированным набором (комнаты/пользователи/календарь), **записи недоступны в принципе** — см. `docs/api-reference.md`. Доменный ключ: доступ по выданным scope |
| Срок жизни | ~30 дней, потом токен надо переизвлечь | До года, задаётся при выпуске |
| Откуда взять | DevTools в браузере, см. ниже | Аватар → «Настройки» → «API ключи» (личный) или «Управление» → «API-ключи» (доменный, выдаёт админ) |

Режим выбирается автоматически: если задан `KTALK_SESSION_TOKEN` — `session`,
иначе `api_key`. Можно закрепить явно через `KTALK_AUTH_MODE`.

Мы пришли к `session` эмпирически: личный API-ключ в нашем пространстве
не даёт доступа ни к одному эндпоинту записей (403 на всех вариантах —
см. `scripts/probe_scopes.py`), а session-токен — это тот же механизм,
которым пользуется сам веб-клиент Толка, поэтому он видит ровно то, что
видит залогиненный пользователь.

## Инструменты

| Инструмент | session | api_key |
|---|---|---|
| `list_recordings` | `GET /api/recordings` — ваши записи | `GET /api/Domain/recordings/v2` — записи всего пространства, нужен доменный ключ |
| `get_recording` | `GET /api/recordings/{key}` | `GET /api/Domain/recordings/{key}` |
| `get_transcript` | `GET /api/recordings/{key}/transcript` (один путь для обоих режимов) | |
| `get_summary` | `GET /api/recordings/v2/{key}/summary` или `/summary/{type}` (один путь для обоих режимов) | |
| `download_recording` | скачивает лучшее качество из `qualities[]` детали записи | `GET /api/Recordings/{key}/file/{quality}`, `quality` обязателен |
| `list_meetings` / `get_meeting` / `get_chat_messages` | `GET /api/conferencesHistory/...` — рабочий путь только подтверждён для session | не проверено, вероятно 403 |
| `auth_status` | проверка credential без побочных эффектов | |

## Установка

Требуется Python 3.12+ и [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/BuDum-Tss/ktalk-mcp.git
cd ktalk-mcp
uv sync
```

## Настройка

```bash
copy .env.example .env
```

Откройте `.env` и заполните сами (значения в чат присылать не нужно):

- `KTALK_SPACE_URL` — адрес вашего пространства, например `https://mycompany.ktalk.ru`.
- **Session-режим (рекомендуется):** `KTALK_SESSION_TOKEN`. Токен живёт
  примерно 30 дней — когда инструменты начнут возвращать 401, обновите его.
  Три способа получить/обновить, от самого простого:

  **Самый простой — попросить Claude.** Если вы обычно работаете с этим
  проектом через Claude Code с доступом к Claude in Chrome (расширение для
  вашего настоящего Chrome) — просто скажите «обновите session-токен».
  Claude сам: откроет вкладку на вашем пространстве (если вы уже залогинены
  в Chrome — достаточно), прочитает токен из `localStorage` и отправит его
  локальному приёмнику (см. ниже) — без букмарклетов и копипаста. Токен
  при этом не появляется в тексте переписки.

  **Букмарклет (один клик, без Claude).** Букмарклет — это закладка
  браузера с зашитым JS-кодом вместо ссылки: клик по ней выполняет этот код
  прямо на открытой странице. Настройка один раз:

  1. Запустите приёмник: `uv run python scripts/token_receiver.py`
     (слушает `localhost:8765`, ждёт ровно один валидный токен и завершается).
  2. Добавьте новую закладку в браузере с этим содержимым в поле URL:
     ```js
     javascript:(async()=>{try{const s=JSON.parse(localStorage.session||"{}"),d=s.data||{};let t=d.token,e=d.expiresAt||null;try{if(d.idToken){const r=await fetch("/api/authorize/session",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({idToken:d.idToken})});if(r.ok){const j=await r.json();if(j&&j.token){t=j.token;e=j.expiresAt||e}}}}catch(_){}if(!t){alert("Толк: токен не найден — залогинься и повтори.");return}const p=await fetch("http://127.0.0.1:8765/ktalk-token",{method:"POST",headers:{"Content-Type":"text/plain"},body:JSON.stringify({token:t,expiresAt:e})});const o=await p.json().catch(()=>({}));if(p.ok&&o.ok){alert("Токен сохранён"+(o.expiresAt?", годен до "+o.expiresAt:""))}else{alert("Не удалось сохранить: "+(o.message||p.status))}}catch(x){alert("Ошибка: "+x)}})();
     ```
     (Chrome иногда обрезает `javascript:` при вставке — если так, откройте
     закладку на редактирование и вставьте текст ещё раз.)
  3. На вкладке своего пространства Толка (залогинены) кликните закладку —
     появится alert «Токен сохранён», приёмник запишет значение в `.env` и
     завершится сам.

  Когда токен протухнет — снова `uv run python scripts/token_receiver.py`,
  снова клик по той же закладке.

  **Вручную, через DevTools** — если не хочется настраивать закладку:
  F12 → Console →
  ```js
  copy(JSON.parse(localStorage.session).data.token)
  ```
  и вставить скопированное значение в `KTALK_SESSION_TOKEN` самостоятельно.
- **API-key режим:** `KTALK_API_KEY`, оставьте `KTALK_SESSION_TOKEN` пустым.

## Проверка

```bash
uv run ktalk-mcp-apikey
```

Сервер запустится на stdio и будет ждать MCP-клиента. Для ручной проверки
без полноценного MCP-клиента:

```bash
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
import asyncio
from ktalk_mcp_apikey.server import auth_status
print(asyncio.run(auth_status()))
"
```

## Подключение к Claude Code

```bash
copy .mcp.json.example .mcp.json
```

`.mcp.json` в `.gitignore` — не коммитьте его. Сервер сам подхватывает
`.env` (через `python-dotenv`), так что `env` в `.mcp.json` можно оставить
пустым, если `.env` уже настроен.

## Подключение к Claude Desktop

Это локальный (stdio) MCP-сервер — у него нет URL, подключение идёт через
`claude_desktop_config.json`. Claude Desktop сам запускает процесс при
старте приложения, вручную ничего держать открытым не нужно.

Путь к файлу: `%APPDATA%\Claude\claude_desktop_config.json` (Windows) /
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS).
Добавьте в `mcpServers`:

```json
{
  "mcpServers": {
    "ktalk": {
      "command": "uv",
      "args": ["run", "--project", "C:/MyProjects/ktalk-mcp", "ktalk-mcp-apikey"]
    }
  }
}
```

Переменные окружения не нужны в самом конфиге — сервер сам читает `.env` из
корня проекта. Перезапустите Claude Desktop, чтобы коннектор появился.

## Структура

```
src/ktalk_mcp_apikey/
  client.py   — HTTP-клиент: base_url, оба режима авторизации, GET/download
  server.py   — FastMCP-сервер и сами инструменты
scripts/
  probe_scopes.py     — read-only сканер scope API-ключа по всей OpenAPI-спеке
  token_receiver.py   — локальный приёмник для букмарклета/Claude in Chrome (см. выше)
docs/
  api-reference.md            — читаемая сводка всех 111 операций спеки
  talk.public.api-api-2.json  — официальная OpenAPI-спека Толка
```
