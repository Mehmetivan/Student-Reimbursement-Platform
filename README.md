# Student Reimbursement Platform

A web-based platform that allows students at the higher education institutions to submit public transport receipts for reimbursement, with an automated fraud detection pipeline to assist administrative staff in review.

This project is the implementation component of a Bachelor's thesis on automated receipt fraud detection.

## Overview

The platform consists of:

- A **FastAPI** backend (Python) running the fraud detection pipeline and REST API
- A **Next.js** frontend (TypeScript) for students and administrative staff
- A **SQLite** database for development (PostgreSQL planned for production)
- Integration with **Google Cloud Vision** and **EasyOCR** for receipt text extraction

The fraud detection pipeline consists of five layers:

1. SHA-256 hash-based duplicate detection
2. EXIF metadata analysis for image manipulation
3. Multi-engine OCR identity verification (STPT card ID matching)
4. Structural anomaly detection on receipt transaction IDs
5. Weighted risk score aggregation with critical signal overrides

## Tech Stack

**Backend:**
- Python 3.12
- FastAPI (REST API framework)
- SQLAlchemy (ORM)
- SQLite (database)
- EasyOCR + Google Cloud Vision (OCR engines)
- Tesseract (only for the testing endpoint)
- JWT-based authentication

**Frontend:**
- Next.js 16 (React framework)
- TypeScript
- Tailwind CSS
- Axios (HTTP client)

## Prerequisites

Before running the project, make sure you have installed:

- **Python 3.12** ([download](https://www.python.org/downloads/))
- **Node.js 20+** ([download](https://nodejs.org/))
- **Tesseract OCR** (Windows: [installer](https://github.com/UB-Mannheim/tesseract/wiki), install to default path `C:\Program Files\Tesseract-OCR\`)
- A **Google Cloud Vision API key** with the Vision API enabled

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd project
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` folder with the following:

```env
SECRET_KEY=your-jwt-secret-key-here
GOOGLE_CLOUD_VISION_API_KEY=your-google-cloud-vision-api-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

Generate a JWT secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Frontend setup

```bash
cd ../frontend
npm install
```

Create `.env.local` in the `frontend/` folder:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Running the application

### Option 1 — Both servers at once (recommended)

From the project root:

```bash
start.bat
```

This launches the backend on port 8000 and the frontend on port 3000 in separate terminals.

### Option 2 — Run separately

**Backend:**
```bash
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0
```

**Frontend:**
```bash
cd frontend
npm run dev
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger API docs: http://localhost:8000/docs

## Creating an admin account

The database is created automatically on first run. To create an admin account, run the following from the backend directory (with venv activated):

```bash
python -c "
from app.database.base import Base
from app.database.models.user import User, UserRole
from app.database.models.student import Student
from app.database.models.request import Request
from app.database.models.receipt import Receipt
from app.database.models.student_document import StudentDocument
from app.database.models.receipt_metadata import ReceiptMetadata
from app.database.models.receipt_ocr import ReceiptOCR
from app.database.models.receipt_anomalies import ReceiptAnomalies
from app.database.models.receipt_risk_assessment import ReceiptRiskAssessment
from app.database.session import SessionLocal
from app.services.auth_service import AuthService
db = SessionLocal()
admin = User(email='admin@test.com', passwd=AuthService.hash_password('admin123'), role=UserRole.ADMIN)
db.add(admin); db.commit(); print('Admin created'); db.close()
"
```

Then log in at http://localhost:3000 with `admin@test.com` / `admin123`.

## Running tests

From the backend directory (with venv activated):

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

This runs the full test suite and prints a coverage report.

To run only unit tests or only integration tests:

```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
```

## Project structure

project/
├── backend/
│   ├── app/
│   │   ├── routers/             FastAPI route handlers
│   │   ├── services/            Business logic and fraud detection layers
│   │   │   └── validation/      Hash, EXIF, OCR, and anomaly services
│   │   ├── database/
│   │   │   └── models/          SQLAlchemy ORM models
│   │   ├── schemas/             Pydantic request/response schemas
│   │   └── main.py              Application entry point
│   ├── tests/
│   │   ├── unit/                Unit tests
│   │   └── integration/         Integration tests
│   ├── uploads/                 Uploaded files (created at runtime)
│   └── requirements.txt
├── frontend/
│   ├── app/                     Next.js pages and routes
│   ├── components/              React components
│   ├── lib/                     API client and utilities
│   └── package.json
├── start.bat                    Helper script to launch both servers
└── README.md


## Notes

- The database file (`student_reimbursement.db`) is created automatically on first run if changes are made. To reset, delete it and restart the backend, then recreate the admin account.
- Uploaded files go into `backend/uploads/` (gitignored). These are not part of the repository.
- Tesseract is only invoked via the testing endpoint `/test/ocr-extraction` for the OCR engine comparison in Chapter 5 of the thesis. The deployed pipeline uses only EasyOCR and Google Cloud Vision.
- Google Cloud Vision has a free tier of 1000 calls per month. Monitor usage if running the project intensively.

## Author

Mehmet Ivan Çınarlı  
Bachelor's thesis, West University of Timișoara  
Supervisor: Lect. univ. dr. Alin Brindusescu  
2026