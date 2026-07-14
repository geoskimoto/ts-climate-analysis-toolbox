"""Shared time-series preparation and day-of-year climatology.

Consolidates ``statisticscalculator/generalstatistics.py``. The original file
carried two near-identical classes (``GeneralStatistics`` and
``StatisticsCalculatorPlotly``); this keeps one.

Water-year convention: the water year runs 1 Oct -- 30 Sep and is labelled by
the calendar year in which it ends (so Oct 2020 -- Sep 2021 is "Water Year
2021"). ``WY_Date`` shifts Oct/Nov/Dec dates forward one year so that a whole
water year sorts and plots as a single contiguous curve.
"""

from __future__ import annotations

import pandas as pd

# October-first ordering used to sort day-of-year stats into water-year order.
_WATER_YEAR_MONTH_ORDER = ["10", "11", "12", "01", "02", "03", "04", "05", "06", "07", "08", "09"]


class GeneralStatistics:
    """Prepare a raw time series and compute its day-of-year climatology.

    Adds water-year columns to the frame and computes, for each calendar day
    (``month-day``), the mean / median / std / 25th / 75th percentile across all
    years -- the climatology envelope used by the hydrograph plots.
    """

    def __init__(self, data_loader):
        self.data_loader = data_loader
        self._df = self.data_loader.df
        self._value_col = self.data_loader._name_of_Q_column

        self._df["Date"] = pd.to_datetime(self._df[self.data_loader._name_of_date_column])
        self._df = self._df[~self._df.duplicated("Date")]

        # WY_Date: shift Oct-Dec forward a year so a water year is contiguous.
        self._df["WY_Date"] = self._df["Date"].apply(
            lambda x: x.replace(year=x.year + 1) if 10 <= x.month <= 12 else x
        )
        self._df["month"] = self._df["WY_Date"].dt.month
        self._df["Water Year"] = self._df["WY_Date"].dt.year
        self._df["Calendar Year"] = self._df["Date"].dt.year
        self._df["month-day"] = self._df["WY_Date"].dt.strftime("%m-%d")
        self._df["dayofyear"] = self._df["WY_Date"].dt.dayofyear

        self._calculate_statistics()
        self._grouped_water_years = self._df.groupby("Water Year")

    def _calculate_statistics(self) -> None:
        stats = (
            self._df.groupby("month-day")[self._value_col]
            .agg(
                [
                    "mean",
                    "median",
                    "std",
                    ("q25", lambda x: x.quantile(0.25)),
                    ("q75", lambda x: x.quantile(0.75)),
                ]
            )
            .reset_index()
        )
        stats["month"] = stats["month-day"].str[:2].fillna("")
        stats["water_year_sort"] = stats["month"].map(
            {month: i for i, month in enumerate(_WATER_YEAR_MONTH_ORDER)}
        )
        stats = stats.sort_values(by="water_year_sort").reset_index(drop=True)
        self._stats = stats

        self._mean = stats["mean"]
        self._median = stats["median"]
        self._st_dev = stats["std"]
        self._percentile25 = stats["q25"]
        self._percentile75 = stats["q75"]
        self._lower_bound_st_dev = self._mean - self._st_dev
        self._upper_bound_st_dev = self._mean + self._st_dev
        self._lower_bound_percentile25 = self._mean - self._percentile25
        self._upper_bound_percentile75 = self._mean + self._percentile75

        # Wide table: one column per calendar year, indexed by month-day.
        pivot = self._df.copy()
        pivot["month-day"] = pivot["Date"].dt.strftime("%m-%d")
        pivot = pivot.pivot(index="month-day", columns="Calendar Year", values=self._value_col)
        self._pivot_table = pivot[self._df["Calendar Year"].unique()]
