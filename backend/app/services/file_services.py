import os
import uuid
from app.config import settings

def save_receipt_file(upload_file) -> str:
    # Create folder for current year/month
    year = str(upload_file.filename[:4])  # or datetime.now().year
    dir_path = os.path.join(settings.RECEIPT_UPLOAD_DIR, year)
    os.makedirs(dir_path, exist_ok=True)

    # Generate UUID filename
    ext = os.path.splitext(upload_file.filename)[1]
    file_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(dir_path, file_name)

    # Save file
    with open(file_path, "wb") as f:
        f.write(upload_file.file.read())

    return file_path
