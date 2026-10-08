"""Reproduce operating characteristics, rather than hardcoding résumé claims."""
from pathlib import Path
from math import sqrt
from experiment.simulation import simulate
from experiment.statistics import design

if __name__ == '__main__':
    out = Path(__file__).resolve().parent / 'data'
    plan = design(.1, .02, power=.8, alpha=.05, looks=5)
    raw = simulate(.1, .02, plan['control_n'], looks=5, trials=1000, seed=2026)
    raw.to_csv(out / 'benchmark_trials.csv', index=False)
    summary = raw.groupby('scenario')[['fixed_reject','naive_peeking_reject','sequential_reject']].mean()
    summary.to_csv(out / 'benchmark_summary.csv')
    null = summary.loc['Null (equal rates)']
    reduction = 1-null.sequential_reject/null.naive_peeking_reject if null.naive_peeking_reject else float('nan')
    text = f'''# Reproducible simulation benchmark

Seed: 2026; 1,000 trials under the null and 1,000 under the alternative.
Baseline: 10%; alternative treatment rate: 12%; five preplanned looks.
Final sample: {plan['control_n']:,} users per arm; overall alpha: 5%.

{summary.to_string(float_format=lambda x: f'{x:.3%}')}

Observed corrected-vs-naive false-positive reduction: {reduction:.1%}.
This is a Monte Carlo estimate for this configuration, not a general guarantee.
Maximum approximate 95% Monte Carlo margin: ±{1.96*sqrt(.25/1000):.1%}.
Planning uses a normal approximation; analysis uses two-sided Fisher exact tests.
Sequential protection uses alpha/5 at every predetermined look; exact-test discreteness can lower power.
'''
    (out / 'benchmark.md').write_text(text)
    print(text)
