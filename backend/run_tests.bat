@echo off
cd /d C:\Users\mehme\student_reimbursement_platform\backend
call venv\Scripts\activate
pytest tests/ -v --cov=app --cov-report=term-missing
pause