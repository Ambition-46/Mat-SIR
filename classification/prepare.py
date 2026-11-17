"""Build classification training inputs from field metadata via text-embedding-v2."""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np
from .predict import features
from system.service import mapping_api


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    dest = parser.parse_args().directory
    with gzip.open(Path(__file__).resolve().parents[1] / 'inputs/classification.json.gz', 'rt') as stream:
        rows = json.load(stream)
    matrix = features(rows, mapping_api('text-embedding-v2').embed)
    dest.mkdir(parents=True, exist_ok=True)
    np.savez(dest / 'features.npz', name=matrix['name'], unit=matrix['unit'])
    np.savez(dest / 'local_features.npz', local=matrix['local'])
    (dest / 'roles.json').write_text(json.dumps([{k: row[k] for k in ('sample_id','split','category_index')}
                                                for row in rows]))


if __name__ == '__main__':
    main()
