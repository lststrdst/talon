# Публичные обсуждения Reddit

Начни с обычного веб-поиска. Укажи сообщество и наблюдаемый симптом или интересующую практику, например `site:reddit.com/r/ClaudeCode "skills" "hooks" "eval"`. Для вопроса о Codex попробуй `site:reddit.com/r/codex "AGENTS.md" "skills" "MCP"`. Открой исходную ветку, проверь дату, контекст и видимые комментарии. Если есть ссылка на код или документацию, проверь её отдельно. В ответе различай найденный фрагмент, прочитанный пост и видимые комментарии.

## Запасной поиск через Agent Reach

Если встроенный поиск пропустил нужные ветки, используй установленный Agent Reach. Проверь `version` и что `channels` показывает `public_web` для Reddit `search`. В [сценарии локального запуска](../../launch/references/agent-reach.md) передай следующие аргументы после `-`.

```text
reddit search 'Claude Code agent skills hooks eval' --backend public-web --timeout 15 --limit 4
```

Agent Reach отправляет запрос поисковому провайдеру Exa. Используй общедоступные термины. При `ok: true` проверь `backend`, `items[].url` и `meta.access.scope`. `search_results` означает, что найдены ссылки. Открой нужный URL встроенным веб-инструментом и сверяй вывод по прочитанному тексту. При блокировке, требовании входа или лимите используй уже доступные источники и укажи пробел. [Возможности Agent Reach 1.6.1](https://github.com/Panniantong/Agent-Reach/blob/v1.6.1/agent_reach/skill/references/capabilities.md), [реализация публичного поиска](https://github.com/Panniantong/Agent-Reach/blob/v1.6.1/agent_reach/runtime/public_web.py).

Для отдельной интеграции оцени `reddit-mcp-buddy`, если уже есть одобренное приложение Reddit с OAuth. По умолчанию его инструменты работают на чтение. Reddit завершил приём новых заявок на публичный Data API 31 октября 2026 года. Прекращение доступа начинается 12 января 2027 года, оставшийся публичный доступ закрывается в марте 2027 года. Если Firecrawl уже доступен, его поиск может дать дополнительные ссылки. Для автоматизированного сбора данных требуется разрешение Reddit. [Reddit Data API](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki), [график миграции](https://www.reddit.com/r/redditdev/comments/1xulk8k/data_api_migration_reminder_register_your_apps/), [правила доступа](https://support.reddithelp.com/hc/en-us/articles/360043512931-Don-t-break-the-site), [reddit-mcp-buddy](https://github.com/karanb192/reddit-mcp-buddy#authentication), [поиск Firecrawl](https://docs.firecrawl.dev/features/search).

## Пример исследования

- В обсуждении настройки Claude Code автор описал хуки, добавленные после конкретных инцидентов, и случай, когда проверка пропустила все 154 записанных вердикта. Для собственного прогона проверь число обработанных записей и проверь, что заведомо сломанный вариант действительно падает. [Обсуждение хуков](https://www.reddit.com/r/ClaudeCode/comments/1w666so/my_claude_code_setup_after_7_months_of_daily_use/).
- Эксперименты с маршрутизацией навыков проверяют выбор нужного навыка и запросы, где ожидается `none`. Добавь обе группы в оценку собственного раннера и измерь долю ошибочных подключений. [Эксперимент с маршрутизатором](https://www.reddit.com/r/ClaudeCode/comments/1wqtm73/built_a_claude_code_hook_that_loads_the_right/), [эксперимент в CLI](https://www.reddit.com/r/ClaudeCode/comments/1qzjy2h/claude_code_skills_went_from_84_to_100_activation/).
