"""Isolated BART fit, allowing the parent to enforce a real time limit."""
import json
import sys
import numpy as np

if __name__ == '__main__':
    from bayesian_models import bart_predict
    with np.load(sys.argv[1], allow_pickle=False) as data:
        result = bart_predict(data['x'], data['y'], data['future'], draws=int(data['draws']))
    with open(sys.argv[2], 'w', encoding='utf-8') as output:
        json.dump(result, output, default=lambda value: value.tolist())
