# Bioprocess Development Data Intelligence Platform

A Streamlit web app for integrating, exploring, analyzing, and explaining bioprocess development data.

## Current milestone

Milestone 5 adds batch-level Pearson correlations, media-group comparisons, Welch/classical ANOVA, effect sizes, confidence intervals, and assumption diagnostics. Earlier data preparation and exploration workflows remain available. Scientific AI Copilot is the next planned feature.

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

## Roadmap

1. **Foundation:** environment, entry point, navigation, and local launch.
2. **Demo data:** reproducible synthetic batches and a data dictionary.
3. **Integration and quality:** uploads, validation, cleaning reports, and SQL joins.
4. **Exploration:** interactive trends and batch comparisons.
5. **Statistics:** correlations, media comparisons, and appropriate statistical tests.
6. **AI explanations:** free OpenRouter models, evidence summaries, and text export.
7. **Deployment:** Streamlit Community Cloud setup and end-to-end verification.
8. **Advanced analytics:** PCA, predictive models, and anomaly investigation.

## Future deployment and secrets

The planned Community Cloud entry point is app.py. Commit the app files and requirements.txt to GitHub, select the repository and branch in Community Cloud, and choose Python 3.13. Deployment is a later milestone.

No API key is required yet. When OpenRouter is added, local credentials will go in the ignored .streamlit/secrets.toml; cloud credentials will go in Community Cloud's Secrets settings. Never commit API keys.

## References

- [Streamlit multipage navigation](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation)
- [uv: using existing environments](https://docs.astral.sh/uv/pip/environments/)
- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
