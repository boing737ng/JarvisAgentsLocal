# 🤖 Jarvis — Local Multi-Agent AI System

Полностью локальная мультиагентная AI-система на базе Ollama. Работает без интернета, без облаков, без API-ключей.

## Быстрый старт

```bash
cd C:\Users\Nikolya\Documents\vibecoding\Jarvis
.venv\Scripts\python.exe run.py
```

## Как запустить

```bash
# Обычный запуск
.venv\Scripts\python.exe run.py

# С подробными логами (для отладки)
.venv\Scripts\python.exe run.py --log-level INFO

# Без ASCII-баннера
.venv\Scripts\python.exe run.py --no-banner
```

## Slash-команды в REPL

| Команда | Действие |
|---|---|
| `/agents` | Показать всех агентов, модели, что сейчас в RAM |
| `/memory query <текст>` | Поиск в долгосрочной памяти |
| `/memory add <текст>` | Сохранить факт в памяти |
| `/image <путь>` | Анализ изображения (Visionary) |
| `/unload` | Выгрузить все модели из RAM |
| `/reset` | Сбросить историю разговора |
| `/help` | Помощь |
| `/quit` | Выйти |

## Архитектура под капотом

```
Пользователь
     │
     ▼
┌─────────────┐   JSON routing
│ Orchestrator│──────────────────┐
│ llama3.1:8b │                  │
└─────────────┘     ┌────────────┼──────────────────────────┐
                    ▼            ▼            ▼              ▼
             ┌──────────┐ ┌──────────┐ ┌─────────┐  ┌──────────────┐
             │  Coder   │ │Architect │ │ Parser  │  │ Grandmaster  │
             │qwen2.5-  │ │deepseek- │ │qwen2.5: │  │qwen3.5:27b   │
             │coder:7b  │ │r1:14b    │ │0.5b     │  │(тяжёлый)     │
             └────┬─────┘ └──────────┘ └─────────┘  └──────────────┘
                  │
                  ▼
          ┌──────────────┐
          │Docker Sandbox│  ← изолированный контейнер
          │ (no network, │    python:3.12-slim
          │ read-only FS)│    1GB RAM limit
          └──────────────┘

Инструменты: Web Search (DuckDuckGo) → Web Fetch (httpx+trafilatura) → Parser
Память: ChromaDB + nomic-embed-text-v2-moe (эмбеддинги)
```

### Управление памятью RAM (главная фича!)

Система строго следит чтобы в RAM не было двух тяжёлых моделей:
- Перед загрузкой тяжёлой модели (deepseek-r1, qwen3.5:27b) — выгружается предыдущая через `keep_alive=0`
- Лёгкие модели (оркестратор, парсер) кэшируются в RAM (`keep_alive=5m`)
- Просмотр текущего состояния: `/agents` → "Currently in RAM"

### Маршрутизация

Оркестратор (`llama3.1:8b`) решает что делать:
- `respond` → отвечает сам (простые вопросы)
- `code` → Coder пишет Python → Docker sandbox выполняет → auto-fix на ошибках
- `research` → DuckDuckGo → fetch страниц → Parser сжимает → Orchestrator резюмирует  
- `plan` → Architect составляет алгоритм (deepseek-r1)
- `recall` → ChromaDB поиск по памяти
- `vision` → Visionary анализирует изображение
- `finalize` → Grandmaster (qwen3.5:27b) делает глубокий анализ

## Конфигурация

- `config/settings.yaml` — URL Ollama, лимиты Docker, параметры памяти
- `config/agents.yaml` — какая модель, keep_alive, температура для каждого агента
- `config/prompts/*.md` — системные промпты агентов

## Структура файлов

```
Jarvis/
├── config/           ← YAML конфиги + промпты
├── jarvis/
│   ├── core/         ← config, model_manager, state
│   ├── agents/       ← все 7 агентов
│   ├── tools/        ← web_search, docker_exec, memory, files
│   ├── memory/       ← ChromaDB store
│   ├── graph.py      ← LangGraph StateGraph
│   └── cli.py        ← Rich REPL
├── workspace/        ← файлы доступные агентам (и Docker sandbox)
├── data/chroma/      ← векторная БД (персистентная)
├── docker/           ← Dockerfile для sandbox
└── run.py            ← точка входа
```
