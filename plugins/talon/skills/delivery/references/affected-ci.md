# Затронутые компоненты и результат CI

## Выбери диапазон

1. Найди рабочий каталог, команды и обязательные задания проекта. Для PR зафиксируй SHA целевой ветки и SHA фактического checkout CI. Он может быть коммитом ветки PR, тестовым merge-коммитом или коммитом merge queue. Для ветки выпуска или основной ветки следуй принятым правилам CI. Подходящая база для накопленных изменений — последний успешный прогон тех же проверок на этой ветке, если его коммит входит в историю проверяемой ревизии. [События GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) · [Выбор базы в Nx](https://nx.dev/docs/features/ci-features/affected#configure-affected-on-ci)
2. Проверь доступность обоих коммитов и общего предка с `git merge-base "$base_sha" "$head_sha"`. Просмотри `git diff --name-status "$base_sha...$head_sha"` и сопоставь файлы с графом зависимостей проекта. Локальные изменения проверь отдельно через `git status --short`, поскольку диапазон коммитов их не включает. [git merge-base](https://git-scm.com/docs/git-merge-base) · [git diff](https://git-scm.com/docs/git-diff)
3. При неполной истории, сомнительном графе или пустом наборе вопреки diff возьми полный штатный набор для затронутой области. При изменении общих настроек, lock-файла, миграций или общей библиотеки включи проверки зависимых компонентов. Сохрани обязательные задания проекта.

## Запусти штатные цели

- **Nx.** Если проект уже использует `nx.json` и локальный Nx, сверь параметры установленной версии и объявленные цели. `nx show projects --affected --base="$base_sha" --head="$head_sha"` помогает посмотреть выборку. Запусти предусмотренные цели, например `nx affected -t lint test build --base="$base_sha" --head="$head_sha"`. На результат влияют граф, игнорируемые пути, настройки входов и версия Nx. [Nx affected](https://nx.dev/docs/features/ci-features/affected)
- **Turborepo.** Если проект уже использует `turbo.json` и локальный Turbo, посмотри задачи командой `TURBO_SCM_BASE="$base_sha" TURBO_SCM_HEAD="$head_sha" turbo run lint test build --affected --dry=json`. Сверь список и повтори команду без `--dry=json` для выполнения. Укажи отдельно результаты из кэша и фактически выполненные проверки. При слишком короткой истории Turbo может считать изменёнными все пакеты. [Turborepo run](https://turborepo.dev/docs/reference/run)

## Привяжи свидетельства к прогону

В GitHub Actions выбери конкретные репозиторий, run ID и номер попытки. Сохрани ссылку, SHA, workflow, событие и результаты обязательных jobs и steps.

```sh
gh run view "$run_id" --repo "$repo" --attempt "$attempt" \
  --json attempt,headSha,event,workflowName,status,conclusion,jobs,url
```

Сверь `headSha` с проверяемым коммитом и конфигурацию checkout с ревизией, на которой реально выполнялись тесты. Для подтверждения нужны завершённые обязательные задания с `success` и выполненные тесты. `Pending`, отмена, пропуск задания, пустая выборка и план запуска оставляют пробел в доказательстве. Общий `success` может включать пропуски через `if` или разрешённый отказ через `continue-on-error`. Для локального и удалённого прогона укажи их собственные SHA, среду и результат. [gh run view](https://cli.github.com/manual/gh_run_view) · [Правила обязательных проверок GitHub](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) · [Синтаксис GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
