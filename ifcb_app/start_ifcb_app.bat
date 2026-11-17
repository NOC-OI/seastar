@echo off
rem Starts the IFCB pipeline app in the web browser (double-click this file).
rem Keep this black window open while you use the app; close it to stop the app.
rem Uses the conda environment ifcb_app when Miniconda or Anaconda is installed
rem in one of the usual folders, otherwise the Python found on this computer.
cd /d "%~dp0"
set PY=python
for %%C in ("%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniconda3" "%ProgramData%\miniconda3" "%ProgramData%\anaconda3") do (
    if exist "%%~C\condabin\conda.bat" (
        call "%%~C\condabin\conda.bat" activate ifcb_app 2>nul && goto run
    )
)
rem no conda environment: the Python launcher (py) if installed, else python
where py >nul 2>nul && set PY=py -3
:run
%PY% -c "import streamlit, pandas, PIL, openpyxl, ifcb_features" 2>nul || %PY% -m pip install -r requirements.txt
rem Streamlit asks for an e-mail address on its first start: an empty one is saved here, so it does not wait
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    mkdir "%USERPROFILE%\.streamlit" 2>nul
    (echo [general]& echo email = "") > "%USERPROFILE%\.streamlit\credentials.toml"
)
%PY% -m streamlit run app.py --browser.gatherUsageStats false
pause
