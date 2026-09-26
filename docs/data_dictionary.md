# Synthetic demo data dictionary

Illustrative CHO simulations for learning, not experimental measurements or a validated biological model. Default seed: **42**. There are 60 batches, each spanning 0–336 hours (14 days).

## Keys and conventions

Metadata and final quality have one row per batch, keyed by `batch_id` (60 rows each). Process and assay tables use `(batch_id, time_hr)` as their unique key. Every clean batch reference exists in metadata. Process measurements occur every 4 hours (5,100 rows); assays every 24 hours (900 rows), including both endpoints. All columns are required and non-null in clean data. Blank CSV cells denote missing values in messy data. Dates are ISO strings; times are integer elapsed hours. Measurement columns are numeric. No cleaning or alignment occurs when loading demo data.

## batch_metadata.csv

| Column | Unit/type | Definition / expected values |
|---|---|---|
| batch_id | string | Unique B001–B060 |
| cell_line | category | CHO-A |
| media_type | category | Media-1, Media-2, Media-3; 20 runs each |
| media_lot | string | Lot identifier within media type |
| bioreactor_scale | L | Nominal working scale: 2 or 5 |
| seed_density | million cells/mL | Inoculation density: 0.4–0.8 |
| experiment_date | YYYY-MM-DD | Synthetic start date; every three days from 2025-01-01 |
| operator | category | Fictional Operator-1 through Operator-4 |

## process_timeseries.csv

| Column | Unit/type | Definition / expectation |
|---|---|---|
| batch_id | string | Metadata foreign key |
| time_hr | h | 0–336, multiples of 4 |
| temperature | °C | Noisy setpoint: 37, then 35.5 from hour 144 |
| pH | dimensionless | Approximately 7.05, lower during stress |
| DO | % air saturation | Dissolved oxygen, bounded 0–100 here |
| agitation | rpm | Positive stirrer speed |
| air_flow | L/min | 0.1 times nominal scale |
| O2_flow | L/min | Supplemental oxygen; nonnegative |
| CO2_flow | L/min | 0.002 times nominal scale |
| feed_rate | mL/(L·h) | Feed normalized by nominal volume; zero before hour 48 |
| sensor_glucose | g/L | Synthetic online glucose; positive |
| sensor_lactate | g/L | Synthetic online lactate; nonnegative |

## offline_assays.csv

| Column | Unit/type | Definition / expectation |
|---|---|---|
| batch_id | string | Metadata foreign key |
| time_hr | h | 0–336, multiples of 24 |
| viable_cell_density | million cells/mL | Growth then late decline; nonnegative |
| viability | % | Viable fraction, 0–100 |
| glucose | g/L | Offline measurement with independent noise; nonnegative |
| lactate | g/L | Offline measurement with independent noise; nonnegative |
| ammonia | mmol/L | Illustrative accumulation with noise; nonnegative |
| product_titer | g/L | Integrated productivity; starts at zero |

Sensor and offline glucose/lactate remain distinct measurements.

## final_quality.csv

| Column | Unit/type | Definition / expectation |
|---|---|---|
| batch_id | string | Unique metadata foreign key |
| final_titer | g/L | Equals product_titer at hour 336 |
| purity | % | Illustrative final purified-product purity, 0–100 |
| aggregation | % | Illustrative aggregate fraction, 0–100 |
| glycosylation_metric | % | Illustrative galactosylated glycan fraction, 0–100 |
| yield | % | Hypothetical downstream product mass recovered / harvested product mass × 100 |

Quality metrics are separate assays, not components required to sum to 100. Downstream process trajectories are not modeled; quality and recovery are illustrative endpoints.

## Simulation assumptions

Growth follows a logistic curve and late decline. Media-2 increases the growth multiplier by 0.12 and Media-3 reduces it by 0.08 relative to Media-1, with random batch variation. Titer integrates viable biomass productivity over time. Glucose has a simple feed association, lactate peaks mid-run, and observations include noise. Coefficients are illustrative, not fitted to real data. No mass balance, changing-volume model, oxygen-transfer model, or causal inference is claimed.

B014, B027, and B048 have a smooth stress event near hour 180: higher lactate, lower DO/pH, and reduced viable biomass/productivity. They are valid unusual runs present in both variants, not data defects. These labels are simulation ground truth, not anomaly detector results.

Media assignments are balanced but deterministic. Dates, operators, lots, and scale are not a randomized experimental design. Generated relationships do not establish biological evidence or guarantee predictive performance.

## Messy variant

The messy variant copies clean data and introduces eight edits:

- Three missing cells: process B003/40 h/DO, process B018/100 h/sensor_glucose, assay B009/72 h/lactate.
- One extra duplicate process row: B005 at 48 h.
- Assay B010 at 120 h has its batch ID changed to nonexistent B999. This also leaves an absent expected time for B010.
- Three removed process rows: B020 at 160, 164, and 168 h.

Messy process data has 5,098 rows; other counts are unchanged. `issue_manifest.csv` records dataset, issue type, original batch/time, affected column, original value, and injected value. It records injected changes, not an automatically computed quality report. Multiple symptoms may arise from one edit.

## Reproducibility

`python data_generation.py` overwrites the bundled demo CSVs using seed 42. `--seed 7 --output-dir data/demo_seed7` produces a separate example. The same seed with pinned dependencies produces identical CSV bytes. The app reads bundled CSVs and keeps loaded tables in the current session; it does not regenerate on reruns. New sessions require loading again.
