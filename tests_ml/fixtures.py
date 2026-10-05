from functools import lru_cache

from ml_demo.synthetic_data import SyntheticDatasetSpec, generate
from ml_demo.split import temporal_split
from ml_demo.modeling import fit, score


@lru_cache(maxsize=1)
def fitted_demo():
    train, validation, test = temporal_split(generate(SyntheticDatasetSpec(rows=1800)))
    bundle, info = fit(train, validation)
    return train, validation, test, bundle, score(bundle, test), info
