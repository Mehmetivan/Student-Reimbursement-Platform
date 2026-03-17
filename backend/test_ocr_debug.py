# test_ocr_debug.py
import pytesseract
from PIL import Image
from pathlib import Path
import sys

print("=" * 60)
print("TESSERACT OCR DEBUG TEST")
print("=" * 60)

# Test 1: Check Tesseract path
print("\n1. Checking Tesseract executable...")
tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
print(f"   Path: {tesseract_path}")
print(f"   Exists: {Path(tesseract_path).exists()}")

if not Path(tesseract_path).exists():
    print("   ❌ ERROR: Tesseract executable not found!")
    print("   Please verify the installation path.")
    sys.exit(1)

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = tesseract_path

# Test 2: Try to get Tesseract version
print("\n2. Testing Tesseract connection...")
try:
    version = pytesseract.get_tesseract_version()
    print(f"   ✓ Tesseract version: {version}")
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    sys.exit(1)

# Test 3: Create a simple test image with text
print("\n3. Creating test image with text...")
try:
    from PIL import Image, ImageDraw, ImageFont
    
    # Create a simple white image with black text
    img = Image.new('RGB', (400, 100), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw some text
    text = "SERIE CARD:555845\nTEST RECEIPT"
    draw.text((10, 10), text, fill='black')
    
    # Save test image
    test_image_path = Path("test_receipt.png")
    img.save(test_image_path)
    print(f"   ✓ Test image saved: {test_image_path}")
    
except Exception as e:
    print(f"   ❌ ERROR creating test image: {e}")
    sys.exit(1)

# Test 4: Perform OCR on test image
print("\n4. Performing OCR on test image...")
try:
    extracted_text = pytesseract.image_to_string(img, lang='eng')
    print(f"   ✓ OCR successful!")
    print(f"   Extracted text ({len(extracted_text)} chars):")
    print(f"   ---")
    print(f"   {extracted_text}")
    print(f"   ---")
    
except pytesseract.TesseractNotFoundError as e:
    print(f"   ❌ Tesseract not found: {e}")
    print(f"   The path might be incorrect or Tesseract is not installed properly.")
    sys.exit(1)
except Exception as e:
    print(f"   ❌ ERROR during OCR: {type(e).__name__}: {e}")
    sys.exit(1)

# Test 5: Test with your OCR service (if it exists)
print("\n5. Testing OCR Service class...")
try:
    from app.services.validation.ocr_service import OCRService
    
    result = OCRService.analyze_receipt_text(test_image_path)
    print(f"   ✓ OCR Service test complete!")
    print(f"   Results:")
    for key, value in result.items():
        if key != 'raw_text':  # Skip raw_text as it's long
            print(f"      {key}: {value}")
    
except ImportError as e:
    print(f"   ⚠ Could not import OCR Service: {e}")
    print(f"   This is OK if you're testing outside the app directory")
except Exception as e:
    print(f"   ❌ ERROR: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)

# Cleanup
if test_image_path.exists():
    print(f"\nTest image saved at: {test_image_path.absolute()}")
    print("You can delete it manually if needed.")