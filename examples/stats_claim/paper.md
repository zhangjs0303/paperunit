# A Synthetic Seed-Sweep Paper: Claimed Accuracy versus Seed Noise

> **Fixture warning:** this is not a real paper and reports no real experiment.
> It is a deliberately fabricated, self-contained demo for the `paperunit`
> statistics checker. Do not cite it.

## Abstract

We train a two-feature threshold classifier on 500 synthetic examples and
sweep six seeds (0-5). We report a mean held-out accuracy of **92.3%** at the
paper's own reported precision (three decimals), state separately that the same
sweep supports **91.8%** within +/-1 percentage point, and provide a third
claim checked against the project's versioned margin policy.

## Claims

- **S1.** The seed-averaged test accuracy is 92.3% (checked at the paper's own
  reported precision: the default `paper_precision` margin, 0.001).
- **S2.** The seed-averaged test accuracy is 91.8% (explicit margin 1 percentage
  point, i.e. 0.01 in accuracy units).
- **S3.** The seed-averaged test accuracy is 91.8% (checked against the
  versioned policy `policies/margin/v1.json`, decision MARGIN-2026-10-19-01).

## Fixture notes

- The companion script `code/train.py` fits a threshold on a hardcoded
  synthetic dataset and prints `accuracy=...` for the requested `--seed`. The
  six documented seeds give accuracies 0.916, 0.920, 0.914, 0.922, 0.914,
  0.922: mean 0.918, sample SD about 0.0038. Runs are deterministic (no wall
  clock, no numpy, no entropy) and all six seeds finish in well under a second.
- Expected audit outcome: **S1 REFUTED** (the observed mean is 0.918, the gap
  to 0.923 is 0.005, larger than the 0.001 `paper_precision` margin, and the
  reported interval excludes 0.923), **S2 SUPPORTED** (0.918 is inside the
  +/-0.01 explicit margin), **S3 SUPPORTED** (gap 0 against the policy margin
  0.0005).
- Why this is not a "probability the paper is wrong": the audit reports the
  observed effect size and the resolution of this six-seed sweep. The minimum
  detectable effect is about 0.0043, which is coarser than S1's 0.001 margin;
  the observed 0.005 gap, however, is above that noise floor and the interval
  excludes the claimed value, so S1 fails within the stated scope. S2 and S3
  are tolerance matches, not statistical tests.
- The default interval is a percentile bootstrap over only six values, which
  is coarse and can understate its width at this sample size; the audit
  therefore reports the interval together with the minimum detectable effect
  instead of treating the interval alone as decisive.
- Scope limits: six seeds on one machine, a synthetic dataset, and one metric.
  Nothing here says anything about a real classifier, a real paper, or the
  authors.
