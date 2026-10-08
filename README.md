# Experiment Lab

An end-to-end A/B testing and scheduled sequential experimentation platform built with Python, Streamlit, Pandas, SciPy, and Statsmodels.

## Run locally

Open a terminal in this folder and run:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit, normally http://localhost:8501.

## Features

- Plan sample size, target power, MDE, unequal allocation, and duration.
- Identify an underpowered sample using the effect specified before the experiment.
- Analyze binary conversions from summary counts or user-level CSV uploads.
- Report absolute change, relative lift, exact p-values, and approximate Newcombe confidence intervals.
- Monitor preplanned sequential checkpoints with conservative Bonferroni protection.
- Export plain-language business recommendations as Markdown and HTML reports.
- Simulate fixed-horizon, uncorrected peeking, and corrected sequential experiments.

The dashboard has five tabs: Plan, Analyze, Sequential, Simulate, and Guide. Sample CSVs are in `data/` and can be downloaded from the dashboard. Calculations run locally; no account or API key is needed.

## Data formats

User-level CSV:

```csv
user_id,variant,converted
u1,control,0
u2,treatment,1
```

A user appears once. Variants are exactly `control` or `treatment`; outcomes are 0 or 1. Missing values, duplicate users, invalid variants, and nonbinary outcomes are rejected.

Sequential CSV (cumulative, not incremental):

```csv
look,control_n,control_conversions,treatment_n,treatment_conversions
1,1000,100,1000,122
2,2000,205,2000,250
```

Precommit the total number of looks, sample checkpoints, alpha, and primary metric. Rows must start at look 1, be consecutive, and add visitors in both arms; conversions added cannot exceed visitors added. Stop at the first significant look. Later rows are displayed for description only.

## Statistical methods and limits

Power planning uses Cohen's h and Statsmodels `NormalIndPower` for a two-sided test. Sequential planning divides alpha by the number of looks; the approximation targets the final corrected look, not an exact sequential-power calculation. Low rates and small samples can need exact simulation.

Analysis uses SciPy's two-sided Fisher exact test. At each of K fixed, precommitted looks, testing at alpha/K controls family-wise rejection under the null by the union bound, regardless of dependence among looks. This is conservative scheduled testing, not an unrestricted anytime-valid test. Outcomes must not determine the timing or number of looks.

Intervals use the approximate Newcombe method on treatment minus control. Sequential intervals use per-look alpha, but their family-wise coverage remains approximate. Exact Fisher p-values and approximate intervals can disagree near a threshold. Decisions use the Fisher threshold. Recommendations also consider the minimum business benefit and whether the horizon is complete. A significant conversion improvement still needs cost, revenue, and guardrail review.

This version supports independent users, two randomized arms, and binary conversion metrics. Continuous revenue, clustering, multiple variants, multiple primary metrics, equivalence tests, and multiplicity across experiments are outside its scope. Do not interpret a nonsignificant result as equivalence. There is no observed-power calculation from measured lift.

References: [Statsmodels planning](https://www.statsmodels.org/stable/generated/statsmodels.stats.power.NormalIndPower.solve_power.html), [SciPy Fisher exact](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html), [Statsmodels intervals](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.confint_proportions_2indep.html).

## Verification and reproducible benchmarks

```sh
python -m unittest discover -s tests -v
python benchmark.py
```

The benchmark runs 2,000 experiment paths (1,000 null, 1,000 alternative), saving raw trials, summary rates, and an interpretation in `data/`. This supports a portfolio demonstration with measured results. A universal 40% false-positive reduction or 80% power is not claimed. Results depend on baseline, lift, sample, schedule, and random seed.

Project layout:

- `app.py`: Streamlit dashboard
- `experiment/statistics.py`: validation, design, analysis, sequential decisions
- `experiment/reports.py`: recommendations and downloadable reports
- `experiment/simulation.py`: seeded experiment simulation
- `tests/`: statistical checks
- `data/`: examples and benchmark results

The repository is ready for a GitHub upload. No remote repository or deployment is created by this package.
