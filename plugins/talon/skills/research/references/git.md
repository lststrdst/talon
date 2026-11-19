# Поиск в Git и GitHub

## Локальный код и история

Начни с затронутого репозитория и компонента. Найди точную строку ошибки, символ или параметр через `rg`. Затем проверь коммиты, в которых изменялось совпадение. Подставь путь от корня репозитория и нужную ветку, тег или SHA.

```sh
git status --short --branch
rg -n -F -- '<строка>' '<путь>'
git log -n 20 --oneline -S'<строка>' -- '<путь>'
git log -n 20 --oneline -G'<регулярное выражение>' -- '<путь>'
git show '<sha>' -- '<путь>'
git show '<тег>:<путь>'
git diff '<старый-тег>..<новый-тег>' -- '<путь>'
```

`-S` ищет изменения числа вхождений строки в файле. `-G` ищет совпадения с регулярным выражением в добавленных или удалённых строках диффа. Для истории другой версии передай её как ревизию в `git log`. Если файл переименовали, проверь предыдущий путь через `git log --follow -- '<файл>'`. Если совпадений нет, проверь нужные ветки и `git rev-parse --is-shallow-repository`. Проверь итоговый файл в версии пользователя, чтобы учесть откат или перенос изменения другим коммитом. [Документация Git log](https://git-scm.com/docs/git-log), [Git show](https://git-scm.com/docs/git-show).

Когда нужен фактический SHA ветки или наличие тега на сервере, найди настроенный remote через `git remote`. Сверь адрес локально через `git remote get-url origin`, подставив нужное имя. Запроси конкретный ref, например `git ls-remote --exit-code origin refs/heads/main` или `git ls-remote --exit-code origin refs/tags/v11.10.0`. Код `2` означает отсутствие совпадения, а ошибку доступа зафиксируй отдельно. `git ls-remote --symref origin HEAD` показывает ветку по умолчанию. [Документация Git ls-remote](https://git-scm.com/docs/git-ls-remote).

## Публичный GitHub

Используй уже доступный GitHub-коннектор или настроенный `gh`. Передавай публичный идентификатор проекта, публичный код ошибки или обезличенный симптом. Оставляй внутри рабочего пространства приватные пути, названия репозиториев, хосты, логи, токены и фрагменты кода. Найденная публикация служит источником для чтения. Отправка комментария или создание issue требуют отдельного поручения.

На примере ошибки npm найди upstream, поищи точную фразу в issues и сузь поиск исходников до файла в этом репозитории.

```sh
gh search repos 'cli in:name' --owner npm --visibility public --limit 3 --json fullName,url
gh search issues '"ERESOLVE unable to resolve dependency tree"' \
  --repo npm/cli --limit 3 --json number,title,url
gh search code 'ERESOLVE path:lib/utils' --repo npm/cli \
  --match file --filename explain-eresolve.js --limit 3 --json path,url
```

Открой issue и проверь версию и условия воспроизведения. Открой найденный файл по ссылке с SHA и сравни с тегом версии пользователя. Поиск выше находит [npm/cli](https://github.com/npm/cli), [issue #10054](https://github.com/npm/cli/issues/10054) и [обработку ERESOLVE в исходниках](https://github.com/npm/cli/blob/787f1520fa412e91a5792468f1c7f25b166867a6/lib/utils/explain-eresolve.js). В ответе укажи подтверждённую связь с симптомом, версию и прямые ссылки. [Справка по репозиториям](https://cli.github.com/manual/gh_search_repos), [issues](https://cli.github.com/manual/gh_search_issues), [коду](https://cli.github.com/manual/gh_search_code).

Если доступен REST, для тех же запросов используй `GET /search/repositories`, `GET /search/issues` и `GET /search/code` с параметром `q`. Если `gh` недоступен, выполни анонимный запрос для поиска публичных issues.

```sh
curl -fsS --get https://api.github.com/search/issues \
  --data-urlencode 'q=repo:npm/cli is:issue "ERESOLVE unable to resolve dependency tree"' \
  --data 'per_page=3'
```

Поиск кода в REST требует авторизации. `gh search code` использует устаревший механизм поиска, поэтому его результаты могут отличаться от поиска на GitHub.com. При `401`, лимите или пустой выдаче продолжи через публичную документацию, страницы релизов и обычный веб-поиск, например `site:github.com/npm/cli/issues "ERESOLVE unable to resolve dependency tree"`. В доступной авторизованной сессии GitHub можно искать код запросом `repo:npm/cli path:lib/utils/explain-eresolve.js content:"ERESOLVE"`. Для известного пути открой публичный файл по нужному тегу или используй его локальную копию. Зафиксируй недоступный маршрут, если от него зависит вывод. [GitHub REST Search](https://docs.github.com/en/rest/search/search), [GitHub Code Search](https://docs.github.com/en/search-github/github-code-search/using-github-code-search), [синтаксис веб-поиска кода](https://docs.github.com/en/search-github/github-code-search/understanding-github-code-search-syntax).
