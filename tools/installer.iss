; Inno Setup 6 — Установщик Детектив: Блэквил (Код Города)
; Собирается на CI: iscc /DVERSION=%VERSION% tools/installer.iss
; Локально:  iscc tools/installer.iss  -> Output/DetectiveBlackville-Setup-x.x.x.exe

#define MyAppName "Детектив: Блэквил — Код Города"
#define MyAppShort "DetectiveBlackville"
#define MyAppLnkName "Детектив Блэквил"
#define MyAppPublisher "Sams_studio128"
#define MyAppURL "https://github.com/ignatus4405-glitch/detective_game"
#define MyAppId "{{8B1A2F3C-4D5E-6F78-90AB-CDEF12345678}"
#ifndef VERSION
  #define VERSION GetEnv("VERSION")
#endif
#if VERSION == ""
  #define VERSION "0.1.35"
#endif
#define MyAppVersion VERSION
#define MyAppExe "DetectiveBlackville.exe"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\BlackvilleDetective
DisableDirPage=no
DefaultGroupName=Детектив Блэквил
DisableProgramGroupPage=no
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\Output
OutputBaseFilename=DetectiveBlackville-Setup-{#MyAppVersion}
SetupIconFile=..\src\detective_game\assets\images\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=110,110
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Обновление всегда идёт туда, куда его направил апдейтер (/DIR),
; а не «как было в прошлый раз» — иначе тихая установка могла ждать UAC
; и молча отменяться.
UsePreviousPrivileges=no
; Журнал установки рядом с setup.exe/в {tmp} — нужен для диагностики
SetupLogging=yes
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Детектив: Блэквил — нуар-расследование в городе Блэквил
VersionInfoCopyright=© 2026 Sams_studio128
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
CloseApplications=yes
RestartApplications=no
AppMutex=BlackvilleDetectiveMutex

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "Закрепить на панели задач"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 0,0

[Files]
; Основной exe — onedir сборка (фикс Failed to load Python DLL _MEI): весь каталог рядом с exe
Source: "..\dist\DetectiveBlackville\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Совместимость с onefile (если сборка старая — один exe в dist)
Source: "..\dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
; Доп. файлы если есть
Source: "..\dist\README.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme skipifsourcedoesntexist
Source: "..\dist\latest.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppLnkName}"; Filename: "{app}\{#MyAppExe}"; IconFilename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"; Comment: "Нуар-расследование в Блэквиле, 1987"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{group}\Репозиторий на GitHub"; Filename: "{#MyAppURL}"
Name: "{autodesktop}\{#MyAppLnkName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#MyAppLnkName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"

[Run]
; Обычный запуск из мастера — чекбокс включён по умолчанию, запуск от имени пользователя (не от админа инсталлятора)
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser; WorkingDir: "{app}"
; Автозапуск после тихого обновления из игры (/SILENT) — runasoriginaluser критичен для _MEI (иначе LoadLibrary python310.dll падает)
Filename: "{app}\{#MyAppExe}"; Flags: nowait runasoriginaluser; Check: ShouldAutoLaunch; WorkingDir: "{app}"

[Registry]
; Для обнаружения установленной версии (для апдейтера — опционально)
Root: HKCU; Subkey: "Software\BlackvilleDetective"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\BlackvilleDetective"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletevalue
; Ассоциация? не нужна

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
function ShouldAutoLaunch(): Boolean;
begin
  // Только тихая установка: в интерактивном мастере игру запускает штатная
  // запись [Run] с галочкой, иначе после обновления открывались ДВА окна игры.
  Result := WizardSilent and (ExpandConstant('{param:AUTOLAUNCH|0}') = '1');
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

[CustomMessages]
russian.LaunchProgram=Запустить %1
english.LaunchProgram=Launch %1
