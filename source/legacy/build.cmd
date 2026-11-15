@echo off
setlocal
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (echo csc.exe not found. .NET Framework 4.x required. & exit /b 1)
pushd "%~dp0"
"%CSC%" /nologo /codepage:65001 /target:exe /platform:anycpu /optimize+ /resource:"dsh-manager.mjs",dsh-manager.mjs /out:"DSHManager.exe" "launcher.cs"
if errorlevel 1 (echo Build failed. & popd & exit /b 1)
copy /y "DSHManager.exe" "..\DSHManager.exe" >nul
popd
echo OK: build\DSHManager.exe  --^>  DSHManager.exe
exit /b 0
