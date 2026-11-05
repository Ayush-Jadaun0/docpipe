"""Usage:  python run.py path/to/file.pdf [--type invoice] [--no-mask]
Needs: pip install -r requirements.txt  and  set GEMINI_API_KEY (free) or ANTHROPIC_API_KEY"""
import argparse
import json

from pipeline import process

ICON = {"verified": "OK ", "unverified": "?? ", "invalid": "BAD", "missing": "-- "}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--type", default=None, help="skip classification (invoice/receipt/id_card/other)")
    ap.add_argument("--no-mask", action="store_true", help="do not mask Aadhaar/PAN before API call")
    ap.add_argument("--json", action="store_true", help="print full JSON")
    a = ap.parse_args()

    res = process(a.path, doc_type=a.type, mask_pii=not a.no_mask,
                  on_progress=lambda s, p: print(f"[{p:3d}%] {s}"))
    res.pop("pages_data", None)
    if a.json:
        print(json.dumps(res, indent=2, default=str))
        return
    print(f"\nType: {res['doc_type']}   Score: {res['score']}/100   "
          f"Time: {res['seconds']}s   Review needed: {res['needs_review']}")
    print("Pages:", ", ".join(f"{p['number']}:{p['source']}" for p in res["pages"]))
    for f in res["fields"]:
        extra = f"  ({'; '.join(f['reasons'])})" if f["reasons"] else ""
        print(f"  [{ICON[f['status']]}] {f['name']:<16} {f['value']}{extra}")


if __name__ == "__main__":
    main()
