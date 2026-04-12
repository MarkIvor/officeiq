@echo off
set PYTHON=C:\Users\0\AppData\Local\Programs\Python\Python312\python.exe
echo.
echo  Skald Bench
echo  Zapusk servera...
echo.
%PYTHON% -m pip install -r requirements.txt -q
echo  Otkryvay: http://127.0.0.1:7860
echo.
%PYTHON% server.py
pause
