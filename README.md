# Student Reimbursement Platform

A comprehensive platform for managing student reimbursement requests with automated validation and document verification.

## Features

### For Students
* Create and manage a student profile with personal and bank details
* Upload required documents (Student ID, transportation card, bank proof)
* Submit reimbursement requests with receipts (images or PDFs)
* Track request status (Pending / Approved / Rejected)

### For Administrative Staff
* View all submitted reimbursement requests
* Access uploaded documents and receipts
* Review automated validation results
   * Duplicate detection
   * EXIF metadata analysis
   * OCR-based ID check
   * Digit-level n-gram analysis
* Approve or reject requests and provide feedback
* Manage student accounts

## Tech Stack

- **Backend:** FastAPI
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **Document Processing:** OCR, EXIF analysis
- **Authentication:** JWT (planned)

## Setup

1. Clone the repository
```bash
   git clone https://github.com/YOUR_USERNAME/student-reimbursement-platform.git
   cd student-reimbursement-platform
```

2. Create virtual environment
```bash
   python -m venv venv
```

3. Activate virtual environment
   - Windows: `.\venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

4. Install dependencies
```bash
   pip install -r requirements.txt
```

5. Create `.env` file in the `backend` directory with your configuration
```env
   DATABASE_URL=postgresql://user:password@localhost/dbname
   SECRET_KEY=your-secret-key
```

6. Run the application
```bash
   cd backend
   python -m uvicorn app.main:app --reload
```

## Project Structure
```
student_reimbursement_platform/
├── backend/
│   ├── app/
│   │   ├── database/
│   │   │   ├── models/
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── routers/
│   │   ├── services/
│   │   └── main.py
│   ├── venv/
│   └── .env
└── README.md
```

