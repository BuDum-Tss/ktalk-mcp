# Talk public API — полный список эндпоинтов

Источник: `talk.public.api-api-2.json` (официальная OpenAPI-спецификация,
включена в репозиторий рядом с этим файлом). 87 путей, 111 операций.
Авторизация везде одинаковая — заголовок `X-Auth-Token` (см. `client.py`).

Открыть спеку интерактивно: вставьте содержимое `talk.public.api-api-2.json`
в https://editor.swagger.io/ (там же видно тело запросов/ответов по каждой
операции, чего нет в списке ниже).

Отмечено `[✓]` — доступно текущему ключу (см. `scripts/probe_scopes.py`),
`[403]` — ключ валиден, но без scope, `[?]` — не проверялось (мутирующие
операции probe-скрипт намеренно не трогает).

| Метод | Путь | Назначение | У нашего ключа |
|---|---|---|---|
| GET | /api/AuditLog | Аудит-лог действий пользователя | 400 (ключ принят, нужны параметры) |
| GET/POST/PUT/DELETE | /api/Calendar/servers(/{id}) | Календарные сервисы пространства | 403 |
| GET | /api/ClientsTelemetry(/v2) | Телеметрия по домену | 403 |
| GET | /api/ConferenceReports/{conferenceKey}/... | Отчёты по прошедшей конференции (сообщения/вопросы/участники/активность) | 403 |
| GET | /api/ConferencesHistory/{conferenceKey} | Метаинформация о конференции | 403 |
| GET | /api/ConferencesHistory/v2/{conferenceKey} | Артефакты конференции | 403 |
| GET | /api/DeepFakeDetector/... | Детекция дипфейков | 403 |
| GET | /api/Domain/recordings(/v2) | **Список записей пространства** | 403 |
| GET | /api/Domain/recordings/{key} | **Детали записи (доменный доступ)** | 403 |
| GET | /api/Domain/recordings/{key}/participants | Участники записи (доменный доступ) | 403 |
| GET | /api/Domain/statistics, statisticsTotal | Статистика пользователей | 403 |
| GET/POST/PUT/DELETE | /api/EmailCalendar/{email}(/{eventId}...) | Встречи в календаре пользователя | 400/403 (частично принято) |
| GET/POST/... | /api/Kiosk/... | Управление киосками (переговорные) | 403 |
| PUT/DELETE | /api/Recordings/{key} | Редактировать/удалить запись | [?] |
| GET/PATCH | /api/Recordings/{key}/access | Права доступа записи | [?] |
| GET | /api/Recordings/{key}/file/{quality} | **Скачать файл записи** | 403 |
| GET | /api/RoomReport/... | Отчёты по посещаемости | 403 |
| GET | /api/Rooms/{roomName} | **Комната по ключу** | ✓ 200 |
| PUT | /api/Rooms/{roomName} | Создать/редактировать комнату | [?] |
| POST | /api/Rooms/{roomName}/cancelCall, endconference, lock, notifyCall | Управление звонком в комнате | [?] |
| POST/DELETE | /api/Rooms/{roomName}/moderators/{userRef} | Модераторы комнаты | [?] |
| GET/POST | /api/Users | Поиск / создание пользователей | ✓ 200 (GET) |
| GET | /api/Users/scan | Список всех пользователей пространства | ✓ 200 |
| GET/DELETE | /api/Users/{userKey} | Пользователь по ключу | ✓ 404 (принято, не найден) |
| GET/POST | /api/Users/{userKey}/roles | Роли пользователя | 403 |
| POST/DELETE | /api/Users/{userKey}/avatar(/sync) | Аватар пользователя | [?] |
| PUT | /api/Users/{userKey}/permissions | Блокировка пользователя | [?] |
| GET/POST/DELETE | /api/Webhooks(/{key}...) | Вебхуки пространства | [?] |
| GET | /api/domain/applications | Список API-ключей | 403 |
| GET | /api/domain/applications/access-info | Доступы текущего ключа | 403 |
| GET | /api/domain/conferencesHistory | Прошедшие конференции пространства | 403 |
| GET | /api/domain/stats/... | Разная статистика (онлайн, записи, киоски, вебинары, доски, тариф) | 403 |
| GET/POST/PUT | /api/domain/surveys(/{id}...) | Опросы | 403 |
| GET | /api/permissions | Список прав для продуктов пространства | 403 |
| GET | /api/recordings/v2/{key}/summary | **Протокол + краткий пересказ + транскрипт** | 403 |
| GET | /api/recordings/{key}/summary | **Краткий пересказ с таймкодами** | 403 |
| GET | /api/recordings/{key}/summary/{type} | **Пересказ/протокол по типу** (shortSummary\|protocol) | 403 |
| GET | /api/recordings/{key}/transcript | **Транскрипция записи** | 403 |
| GET/POST/PUT/DELETE | /api/roles(/{id}...) | Роли пространства | 403 |

Жирным — то, что нужно для сценария «записи/расшифровки/саммари»: всё
целиком закрыто текущим личным ключом (см. `scripts/probe_scopes.py`).
Открыто только: `Rooms` (чтение), `Users`/`Users/scan` (чтение),
частично `EmailCalendar`/`AuditLog` (ключ принят, но нужны корректные
параметры — не проверялось до конца).

Полный экспорт всех 111 операций с уже подставленными плейсхолдерами
параметров — в `talk.public.api-api-2.json` в этой же папке.
