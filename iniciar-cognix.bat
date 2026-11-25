@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Cognix - Inicializador Windows
color 1F

echo ======================================================
echo                  COGNIX - INICIAR
echo ======================================================
echo.
echo Pasta do projeto: %CD%
echo.
if not exist "backend\main.py" (
  echo ERRO: Arquivo backend\main.py nao encontrado.
  echo Extraia TODO o arquivo ZIP antes de executar.
  goto erro
)
if not exist "requirements.txt" (
  echo ERRO: requirements.txt nao encontrado.
  goto erro
)
if not exist "scripts\iniciar-servidor.py" (
  echo ERRO: scripts\iniciar-servidor.py nao encontrado.
  echo Extraia TODO o arquivo ZIP antes de executar.
  goto erro
)

set "PYCMD="
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD (
  where python >nul 2>&1
  if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYCMD=python"
  )
)
if not defined PYCMD (
  echo ERRO: Python 3.11 ou mais recente nao foi encontrado.
  echo Instale pelo site https://www.python.org/downloads/windows/
  echo Marque a opcao Add Python to PATH, se aparecer.
  echo Feche esta janela e execute iniciar-cognix.bat novamente.
  goto erro
)
echo [1/4] Python encontrado: %PYCMD%

set "VENV=.venv\Scripts\python.exe"
if not exist "%VENV%" (
  echo [2/4] Preparando o ambiente Python. Isso acontece somente na primeira vez...
  %PYCMD% -m venv .venv
  if errorlevel 1 (
    echo ERRO: Falha ao criar o ambiente virtual .venv.
    goto erro
  )
) else (
  echo [2/4] Ambiente Python encontrado.
)

"%VENV%" -c "import fastapi, uvicorn, httpx, docx, pypdf, dotenv" >nul 2>&1
if errorlevel 1 (
  echo [3/4] Instalando bibliotecas do Cognix...
  "%VENV%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo ERRO: Nao foi possivel instalar as bibliotecas.
    echo Confira sua conexao com a Internet e o erro mostrado acima.
    goto erro
  )
) else (
  echo [3/4] Bibliotecas ja instaladas.
)

echo [4/4] Iniciando Cognix e procurando uma porta disponivel...
echo.
echo A pagina sera aberta automaticamente assim que o servidor responder.
echo MANTENHA ESTA JANELA ABERTA durante o uso do Cognix.
echo Para encerrar, pressione CTRL+C aqui.
echo.
"%VENV%" "scripts\iniciar-servidor.py"
if errorlevel 1 (
  echo.
  echo ERRO: O servidor foi encerrado com falha.
  echo As ultimas linhas desta janela informam a causa do erro.
  goto erro
)
goto fim

:erro
echo.
echo CORRECAO: envie uma foto desta janela mostrando o erro.
:fim
echo.
echo Pressione qualquer tecla para fechar.
pause >nul
endlocal
