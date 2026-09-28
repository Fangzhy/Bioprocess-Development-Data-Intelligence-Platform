# Deploy through GitHub to Streamlit Community Cloud

This guide uses the existing repository and current `dev` branch. Preparing files does not publish or deploy the application.

| Setting | Value |
|---|---|
| Repository | Fangzhy/Bioprocess-Development-Data-Intelligence-Platform |
| Branch | dev |
| Entry point | app.py |
| Python | 3.13 |
| Python dependencies | requirements.txt |
| Linux packages | packages.txt (libgomp1 for native OpenMP libraries such as XGBoost) |
| Streamlit configuration | .streamlit/config.toml |

## 1. Check locally

From the repository folder in PowerShell:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
git status --short
git ls-files .env views/.env .streamlit/secrets.toml
```

The last command should return no files: credentials must not be tracked. `.env` and `.streamlit/secrets.toml` are ignored. `.env.example` and `.streamlit/secrets.example.toml` contain placeholders and may be committed. Keep the synthetic demo CSVs under data/demo in Git; the app reads them at runtime. The local .venv is never uploaded.

## 2. Commit and push the prepared deployment files

Your origin already points to the repository above. Review the changes, then:

```powershell
git diff
git add README.md docs/deployment.md .streamlit/config.toml .streamlit/secrets.example.toml packages.txt .github/workflows/ci.yml
git commit -m "Prepare Streamlit Community Cloud deployment"
git push -u origin dev
```

All existing application files were tracked when this preparation was performed. If you have additional app changes, review and commit those too. Authenticate to GitHub if prompted. If push is rejected, fetch and reconcile remote changes; do not force-push as a deployment shortcut.

Open the repository's **Actions** tab and check **Python regression checks**. This workflow installs the pinned packages on Ubuntu/Python 3.13, runs the test suite without an OpenRouter key, and checks server startup. It does not run long Bayesian sampling or live API tests. A successful dependency resolution locally is not a substitute for this Linux runtime check.

## 3. Create the cloud app

1. Open https://share.streamlit.io and sign in with GitHub.
2. Authorize access to the repository if needed.
3. Click **Create app**, then choose deployment from an existing GitHub repository if prompted.
4. Select the repository above, branch **dev**, and main file **app.py**.
5. Choose a custom subdomain if desired.
6. Open **Advanced settings** and select **Python 3.13** explicitly.
7. In **Secrets**, paste the following TOML, replacing only the key placeholder with the value from your local .env:

```toml
OPEN_ROUTER_API = "your-real-openrouter-key"
OPENROUTER_MODEL = "dots-studio/dots-3-note-preview:free"
```

Use quotes as shown. Do not upload the .env file or place a real key in the tracked example. The app reads cloud values through st.secrets; no code change is needed. Alternatively deploy without secrets first: calculations and template summaries still work.

8. Click **Deploy** and watch the build logs. Installation can take longer than a small Streamlit app because this app includes scientific and Bayesian dependencies.

Official instructions: [deploy an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [cloud secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## 4. Verify the hosted app

1. Overview: load the clean demo and inspect all four tables.
2. Data Integration & Quality: use the loaded demo and apply reviewed changes. Confirm 60 integrated batch rows.
3. Process Explorer: select batches, change the window, and download a summary.
4. Statistical Analysis: inspect the correlation and media-group results.
5. Predictive Modeling: start with Ridge/random forest/XGBoost/neural network. Confirm comparison scores and a test-set evaluation. BART is off by default and has a 60-second comparison budget.
6. Scientific AI Copilot: inspect the evidence, then generate one explanation using only synthetic demo results. Confirm the reported request cost and model. If quota/availability blocks it, verify the template summary remains usable.
7. Optionally benchmark BSTS separately. Local runtime was roughly 131 seconds for a short demo run; cloud runtime and memory behavior are not yet verified. Its short-chain results are provisional when diagnostics fail. Do not run multiple Bayesian jobs concurrently during the first check.

The app has no durable user database: browser sessions hold prepared data and results, and restarts clear them. Public visitors share the app owner's OpenRouter quota. The client enforces free-only generation but cannot guarantee provider availability. Use synthetic/public demo data for the portfolio deployment.

## 5. Updates and troubleshooting

- Push later commits to the deployed branch; Community Cloud updates the app from that branch. Keep the branch choice consistent if you later move from dev to main.
- Missing dependency or import failure: inspect build logs, confirm Python 3.13 and requirements.txt at the root, then check the GitHub Actions result. Do not randomly unpin versions.
- XGBoost reports libgomp missing: confirm packages.txt is in the deployed commit and reboot/rebuild the app.
- Copilot has no key: open app settings > Secrets and check the configuration names and TOML syntax. Restart if needed. Never paste credentials into logs or issues.
- Copilot reports unavailable/free quota: computed analytics remain available; update OPENROUTER_MODEL in Secrets only after verifying a new free endpoint.
- Resource limits during Bayesian sampling: use fewer draws and run one job at a time. Reboot from app management if necessary. Keeping BSTS within Community Cloud limits requires validation on the actual deployment.
- Local changes missing online: confirm the commit was pushed to dev and the deployment points to that branch.

For a future production application, evaluate authentication, durable storage, per-user API quotas, and a separate background training service. They are not part of this portfolio deployment.
