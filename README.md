# Bioprocess Development Data Intelligence Platform

A Streamlit web app for integrating, exploring, analyzing, and explaining bioprocess development data.

## Current milestone

Milestone 2 adds 60 reproducible synthetic CHO batches, clean and deliberately messy demo variants, previews, and CSV downloads on the Overview page. The other four pages describe upcoming capabilities. Data upload, analytics, and OpenRouter calls are not implemented yet.

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
