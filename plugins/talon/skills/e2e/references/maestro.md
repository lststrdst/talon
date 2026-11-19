# Maestro · мобильные E2E

Используй установленную версию Maestro и существующие Flow проекта. Maestro CLI требует Java 17+. Сверь `java -version` для выбранного рантайма, версию CLI и доступные параметры `test --help`. Если Maestro отсутствует в `PATH`, проверь, подготовлена ли локальная обёртка Talon `"$HOME/.local/share/talon/bin/maestro"` со своей Java. Для разовой установки скачай закреплённый `maestro.zip` из официального репозитория, сверь опубликованную SHA-256 и распакуй архив во временный каталог. [Установка](https://docs.maestro.dev/maestro-cli/how-to-install-maestro-cli) · [Релизы](https://github.com/mobile-dev-inc/Maestro/releases)

## Целевое устройство и сборка

- **Android**. Выбери запущенный эмулятор или подключённое тестовое устройство через `adb devices -l`. Установи APK проекта через `adb -s "$device_id" install -r "$apk"`. В `appId` передай Android `applicationId` этой сборки.
- **iOS**. Используй macOS с Xcode, запущенный симулятор и собранный для симулятора `.app`. Сверь UUID через `xcrun simctl list devices booted`. Установи приложение через `xcrun simctl install "$device_id" "$app_bundle"`. В `appId` передай `CFBundleIdentifier` этой сборки.

Указывай `--device` перед `test`, чтобы запуск относился к выбранному экземпляру. Зафиксируй модель, версию ОС или API, идентификатор приложения и ревизию или номер сборки. Используй тестовую учётную запись и изолированное состояние. Сброс данных через `clearState` добавляй на одноразовом устройстве, если сценарию нужен чистый запуск. Если проверяешь системные разрешения, укажи их явно в `launchApp.permissions`. [Выбор устройства](https://docs.maestro.dev/maestro-flows/flow-control-and-logic/specify-and-start-devices) · [Параметры запуска](https://docs.maestro.dev/reference/commands-available/launchapp)

## Flow и запуск

Открой нужный экран и проверь селектор в `maestro --device "$device_id" hierarchy`. Используй устойчивый `id` для действий и проверяй наблюдаемый результат. Подставь идентификатор приложения, селектор и ожидаемый текст по контракту проекта. [Структура Flow](https://docs.maestro.dev/maestro-flows) · [Селекторы](https://docs.maestro.dev/reference/selectors/core-selectors)

```yaml
appId: ${APP_ID}
name: Завершение действия
---
- launchApp
- tapOn:
    id: continue_button
- assertVisible: "Готово"
```

Задай `flow` путём к YAML и `app_id` идентификатором установленной сборки. При локальной установке укажи в `maestro_cli` абсолютный путь к CLI. Создавай свежий каталог для каждого прогона.

```bash
maestro_cli=maestro
artifacts=$(mktemp -d "${TMPDIR:-/tmp}/talon-maestro.XXXXXXXX")
"$maestro_cli" --device "$device_id" test \
  --env "APP_ID=$app_id" \
  --format junit --output "$artifacts/junit.xml" \
  --debug-output "$artifacts" --test-output-dir "$artifacts" \
  "$flow"
```

## Подтверждение результата

Запиши код возврата, число выполненных сценариев и исход проверки, сопоставив их со свежим JUnit. Для автоматической сверки вызови Maestro через `verify.py --junit` по [сценарию Checks](../../checks/SKILL.md), передав тот же путь в `--junit` и `--output`. При падении приведи шаг и наблюдаемый результат со ссылкой на отчёт, лог или скриншот. Если раннер остановился до начала сценария, укажи причину и оставь сценарий неподтверждённым. [Параметры CLI](https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options) · [Отчёты и артефакты](https://docs.maestro.dev/maestro-flows/workspace-management/test-reports-and-artifacts)

Если на iOS истёк таймаут старта XCUITest, сверь время загрузки симулятора и запуска драйвера по журналу. При подтверждённом долгом старте увеличь `MAESTRO_DRIVER_STARTUP_TIMEOUT` в миллисекундах для повтора и выдели свежий каталог отчёта. [Переменные Maestro](https://docs.maestro.dev/maestro-cli/environment-variables)
