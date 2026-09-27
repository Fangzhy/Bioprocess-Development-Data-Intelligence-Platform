# Bioprocess Development Data Intelligence Platform

A Streamlit web app for integrating, exploring, analyzing, and explaining bioprocess development data.

## Current milestone

Milestone 7 adds a Scientific AI Copilot using a free OpenRouter model, evidence previews, session-level response reuse, and computed fallback summaries. Earlier preparation, statistics, predictive modeling, and Bayesian forecasting workflows remain available.

## Run locally with your existing uv environment

Run these commands in PowerShell from this repository's folder. They use your existing .venv.

1. Check Python:

   ~~~powershell
   .\.venv\Scripts\python.exe --version
   ~~~

2. Install dependencies:

   ~~~powershell
   uv pip install --python .venv/Scripts/python.exe -r requirements.txt
   ~~~

3. Start the app:

   ~~~powershell
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ~~~

4. Open the URL printed in the terminal (normally http://localhost:8501). Visit all five pages using the sidebar. Stop the server with **Ctrl+C**.

The existing environment uses Python 3.13. Select Python 3.13 for deployment too. Activation is optional because these commands explicitly select the environment.

## How the app works

- app.py sets the shared layout and registers pages with st.Page and st.navigation.
- views/ contains the page scripts. The selected page is executed by page.run().
- requirements.txt specifies the dependency for local installation and cloud deployment.
- .gitignore excludes the virtual environment and .streamlit/secrets.toml.

Streamlit reruns Python code when users interact with widgets. Loaded demo tables are retained in st.session_state under demo_data, with their variant under demo_variant. Selecting a different variant does not replace data until you click Load demo data. State belongs to the current session, not permanent storage.

## Demo data walkthrough

1. Start the app and select Clean on the Overview page.
2. Click **Load demo data**. Inspect the four tabs and download a CSV. Previews show the first 100 rows; downloads contain every row.
3. Select Messy and click **Load demo data** again to replace the loaded tables.
4. Expand the data dictionary to learn the units and relationships. The same document is in [docs/data_dictionary.md](docs/data_dictionary.md).

The four datasets live under data/demo/clean and data/demo/messy. The issue_manifest.csv records deliberately injected defects. B014, B027, and B048 are unusual process runs in both variants, separately from those defects. All data is synthetic and illustrates software behavior, not validated biology.

Regenerate the bundled files (overwrites the demo CSVs only):

~~~powershell
.\.venv\Scripts\python.exe data_generation.py
~~~

Try a different seed in a separate folder:

~~~powershell
.\.venv\Scripts\python.exe data_generation.py --seed 7 --output-dir data/demo_seed7
~~~

Run data integrity and reproducibility checks:

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
~~~

### Try it yourself

Start the app and visit each page. Change the introductory sentence in views/overview.py and save it. Rerun if prompted and observe the updated text. This demonstrates how a Python page script becomes a web interface.

## Integration and quality walkthrough

1. On Overview, load the Messy demo.
2. Open **Data Integration & Quality** and click **Use loaded demo**. This copies the current demo into a separate working source.
3. Inspect the source report and original table previews. Reports count overlapping findings, not unique bad records.
4. Select **Remove exact duplicate rows** and **Exclude rows with unknown batch IDs**. Review the proposed row removals and remaining findings.
5. Click **Apply reviewed changes**. Originals remain unchanged. Working copies and the row-level cleaning log are downloadable.
6. Review the SQL query and integrated table: 60 metadata batches, one row each. Missing measurements and time gaps remain warnings; no interpolation or outlier deletion occurs.

For uploads, supply all four CSV or .xlsx files (first worksheet), each at most 10 MB / 100,000 rows, and confirm units match the [data dictionary](docs/data_dictionary.md). Old .xls files are not supported. IDs should be stored as text in Excel to preserve leading zeros. Unit correctness cannot be inferred from numeric values alone. Empty cells are missing; literal text such as NA is preserved and may be flagged in numeric columns.

Required columns, numeric parsing, date parsing, missing keys, duplicate/conflicting keys, and foreign-key references are checked. Broad numeric ranges flag suspicious values; these are not scientifically validated process specifications. Missing measurements and out-of-range non-key values are warnings and remain visible. Invalid numeric/date text, missing columns/keys, and unresolved duplicate/foreign keys block SQL. Correct such errors in the source and reload. Extra columns remain in prepared downloads but are excluded from the fixed SQL schema.

Expected sampling duration and intervals are configurable; defaults match the 336-hour demo. Time gaps include expected start/end points and missing batch histories. Irregular sampling can therefore produce warnings. Rows with time outside the configured duration or negative/fractional hours block integration.

Applying cleaning always starts from the original source; it does not accumulate removals across clicks. Parsing normalizes numeric types on copies, while originals remain available. Changing checkbox choices does not alter the last applied result until Apply is clicked. Loading another source clears the applied result. Merely changing a source selector does not replace the active workspace; its label remains visible.

SQLite uses explicit primary/foreign keys and an in-memory database, created and closed for each integration. A left join preserves metadata batches even when quality records are absent. Sensor and assay tables remain separate. Data is session-scoped and not persisted to shared storage. No API keys are needed.

Implementation: integration.py contains reusable validation, cleaning, upload, and SQL functions; views/integration.py handles the interface. Run the unittest command above to check data reproducibility, ingestion, cleaning, SQL row counts, and Streamlit navigation/session behavior.

## Process Explorer walkthrough

1. Load a demo on Overview, use it on Data Integration & Quality, and apply reviewed changes. For the messy demo, remove exact duplicates and exclude unknown batch IDs first.
2. Open **Process Explorer**. It uses the last applied working data and sampling schedule, not an unreviewed demo or upload. Blocking validation errors prevent charts; remaining warnings are visible.
3. Filter by media, select up to eight batches and six measurements, and adjust the time window. Clear the media filter to show all media. Separate plots preserve units and distinguish sensor from offline measurements.
4. Hover to inspect values, zoom or pan using Plotly controls, and use the legend to hide individual traces. Missing measurements and gaps longer than the configured sampling interval break lines; values are not interpolated.
5. Inspect the batch summary and choose a comparison metric. Window statistics exclude missing values and include per-metric observation counts. Means are observation-weighted, not time-weighted; sample standard deviation requires two measurements. Missing summaries remain blank, not zero. Final titer is explicitly a full-run endpoint, unaffected by the selected time window.
6. Download the summary or filtered sensor/assay observations. Data previews show the first 100 rows; CSVs include all filtered rows and retain the source columns.

The explorer does not establish causation or perform statistical significance tests. Measurements outside plausibility ranges are retained with the existing quality warnings. Reapply changes on the integration page after changing its expected sampling schedule. Loading a new integration source clears the applied data, so the explorer asks for preparation again.

Implementation: exploration.py provides filtering, summary calculations, and figure construction; views/explorer.py provides the UI. The full unittest suite includes empty selections, missing data, line-gap handling, summary calculations, media filters, and earlier-milestone regression checks.

## Statistical Analysis walkthrough

1. Prepare and apply data in Data Integration & Quality, then open **Statistical Analysis**.
2. Optionally filter media groups. The cohort has one row per batch; full-run process summaries include measurement counts. Explorer time-window filters do not affect this page.
3. Choose two different metrics for Pearson correlation. Inspect the scatter plot, complete-pair count, excluded batches, r, two-sided p-value, and Fisher 95% confidence interval. At least four complete pairs and nonconstant metrics are required.
4. Choose a response metric for media comparison. Review sample sizes, missing counts, means, sample SDs, individual 95% Student-t mean intervals, and batch-level box/scatter plots.
5. Welch ANOVA is the default for unequal variances; classical ANOVA assumes equal variances. Both require independent observations and appropriate group distributions. At least two groups with three observations each and nonzero group variance are required by this app.
6. Inspect Shapiro-Wilk and median-centered Levene diagnostics. These do not prove assumptions, and should not mechanically determine method choice. Descriptive eta-squared is the between-group share of observed variation, not a causal or Welch-adjusted effect. An omnibus p-value does not identify which pairs differ.
7. Download the cohort, correlation results, group summaries, ANOVA result, and diagnostics.

Missing values are excluded per analysis, without imputation. Tests are exploratory and unadjusted for multiple comparisons. Repeatedly trying outcomes or filters raises false-positive risk. Independence and confounding require study-design judgment; the synthetic data is not experimental evidence. Full-run features are descriptive and are not early prediction inputs.

Statistical calculations live in statistical_analysis.py and use SciPy. Checks include a hand-calculable ANOVA example (F = 13.5), batch grain, missing/constant/small inputs, and UI navigation. See the [SciPy ANOVA documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.f_oneway.html) and [Pearson correlation documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html) for method assumptions.

## Predictive Modeling & Forecasting walkthrough

Prepare and apply the clean demo (or resolve blocking errors in the messy demo), then open **Predictive Modeling**. Models run only when you click their training buttons. Results are session-scoped and hidden as stale when input data or settings change. No models or uploaded data are written to shared disk.

### Final-quality prediction

1. Default target: final titer at hour 336, predicted from measurements through hour 168. Other targets are aggregation, purity, downstream recovery yield, and the glycosylation metric. The latter endpoints contain substantial random noise in this demo; poor scores are informative.
2. Inspect the feature table. Metadata includes media, scale, and inoculation density. Process/assay features include means, minima, maxima, last observed values, and counts through the selected cutoff. Offline product titer, final-quality values, batch IDs, dates, lots, and operators are excluded from predictors.
3. Select models and click **Run model comparison**. A mean baseline always runs. Ridge, random forest, XGBoost, and a small MLP neural network are selected by default. Select BART explicitly for Bayesian tree sampling.
4. An 80/20 fixed batch split reserves 12 of the 60 demo batches. Identical three-fold CV splits operate within the remaining 48. Imputation, one-hot encoding, and scaling are fitted inside each training fold; unseen media categories are tolerated. The MLP also scales its target using training data only. There is no hyperparameter search.
5. Compare fold-average RMSE, MAE, R², runtime, and improvement over the mean baseline. Fold SD is not a confidence interval. Out-of-fold plots and exports never include reserved test predictions. Model failures are reported rather than presented as successful fits.
6. Choose a model using development results, then explicitly evaluate it on the reserved test set. Repeated test-set evaluation makes later scores exploratory. Download predictions, settings, split membership, and feature definitions.

BART uses 20 trees, a Gaussian outcome likelihood, two sequential chains, and selectable 100/200/500 draws plus the same number of tuning iterations. Its mean-response interval is separate from the new-observation predictive interval. The app reports maximum R-hat and minimum bulk ESS across monitored variables, and flags R-hat above 1.05 or bulk ESS below 100. These diagnostic thresholds do not guarantee convergence or calibration. Short runs can fail diagnostics; estimates must then remain provisional.

The interactive regression limit is 30–500 labeled batches. Missing targets are excluded, never imputed. Missing input measurements are imputed from training data only. Partial histories can still bias features. This estimates performance for similar batches, not future campaigns or unseen lots. The demo has only 60 independent runs, regardless of its number of sensor rows.

BART remains off by default. If selected in the app, it runs in an isolated worker with a **60-second total cross-validation budget**, including worker startup. A timed-out run is terminated and omitted; completed results from other models remain available. Reserved-test BART evaluation has a separate 60-second limit. Temporary worker inputs/results are removed after execution. Direct Bayesian smoke checks can still run without the app comparison budget. BSTS forecasting is unchanged.

### Within-batch BSTS forecasting

1. Choose a batch and measurement. Sensor glucose is the default; sensor lactate, DO, and sparse offline product titer are also available.
2. Choose a historical cutoff and 24/48/72-hour horizon. Both must align with the configured cadence. At least 12 sensor or 10 offline observations and 60% grid coverage are required. Offline titer at hour 168 has only eight observations, so choose a later cutoff. At most 200 historical grid points are supported interactively.
3. Click **Run Bayesian forecast**. A PyMC/pymc-extras local level + trend model with observation noise fits only this batch's history. Missing grid points stay missing; observations are not interpolated. There are no seasonal terms, future regressors, or causal-impact claims.
4. Inspect the forecast boundary, mean, 80%/95% predictive bands, runtime, and diagnostics. Gaussian forecasts can exceed physical bounds and are not silently clipped. Unexpected process shifts may invalidate extrapolation.
5. **Run historical backtest** fits up to three earlier origins with nonoverlapping forecast windows, all ending by the selected cutoff. Histories overlap, so errors are not independent. Compare BSTS with persistence and linear drift. Scores, interval coverage, and widths are evaluated only at available future measurements and are reported by horizon as well as overall. Forecast scores are separate from the batch-quality leaderboard.

BSTS standardizes history using historical observations only. Priors in standardized units: initial level/trend Normal(0, [2, 0.5]); level/trend innovation SD HalfNormal([0.2, 0.05]); measurement SD HalfNormal(0.5); initial state covariance 0.1 × identity. Two sequential Metropolis chains use selectable 100/200/500 draws and tuning iterations. These are transparent teaching defaults, not scientifically calibrated priors. The diagnostics include initial state and noise parameters.

### Runtime and testing

The Bayesian packages are imported lazily. PyTensor defaults to FAST_COMPILE with its Python linker to support this Windows environment without a C++ compiler; advanced users can override PYTENSOR_FLAGS before launch. Bayesian runs may take minutes, especially rolling backtests; CPU workers and sampling counts are bounded. Community Cloud deployment and resource limits still require testing on the actual host.

Run the regular 25-test suite with the unittest command above. It checks previous milestones, cutoff leakage, batch splits, training-only preprocessing, model fitting, forecast grids, chronological backtests, and UI stale-result behavior. Forecast orchestration unit tests use a lightweight deterministic predictor; real Bayesian compatibility checks are separate:

~~~powershell
.\.venv\Scripts\python.exe bayesian_smoke.py
.\.venv\Scripts\python.exe bayesian_smoke.py --demo
~~~

The first runs tiny BART/BSTS fits to verify output shapes and interval ordering, not inference quality. The second benchmarks real demo BART test predictions and a sensor forecast with 100 draws per chain, printing diagnostics and runtime. Code is split across modeling.py, bayesian_models.py, forecasting.py, and views/modeling.py.

Measured locally on this Windows environment: the 100-draw demo BART test fit took about 9 seconds; the 43-point sensor BSTS fit and forecast took about 131 seconds. Both failed the sampling diagnostic thresholds at this budget, so their inference remains provisional. Longer runs may help but do not guarantee convergence. These measurements are not Community Cloud benchmarks. Use `python bayesian_smoke.py --edge` for tiny real fits with a missing sensor observation and sparse offline titer. Missing measurements are marginalized through the state-space model; raw observations remain missing and are not filled by future values.

## Scientific AI Copilot walkthrough

1. Install updated requirements with the existing uv command above. Use the root .env (not views/.env), or Streamlit secrets, to configure OPEN_ROUTER_API (OPENROUTER_API_KEY is also accepted) and OPENROUTER_MODEL. See .env.example for names only; never commit credentials. Priority is Streamlit secrets, environment variables, then the root .env.
2. Prepare and apply data, then open Scientific AI Copilot. Choose statistical explanation, model comparison, forecast explanation, or study summary.
3. Review the exact JSON evidence and the explanation instructions. Statistical summaries are recomputed for full-run final titer by media and peak-VCD correlation; they are not copies of arbitrary selections from the Statistics page. Modeling and forecasting explanations use the latest completed results matching the applied data, with the settings recorded at completion. If results predate this milestone, rerun them to attach source/settings provenance.
4. Click Generate AI explanation to send the previewed summary to OpenRouter and its model provider. Raw input tables are not sent. Summaries may contain media labels; inspect the preview before using uploaded data. The key is sent only in the authentication header to OpenRouter.
5. Check the explanation against its evidence identifiers. Prompts constrain unsupported claims, but the app does not automatically prove every AI claim. AI text is displayed as plain text. Failed Bayesian diagnostics remain visible as a warning independent of the explanation.
6. Download the explanation and evidence, or use the computed template summary without an API call. Up to ten explanations are reused within the session for identical evidence, instructions, and model. Stale explanations are hidden; there is no shared result cache.

The default model is dots-studio/dots-3-note-preview:free. Each generation verifies that the configured model is listed with zero prompt/completion/request pricing, then sets zero-price provider caps. Only :free IDs or openrouter/free are accepted, with no automatic paid fallback. Free availability can change. Requests disable reasoning and allow 2,048 output tokens; empty or truncated responses are rejected. Connection/read timeouts are bounded, with at most one retry after two seconds for rate limits or transient gateway/service errors. Missing keys, unavailable models, and API failures leave the computed template available.

Local .env files are not deployed. On Community Cloud, enter the same configuration names in app Secrets, for example:

~~~toml
OPEN_ROUTER_API = "your-key-here"
OPENROUTER_MODEL = "dots-studio/dots-3-note-preview:free"
~~~

Copilot tests mock network requests and never use the local key. Run the full unittest suite for key precedence, free-only enforcement, retry/error behavior, incomplete responses, stale evidence, explicit generation, response reuse, and previous-milestone regression tests. Live smoke tests should send synthetic evidence only. Prompt grounding is a safeguard, not a guarantee of factual correctness.

## Roadmap

1. **Foundation:** environment, entry point, navigation, and local launch.
2. **Demo data:** reproducible synthetic batches and a data dictionary.
3. **Integration and quality:** uploads, validation, cleaning reports, and SQL joins.
4. **Exploration:** interactive trends and batch comparisons.
5. **Statistics:** correlations, media comparisons, and appropriate statistical tests.
6. **Predictive modeling and forecasting:** final-quality regressors, BART, BSTS, validation, and uncertainty.
7. **AI explanations:** free OpenRouter models, evidence summaries, and text export.
8. **Deployment:** Streamlit Community Cloud setup and end-to-end verification.
9. **Advanced analytics:** PCA, deeper interpretation, and anomaly investigation.

## Future deployment and secrets

The planned Community Cloud entry point is app.py. Commit the app files and requirements.txt to GitHub, select the repository and branch in Community Cloud, and choose Python 3.13. Deployment is a later milestone.

Only AI generation requires an OpenRouter key. Local credentials can be stored in the ignored root .env or .streamlit/secrets.toml; cloud credentials belong in Community Cloud's Secrets settings. Computed analytics and template summaries work without a key. Never commit API keys.

## References

- [Streamlit multipage navigation](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation)
- [uv: using existing environments](https://docs.astral.sh/uv/pip/environments/)
- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
