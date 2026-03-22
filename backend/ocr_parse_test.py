import sys
from pathlib import Path
import re

from PIL import Image
import pytesseract
from pytesseract import pytesseract as pt
from PIL import ImageOps


def main() -> None:
    # Import backend parsing functions without starting FastAPI.
    sys.path.append(str(Path(__file__).resolve().parent))
    import main as m  # noqa: E402

    # The winget install may not have updated PATH for this process.
    pt.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # These are the absolute paths provided by the system when the user uploaded images.
    paths = [
        Path(
            r"C:\Users\desai\.cursor\projects\c-Users-desai-OneDrive-Desktop-part/assets/c__Users_desai_AppData_Roaming_Cursor_User_workspaceStorage_8973a3d79d25810dff109ab742f444fc_images_WhatsApp_Image_2026-03-18_at_18.47.08-39799eda-bb8f-418a-a760-de5386a45e8c.png"
        ),
        Path(
            r"C:\Users\desai\.cursor\projects\c-Users-desai-OneDrive-Desktop-part/assets/c__Users_desai_AppData_Roaming_Cursor_User_workspaceStorage_8973a3d79d25810dff109ab742f444fc_images_image-8eaa5c82-6126-4c6d-a952-f3d1abb2f9b7.png"
        ),
    ]

    for fp in paths:
        print(f"\n=== {fp.name} ===")
        img = Image.open(fp).convert("RGB")

        # Basic preprocessing to help OCR on low-contrast screenshots.
        base = img.convert("L")
        base = base.resize((base.width * 2, base.height * 2))
        thresh = 170
        bw = base.point(lambda x: 0 if x < thresh else 255, mode="1")

        variants = [
            ("bw", bw),
            ("inv_bw", ImageOps.invert(bw.convert("L"))),
            ("gray", base),
        ]

        best_txt = ""
        for name, v in variants:
            txt = pt.image_to_string(v, config="--psm 6")
            if (txt or "").strip() and len(txt.strip()) > len(best_txt.strip()):
                best_txt = txt

        t = (best_txt or "").strip()
        print("ocr_len", len(t), "variant_best_len", len(best_txt.strip()))

        # Debug: show a few OCR lines likely containing designations.
        hits = []
        for ln in t.splitlines():
            if re.search(r"VK[TRCBA]|V K|VKTC|VKT", ln, flags=re.IGNORECASE):
                hits.append(ln.strip())
            if len(hits) >= 8:
                break
        if hits:
            print("sample_hits:")
            for h in hits:
                print("  ", h)

        f1 = m.parse_format1(t, source_file=str(fp))
        f2 = m.parse_format2(t, source_file=str(fp))
        print("format1", len(f1), "format2", len(f2))

        for r in f1[:3]:
            print(
                "f1",
                r["designation"],
                r["price"],
                r.get("pack_code"),
                r.get("case_qty"),
            )
        for r in f2[:3]:
            print("f2", r["designation"], r["price"])


if __name__ == "__main__":
    main()

