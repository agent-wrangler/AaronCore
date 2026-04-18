!ifndef BUILD_UNINSTALLER
  !include LogicLib.nsh
  !include FileFunc.nsh
  !define /ifndef INSTALL_REGISTRY_KEY "Software\${APP_GUID}"

  Var AaronCoreDataRoot
  Var AaronCoreLegacyInstallRoot

  Function AaronCoreNormalizeInstallDir
    Push $0
    Push $1

    ${GetFileName} "$INSTDIR" $0
    ${if} $0 == "App"
    ${orIf} $0 == "app"
      Goto done
    ${endIf}

    ${if} $0 == "AaronCore"
    ${orIf} $0 == "aaroncore"
      StrCpy $INSTDIR "$INSTDIR\App"
      Goto done
    ${endIf}

    ${if} ${FileExists} "$INSTDIR\resources\*.*"
    ${orIf} ${FileExists} "$INSTDIR\${PRODUCT_FILENAME}.exe"
      ${GetParent} "$INSTDIR" $1
      StrCpy $INSTDIR "$1\AaronCore\App"
      Goto done
    ${endIf}

    StrCpy $INSTDIR "$INSTDIR\AaronCore\App"

  done:
    Pop $1
    Pop $0
  FunctionEnd

  Function AaronCoreSetDataRoot
    StrCpy $AaronCoreDataRoot "$PROFILE\.aaroncore"
    CreateDirectory "$AaronCoreDataRoot"
    CreateDirectory "$AaronCoreDataRoot\brain"
  FunctionEnd

  Function AaronCoreReadLegacyInstallRoot
    StrCpy $AaronCoreLegacyInstallRoot ""
    ReadRegStr $AaronCoreLegacyInstallRoot HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation
    ${if} $AaronCoreLegacyInstallRoot == ""
      ReadRegStr $AaronCoreLegacyInstallRoot HKLM "${INSTALL_REGISTRY_KEY}" InstallLocation
    ${endIf}
  FunctionEnd

  Function AaronCoreCopyDataSourceIfMissing
    Exch $0
    Push $1

    ${if} $0 == ""
      Goto done
    ${endIf}
    ${if} $0 == "$AaronCoreDataRoot"
      Goto done
    ${endIf}
    ${ifNot} ${FileExists} "$0\*.*"
      Goto done
    ${endIf}

    CreateDirectory "$AaronCoreDataRoot"
    CreateDirectory "$AaronCoreDataRoot\brain"

    ${ifNot} ${FileExists} "$AaronCoreDataRoot\brain\llm_config.json"
      CopyFiles /SILENT "$0\brain\llm_config.json" "$AaronCoreDataRoot\brain\llm_config.json"
    ${endIf}
    ${ifNot} ${FileExists} "$AaronCoreDataRoot\brain\llm_config.local.json"
      CopyFiles /SILENT "$0\brain\llm_config.local.json" "$AaronCoreDataRoot\brain\llm_config.local.json"
    ${endIf}
    ${ifNot} ${FileExists} "$AaronCoreDataRoot\state_data\*.*"
      nsExec::ExecToLog 'cmd /C if exist "$0\state_data\*" xcopy "$0\state_data" "$AaronCoreDataRoot\state_data" /E /I /Y /Q >nul'
    ${endIf}
    ${ifNot} ${FileExists} "$AaronCoreDataRoot\logs\*.*"
      nsExec::ExecToLog 'cmd /C if exist "$0\logs\*" xcopy "$0\logs" "$AaronCoreDataRoot\logs" /E /I /Y /Q >nul'
    ${endIf}

  done:
    Pop $1
    Exch $0
  FunctionEnd

  Function AaronCorePrepareDataRoot
    Push $0
    Push $1

    Call AaronCoreSetDataRoot
    Call AaronCoreReadLegacyInstallRoot
    ${if} $AaronCoreLegacyInstallRoot == ""
      Goto done
    ${endIf}

    ${GetFileName} "$AaronCoreLegacyInstallRoot" $0
    ${if} $0 == "App"
    ${orIf} $0 == "app"
      ${GetParent} "$AaronCoreLegacyInstallRoot" $1
      Push "$1\Data"
      Call AaronCoreCopyDataSourceIfMissing
    ${endIf}

    Push "$AaronCoreLegacyInstallRoot\Data"
    Call AaronCoreCopyDataSourceIfMissing
    Push "$AaronCoreLegacyInstallRoot\resources\aaroncore"
    Call AaronCoreCopyDataSourceIfMissing

  done:
    Pop $1
    Pop $0
  FunctionEnd

  Function AaronCoreFinalizeInstallDir
    Call AaronCoreNormalizeInstallDir
    Call AaronCorePrepareDataRoot
    Abort
  FunctionEnd

  !macro customInit
    Call AaronCoreNormalizeInstallDir
    ${if} ${Silent}
      Call AaronCorePrepareDataRoot
    ${endIf}
  !macroend

  !macro customPageAfterChangeDir
    Page custom AaronCoreFinalizeInstallDir
  !macroend
!endif
