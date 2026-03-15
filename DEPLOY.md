# Деплой AI Content Machine — Railway.app

Railway — PaaS-платформа с поддержкой Docker, PostgreSQL и GitHub Student Pack ($5/мес бесплатно).

---

## Шаг 1: Зарегистрироваться на Railway

1. Зайди на [railway.app](https://railway.app)
2. Нажми **Login with GitHub**
3. Railway автоматически подтянет Student Pack и даст **$5/мес бесплатного кредита**

> $5/мес хватит для работы пайплайна (PostgreSQL + App). При превышении лимита Railway приостановит сервисы, но ничего не спишет.

---

## Шаг 2: Загрузить проект на GitHub

На своём Mac:

```bash
cd ~/AntigravityProjects/automations/content-machine

git init
git add .
git commit -m "Initial commit: AI Content Machine"
```

Создай **приватный** репозиторий на GitHub, затем:

```bash
git remote add origin git@github.com:YOUR_USERNAME/content-machine.git
git branch -M main
git push -u origin main
```

---

## Шаг 3: Создать проект на Railway

1. В Railway → **New Project** → **Deploy from GitHub repo**
2. Выбери свой репозиторий `content-machine`
3. Railway автоматически обнаружит `Dockerfile` и начнёт сборку

---

## Шаг 4: Добавить PostgreSQL

1. В Railway-проекте → **New** → **Database** → **Add PostgreSQL**
2. Railway создаст PostgreSQL и даст переменную `DATABASE_URL`
3. Нажми на PostgreSQL сервис → **Data** → скопируй `DATABASE_URL`

Формат будет примерно такой:
```
postgresql://postgres:PASSWORD@HOST:PORT/railway
```

---

## Шаг 5: Настроить переменные окружения

В Railway → твой сервис (app) → **Variables** → добавь:

```env
# AI APIs
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-api03-...
PERPLEXITY_API_KEY=pplx-...

# Database (из Railway PostgreSQL)
POSTGRES_HOST=<host из DATABASE_URL>
POSTGRES_PORT=<port из DATABASE_URL>
POSTGRES_DB=railway
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<password из DATABASE_URL>

# Content
NICHES=gym discipline,engineer life,coding mindset,football motivation
MIN_VIEWS=500000
MAX_DURATION=30
POSTS_PER_DAY=5
LOG_LEVEL=INFO
```

> **Лайфхак:** Railway позволяет использовать Reference Variables. Если PostgreSQL в том же проекте, можно ссылаться на `${{Postgres.PGHOST}}` и т.д.

---

## Шаг 6: Инициализировать БД

Нажми на PostgreSQL сервис → **Query** → вставь содержимое `database/schema.sql` и выполни.

Или через терминал Railway:

```bash
# Установи Railway CLI
npm install -g @railway/cli

# Логин
railway login

# Подключись к проекту
railway link

# Выполни schema.sql
railway run psql $DATABASE_URL -f database/schema.sql
```

---

## Шаг 7: Проверить деплой

После деплоя Railway даст URL, например: `content-machine-production.up.railway.app`

```bash
curl https://content-machine-production.up.railway.app/health
# {"status":"healthy","service":"content-machine"}

curl https://content-machine-production.up.railway.app/status
# {"pipeline_status":{...},"total_videos":0}
```

---

## Шаг 8: Настроить CRON (вместо n8n)

Railway **не поддерживает** n8n как отдельный сервис в бесплатном плане (нужно больше RAM). Вместо этого используй **Railway Cron Jobs** или встроенный CRON в Python.

В проект уже встроен APScheduler. Добавь запуск через переменную:

В Railway Variables добавь:
```env
RUN_MODE=scheduler
```

Railway запустит `api_server.py`, который и так включает API + может запускать CRON через APScheduler.

---

## Шаг 9: Привязать домен (опционально)

1. В Railway → твой сервис → **Settings** → **Domains**
2. Нажми **Custom Domain** → введи `api.namazbek.dev`
3. Railway покажет CNAME запись → добавь её на Name.com:

```
Type: CNAME
Host: api
Answer: content-machine-production.up.railway.app
TTL: 300
```

---

## Шаг 10: Управление

```bash
# Установить CLI
npm install -g @railway/cli

# Логин
railway login

# Привязать проект
railway link

# Посмотреть логи
railway logs

# Запустить команду на сервере
railway run python main.py discover
railway run python main.py run-pipeline --limit 2

# Подключиться к БД
railway run psql $DATABASE_URL
```

---

## Бюджет Railway

| Компонент | Стоимость |
|---|---|
| App (Docker) | ~$3-5/мес |
| PostgreSQL | ~$1-2/мес |
| **Student Pack кредит** | **-$5/мес** |
| OpenAI / Anthropic API | ~$2-5/мес |
| **Итого к оплате** | **~$2-5/мес** (только API) |

---

## Ограничения Railway Free

- 500 часов выполнения в месяц (~20 дней нон-стоп)
- 512MB RAM (хватит для API + лёгкой обработки)
- Нет n8n (вместо него — CLI через `railway run` или APScheduler)
- Playwright **может не работать** на Railway из-за ограничений RAM (512MB мало для Chromium)

### Обход ограничения Playwright:
Загрузку видео (upload) лучше делать **локально со своего Mac**, а остальной пайплайн (поиск трендов, скачивание, обработка, генерация подписей) — на Railway:

```bash
# На Railway (автоматически):
# discover → find → download → process → generate-captions

# На своём Mac (вручную раз в день):
railway run python main.py upload --platform tiktok --limit 3
```
