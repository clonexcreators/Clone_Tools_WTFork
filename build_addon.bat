@echo off
echo Building Clone Tools Fork for Blender 4.5...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0build_addon.ps1" -Verbose

echo.
echo Build completed! Check the build directory for the ZIP file.
pause
