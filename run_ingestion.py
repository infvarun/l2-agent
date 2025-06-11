"""CLI script: python run_ingestion.py ./sops/"""
import sys, glob, os, json
from sop_loader import parse_sop
from graph_builder import ingest_sops

def main(sop_folder: str):
    sop_dicts = []
    for path in glob.glob(os.path.join(sop_folder, "*.txt")):
        try:
            sop = parse_sop(path)
            sop_dicts.append(sop)
            print(f"Parsed {path}: {sop['title']}")
        except Exception as e:
            print(f"Failed to parse {path}: {e}")
    if sop_dicts:
        ingest_sops(sop_dicts)
        print("Ingestion complete.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_ingestion.py <folder_with_sop_txt>")
        sys.exit(1)
    main(sys.argv[1])
