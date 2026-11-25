from pathlib import Path

import fitz


ROOT = Path(__file__).parent
SOURCES = ["Food_Menu", "Ingredients_and_Allergens", "Restaurant_Policy", "Refund_Policy"]

for stem in SOURCES:
    source = ROOT / f"{stem}.txt"
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(55, 55, 540, 770), source.read_text(encoding="utf-8"), fontsize=11, lineheight=1.35)
    document.save(ROOT / f"{stem}.pdf")
    document.close()
