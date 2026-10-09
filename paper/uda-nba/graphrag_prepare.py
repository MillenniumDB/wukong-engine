"""Copy the documents of a run into a GraphRAG project's input folder.

    python3 graphrag_prepare.py runs/lightrag-pilot/docs.txt runs/graphrag-pilot

File names become <type>_<n>.txt, which GraphRAG uses as document titles.
"""

import shutil
import sys
from pathlib import Path

DOCS = Path(__file__).parent / 'data' / 'docs'

manifest, root = Path(sys.argv[1]), Path(sys.argv[2])
target = root / 'input'
target.mkdir(parents=True, exist_ok=True)
for line in manifest.read_text().split():
    doc_type, _, name = line.split('/')
    shutil.copy(DOCS / line, target / f'{doc_type}_{name}')
print(f'{len(list(target.iterdir()))} documents in {target}')
