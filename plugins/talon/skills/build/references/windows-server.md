# Администрирование Windows Server

Начни с согласованного узла или списка узлов. Зафиксируй FQDN, назначение и среду, роль сервера, версию ОС, учётную запись для проверки и разрешённый канал доступа. Отдельно укажи, где выполнялась каждая команда. Для начала собери состояние в режиме чтения с минимальными правами, достаточными для выбранных данных.

## PowerShell и удалённый доступ

- Windows PowerShell 5.1 запускается через `powershell.exe`. PowerShell 7 (`pwsh`) устанавливается отдельно и может работать на том же сервере. Сверь `$PSVersionTable` и доступность нужных модулей в той сессии, где выполняется команда. Для `ActiveDirectory` и `GroupPolicy` используй Windows с нужными компонентами RSAT или серверными средствами управления и проверь совместимость с выбранной версией. [PowerShell на GitHub](https://github.com/PowerShell/PowerShell) · [Различия 5.1 и 7](https://learn.microsoft.com/en-us/powershell/scripting/whats-new/differences-from-windows-powershell?view=powershell-7.6)
- С Windows используй настроенный WinRM и `Invoke-Command -ComputerName <FQDN>`. В домене используй согласованную аутентификацию Kerberos по FQDN, для HTTPS проверь доверие к сертификату и соответствие имени. Имя WinRM endpoint определяет версию PowerShell на сервере. Для ограниченного набора административных команд используй уже настроенный JEA endpoint с `-ConfigurationName`. [Требования WinRM](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_remote_requirements?view=powershell-7.6) · [JEA на GitHub](https://github.com/PowerShell/JEA)
- Из macOS или Linux для нативного PowerShell Remoting используй `Invoke-Command -HostName <FQDN> -UserName <account>` через существующий OpenSSH с подсистемой PowerShell. Сверь ключ хоста с доверенным источником. Для WinRM, включая подключение к JEA endpoint, используй согласованный Windows runner или административную машину с нужным доступом. [Win32-OpenSSH на GitHub](https://github.com/PowerShell/Win32-OpenSSH) · [PowerShell Remoting через SSH](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/ssh-remoting-in-powershell?view=powershell-7.5)
- Проверь доступ на одном сервере. В обычной сессии выполни `$env:COMPUTERNAME`, `$PSVersionTable.PSVersion` и одну разрешённую проверку. В JEA сверь доступные команды через `Get-Command` и выбери разрешённую операцию чтения. Различай недоступность сети, отказ аутентификации и отсутствие прав на команду или данные. Если у агента доступна только локальная macOS или Linux-среда, изучи скрипт локально и зафиксируй, какое свидетельство нужно получить с Windows. Проверки под пользовательской учётной записью в сессии и под учётной записью службы проводи отдельно. [Работа с JEA](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/jea/using-jea?view=powershell-7.6)

## Инвентаризация

Выполняй команды в Windows-сессии. Уменьшай вывод до необходимых для задачи полей, исключай секреты и фиксируй период событий. Вместо `Spooler` укажи имя согласованной службы.

```powershell
Get-CimInstance -ClassName Win32_OperatingSystem |
    Select-Object CSName, Caption, Version, BuildNumber, LastBootUpTime

Get-Service -Name 'Spooler' |
    Select-Object Name, Status, StartType

Get-WinEvent -FilterHashtable @{ LogName = 'System'; StartTime = (Get-Date).AddHours(-2) } -MaxEvents 50 |
    Select-Object TimeCreated, Id, LevelDisplayName, ProviderName
```

Состояние службы сопоставь с зависимостями, событиями и проверкой функции приложения. Для ошибок политики проверь `Microsoft-Windows-GroupPolicy/Operational` на целевой Windows. Для AD DS используй релевантные журналы `Directory Service` и `DFS Replication` на выбранном контроллере домена. Сохрани источник, часовой пояс и время проверки. Пустой результат оценивай с учётом прав, периода и доступности канала. [Фильтры Get-WinEvent](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.diagnostics/get-winevent?view=powershell-5.1)

## Active Directory и групповые политики

- Укажи домен, контроллер, OU и конкретный объект. Из Windows с RSAT собери `Get-ADDomainController -Identity <DC>` и нужные свойства объекта. Для репликации проверь ошибки и время последнего успешного обмена на выбранных контроллерах через `Get-ADReplicationFailure -Target <DC> -Scope Server`, `Get-ADReplicationPartnerMetadata -Target <DC> -Scope Server` или `repadmin /showrepl <DC>`. Запиши партнёра и раздел каталога. [Диагностика репликации AD DS](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/troubleshoot/troubleshooting-active-directory-replication-problems)
- Для конфигурации GPO используй `Get-GPOReport -Guid <GPO-ID> -ReportType Xml` с нужными `-Domain` и `-Server`. Сверь связи, фильтрацию и версии AD/SYSVOL. Для порядка связей и наследования проверь `Get-GPInheritance -Target <OU-DN>`. Для фактического применения на целевой машине получи `gpresult /scope computer /r` и, если затронута пользовательская часть, `gpresult /user <DOMAIN\account> /scope user /r` после входа проверяемого пользователя и обработки его политик. Подтверди прикладной эффект на этом же узле. [Get-GPOReport](https://learn.microsoft.com/en-us/powershell/module/grouppolicy/get-gporeport?view=windowsserver2025-ps) · [Get-GPInheritance](https://learn.microsoft.com/en-us/powershell/module/grouppolicy/get-gpinheritance?view=windowsserver2025-ps) · [gpresult](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/gpresult)

## Пилот и проверка изменения

1. Зафиксируй исходное состояние, ожидаемый результат и условие остановки. Для службы запиши конфигурацию и состояние. Для GPO сохрани копию через `Backup-GPO`, идентификатор копии и отдельно состояние связей на OU, домене или сайте. Проверь способ восстановления, включая доступ к узлу при сбое удалённого канала. [Резервное копирование и восстановление GPO](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-backup-restore)
2. Начни с согласованного пилотного сервера или пилотной OU. Примени только утверждённое изменение. Используй `-WhatIf` или Ansible `--check --diff` лишь для команд и модулей, которые поддерживают предварительную проверку. Проверяй вывод перед сохранением, особенно если diff содержит значения конфигурации. [Режимы check и diff в Ansible](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_checkmode.html)
3. Повтори исходные проверки. Для GPO дождись репликации и нужного цикла применения, затем сверь RSoP и фактический эффект. Проверь повторный запуск автоматизации, если она управляет состоянием. При выполнении условия остановки примени согласованный откат и проверь восстановление теми же командами. Сохрани временные метки, версии, контекст запуска, коды завершения и очищенные результаты.

## Автоматизация нескольких серверов

Выбирай модули по задаче. `ansible.windows` покрывает штатные операции с Windows, `community.windows` дополняет коллекцию, `microsoft.ad` предназначена для Active Directory. Зафиксируй совместимые версии Ansible и коллекций, проверь параметры и предусловия модуля. Храни секреты в согласованном хранилище. Для `psrp` или `winrm` используй согласованный Linux control node, если локальный macOS-клиент сталкивается с ограничениями этих плагинов. [ansible.windows](https://github.com/ansible-collections/ansible.windows) · [community.windows](https://github.com/ansible-collections/community.windows) · [microsoft.ad](https://github.com/ansible-collections/microsoft.ad) · [Подключения к Windows в Ansible](https://docs.ansible.com/projects/ansible/latest/os_guide/windows_winrm.html)
