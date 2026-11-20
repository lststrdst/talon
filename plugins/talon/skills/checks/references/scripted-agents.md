# Проверка оркестрации OpenAI Agents SDK через ScriptedModel

Используй, когда проект на OpenAI Agents SDK должен выполнять инструменты в определённом порядке, передавать результаты между ходами, соблюдать guardrails или обрабатывать ошибку модели. Подключи `ScriptedModel` из `agents.testing` к штатной точке запуска агента. Собери инструменты на тестовых данных, а внешние зависимости подключи через проектные фикстуры. Выключи трассировку через `RunConfig(tracing_disabled=True)`. [Документация SDK v0.25.0](https://github.com/openai/openai-agents-python/blob/v0.25.0/docs/testing.md).

1. Опиши один ожидаемый ответ на каждый вызов модели. Используй `function_call()` для вызова инструмента, `assistant_message()` для ответа и `ModelStep.respond()` для проверки результата предыдущего инструмента в следующем запросе.
2. Выполни `Runner.run()` и проверь последовательность вызовов, аргументы, `call_id`, нормализованный `function_call_output`, итоговый ответ и наблюдаемое состояние фикстуры. Проверь `model.assert_complete()`, чтобы обнаружить преждевременный выход. Запусти отдельный случай с лишним или отсутствующим шагом, чтобы подтвердить чувствительность теста.
3. Запиши версию SDK, использованный раннер и границу проверки. Поведение реальной модели, протокол провайдера и фактическую работу внешних инструментов подтверждай отдельным интеграционным тестом. [API `agents.testing`](https://openai.github.io/openai-agents-python/ref/testing/).

## Офлайн-пример

[test_tool_sequence.py](../assets/scripted-agents/test_tool_sequence.py) проверяет два последовательных инструмента поиска и резервирования тестового слота, оба результата на входе в модель и два отказа при лишних или неиспользованных шагах. Для проекта используй его закреплённую версию SDK с доступным `agents.testing`. Для воспроизведения примера под Python 3.10 или новее установи SDK в отдельное окружение. [Релиз PyPI](https://pypi.org/project/openai-agents/0.25.0/).

```sh
talon_agents=$(mktemp -d)
python3 -m venv "$talon_agents/env"
"$talon_agents/env/bin/python" -m pip install 'openai-agents==0.25.0'
env -u OPENAI_API_KEY -u OPENAI_AGENTS_TRACE_API_KEY \
  "$talon_agents/env/bin/python" test_tool_sequence.py -v
```

На Python 3.12 и `openai-agents 0.25.0` прошли все три теста. Для запуска использовались реальные `Runner` и SDK-инструменты, локальные данные и модель из `agents.testing`.
