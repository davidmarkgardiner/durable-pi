"""Deliberately scripted demo decisions. No network, model or API key."""
LABEL = 'Synthetic decision (scripted HTTP rule)'


def classify(sample):
    incident = sample['status'] >= 500
    return {'model': 'synthetic-http-status-rule/v1', 'synthetic': True,
        'answers': {'verdict': {'type': 'choice', 'choice': 'incident' if incident else 'normal',
            'confidence': 1.0, 'probabilities': {'normal': 0.0 if incident else 1.0, 'incident': 1.0 if incident else 0.0}}},
        'usage': {'input_tokens': 0, 'output_tokens': 0}}
