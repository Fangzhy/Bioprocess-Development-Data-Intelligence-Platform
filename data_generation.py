"""Illustrative synthetic CHO data; not a validated biological simulator."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_SEED = 42
DATASETS = ("batch_metadata", "process_timeseries", "offline_assays", "final_quality")
DEMO_DIR = Path(__file__).resolve().parent / "data" / "demo"


def generate_clean(seed=DEFAULT_SEED):
    """Return four related tables with 60 independent batches."""
    rng = np.random.default_rng(seed)
    metadata, process, assays, quality = [], [], [], []
    time = np.arange(0, 337, 4)
    for i in range(60):
        batch = f"B{i + 1:03d}"
        media = i % 3
        scale = (2, 5)[i % 2]
        seed_density = rng.uniform(0.4, 0.8)
        unusual = i + 1 in (14, 27, 48)
        effect = (0.0, 0.12, -0.08)[media]
        vigor = rng.normal(1 + effect, 0.08)
        stress = (1.0 if unusual else 0.0) * np.exp(-((time - 180) / 55) ** 2)
        growth = seed_density + 20 * vigor / (1 + np.exp(-(time - 110) / 28))
        vcd = growth * np.exp(-np.maximum(time - 240, 0) / 230) * (1 - 0.22 * stress)
        viability = np.clip(98 - 0.045 * np.maximum(time - 150, 0) - 9 * stress + rng.normal(0, 0.4, len(time)), 0, 100)
        feed = np.where(time >= 48, 0.035 + 0.012 * np.sin(time / 60) + rng.normal(0, 0.002, len(time)), 0).clip(0)
        glucose = np.clip(5.5 - 0.012 * time + 25 * feed - 0.6 * stress + rng.normal(0, 0.18, len(time)), 0.1, None)
        lactate = np.clip(0.4 + 2.2 * np.exp(-((time - 160) / 90) ** 2) + 2.0 * stress + rng.normal(0, 0.12, len(time)), 0, None)
        do = np.clip(45 + rng.normal(0, 1.7, len(time)) - 14 * stress, 0, 100)
        ph = 7.05 + rng.normal(0, 0.025, len(time)) - 0.13 * stress
        # Integrate productivity over the preceding interval; titer starts at zero.
        rate = vcd * viability / 100 * 0.0012 * (1 - 0.18 * stress)
        titer = np.r_[0, np.cumsum((rate[:-1] + rate[1:]) / 2 * 4)]
        metadata.append(dict(batch_id=batch, cell_line="CHO-A", media_type=f"Media-{media + 1}",
                             media_lot=f"M{media + 1}-L{i % 4 + 1:02d}", bioreactor_scale=scale,
                             seed_density=seed_density, experiment_date=(pd.Timestamp("2025-01-01") + pd.Timedelta(days=i * 3)).strftime("%Y-%m-%d"),
                             operator=f"Operator-{i % 4 + 1}"))
        for j, hour in enumerate(time):
            process.append(dict(batch_id=batch, time_hr=int(hour), temperature=37 - 1.5 * (hour >= 144) + rng.normal(0, 0.08),
                                pH=ph[j], DO=do[j], agitation=220 + 0.15 * hour + rng.normal(0, 3),
                                air_flow=0.1 * scale, O2_flow=max(0, 0.012 * scale + 0.01 * stress[j]),
                                CO2_flow=0.002 * scale, feed_rate=feed[j],
                                sensor_glucose=glucose[j], sensor_lactate=lactate[j]))
            if hour % 24 == 0:
                assays.append(dict(batch_id=batch, time_hr=int(hour), viable_cell_density=max(0, vcd[j] + rng.normal(0, 0.15)),
                                   viability=viability[j], glucose=max(0, glucose[j] + rng.normal(0, 0.1)),
                                   lactate=max(0, lactate[j] + rng.normal(0, 0.08)),
                                   ammonia=max(0, 0.2 + 0.004 * hour + rng.normal(0, 0.05)), product_titer=titer[j]))
        aggregation = np.clip(rng.normal(2 + 0.8 * unusual, 0.25), 0, 10)
        purity = np.clip(rng.normal(97 - 1.0 * unusual, 0.4), 90, 100)
        quality.append(dict(batch_id=batch, final_titer=titer[-1], purity=purity, aggregation=aggregation,
                            glycosylation_metric=np.clip(rng.normal(35 + 3 * effect, 2), 0, 100),
                            **{"yield": np.clip(rng.normal(82 - 4 * unusual, 2), 0, 100)}))
    return {name: pd.DataFrame(rows).round(5) for name, rows in zip(DATASETS, (metadata, process, assays, quality))}


def make_messy(clean):
    """Copy clean tables and inject deterministic defects, recording each change."""
    messy = {name: frame.copy(deep=True) for name, frame in clean.items()}
    issues = []

    def record(dataset, kind, batch, hour, column, original, replacement):
        issues.append(dict(dataset=dataset, issue_type=kind, batch_id=batch, time_hr=hour,
                           column=column, original_value=str(original), injected_value=str(replacement)))

    for dataset, batch, hour, column in [
        ("process_timeseries", "B003", 40, "DO"),
        ("process_timeseries", "B018", 100, "sensor_glucose"),
        ("offline_assays", "B009", 72, "lactate"),
    ]:
        frame = messy[dataset]
        mask = (frame.batch_id == batch) & (frame.time_hr == hour)
        record(dataset, "missing_value", batch, hour, column, frame.loc[mask, column].iloc[0], "missing")
        frame.loc[mask, column] = np.nan
    frame = messy["process_timeseries"]
    duplicate = frame[(frame.batch_id == "B005") & (frame.time_hr == 48)]
    messy["process_timeseries"] = pd.concat([frame, duplicate], ignore_index=True)
    record("process_timeseries", "duplicate_record", "B005", 48, "all", "one row", "two identical rows")
    frame = messy["offline_assays"]
    mask = (frame.batch_id == "B010") & (frame.time_hr == 120)
    frame.loc[mask, "batch_id"] = "B999"
    record("offline_assays", "invalid_batch_reference", "B010", 120, "batch_id", "B010", "B999")
    frame = messy["process_timeseries"]
    for hour in (160, 164, 168):
        record("process_timeseries", "time_gap", "B020", hour, "all", "row present", "row removed")
    messy["process_timeseries"] = frame.loc[~((frame.batch_id == "B020") & frame.time_hr.isin([160, 164, 168]))].reset_index(drop=True)
    return messy, pd.DataFrame(issues)


def export_demo(output_dir=DEMO_DIR, seed=DEFAULT_SEED):
    """Write reproducible CSVs, overwriting the named demo files only."""
    output_dir = Path(output_dir)
    clean = generate_clean(seed)
    messy, manifest = make_messy(clean)
    for variant, tables in (("clean", clean), ("messy", messy)):
        folder = output_dir / variant
        folder.mkdir(parents=True, exist_ok=True)
        for name, frame in tables.items():
            frame.to_csv(folder / f"{name}.csv", index=False, lineterminator="\n")
    manifest.to_csv(output_dir / "issue_manifest.csv", index=False, lineterminator="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-dir", type=Path, default=DEMO_DIR)
    args = parser.parse_args()
    export_demo(args.output_dir, args.seed)
    print(f"Exported synthetic demo data to {args.output_dir}")
