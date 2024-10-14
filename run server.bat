@echo off
:: Habilita o suporte a ANSI no CMD
REG ADD HKCU\CONSOLE /f /v VirtualTerminalLevel /t REG_DWORD /d 1

:: Executa o script Python
python "%~dp0main.py"

echo.
echo Server finalizado!
pause