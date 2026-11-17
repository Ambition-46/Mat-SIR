"""Fit the fixed classifier on 203 development rows, evaluate on 781 held-out rows."""
import argparse
from pathlib import Path
import json
import numpy as np
from sklearn.metrics import accuracy_score, f1_score
from .weighted_model import WeightedMatSIR

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path, help="Directory containing roles.json, features.npz and local_features.npz")
    data = parser.parse_args().data
    rows = json.loads((data / "roles.json").read_text())
    with np.load(data / "features.npz") as base, np.load(data / "local_features.npz") as extra:
        features = {"name": base["name"], "unit": base["unit"], "local": extra["local"]}
    train, test = ([i for i,row in enumerate(rows) if row["split"] == split] for split in ("dev","test"))
    y = np.array([row["category_index"] for row in rows])
    model = WeightedMatSIR(dict(family="full", C_name=.03, name_weight=4, unit_weight=.25, context_weight=1, class_balance_power=1))
    model.fit(features,train,y[train])
    prediction = model.model.predict(model.matrix(features,test))
    print("accuracy",accuracy_score(y[test],prediction),"macro-F1",f1_score(y[test],prediction,average="macro"))

if __name__ == "__main__":
    main()
