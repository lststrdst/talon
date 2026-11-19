# Браузерные проверки

Запусти целевой сценарий штатным Playwright-раннером на тестовом стенде. Укажи сборку, браузерный проект, роль и исходное состояние. Привяжи каждое действие к наблюдаемому результату. Если состояние должно сохраниться, проверь его после повторного открытия страницы.

## Отчёт и trace

Сохрани полный JUnit с числом выполненных, упавших и пропущенных тестов. Включи trace для первого повтора на CI или для упавшего теста при запуске без повторов. Сначала прочитай сводку прогона, затем открой нужный trace из HTML-отчёта, чтобы проверить действие, состояние DOM, сеть или консоль. Укажи flaky-результаты отдельно. Playwright может считать сценарий прошедшим после успешного повтора. [Отчёты Playwright](https://playwright.dev/docs/test-reporters) · [Trace Viewer](https://playwright.dev/docs/trace-viewer-intro) · [Повторы](https://playwright.dev/docs/test-retries)

Используй репортёры и пути проекта, если они уже настроены. Для разового прогона в POSIX shell подставь реальный тест и задай `talon_verify` абсолютным путём к `verify.py`, как указано в навыке. Отдельный каталог привязывает отчёт и trace к этому запуску.

```sh
talon_run_dir="$(mktemp -d)" || exit 1
PLAYWRIGHT_JUNIT_OUTPUT_FILE="$talon_run_dir/results.xml" \
  PLAYWRIGHT_HTML_OUTPUT_DIR="$talon_run_dir/html" PLAYWRIGHT_HTML_OPEN=never \
  python3 "$talon_verify" --label browser --junit "$talon_run_dir/results.xml" \
  -- npx --no-install playwright test tests/checkout.spec.ts \
    --reporter=junit,html --trace=retain-on-failure --output="$talon_run_dir/test-results"
```

Сообщи фактическую команду, статус и число выполненных тестов, существенные пропуски и путь к артефактам. Публикуй очищенные выдержки из trace и логов. Если проект уже выпускает сырые результаты Allure и установлен Allure 3.12+, `allure agent inspect <каталог-результатов>` создаст индекс для анализа пропусков и повторов из существующего прогона. [Allure Agent Mode](https://allurereport.org/docs/agent-mode/)

## Создание и исправление тестов

Для нового покрытия передай planner целевой сценарий, исходную фикстуру или seed и ожидаемый результат. Generator связывает пункты плана с тестами и проверяет локаторы на стенде. Healer начинает с фактического падения, проверяет причину по trace и предлагает правку теста, если нарушилась его привязка к интерфейсу или окружению. Сверь итоговый diff с исходными ожиданиями. Ослабленная проверка и добавленный skip или fixme оставляют сценарий неподтверждённым. Если trace показывает нарушение требований продукта, зафиксируй дефект и повтори исходную проверку после исправления. [Playwright Test Agents](https://playwright.dev/docs/test-agents)

Для короткого исследования интерфейса используй доступный браузерный инструмент. Если в среде уже есть Playwright CLI, читай снимок нужного элемента или ограничивай глубину. Доступный `agent-browser` поддерживает компактный снимок интерактивных элементов и снимок конкретной области. Скриншот добавляй, когда доказательство зависит от внешнего вида. [Playwright CLI](https://github.com/microsoft/playwright-cli#snapshots) · [agent-browser](https://github.com/vercel-labs/agent-browser/blob/main/skill-data/core/references/snapshot-refs.md)
