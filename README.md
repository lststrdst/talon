# Talon

Плагин для Codex, который помогает разработать функцию, проверить результат и подготовить запуск.

```text
$talon:go Добавь экспорт отчёта в CSV и проверь, что он работает с кириллицей и доступен только нужным ролям.
```

Можно выбрать `@Talon` в чате и описать задачу своими словами. Для явного вызова навыка выбора режима используй `$talon:go`.

## Установка

```sh
codex plugin marketplace add https://github.com/lststrdst/talon.git
codex plugin add talon@talon-marketplace
```

Откройте новый чат Codex в нужном проекте. Для обновления сначала выполните `codex plugin marketplace upgrade talon-marketplace`, затем повторите команду установки плагина.

Для ChatGPT в браузере скачайте [ZIP-архив Talon](https://github.com/lststrdst/talon/raw/refs/heads/main/releases/Talon-2.2.0-web.zip) и выберите «Плагины → Добавить → Загрузить архив плагина». Архив содержит пять навыков Talon. Разработчик — `lststrdst`.

## Режимы

- **Разработка** `$talon:build` — спланировать и сделать новую функцию или изменить существующую.
- **Тестирование** `$talon:qa` — проверить то, что уже работает, найти и по запросу исправить баг.
- **Запуск** `$talon:launch` — выбрать аудиторию и канал, подготовить анонс или пилот.
- **Проверка безопасности** `$talon:security` — подготовить проверку веб-приложения или API. Активные проверки через Strix выполняются по явному поручению на разрешённой цели.

<details>
<summary>Подключить именованных QA-агентов</summary>

Шесть профилей помогают разделить диагностику, браузерные проверки, API, Windows, исправление и независимое ревью.

```sh
git clone https://github.com/lststrdst/talon.git
cd talon
talon_profiles="$HOME/.codex/agents"
mkdir -p "$talon_profiles"
for profile in plugins/talon/agent-profiles/*.toml; do
  target="$talon_profiles/${profile##*/}"
  if [ ! -e "$target" ] && [ ! -L "$target" ]; then
    cp -n "$profile" "$target"
  fi
done
```

Откройте новый чат. Для установки ролей только в одном проекте скопируйте профили в его `.codex/agents/`. [Документация Codex](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents)

</details>

<details>
<summary>Дополнительные инструменты</summary>

Устанавливаются отдельно и используются по задаче.

- **ECC** дополняет Talon практиками для API, миграций БД, тестов, релизов, продвижения и ревью безопасности. Установите `codex plugin add ecc@talon-marketplace`, затем в новом чате попросите `@Talon Спланируй миграцию БД без простоя с ECC`. Если ECC уже установлен из собственного каталога, используйте эту установку. [ECC для Codex](https://github.com/affaan-m/ECC/blob/v2.2.3/.codex-plugin/README.md)
- **OpenAI Plugin Eval** проверяет структуру навыков и манифест плагина Codex. В репозитории Talon можно попросить `$talon:go Оцени этот плагин через Plugin Eval`. [Установка CLI](https://github.com/openai/plugins/blob/main/plugins/plugin-eval/README.md#install-as-a-cli-tool)
- **Vercel Agent Desktop** помогает QA проверить окна, меню и системные диалоги нативного приложения. Если CLI уже установлен, укажите Talon тестовое приложение и нужный сценарий. [Установка и права доступа](https://github.com/vercel-labs/agent-desktop/blob/main/docs/install.md)
- **Graphify** строит карту связей в исходном коде. [Документация](https://docs.graphify.com/open-source/configuration/cli)
- **Agent Reach** помогает найти публичные обсуждения для исследования аудитории. [Репозиторий](https://github.com/Panniantong/Agent-Reach)
- **Strix** запускает активную проверку безопасности. Для локального запуска нужны Docker и настроенная модель. [Документация](https://docs.strix.ai/quickstart)

</details>
