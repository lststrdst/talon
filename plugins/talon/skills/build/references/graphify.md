# Карта кода через Graphify

Используй для незнакомого модуля, плана рефакторинга и оценки влияния изменения. При обычном поиске известного файла или строки достаточно штатных средств проекта.

## Локальное построение графа

Команды проверены на официальном пакете `graphifyy` версии 0.9.105. Ищи CLI по пути `$HOME/.local/share/talon/graphify-venv/bin/graphify` или в `PATH` и проверь версию. При недоступности продолжи разбор с помощью поиска по исходникам и сообщи, каким способом получена карта.

Выбери конкретный checkout и папку исходников. Запускай из этой папки. Для смешанного рабочего дерева с архивами, ключами и служебными файлами возьми отдельную папку с нужным исходным кодом. Создай свежий приватный каталог результатов, чтобы граф относился к текущему состоянию и не наследовал записи из старого индекса.

```sh
graphify_cli="$HOME/.local/share/talon/graphify-venv/bin/graphify"
if ! test -x "$graphify_cli"; then
  graphify_cli="$(command -v graphify)" || exit 1
fi
graphify_output="$(mktemp -d)"
export GRAPHIFY_BACKEND=none GRAPHIFY_NO_AUTO_REFRESH=1
export GRAPHIFY_OUT=graphify-out GRAPHIFY_QUERY_LOG_DISABLE=1
"$graphify_cli" extract . --code-only --out "$graphify_output"
graphify_graph="$graphify_output/graphify-out/graph.json"
"$graphify_cli" explain "ИмяСимвола" --graph "$graphify_graph"
```

Пара `GRAPHIFY_BACKEND=none` и `--code-only` оставляет структурный разбор кода на машине. Для анализа связи между двумя символами используй `path`, для поиска узлов `query`, для обратных зависимостей `affected`. Передавай тот же `--graph`. Если одинаковых имён несколько, уточни символ по пути и строке.

Верни найденные точки входа, связанные файлы и кандидаты на регрессионные проверки. Сверь существенные связи с кодом, особенно метки `INFERRED`, и подтверди поведение обычным тестом. Храни граф приватно, поскольку он содержит имена и пути проекта. Установка ассистентской интеграции Graphify, автоматические хуки и внешнее семантическое извлечение требуют отдельной задачи.

[CLI Graphify](https://docs.graphify.com/open-source/configuration/cli) · [Исходники v0.9.105](https://github.com/Graphify-Labs/graphify/tree/v0.9.105)
