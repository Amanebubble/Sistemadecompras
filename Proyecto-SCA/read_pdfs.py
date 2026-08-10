import pdfplumber
import glob
from pathlib import Path

pdf_dir = Path(r"c:\Users\Lenovo P52s\Desktop\github-personal\proyecto01\Sistemadecompras\pdf")
pdfs = glob.glob(str(pdf_dir / "*.pdf"))

for pdf_path in pdfs:
    print(f"\n--- {Path(pdf_path).name} ---")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            if text:
                lines = text.split('\n')
                print('\n'.join(lines[:10]))
            else:
                print("NO TEXT (Scanned?)")
    except Exception as e:
        print(f"Error: {e}")
