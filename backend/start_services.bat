@echo off
echo Starting NeuraDesk Backend Services...

:: Ensure we are in the backend directory
cd /d "%~dp0"

:: Start Celery Worker in a new window
start "NeuraDesk Celery Worker" cmd /c "echo Starting Celery Worker... && .venv\Scripts\activate && python -m celery -A app.core.celery_app worker --loglevel=info --pool=solo || pause"

:: Start Uvicorn in the current window
echo Starting FastAPI Uvicorn Server...
call .venv\Scripts\activate
uvicorn app.main:app --reload
