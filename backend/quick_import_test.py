import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import main  # noqa: F401,E402

print("import_ok")

