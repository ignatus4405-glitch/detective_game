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
  #define VERSION "0.1.16"
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
; Основной exe — onefile сборка
Source: "..\dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion sign
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
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent unchecked

[Registry]
; Для обнаружения установленной версии (для апдейтера — опционально)
Root: HKCU; Subkey: "Software\BlackvilleDetective"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\BlackvilleDetective"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletevalue
; Ассоциация? не нужна

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

[CustomMessages]
russian.LaunchProgram=Запустить %1
english.LaunchProgram=Launch %1
