import argparse
import hashlib
import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data import RAW
from src.language import translate

URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"
FILES = [f"olist_{name}_dataset.csv" for name in ["orders", "order_items", "order_reviews", "customers", "products", "sellers"]]


def main():
    parser = argparse.ArgumentParser(description="Download Olist tables / Scarica le tabelle Olist")
    parser.add_argument("--language", choices=["en", "it"], default="en", help="Message language / Lingua dei messaggi")
    args = parser.parse_args()
    t = lambda text: translate(text, args.language)
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = RAW.parent / "manifest.json"
    expected = json.loads(manifest.read_text())["sha256"] if manifest.exists() else None
    if not all((RAW / name).exists() for name in FILES):
        response = requests.get(URL, timeout=180)
        response.raise_for_status()
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            for name in FILES:
                (RAW / name).write_bytes(archive.read(name))
    hashes = {name: hashlib.sha256((RAW / name).read_bytes()).hexdigest() for name in FILES}
    if expected is not None and hashes != expected:
        raise ValueError(t("The tables differ from the saved Olist version. Check the source and recalculate the results before updating manifest.json."))
    manifest.write_text(json.dumps({"source": URL, "sha256": hashes}, indent=2))
    print(t("Done: 6 Olist tables, checksums saved."))


if __name__ == "__main__":
    main()
