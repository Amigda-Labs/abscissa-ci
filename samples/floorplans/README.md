# Synthetic Floor Plan Samples

These five generated plans are controlled fixtures for Area Agent evaluation.

- Images contain room labels and metric dimensions only.
- Images intentionally do not contain room areas or total areas.
- Answer sheets contain the ground-truth area computations.
- Gold extraction JSON files match the Area Agent structured schema for
  deterministic harness tests.
- Dimensions are net internal room dimensions.
- SVG files are the source drawings; PNG files are generated for model input.

Regenerate the set from the repository root:

```bash
PYTHONPATH=src .venv/bin/python tools/generate_synthetic_floorplans.py
```

Run the Area Agent evaluation:

```bash
PYTHONPATH=src .venv/bin/python -m abscissa_ci.cli eval-samples
```
