"""Refresh the standalone driver snapshot bundled for offline HACS installs.

    .venv/bin/python scripts/vendor_ble_labels.py ../bluetooth-label

The formatter is intentionally applied to copies, leaving library sources alone.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
source = args.source / "src/ble_labels"
target = root / "custom_components/ble_esl/_vendor/ble_labels"
for relative in [
    Path("__init__.py"),
    *(path.relative_to(source) for path in sorted((source / "tags").glob("*.py"))),
]:
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / relative, destination)
    destination.write_text(destination.read_text().replace("×", "x"))
shutil.copyfile(args.source / "LICENSE", target / "LICENSE")
subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", str(target)], check=True)
subprocess.run([sys.executable, "-m", "ruff", "format", str(target)], check=True)
