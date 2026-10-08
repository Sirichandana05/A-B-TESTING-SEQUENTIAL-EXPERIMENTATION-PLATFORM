from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
from experiment.statistics import design, planned_power, detectable_effect, analyze, sequential, recommendation
from experiment.reports import report, html_report
from experiment.simulation import simulate

DATA = Path(__file__).resolve().parent / 'data'

st.set_page_config(page_title='Experiment Lab', page_icon='🧪', layout='wide')
st.markdown('''<style>.stApp{background:#f5f7fb}h1,h2,h3{color:#142440}div[data-testid="stMetric"]{background:white;border:1px solid #e0e6ef;padding:18px;border-radius:12px} .block-container{padding-top:2.5rem} </style>''', unsafe_allow_html=True)
st.caption('EXPERIMENT LAB / DECISIONS WITH EVIDENCE')
st.title('Turn experiments into confident decisions.')
st.write('Plan the sample. Measure the effect. Know when the evidence is ready.')
with st.sidebar:
    st.header('Experiment settings')
    name = st.text_input('Experiment name', 'Checkout redesign')
    alpha = st.selectbox('Overall significance level', [.05, .01, .10], format_func=lambda x: f'{x:.0%}')
    business = st.number_input('Minimum business benefit (percentage points)', 0., 50., .5, .1) / 100
    st.info('Binary conversion metrics: one independent, randomized observation per user. An increase is treated as beneficial.')
plan, fixed, seq, sims, guide = st.tabs(['01 · Plan', '02 · Analyze', '03 · Sequential', '04 · Simulate', '05 · Guide'])


def downloads(text, key):
    a, b = st.columns(2)
    a.download_button('Download Markdown report', text, file_name='experiment-report.md', mime='text/markdown', key=key+'md')
    b.download_button('Download HTML report', html_report(text), file_name='experiment-report.html', mime='text/html', key=key+'html')


def metrics(r):
    cols = st.columns(4)
    cols[0].metric('Control conversion', f"{r['control_rate']:.2%}")
    cols[1].metric('Treatment conversion', f"{r['treatment_rate']:.2%}")
    cols[2].metric('Absolute improvement', f"{100*r['difference']:+.3f} pp")
    cols[3].metric('Two-sided p-value', f"{r['p_value']:.4g}")
    st.write(f"{100*(1-r['alpha']):.2f}% approximate Newcombe interval: **{100*r['ci_low']:.3f} to {100*r['ci_high']:.3f} percentage points**")
    st.bar_chart(pd.DataFrame({'Conversion rate': [r['control_rate'], r['treatment_rate']]}, index=['Control', 'Treatment']))

with plan:
    st.header('Design your experiment')
    st.write('Minimum detectable effect (MDE) is an absolute change in percentage points. A 10% baseline plus 2 pp means a 12% treatment rate.')
    c1, c2, c3 = st.columns(3)
    baseline = c1.number_input('Baseline conversion (%)', .01, 99.9, 10., .5) / 100
    mde = c2.number_input('MDE (percentage points)', .01, 50., 2., .1) / 100
    target = c3.slider('Target power', .5, .99, .8, .01)
    c1, c2, c3 = st.columns(3)
    ratio = c1.number_input('Treatment / control allocation', .1, 10., 1., .1)
    looks = c2.number_input('Preplanned looks (1 = fixed horizon)', 1, 20, 1)
    traffic = c3.number_input('Eligible experiment users per day', 1, 10000000, 1000)
    try:
        d = design(baseline, mde, target, alpha, ratio, looks)
        cols = st.columns(3)
        cols[0].metric('Control users', f"{d['control_n']:,}")
        cols[1].metric('Treatment users', f"{d['treatment_n']:,}")
        cols[2].metric('Estimated duration', f"{int(np.ceil((d['control_n']+d['treatment_n'])/traffic))} days")
        st.caption('Normal-approximation planning via Statsmodels. Exact Fisher testing can be more conservative. Sequential planning targets the final corrected look; confirm actual operating power through simulation. Account for full weekly cycles and delayed outcomes.')
        ns = np.unique(np.linspace(max(2, int(d['control_n']*.1)), d['control_n']*2, 40, dtype=int))
        curve = pd.DataFrame({'Control users': ns, 'Power': [planned_power(baseline, mde, int(n), max(1, int(n*ratio)), alpha/looks) for n in ns]})
        st.line_chart(curve.set_index('Control users'))
        available = st.number_input('Available users per arm (power check)', 2, 10000000, 1000)
        power_available = planned_power(baseline, mde, available, available, alpha/looks)
        detectable = detectable_effect(baseline, available, available, target, alpha/looks)
        st.write(f'Power for the specified effect at this sample: **{power_available:.1%}**.')
        if power_available < target:
            st.warning('This sample is underpowered for the effect you specified.')
        st.write('Detectable improvement at target power: ' + (f'**{100*detectable:.3f} pp**' if detectable is not None else 'not attainable with this sample.'))
        st.download_button('Download experiment plan', pd.DataFrame([{'name':name,'baseline':baseline,'mde':mde,'target_power':target,'overall_alpha':alpha,'planned_looks':looks,'allocation_ratio':ratio,**d}]).to_csv(index=False), 'experiment-plan.csv', 'text/csv')
    except ValueError as e:
        st.error(str(e))

with fixed:
    st.header('Fixed-horizon A/B analysis')
    source = st.radio('Input format', ['Summary counts', 'User-level CSV'], horizontal=True)
    values = None
    if source == 'Summary counts':
        c1, c2 = st.columns(2)
        na = c1.number_input('Control visitors', 1, 100000000, 5000)
        xa = c1.number_input('Control conversions', 0, 100000000, 500)
        nb = c2.number_input('Treatment visitors', 1, 100000000, 5000)
        xb = c2.number_input('Treatment conversions', 0, 100000000, 620)
        values = na, xa, nb, xb
    else:
        st.caption('CSV columns: user_id, variant (control or treatment), converted (0 or 1). One row per user; duplicate users are rejected.')
        upload = st.file_uploader('User-level observations', type='csv')
        st.download_button('Download sample user data', (DATA / 'users.csv').read_bytes(), 'users.csv', 'text/csv')
        if upload:
            try:
                df = pd.read_csv(upload)
                if not {'user_id','variant','converted'}.issubset(df.columns):
                    raise ValueError('Required columns: user_id, variant, converted.')
                if df.empty or df[['user_id','variant','converted']].isna().any().any() or df.user_id.duplicated().any():
                    raise ValueError('Data must contain nonmissing, unique user IDs and nonmissing outcomes and variants.')
                if not df.variant.isin(['control','treatment']).all() or not df.converted.isin([0,1]).all():
                    raise ValueError('Variants must be control/treatment; outcomes must be 0/1.')
                a, b = df[df.variant == 'control'], df[df.variant == 'treatment']
                values = len(a), int(a.converted.sum()), len(b), int(b.converted.sum())
                st.dataframe(df.head(10), hide_index=True)
            except (ValueError, pd.errors.ParserError) as e:
                st.error(str(e))
    complete = st.checkbox('The preplanned sample and duration have been reached', value=False)
    if values:
        try:
            r = analyze(*values, alpha)
            metrics(r)
            decision = dict(r)
            if not complete:
                decision['significant'] = False
                st.warning('Interim fixed-horizon results are descriptive. Wait for the preplanned horizon to make a decision; repeated peeking invalidates fixed-horizon testing.')
            st.info(recommendation(decision, business, complete))
            downloads(report(name, decision, business, complete), 'fixed')
        except ValueError as e:
            st.error(str(e))

with seq:
    st.header('Scheduled sequential testing')
    st.write('Commit to K checkpoints before the experiment. Each two-sided Fisher test uses α/K, giving a conservative family-wise false-positive bound by the union bound. Checkpoints must be determined independently of observed outcomes.')
    k = st.number_input('Total preplanned checkpoints', 1, 20, 5)
    st.caption('Cumulative counts at each look, ordered 1 through K. After a stopping decision, subsequent rows are descriptive only.')
    upload_seq = st.file_uploader('Upload cumulative checkpoints', type='csv', key='seqfile')
    example = (DATA / 'checkpoints.csv').read_bytes()
    st.download_button('Download sample checkpoints', example, 'checkpoints.csv', 'text/csv')
    use_example = st.checkbox('Use sample checkpoints', value=True)
    try:
        frame = pd.read_csv(upload_seq) if upload_seq else pd.read_csv(DATA / 'checkpoints.csv') if use_example else None
        if frame is not None:
            result = sequential(frame, k, alpha)
            st.dataframe(result[['look','control_n','treatment_n','difference','p_value','adjusted_p','decision']], hide_index=True, width='stretch')
            st.line_chart(result.set_index('look')[['p_value','adjusted_p']])
            selected = result[result.eligible].iloc[-1].to_dict()
            metrics(selected)
            done = selected['look'] == k or selected['significant']
            st.info(recommendation(selected, business, done))
            downloads(report(name, selected, business, done, f"Scheduled sequential — Fisher exact, Bonferroni over {k} looks; decision at look {selected['look']}"), 'seq')
            st.download_button('Download checkpoint results', result.to_csv(index=False), 'sequential-results.csv', 'text/csv')
    except (ValueError, pd.errors.ParserError) as e:
        st.error(str(e))

with sims:
    st.header('Validate the design with simulations')
    st.write('Compare a single final test, uncorrected repeated peeking, and corrected sequential testing on the same simulated paths. Null rejection measures false positives; alternative rejection measures power for any difference.')
    c1,c2,c3 = st.columns(3)
    sim_n = c1.number_input('Simulated users per arm', 20, 100000, 2000)
    sim_trials = c2.selectbox('Trials per scenario', [50, 200, 500, 1000], index=1)
    sim_looks = c3.number_input('Simulated checkpoints', 1, 20, 5)
    c1,c2,c3 = st.columns(3)
    sim_base = c1.number_input('Simulation baseline (%)', .1, 99., 10.) / 100
    sim_lift = c2.number_input('Simulation lift (pp)', .01, 50., 2.) / 100
    seed = c3.number_input('Random seed', 0, 1000000, 42)
    if st.button('Run simulations', type='primary'):
        try:
            with st.spinner('Generating randomized experiments…'):
                raw = simulate(sim_base, sim_lift, sim_n, sim_looks, sim_trials, alpha, seed)
            st.session_state.sim_results = raw
            st.session_state.sim_settings = f'{sim_trials} trials per scenario; n={sim_n}/arm; baseline={sim_base:.1%}; lift={sim_lift:.1%}; K={sim_looks}; alpha={alpha}; seed={seed}'
        except ValueError as e:
            st.error(str(e))
    if 'sim_results' in st.session_state:
        raw = st.session_state.sim_results
        st.caption('Saved simulation: '+st.session_state.sim_settings)
        summary = raw.groupby('scenario')[['fixed_reject','naive_peeking_reject','sequential_reject']].mean()
        st.dataframe(summary.style.format('{:.1%}'), width='stretch')
        st.bar_chart(summary.T)
        st.write('Average users per arm at the corrected stopping point:')
        st.dataframe(raw.groupby('scenario').sequential_n_per_arm.mean())
        st.caption('Monte Carlo estimates vary by seed and trial count. Maximum approximate 95% sampling margin is 1.96 × √(0.25 / trials). These results do not establish a universal 40% false-positive reduction or 80% power.')
        st.download_button('Download simulation results', raw.to_csv(index=False), 'simulation-results.csv', 'text/csv')

with guide:
    st.header('How to use the platform')
    st.markdown('''1. Choose one binary primary metric and a business threshold. Randomize users into stable groups.
2. Plan sample size, allocation, duration, and checkpoints before collecting data.
3. For a fixed horizon, make the decision once at the planned end. For sequential testing, use only the planned checkpoints.
4. Upload observations or cumulative counts. Read the effect, uncertainty, and recommendation together.
5. Export your report, then review revenue, costs, and guardrails before rollout.

**Supported:** two independent arms and binary conversion outcomes. Pricing experiments can use purchase conversion as the primary metric.

**Outside this version:** revenue/continuous metrics, clustered users, multiple variants, multiple primary metrics, equivalence tests, and unrestricted anytime monitoring. No adjustment for multiple experiments is automatic.

**Power:** planning uses the anticipated baseline and effect, not observed lift. Normal-approximation sample sizes are estimates, particularly at very low conversion rates. Simulations validate the actual exact-test design.

**Sequential intervals:** the Newcombe interval uses α/K but is approximate. The exact false-positive guarantee applies to the Fisher test decisions under the stated assumptions, not exact confidence-interval coverage.

[Statsmodels power documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.power.NormalIndPower.solve_power.html) · [SciPy Fisher exact documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html)
''')
