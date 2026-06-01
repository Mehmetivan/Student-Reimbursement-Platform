@echo off
echo Starting Student Reimbursement Platform...

start "Backend" cmd /k "cd /d C:\Users\mehme\student_reimbursement_platform\backend && venv\Scripts\activate && python -m uvicorn app.main:app --reload"

timeout /t 6 /nobreak > nul

start "Frontend" cmd /k "cd /d C:\Users\mehme\student_reimbursement_platform\frontend && npm run dev"

echo Both servers starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000