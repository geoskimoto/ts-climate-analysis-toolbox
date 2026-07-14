"""Helpers shared by the streamflow and snow analysis services.

Extracted so both data sources compute water-year trimming, the day-of-water-
year axis, the climatology envelope, and the hydrograph curves the same way.
"""

from __future__ import annotations

import pandas as pd

from climate_core import mk_to_dict

from api import schemas


def day_of_water_year(dt: pd.Timestamp, water_year: int) -> int:
    """1 = Oct 1, ... ~365 = Sep 30. A monotonic within-water-year axis."""
    return (pd.Timestamp(dt) - pd.Timestamp(year=water_year - 1, month=10, day=1)).days + 1


def trim_to_complete_water_years(df: pd.DataFrame, date_col: str, min_days: int) -> pd.DataFrame:
    """Drop water years with fewer than ``min_days`` measured days."""
    dates = pd.to_datetime(df[date_col])
    wy = dates.dt.year.where(dates.dt.month < 10, dates.dt.year + 1)
    counts = wy.value_counts()
    keep = counts[counts >= min_days].index
    return df[wy.isin(keep)].reset_index(drop=True)


def mk(result) -> schemas.MannKendall | None:
    """Wrap a pymannkendall result as a schema, tolerating None (insufficient data)."""
    return None if result is None else schemas.MannKendall(**mk_to_dict(result))


def attach_dowy(stats_obj, value_col: str) -> pd.Series:
    """Add a ``dowy`` column to the stats object's frame and return a
    month-day -> day-of-water-year lookup for the climatology envelope.
    """
    df = stats_obj._df
    df["dowy"] = [day_of_water_year(d, wy) for d, wy in zip(df["Date"], df["Water Year"])]
    return df.groupby("month-day")["dowy"].first()


def build_climatology(stats_obj, dowy_by_month_day: pd.Series) -> list[schemas.ClimatologyPoint]:
    stats = stats_obj._stats.copy()
    stats["dowy"] = stats["month-day"].map(dowy_by_month_day)
    stats = stats.sort_values("dowy")

    def num(v):
        return None if pd.isna(v) else float(v)

    return [
        schemas.ClimatologyPoint(
            day_of_year=int(row["dowy"]),
            month_day=row["month-day"],
            mean=num(row["mean"]), median=num(row["median"]),
            q25=num(row["q25"]), q75=num(row["q75"]), std=num(row["std"]),
        )
        for _, row in stats.iterrows()
        if not pd.isna(row["dowy"])
    ]


def build_hydrograph(stats_obj, value_col: str) -> list[schemas.HydrographYear]:
    out = []
    for wy, group in stats_obj._df.groupby("Water Year"):
        group = group.sort_values("dowy")
        out.append(
            schemas.HydrographYear(
                water_year=int(wy),
                day_of_year=[int(d) for d in group["dowy"]],
                value=[None if pd.isna(v) else float(v) for v in group[value_col]],
            )
        )
    out.sort(key=lambda h: h.water_year)
    return out
