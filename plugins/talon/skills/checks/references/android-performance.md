# Производительность Android на устройстве

Выбери пользовательское действие в установленном Android-приложении, для которого нужно измерить задержку отрисовки или память. Зафиксируй версию сборки, модель и Android API, частоту дисплея, данные, способ запуска и количество повторов. Для подтверждения регрессии сравнивай базовую и текущую версии на одном физическом устройстве в сопоставимом состоянии. Эмулятор подходит для проверки сценария и сбора артефактов.

1. В `adb devices -l` найди серийный номер тестового устройства со статусом `device`. Запусти установленное приложение и перейди в исходное состояние. [Android Debug Bridge](https://developer.android.com/tools/adb).
2. Из каталога с [capture.sh](../assets/android-performance/capture.sh) и [frames.pbtxt](../assets/android-performance/frames.pbtxt) запусти команду с выбранными номером и пакетом. Сборщик требует Android 12 (API 31) или новее для FrameTimeline. На выделенном тестовом устройстве он сбрасывает счётчики `gfxinfo` выбранного пакета, снимает `meminfo` до и после записи и сохраняет `framestats` после неё. Укажи абсолютный путь через `ADB`, если Platform-Tools находятся вне `PATH`. [Android dumpsys](https://developer.android.com/tools/dumpsys), [Perfetto FrameTimeline](https://perfetto.dev/docs/data-sources/frametimeline).

   ```sh
   adb devices -l
   sh capture.sh "$android_serial" "$android_package"
   ```

3. После сообщения о начале сбора выполни действие в течение 15 секунд. Используй одинаковую последовательность и продолжительность в каждом повторе. По завершении открой `trace.perfetto-trace` локально в Perfetto UI или Trace Processor. В системной трассе могут быть сведения о других процессах, поэтому сохраняй артефакты в рабочей среде проекта. Убедись, что для нужного процесса и интервала действительно есть кадры и события. [Perfetto CLI](https://perfetto.dev/docs/reference/perfetto-cli), [Анализ трасс Android](https://perfetto.dev/docs/getting-started/android-trace-analysis).
4. Для рывка сравни число и долю кадров с jank на дорожке FrameTimeline и сопоставь их с UI thread, RenderThread или SurfaceFlinger. В `framestats` зафиксируй процесс, окно и число валидных строк. Для длительности обычных кадров HWUI используй разницу между `FrameCompleted` и `IntendedVsync`, преобразуй наносекунды в миллисекунды и явно укажи фильтр `Flags=0`. Ориентируйся на дедлайн кадра и частоту дисплея. Для сравнения памяти выпиши `TOTAL PSS` в КБ по одному и тому же набору процессов и учитывай прогрев, фоновые процессы и сборку мусора. Два замера описывают изменение за прогон. [Android dumpsys](https://developer.android.com/tools/dumpsys), [Android FrameTimeline](https://perfetto.dev/docs/data-sources/frametimeline).

Зафиксируй число повторов, диапазон результата и условия каждого прогона. Если обнаружен троттлинг, исчез нужный процесс, отсутствуют кадры или трасса потеряла события, отметь неполный прогон. Для регулярного порога в CI используй Macrobenchmark на совместимой тестовой среде. [Android Macrobenchmark](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-overview).

На macOS ADB 37.0.3 запустился и вернул пустой список устройств. На локальной фикстуре прошли сбор и проверка артефактов, отказ при пустой трассе и остановка на старом API. Protobuf-парсер прочитал конфигурацию длительностью 15 секунд и три источника по схеме Perfetto `TraceConfig`. Для оценки кадров и памяти нужна запись с Android-устройства. [Схема конфигурации Perfetto](https://perfetto.dev/docs/reference/trace-config-proto).
