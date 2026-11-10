# Подбор инструментов по задаче

Это выбранные официальные upstream-проекты, проверенные 6 ноября 2026. Используй их по стеку и пробелу в покрытии; список не требует устанавливать или запускать всё. Фиксируй реально установленную версию, поддерживаемую платформу и выполненные команды. Наличие ссылки здесь не означает, что инструмент установлен.

| Задача | Официальный проект | Как применять |
|---|---|---|
| Web E2E, API, trace и visual regression | [microsoft/playwright](https://github.com/microsoft/playwright), [Test Agents](https://playwright.dev/docs/test-agents) | Planner исследует сценарии, generator пишет тесты, healer разбирает сбои. Проверяй пользовательский результат; различай offline fixture и авторизованный стенд. |
| Доступность UI | [dequelabs/axe-core](https://github.com/dequelabs/axe-core) | Дополнение к Playwright для нарушений доступности. Автоматическая проверка не заменяет клавиатуру, фокус и визуальную оценку. |
| Поиск подозрительных паттернов и вариантов бага | [semgrep/semgrep](https://github.com/semgrep/semgrep) | Выбирай поддерживаемые языки и релевантные правила. Валидируй достижимость; PowerShell проверяй отдельно. |
| Секреты в исходниках и истории | [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) | Редактируй значения в выводе, проверяй scope и ложные совпадения; хеш манифеста не считать паролем. |
| PowerShell: поведение и статический анализ | [pester/Pester](https://github.com/pester/Pester), [PowerShell/PSScriptAnalyzer](https://github.com/PowerShell/PSScriptAnalyzer) | Pester для контрактов/ошибок/mocks, анализатор для языка. Нативные права, задачи и UAC проверяй на Windows. |
| PHP/Laravel: типы и исполнение | [phpstan/phpstan](https://github.com/phpstan/phpstan), [larastan/larastan](https://github.com/larastan/larastan), [PHPUnit](https://github.com/sebastianbergmann/phpunit) | Сначала используй настройки и тесты проекта; Laravel требует подходящей версии расширения. Не скрывай новые ошибки расширением baseline без разбора. |
| Python: регрессии и сложные входы | [pytest-dev/pytest](https://github.com/pytest-dev/pytest), [HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis) | pytest для воспроизведения; Hypothesis для Unicode, сериализации, диапазонов и инвариантов с сохраняемым минимальным примером. |
| JS/TS: генерация граничных случаев | [dubzzz/fast-check](https://github.com/dubzzz/fast-check) | Дополнение к существующему test runner для парсеров и моделей состояния. Сохраняй seed и уменьшенный пример. |
| Уязвимости зависимостей | [npm audit](https://docs.npmjs.com/cli/v11/commands/npm-audit/), [Composer audit](https://getcomposer.org/doc/03-cli.md#audit), [google/osv-scanner](https://github.com/google/osv-scanner) | Сканируй фактический lock/SBOM. Разделяй runtime/build/dev и версионное совпадение/доказанный путь. Целевой патч проверяй сборкой и регрессиями. |
| Динамическая проверка web | [zaproxy/zaproxy](https://github.com/zaproxy/zaproxy) | Укажи выбранный стенд, контекст и границы. Активный scan может менять данные; выполняй только в разрешённой среде с контролируемой тестовой записью. |

Предпочитай существующий инструмент репозитория эквиваленту из таблицы. Если нужна новая зависимость, бери официальный release/package, проверь актуальные требования и release notes, фиксируй версию и сохраняй воспроизводимый lock. Не импортируй чужой набор инструкций, сборку или бинарник только по популярности репозитория; не запускай скачанный shell-скрипт вслепую.
