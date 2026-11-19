<p align="center">
  <img src="plugins/talon/assets/talon.png" alt="Иконка Talon" width="112" height="112" />
</p>

<h1 align="center">Talon</h1>

Плагин для ChatGPT и Codex, который помогает спроектировать интерфейс, разработать функцию, проверить результат и подготовить запуск.

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

Для ChatGPT в браузере скачайте [веб-архив Talon 2.6.0](https://github.com/lststrdst/talon/raw/refs/tags/v2.6.0/releases/Talon-2.6.0-web.zip) и выберите «Плагины → Добавить → Загрузить архив плагина». Архив содержит семь навыков, скрипты и каталог UI/UX Pro Max. Разработчик — `lststrdst`.

Для Hermes Agent, OpenCode, OpenClaw, Pi и DeepSeek Harness скачайте [Talon для агентских рантаймов](https://github.com/lststrdst/talon/raw/refs/tags/v2.6.0/releases/Talon-2.6.0-agents.zip). Навык разработки, Python, PowerShell, серверного администрирования и QA подключается к проекту через `.agents/skills/`. В архиве есть инструкция для каждого рантайма и готовый блок для `AGENTS.md`.

Чтобы Talon запоминал проверенные решения, попросите включить память в конкретном проекте или добавьте правила из `PROJECT-RULES.md`. Записи в `.agents/talon/learned.md` дают следующей сессии рабочие команды проверки и условия, при которых они пригодились.

Для обычных задач Talon использует модель основного чата. Для новых обычных подагентов Talon выбирает GPT-6.2 Sol Ultra, для сложного этапа — GPT-6.2 Astra Extra High, если среда поддерживает выбор модели подагента. Повторное поручение сохраняет модель агента. Talon сверяет её перед повторным использованием. В локальном Codex также доступен профиль `talon-astra` из инструкции ниже.

## Режимы

- **Разработка** `$talon:build` — понять, как устроен код, определить, где добавить функцию, и довести её до проверенного результата. Для PowerShell Talon учитывает скрипты, модули, совместимость версий и запуск на Windows.
- **Дизайн** `$talon:design` — продумать экраны, компоненты, цвета, типографику, адаптивность и доступность через UI/UX Pro Max. Локальный поиск требует Python 3.
- **Тестирование** `$talon:qa` — проверить то, что уже работает, найти и по запросу исправить баг.
- **Запуск** `$talon:launch` — выбрать аудиторию и канал, подготовить анонс или пилот.
- **Проверка безопасности** `$talon:security` — оценить защиту по коду и конфигурации и составить план исправлений.
- **Подбор навыков** `$talon:autoskills` — подключить подходящий навык при конкретном пробеле в текущей задаче. Talon сначала использует доступные навыки, затем при необходимости показывает до трёх кандидатов. При разрешённой автоматической установке готовит один выбранный набор в отдельном кэше и применяет его сразу. Для помощника нужны Node.js 22.6+ и autoskills 0.4.1.

В Build можно попросить написать Python-скрипт и прогнать его на тестовых данных или разобраться со службой на Windows Server, Ubuntu или Debian. Для удалённой работы укажите доступный SSH-алиас или настроенный WinRM. Talon сверит состояние, выполнит запрошенные проверки и покажет наблюдаемый результат. Для короткой проверки по коду выхода и ожидаемому выводу в пакет включён `verify.py`.

Для автоматического подключения достаточно один раз разрешить его в чате или инструкциях проекта. Обычная задача ограничена двумя новыми навыками, а результаты подбора и загрузки используются повторно. Без CLI Talon даёт рекомендацию по файлам проекта. Постоянная установка в проект выполняется по отдельному запросу.

UI/UX Pro Max включён с исходной лицензией MIT. Autoskills подключён как отдельный CLI версии 0.4.1 и распространяется по CC BY-NC 4.0. [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) · [Autoskills](https://github.com/midudev/autoskills)

<details>
<summary>Подключить профили QA и Astra</summary>

Семь профилей помогают разделить диагностику, браузерные проверки, API, Windows, Linux и SSH, исправление и независимое ревью. Для сложного этапа `talon-astra` закрепляет GPT-6.2 Astra.

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

Если `talon-astra` уже установлен, для уровня Extra High обновите в его TOML `model_reasoning_effort` до `"xhigh"`.

</details>

<details>
<summary>Дополнительные инструменты</summary>

Устанавливаются отдельно и используются по задаче.

- **ECC** дополняет Talon практиками для API, миграций БД, тестов, релизов, продвижения и ревью безопасности. Установите `codex plugin add ecc@talon-marketplace`, затем в новом чате попросите `@Talon Спланируй миграцию БД без простоя с ECC`. Если ECC уже установлен из собственного каталога, используйте эту установку. [ECC для Codex](https://github.com/affaan-m/ECC/blob/v2.2.3/.codex-plugin/README.md)
- **OpenAI Plugin Eval** проверяет структуру навыков и манифест плагина Codex. В репозитории Talon можно попросить `$talon:go Оцени этот плагин через Plugin Eval`. [Установка CLI](https://github.com/openai/plugins/blob/main/plugins/plugin-eval/README.md#install-as-a-cli-tool)
- **Vercel Agent Desktop** помогает QA проверить окна, меню и системные диалоги нативного приложения. Если CLI уже установлен, укажите Talon тестовое приложение и нужный сценарий. [Установка и права доступа](https://github.com/vercel-labs/agent-desktop/blob/main/docs/install.md)
- **Graphify** строит карту связей в исходном коде. [Документация](https://docs.graphify.com/open-source/configuration/cli)
- **Agent Reach** помогает найти публичные обсуждения для исследования аудитории. [Репозиторий](https://github.com/Panniantong/Agent-Reach)

</details>
