"""Field-role inference with the original three-class classifier."""
import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np

from .units import GROUPS, dimensions

LABELS = ('object', 'operate', 'result')


@lru_cache(maxsize=1)
def load_model():
    return joblib.load(Path(__file__).with_name('model.joblib'))


def features(rows, embed):
    names = [row['original_field'] for row in rows]
    contexts = [json.dumps(dict(column=name, description=row['description'],
                                values=row['sample_values']), ensure_ascii=False)
                for name, row in zip(names, rows)]
    texts = list(dict.fromkeys(names + contexts))
    vectors = np.asarray(embed(texts), dtype=np.float32)
    if vectors.shape != (len(texts), 1536) or not np.isfinite(vectors).all():
        raise ValueError('Expected 1536-dimensional text-embedding-v2 vectors')
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError('Empty embedding')
    lookup = dict(zip(texts, vectors / norms))
    units = []
    for name, row in zip(names, rows):
        found = dimensions(name) | dimensions(row['description'])
        unit = np.array([key in found for key in sorted(GROUPS)] + [not found], dtype=np.float32)
        units.append(unit / np.linalg.norm(unit))
    return dict(name=np.stack([lookup[t] for t in names]), unit=np.stack(units),
                local=np.stack([lookup[t] for t in contexts]))


def classify(rows, embed):
    matrix = features(rows, embed)
    classes, probs = load_model().predict(matrix, np.arange(len(rows)))
    return [dict(role=LABELS[c], confidence=float(p[c])) for c, p in zip(classes, probs)]
