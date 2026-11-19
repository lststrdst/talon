# Talon для агентских рантаймов

Пакет добавляет разбор репозитория, реализацию фич, работу с Python, PowerShell, Linux, Windows Server, удалённым доступом и QA. Общий навык `talon` работает с инструментами выбранного рантайма и выдаёт задачи исследователю, исполнителю, QA или ревьюеру по мере необходимости. Модель, делегирование и доступ к серверу определяет конфигурация рантайма.

В обычной задаче попросите «Напиши Python-скрипт, прогони его на тестовых данных и покажи результат». Для сервера укажите доступный SSH-алиас и нужный объект, например службу или задачу. В комплекте есть помощник `scripts/verify.py` для локального прогона с кодом завершения, ожидаемым выводом и таймаутом.

## Подключение к проекту

1. Распакуй архив и скопируй каталоги из `skills/` в `.agents/skills/` корня проекта. Помимо `.agents/skills/talon/SKILL.md` появятся пять навыков `harness-*`. При обновлении замени эти каталоги свежими копиями, сохранив свои изменения при необходимости.
2. Добавь подходящие правила из `PROJECT-RULES.md` в действующий файл инструкций проекта для автоматического выбора Talon. Когда Talon выбран, память включена по умолчанию. Она хранится в `.agents/talon/learned.md` или в `.talon/learned.md`, если `.agents/` защищён. Отключение можно указать правилами проекта или в задаче.
3. Открой проект в своём рантайме и начни новую сессию. Пробный запрос — «Используй навык talon. Покажи, где начинается установка в этом проекте и как проверить повторный запуск. Только разбор».

| Рантайм | Как подхватывает навык |
| --- | --- |
| Hermes Agent | Стартуй в Git-проекте и доверь ему загрузку локальных навыков через `hermes skills trust`, если проект ещё не доверен. [Навыки Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills#project-local-skills) |
| OpenCode | Запусти из каталога проекта. В OpenCode 2 можно явно выбрать `@talon`. В OpenCode 1 используй `/talon`, если имя свободно. [OpenCode 2](https://opencode.ai/docs/skills/) · [OpenCode 1](https://github.com/anomalyco/opencode/blob/v1.19.6/packages/web/src/content/docs/skills.mdx) |
| OpenClaw | Помести навык в рабочую папку агента или сессии. Проверь его через `openclaw skills list` и вызови через `/skill talon`. Одноимённый навык в `skills/` имеет приоритет. [Навыки OpenClaw](https://docs.openclaw.ai/tools/skills) |
| Pi | Открой доверенный проект и вызови `/skill:talon`. Роль ревьюера можно выполнить в текущей сессии. При уже настроенном делегировании используй имеющиеся подагенты. [Навыки Pi](https://docs.pi.dev/latest/skills) |
| DeepSeek Harness | Открой проект как рабочую папку с файловыми навыками и вызови `/talon` с задачей. Одноимённый навык в `.dsh/skills/` имеет приоритет. [Файловые навыки и приоритет](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/packages/skill/skill-filesystem/README.md#roots-and-priority) · [Вызов навыка](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/packages/client/ui-skill/README.md#use-this-package) |

Распакованный пакет также содержит стандартный `plugin.json` формата Agent Plugins. Hermes Agent и OpenClaw с поддержкой этого формата могут загружать каталог как пакет навыков. Для памяти и правил конкретного проекта используй настройку выше. [Agent Plugins](https://agent-plugins.org/specification) · [Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins#portable-agent-plugins-v1-packages) · [OpenClaw](https://docs.openclaw.ai/plugins/bundles)
