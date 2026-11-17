"""A single Softmax head on weighted name/unit/context features; no ensemble."""
import numpy as np
from sklearn.linear_model import LogisticRegression


class WeightedMatSIR:
    def __init__(self, spec):
        self.spec = dict(spec)
        # Keep name-space regularization comparable while changing feature ratios.
        self.actual_C = spec['C_name'] / spec['name_weight']**2
        self.model = LogisticRegression(C=self.actual_C, class_weight=None,
            solver='lbfgs', max_iter=3000, tol=1e-5, random_state=42)

    def matrix(self, features, idx):
        if self.spec['family'] == 'embedding': return features['name'][idx]
        if self.spec['family'] == 'local_embedding': return features['local'][idx]
        return np.concatenate([features[k][idx]*self.spec[w] for k,w in
            [('name','name_weight'),('unit','unit_weight'),('local','context_weight')]],axis=1)

    def fit(self, features, idx, targets):
        assert len(idx)==len(targets)
        targets=np.asarray(targets,dtype=int)
        counts=np.bincount(targets,minlength=3)
        assert (counts>0).all()
        power=self.spec['class_balance_power']
        sample_weights=np.power(counts[targets].astype(float),-power)
        sample_weights*=len(targets)/sample_weights.sum()
        self.training_counts=counts.tolist()
        self.training_weight_sums=[float(sample_weights[targets==c].sum()) for c in range(3)]
        self.model.fit(self.matrix(features,idx),targets,sample_weight=sample_weights)
        assert list(self.model.classes_)==[0,1,2]
        return self

    def predict(self, features, idx):
        p=self.model.predict_proba(self.matrix(features,idx))
        return p.argmax(1),p
