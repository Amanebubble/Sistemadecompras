import pdfplumber
import glob
from pathlib import Path

pdf_dir = Path(r"c:\Users\Lenovo P52s\Desktop\github-personal\proyecto01\Sistemadecompras\pdf")
pdfs = [
    "TRANSPORTESHALOM_2F9CB9EC-E2B0-444B-A6B6-1D3500C51299_05072023.pdf", # Autofacil
    "TRANSPORTESHALOM_4F0FF45D-B617-4B66-A1E3-5C7AD01A293D_23012024.pdf", # Check Point
    "TRANSPORTESHALOM_926B65A8-26D2-4A93-BEE8-012E1368A85E_05092023.pdf", # Banco Agricola
    "TRANSPORTESHALOM_9BDEB9C2-C37E-441A-AFB2-397A8928DB2D_25072023.pdf"  # Jose Enrique
]

for pdf_name in pdfs:
    pdf_path = pdf_dir / pdf_name
    print(f"\n--- {pdf_name} ---")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            if text:
                print(text)
            else:
                print("NO TEXT")
    except Exception as e:
        print(f"Error: {e}")
