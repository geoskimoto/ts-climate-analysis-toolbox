"""Snow (SNOTEL) climate-signal statistics.

Ports the ``Snow`` class from ``statisticscalculator/climatestatistics.py``.
Same trend-detection approach as :mod:`climate_core.stats.streamflow`, applied
to snow water equivalent / precipitation accumulation. The original
``calc_max`` had a stray inner loop and commented-out block; this is the
cleaned equivalent.
"""

from __future__ import annotations

import pandas as pd
from pymannkendall import original_test

from climate_core.stats.base import GeneralStatistics


class Snow(GeneralStatistics):
    def __init__(self, data_loader):
        super().__init__(data_loader)

    @staticmethod
    def _day_of_water_year(dt: pd.Timestamp, water_year: int) -> int:
        """1 = Oct 1 ... ~365 = Sep 30 — a monotonic within-water-year day."""
        return (pd.Timestamp(dt) - pd.Timestamp(year=water_year - 1, month=10, day=1)).days + 1

    def calc_benchmark_swe(self, benchmark_month_day: str = "04-01", alpha: float = 0.10):
        """SWE on a fixed benchmark date each water year (default 1 April — the
        classic water-supply index). A declining trend is a warming signal.

        Populates ``self.benchmark_swe_df`` (one value per water year) and
        ``self.benchmark_swe_mann_kendall_test``.
        """
        self.benchmark_month_day = benchmark_month_day
        values = {}
        for wy in self._df["Water Year"].unique():
            wy_rows = self._df[self._df["Water Year"] == wy]
            match = wy_rows[wy_rows["month-day"] == benchmark_month_day]
            if not match.empty and pd.notna(match[self._value_col].iloc[0]):
                values[int(wy)] = float(match[self._value_col].iloc[0])

        self.benchmark_swe_df = pd.DataFrame(
            {self._value_col: list(values.values())},
            index=pd.Index(list(values.keys()), name="Year"),
        )
        self.benchmark_swe_mann_kendall_test = (
            original_test(self.benchmark_swe_df[self._value_col], alpha=alpha)
            if not self.benchmark_swe_df.empty
            else None
        )

    def calc_melt_out_date(self, threshold: float = 0.0, min_peak: float = 1.0, alpha: float = 0.10):
        """Snow-disappearance date: the first day after the annual peak when SWE
        falls to ``threshold`` (default 0). An earlier trend is a warming signal.

        Water years whose peak SWE never exceeds ``min_peak`` (essentially
        snow-free records) are skipped. Populates ``self.melt_out_df`` (date +
        day-of-water-year per year) and ``self.melt_out_mann_kendall_test``.
        """
        records = {}
        for wy in self._df["Water Year"].unique():
            wy_rows = self._df[self._df["Water Year"] == wy].sort_values("Date")
            swe = wy_rows[self._value_col]
            if swe.dropna().empty or swe.max() < min_peak:
                continue
            peak_pos = swe.values.argmax()
            after_peak = wy_rows.iloc[peak_pos:]
            melted = after_peak[after_peak[self._value_col] <= threshold]
            if melted.empty:
                continue  # never melted out within the record for this year
            melt_date = pd.Timestamp(melted["Date"].iloc[0])
            records[int(wy)] = {
                "date": melt_date,
                "dayofwateryear": self._day_of_water_year(melt_date, int(wy)),
            }

        if not records:
            self.melt_out_df = pd.DataFrame(columns=["date", "dayofwateryear"])
            self.melt_out_mann_kendall_test = None
            return
        self.melt_out_df = pd.DataFrame(records).T
        self.melt_out_mann_kendall_test = original_test(
            self.melt_out_df["dayofwateryear"].astype(float), alpha=alpha
        )

    def calc_accumulation_bw_days(
        self,
        begin_month_day: str = "10-01",
        end_month_day: str = "06-01",
        parameter: str = "WTEQ",
        alpha: float = 0.10,
    ):
        """Accumulated value (e.g. SWE, precip) between two dates, per water year.

        NOTE: summing daily values is meaningful for a *flux* like incremental
        precipitation, not for a *stock* like SWE (which is a standing depth, not
        a rate). For snowpack climate signals prefer :meth:`calc_benchmark_swe`,
        :meth:`calc_melt_out_date`, and :meth:`calc_max`.

        Runs Mann-Kendall over the per-year accumulation series.
        """
        self.begin_month_day = begin_month_day
        self.end_month_day = end_month_day
        accumulation_dict = {}
        for wy in self._df["Water Year"].unique():
            wy_rows = self._df[self._df["Water Year"] == wy]
            window = wy_rows[wy_rows["month-day"].between(begin_month_day, end_month_day)]
            accumulation_dict[wy] = window[self._value_col].sum()

        self.volume_bw_days_df = pd.DataFrame(
            {self._value_col: list(accumulation_dict.values())},
            index=pd.Index(list(accumulation_dict.keys()), name="Year"),
        )
        self.volume_bw_days_mann_kendall_test = original_test(
            self.volume_bw_days_df[self._value_col], alpha=alpha
        )

    def calc_max(self, window_size: int = 1, alpha: float = 0.10):
        """Annual peak of the ``window_size``-day rolling mean (e.g. peak SWE),
        and its day of year. Runs Mann-Kendall on both.
        """
        max_dfs = []
        for wy in self._df["Water Year"].unique():
            wy_rows = self._df[self._df["Water Year"] == wy]
            rolling_mean_df = pd.DataFrame(
                {
                    "Date": wy_rows["Date"],
                    "month-day": wy_rows["month-day"],
                    "dayofyear": wy_rows["dayofyear"],
                    "WY_Date": wy_rows["WY_Date"],
                    "Water Year": wy_rows["Water Year"],
                    "Calendar Year": wy_rows["Calendar Year"],
                    self._value_col: wy_rows[self._value_col],
                    "rolling mean max": wy_rows[self._value_col].rolling(window=window_size).mean(),
                }
            )
            if rolling_mean_df["rolling mean max"].notna().any():
                wy_max = rolling_mean_df[
                    rolling_mean_df["rolling mean max"] == rolling_mean_df["rolling mean max"].max()
                ]
                max_dfs.append(wy_max)

        self.rolling_yr_maxs = pd.concat(max_dfs, ignore_index=True)
        self.rolling_yr_Qmax_mk_test = original_test(
            self.rolling_yr_maxs[self._value_col], alpha=alpha
        )
        self.rolling_yr_DOYmax_mk_test = original_test(
            self.rolling_yr_maxs["dayofyear"], alpha=alpha
        )
