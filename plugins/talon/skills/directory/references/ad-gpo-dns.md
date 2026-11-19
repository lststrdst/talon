# Active Directory Domain Services, GPO и DNS

## Среда и область проверки

Зафиксируй лес, домен, сайт, FQDN задействованных контроллеров домена (DC), DN подразделения (OU), GUID политики и затронутые компьютер и пользователя. Отметь, где и когда наблюдался симптом и какой результат ожидается. Сверь версии ОС контроллеров и клиента, функциональные уровни домена и леса, версию PowerShell и доступность модулей `ActiveDirectory`, `GroupPolicy` и при необходимости `DnsServer`. Выполняй проверки из Windows с нужными компонентами RSAT и правами на чтение. Для узла исполнения и удалённого доступа используй справочник Windows Server из основного навыка Talon. [Функциональные уровни AD DS](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/plan/raise-domain-forest-functional-levels) · [Get-ADDomainController](https://learn.microsoft.com/en-us/powershell/module/activedirectory/get-addomaincontroller?view=windowsserver2025-ps)

Подставь согласованные значения вместо примеров. Указывай конкретный DC, когда сравниваешь данные между репликами.

```powershell
$dc = 'dc01.ad.example'
$domain = 'ad.example'
$ou = 'OU=Pilot,DC=ad,DC=example'
$gpo = [guid]'12345678-1234-1234-1234-123456789abc'

$PSVersionTable
Get-Module -ListAvailable -Name ActiveDirectory, GroupPolicy, DnsServer |
    Select-Object Name, Version
Get-ADForest -Server $dc | Select-Object Name, ForestMode
Get-ADDomain -Server $dc | Select-Object DNSRoot, DomainMode
Get-ADDomainController -Identity $dc -Server $dc |
    Select-Object HostName, Site, OperatingSystem, OperatingSystemVersion, IsReadOnly
```

## DC Locator, DNS и репликация

1. На затронутом клиенте сверь адреса DNS-серверов через `Get-DnsClientServerAddress` и сайт через `nltest /dsgetsite`. Проверь `nltest /dsgetdc:ad.example`. На каждом DNS-сервере, который использует клиент, запроси `Resolve-DnsName -Server <DNS-IP> -Name _ldap._tcp.dc._msdcs.ad.example -Type SRV` и при необходимости запись сайта `_ldap._tcp.<сайт>._sites.dc._msdcs.ad.example`. Убедись, что имена DC из ответа разрешаются в ожидаемые адреса. При расхождении проверь авторитетную зону, делегирование и область репликации зоны Active Directory. [Диагностика DC Locator](https://learn.microsoft.com/en-us/troubleshoot/windows-server/windows-security/troubleshoot-domain-controller-location-issues) · [Поиск DC по записи сайта](https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/domain-joined-machines-cannot-detect-domain-profile) · [Зоны, интегрированные в AD](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/plan/active-directory-integrated-dns-zones)
2. Из Windows с RSAT запусти `repadmin /showrepl <DC>` для нужных контроллеров. Для каждого сбоя запиши партнёра, раздел каталога, код ошибки и время последней успешной входящей репликации. Сверь по затронутым DC фактические атрибуты нужного объекта. При необходимости проверь DNS и связность через `dcdiag /s:<DC> /test:DNS /DnsBasic` и сопоставь результат с журналом `Directory Service` на соответствующем DC. Для зон, интегрированных в AD, проверь раздел, в котором хранится конкретная зона, например `DomainDnsZones` или `ForestDnsZones`. [Диагностика репликации](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/diagnose-replication-failures) · [DCDiag](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/dcdiag)
3. Проверь репликацию файлов SYSVOL по журналу `DFS Replication`, состояние SYSVOL и доступность общих ресурсов через `dcdiag /s:<DC> /test:SysVolCheck /test:NetLogons`. Проверь чтение нужного пути с затронутого клиента. Если расследуется миграция SYSVOL, уточни её состояние через `dfsrmig /getmigrationstate`. Сравни AD Version и SysVol Version для пользовательской и компьютерной частей GPO через `Get-GPO -Guid $gpo -Domain $domain -Server $dc` на нужных DC. Если версии расходятся, проверь `gpt.ini` и нужный файл политики в `\\<DC>\SYSVOL\<домен>\Policies\{<GUID>}` на каждом из них. [Get-GPO](https://learn.microsoft.com/en-us/powershell/module/grouppolicy/get-gpo?view=windowsserver2025-ps) · [Хранение GPO](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-backup-restore) · [Диагностика репликации SYSVOL](https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/dfsr-sysvol-fails-migrate-replicate)

## Проверка настроенной и применённой политики

1. Собери конфигурацию GPO и порядок наследования на том же DC. Сверь наличие и включение связей сайта, домена и OU, порядок связей, Enforced и Block Inheritance, статус нужной части политики, права Read/Apply Group Policy, WMI-фильтр и loopback (Merge или Replace). Для Group Policy Preferences при необходимости проверь условия Item-level Targeting. [Обработка групповой политики](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing) · [Область действия GPO](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-scope)

   ```powershell
   Get-GPOReport -Guid $gpo -Domain $domain -Server $dc -ReportType Xml
   Get-GPInheritance -Target $ou -Domain $domain -Server $dc
   ```

2. На целевом компьютере получи данные Resultant Set of Policy (RSoP) после обработки политики. Для компьютерной части запусти `gpresult /scope computer /r` в сеансе с повышенными правами. Для пользовательской части выполни `gpresult /scope user /r` в сеансе нужного пользователя или явно укажи его через `/user` с достаточными правами. Для детального отчёта используй `gpresult /h gp-result.html`. Сверь применённые и отклонённые GPO по `Microsoft-Windows-GroupPolicy/Operational` с временем и ActivityID нужного цикла. В GPMC используй Group Policy Results для наблюдений и Group Policy Modeling для прогноза. [gpresult](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/gpresult) · [Результаты и моделирование](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-modeling-results) · [Журнал обработки GPO](https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/applying-group-policy-troubleshooting-guidance)
3. Подтверди фактический результат на том же клиенте. В зависимости от настройки проверь состояние службы, запланированной задачи, ключа реестра или поведения приложения. Учитывай, когда конкретное расширение применяет настройки, например во время входа пользователя или запуска компьютера. [Обработка групповой политики](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing)

## Пилот изменения и откат

Перед изменением GPO сделай `Backup-GPO`, сохрани ID резервной копии и отдельно зафиксируй связи с сайтами, доменом и OU, их порядок и состояние. Восстановление GPO из копии в исходном домене восстанавливает сам объект. Связи восстанавливай по снимку состояния соответствующих контейнеров. Для изменения DNS сохрани текущие записи и параметры зоны в пределах запрошенного изменения. [Резервное копирование и восстановление GPO](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-backup-restore) · [Операции GPMC](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/gpmc/gpo-operations-supported-by-the-gpmc)

Начни с согласованной пилотной OU или группы устройств. Дождись репликации и нужного цикла обработки. Повтори проверку DNS, AD/SYSVOL или RSoP на затронутых узлах и проверь один контрольный объект вне области изменения. До расширения области зафиксируй наблюдаемый результат, время и контекст. Если выявлен непредвиденный охват или потеря нужной функции, останови расширение, примени согласованный откат и повтори ту же проверку.
