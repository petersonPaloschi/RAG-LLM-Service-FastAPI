@echo off
setlocal enabledelayedexpansion

echo Iniciando a limpeza de diretorios __pycache__...
echo.

set "count=0"

for /d /r "%CD%" %%d in (*) do (
    if "%%~nxd"=="__pycache__" (
        set /a count+=1
        echo Deletando: %%d
        rd /s /q "%%d" 2>nul
        if !errorlevel! neq 0 (
            echo Falha ao deletar: %%d
        )
    )
)

echo.
echo Processo concluido.
echo Total de diretorios __pycache__ deletados: !count!

#pause