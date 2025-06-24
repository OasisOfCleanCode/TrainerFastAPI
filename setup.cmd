@echo off
setlocal

echo Installing uv...
curl -Ls https://astral.sh/uv/install.sh | sh

set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

echo Creating virtual environment...
uv venv

echo Installing dependencies...
uv pip install .

echo Done. To activate the venv, run:
echo     .venv\Scripts\activate
endlocal
