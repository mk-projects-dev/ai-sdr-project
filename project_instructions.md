# Проект: AI SDR Agent (Автономная система аутрича)

## Контекст
Мы создаем конфигурируемое B2B-приложение (Single-Tenant) для автоматизации холодных рассылок под конкретного клиента. Система устанавливается индивидуально. Она должна уметь загружать лидов из CSV, генерировать персонализированные письма с помощью Anthropic API (модель **claude-4.6-sonnet**) и обрабатывать входящие ответы. 

## Стек технологий
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (асинхронный), Pydantic.
- **Frontend:** Next.js 14 (App Router), React, TypeScript, Tailwind CSS, shadcn/ui.
- **Database:** PostgreSQL (локально через Docker).
- **AI:** Anthropic SDK (используем модель `claude-4.6-sonnet`).
- **Безопасность:** Простая JWT-авторизация для владельца инстанса (Admin), python-dotenv для секретов, CORS.

## Схема Базы Данных (PostgreSQL - Single Tenant)
Поскольку инстанс принадлежит одному клиенту, нам не нужна таблица пользователей для изоляции данных. Нужна только таблица для доступа в админку.

1. `admin`: id (UUID, PK), email (Unique), hashed_password. (Только для доступа к UI).
2. `campaigns`: id (UUID, PK), name, system_prompt, first_email_rules, follow_up_rules, status (Enum: draft, active, paused).
3. `leads`: id (UUID, PK), campaign_id (FK), email (Unique), first_name, company_name, pain_point, status (Enum: new, contacted, replied, interested, rejected), created_at.
4. `email_interactions`: id (UUID, PK), lead_id (FK), direction (Enum: outbound, inbound), subject, body, ai_intent (String, Nullable), sent_at.

## Правила написания кода (КРИТИЧНО)
1. Строгая типизация: Type Hints в Python и интерфейсы в TypeScript.
2. Безопасность: ВСЕ секреты (API ключи, SMTP доступы, URL базы) должны браться ИСКЛЮЧИТЕЛЬНО из `.env`.
3. Асинхронность: `async/await` для всех операций с БД и API Anthropic.
4. **ПРАВИЛО ГЕНЕРАЦИИ:** Выполняй проект строго по фазам. НЕ начинай следующую фазу, пока не получишь команду на продолжение.

## Roadmap (План выполнения)

### Фаза 1: Скелет, БД и Авторизация (Текущая цель)
- Создать `docker-compose.yml` для PostgreSQL.
- Настроить FastAPI с CORS и асинхронным SQLAlchemy.
- Создать `.env.example` с заглушками для ANTHROPIC_API_KEY и SMTP.
- Написать ORM-модели по схеме БД.
- Сделать эндпоинт `/api/login` для получения JWT токена админа и защищенный `/api/health`.

### Фаза 2: Frontend База
- Инициализировать Next.js (App Router).
- Настроить Tailwind и shadcn/ui.
- Создать страницу логина и базовый Layout дашборда.

### Фаза 3: Логика Кампаний и CSV
- CRUD эндпоинты для `campaigns` и `leads`.
- UI: Создание кампании (ввод промптов).
- UI: Загрузка CSV, парсинг и отправка лидов на бэкенд.

### Фаза 4: AI Агент & Email Отправка (Claude 4.6 Sonnet)
- Интеграция Anthropic SDK (`claude-4.6-sonnet`) для генерации текстов.
- Фоновая задача (Background Tasks), которая берет новых лидов, генерирует письмо и отправляет через SMTP.

### Фаза 5: Слушатель ответов (IMAP)
- Скрипт IMAP для чтения ответов клиента.
- Анализ ответа через Claude 4.6 (определение Intent) и обновление статуса лида.

---
**ИНСТРУКЦИЯ ДЛЯ AI:** Прочитай план. Начни выполнение **Фазы 1**. Выведи список файлов, которые создашь, и напиши код только для Фазы 1. После завершения остановись.