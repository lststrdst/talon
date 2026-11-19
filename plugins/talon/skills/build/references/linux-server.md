# Администрирование Linux-серверов

Определи целевой хост, окружение, задачу и наблюдаемый результат. Для удалённой работы используй согласованный инвентарь, учётную запись и [порядок подключения по SSH](remote-ssh.md). Начни с чтения состояния. Ограничь команды конкретным пакетом, службой, каталогом или интервалом времени.

## Определи окружение и исходное состояние

```sh
hostname
id
cat /etc/os-release
uname -r -m
ps -p 1 -o comm=
```

Сверь хост и учётную запись с задачей. Если `/etc/os-release` отсутствует, прочитай `/usr/lib/os-release`. Выбирай команды по `ID`, `VERSION_ID`, `ID_LIKE` и фактически доступному менеджеру. Уточни, где выполнена проверка, если рабочая среда находится в контейнере. Используй команды systemd, если соответствующим окружением управляет systemd. [Поля os-release](https://www.freedesktop.org/software/systemd/man/latest/os-release.html)

| Что выяснить | Что прочитать |
| --- | --- |
| Пакет в Ubuntu/Debian | `dpkg-query -W "$package"` и `apt-cache policy "$package"`. Сверь установленную версию, статус пакета, версию кандидата и её источник. Для точного статуса используй `dpkg-query -s "$package"`. |
| Пакет в Fedora/RHEL и производных | `rpm -q "$package"` для установленной версии, `dnf --version` или `dnf5 --version` для выбора команд. |
| Служба systemd | `systemctl status --no-pager "$unit"` для состояния и сводки, `systemctl cat "$unit"` для файлов unit и drop-in на диске. При необходимости сверяй `systemctl is-active "$unit"` и `systemctl is-enabled "$unit"` по отдельности, учитывая ожидаемое состояние этого unit. Для пользовательской службы используй `systemctl --user` в её контексте. |
| Журнал службы | `journalctl -u "$unit" -b -n 100 --no-pager` для текущей загрузки. Для инцидента задай нужный интервал через `--since` и `--until` и выбери нужную загрузку, если она важна. Учитывай права на чтение и доступную историю. |
| Файловая система | `findmnt --target "$path"`, `df -hT -- "$path"` и при необходимости `df -i -- "$path"` для указанного пути. |

Подставь значения пакета, unit и пути из задачи. Сохраняй для диагностики только релевантные строки и скрывай секреты перед передачей вывода. [dpkg-query](https://manpages.debian.org/stable/dpkg/dpkg-query.1.en.html), [apt-cache](https://manpages.debian.org/stable/apt/apt-cache.8.en.html), [systemctl](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html), [journalctl](https://www.freedesktop.org/software/systemd/man/latest/journalctl.html)

## Выполни изменение и проверь результат

1. Зафиксируй исходное состояние и подготовь способ восстановления. Для файла проверь путь, владельца, права и применимые метки безопасности, сохрани прежнюю версию с ограниченным доступом. Для пакета проверь доступность нужной и прежней версий и учти эффекты установки на зависимости, службы и данные. Для данных и конфигурации определи собственный способ восстановления.
2. Проверь план пакетной операции. В Ubuntu/Debian используй `apt-get -s install "$package"`. Вывод зависит от актуальности индексов и доступа к локальной конфигурации APT. В Fedora/RHEL с DNF используй `dnf --assumeno install "$package"` или соответствующую команду `dnf5` для найденной версии. `--assumeno` отклоняет транзакцию, а DNF при расчёте может обновить метаданные. Для расчёта по имеющемуся кэшу используй поддерживаемый менеджером `--cacheonly`. Сверь версии, источники, зависимости и удаления. Для автоматизации APT используй `apt-get` и `apt-cache`. [Ubuntu Server](https://ubuntu.com/server/docs/how-to/software/package-management/), [apt-get](https://manpages.debian.org/stable/apt/apt-get.8.en.html), [DNF](https://dnf.readthedocs.io/en/latest/command_ref.html), [DNF5](https://dnf5.readthedocs.io/en/latest/dnf5.8.html)
3. Проверь конфигурацию штатным валидатором приложения, а изменённый unit проверь через `systemd-analyze verify` на совместимой версии systemd. Примени согласованное изменение на разрешённой цели. После установки изменённого unit или drop-in выполни `systemctl daemon-reload`. Чтобы служба перечитала конфигурацию, используй её штатный `reload`, если он поддерживается, или предусмотренный задачей `restart`. Повышай права только для действий, которым они нужны. [Проверка unit](https://www.freedesktop.org/software/systemd/man/latest/systemd-analyze.html), [systemctl](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html)
4. Перечитай затронутое состояние и журнал с начала изменения, затем выполни минимальную функциональную проверку службы в её реальном контексте запуска. На разрешённом стенде проверь нативное выполнение, повтор с теми же параметрами и восстановление после значимого частичного отказа. При повторном запуске целевое состояние должно сохраниться без лишних записей и перезапусков. После таймаута сначала узнай, какие шаги завершились. При откате учти промежуточные изменения и повтори функциональную проверку. Зафиксируй окружение, версии, команды, коды завершения и фактический результат.

## Выбери средство по проекту

- Для повторяемых изменений в проекте с Ansible используй существующий inventory и роли. Для общих пакетных операций подходит `ansible.builtin.package`, для специфичных параметров используй модуль найденного менеджера. Управляй systemd через `ansible.builtin.systemd_service` и вызывай обработчик перечитывания конфигурации или перезапуска только при нужных изменениях. Проверь выбранный inventory и состав целей с `--list-hosts`, затем запусти playbook с `--check` и ограничь цели пилотным хостом через `--limit`, если задачи поддерживают этот режим. Добавляй `--diff` только для задач, вывод которых можно раскрывать. После реального прогона сверь состояние и результат второго запуска. [Ansible на GitHub](https://github.com/ansible/ansible), [модуль package](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/package_module.html), [модуль systemd_service](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/systemd_service_module.html), [check mode и diff mode](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_checkmode.html)
- Для shell-скрипта выбери интерпретатор по контракту запуска. Проверь синтаксис его штатной командой, например `bash -n "$script"` для Bash, и запусти ShellCheck с настройками проекта, если он доступен. Подтверди поведение запуском в целевой среде. [ShellCheck на GitHub](https://github.com/koalaman/shellcheck)
- Для различий между выпусками начни с `man` и версии на целевом хосте. Используй исходники upstream для уточнения поведения конкретной версии. [systemd на GitHub](https://github.com/systemd/systemd), [DNF на GitHub](https://github.com/rpm-software-management/dnf), [DNF5 на GitHub](https://github.com/rpm-software-management/dnf5), [APT на Debian Salsa](https://salsa.debian.org/apt-team/apt)
