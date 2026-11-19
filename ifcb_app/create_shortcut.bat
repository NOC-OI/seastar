@echo off
rem Puts an "IFCB pipeline" shortcut on the desktop, with the app icon (double-click this file once).
rem The shortcut starts start_ifcb_app.bat from this folder: run this file again if the folder is moved.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desk = [Environment]::GetFolderPath('Desktop');" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desk 'IFCB pipeline.lnk'));" ^
  "$s.TargetPath = (Join-Path (Get-Location) 'start_ifcb_app.bat');" ^
  "$s.WorkingDirectory = (Get-Location).Path;" ^
  "$s.IconLocation = (Join-Path (Get-Location) 'ifcb_app.ico') + ',0';" ^
  "$s.Description = 'Starts the IFCB pipeline app in the web browser';" ^
  "$s.Save();" ^
  "Write-Host ('Shortcut created: ' + (Join-Path $desk 'IFCB pipeline.lnk'))"
pause
