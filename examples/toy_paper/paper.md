# A Synthetic Toy Paper: Two-Feature Threshold Classification

> **Fixture warning:** this is not a real paper and reports no real experiment.
> It is a deliberately fabricated, self-contained demo for the `paperaudit`
> prototype. The numbers below are chosen to create a mix of supported and
> refuted claims. Do not cite it.

## Abstract

We study a two-feature threshold classifier on a hardcoded synthetic dataset.
On 1,000 held-out examples the classifier reaches **92.3% accuracy**, and
training takes **4.2 seconds** on a laptop CPU. The implementation is
deterministic and reports the dataset size. These results suggest that simple
threshold rules can be both accurate and cheap.

## Fixture notes

- The companion script `code/train.py` uses 500 synthetic examples, not 1,000,
  and its computed accuracy is 91.8%, not 92.3%.
- The script prints a fixed `train_seconds=4.200` so that re-running the audit
  is byte-reproducible. It does not measure wall-clock training time; the
  4.2-second claim is part of the synthetic story, not a benchmark.
- The expected audit outcome is C1 REFUTED, C2 SUPPORTED, C3 SUPPORTED,
  C4 REFUTED. C4 checks the fabricated 1,000-example statement.
