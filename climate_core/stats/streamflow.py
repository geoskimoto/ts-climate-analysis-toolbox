"""Streamflow climate-signal statistics.

Ports ``statisticscalculator/climatestatistics.py`` (the ``Streamflow`` class),
fixing the broken ``ignore_winter_months`` branch in :meth:`calc_max`.

The three headline metrics for a snowmelt-driven river:
    * ``calc_annual_runoff_threshold_day`` -- center-of-timing (day when N% of
      annual volume has passed). Earlier over time = warming signal.
    * ``calc_runoff_bw_days`` -- runoff volume within a seasonal window.
    * ``calc_max`` -- annual peak magnitude and its day of year.

Each computes a Mann-Kendall trend test over the per-year series.
"""

from __future__ import annotations

import pandas as pd
from pymannkendall import original_test

from climate_core.stats.base import GeneralStatistics

# Conversion: 1 cfs sustained for a day; 1 acre-foot = 43,560 ft^3.
_SECONDS_PER_DAY_OVER_1000 = 86.4  # 86400 s/day / 1000 -> thousand-second-feet-day (ksfd)
_CFS_TO_ACREFEET = 43560.0


class Streamflow(GeneralStatistics):
    def __init__(self, data_loader):
        super().__init__(data_loader)

    def calc_annual_runoff_threshold_day(self, percent: float = 0.5, alpha: float = 0.10):
        """Center-of-timing: the date each water year when ``percent`` of the
        annual runoff volume has accumulated.

        Populates ``self.threshold_vol_stats`` and runs Mann-Kendall tests on
        the threshold volume, its day-of-year, and the total annual volume.
        """
        self._percent = percent
        yearly_volume_statistics = {}
        for wy in self._df["Water Year"].unique():
            wy_rows = self._df[self._df["Water Year"] == wy]
            volume_df = pd.DataFrame(
                {
                    "values": wy_rows[self._value_col],
                    "WY_Date": wy_rows["WY_Date"],
                }
            )
            volume_df["daily_volume_maf"] = volume_df["values"] / _CFS_TO_ACREFEET
            volume_df["cumsum_volume_maf"] = volume_df["daily_volume_maf"].cumsum()

            total_volume = volume_df["daily_volume_maf"].sum()
            wy_dates = wy_rows["WY_Date"]
            threshold_mask = volume_df["cumsum_volume_maf"] >= percent * total_volume
            volume_point_date = wy_dates[threshold_mask].iloc[0]

            yearly_volume_statistics[wy] = {
                "total_volume": total_volume,
                f"{percent * 100}%_volume": total_volume * percent,
                f"{percent * 100}%_volume_point_date": volume_point_date,
            }

        stats = pd.DataFrame(yearly_volume_statistics).T
        date_col = f"{percent * 100}%_volume_point_date"
        stats[f"{percent * 100}%_volume_point_day_of_yr"] = stats[date_col].apply(
            lambda x: x.strftime("%m-%d")
        )
        stats["50%_volume_point_month_day"] = pd.to_datetime(stats[date_col]).dt.strftime("%b %d")
        self.threshold_vol_stats = stats

        self.threshold_vol_mann_kendall_test = original_test(
            stats[f"{percent * 100}%_volume"], alpha=alpha
        )
        self.threshold_vol_dates_mann_kendall_test = original_test(
            stats[date_col].apply(lambda dt: dt.timetuple().tm_yday), alpha=alpha
        )
        self.total_volume_mann_kendall_test = original_test(stats["total_volume"], alpha=alpha)

    def calc_runoff_bw_days(
        self,
        begin_month_day: str = "09-25",
        end_month_day: str = "09-28",
        alpha: float = 0.10,
    ):
        """Runoff volume (million acre-feet) between two calendar dates, for each
        water year -- e.g. summer low-flow volume. Runs Mann-Kendall on the series.
        """
        self.begin_month_day = begin_month_day
        self.end_month_day = end_month_day
        volume_bw_days_dict = {}
        for wy in self._df["Water Year"].unique():
            wy_rows = self._df[self._df["Water Year"] == wy]
            window = wy_rows[wy_rows["month-day"].between(begin_month_day, end_month_day)]
            daily_volume_maf = window[self._value_col] / _CFS_TO_ACREFEET
            volume_bw_days_dict[wy] = daily_volume_maf.sum()

        self.volume_bw_days_df = pd.DataFrame(
            {self._value_col: list(volume_bw_days_dict.values())},
            index=pd.Index(list(volume_bw_days_dict.keys()), name="Year"),
        )
        self.volume_bw_days_mann_kendall_test = original_test(
            self.volume_bw_days_df[self._value_col], alpha=alpha
        )

    def calc_max(
        self,
        window_size: int = 5,
        alpha: float = 0.10,
        ignore_winter_months: bool = False,
    ):
        """Annual peak of the ``window_size``-day rolling mean, and its day of year.

        With ``ignore_winter_months=True`` the search is restricted to Feb--Jun,
        so winter rain-on-snow spikes don't mask the snowmelt peak. Runs
        Mann-Kendall on both the peak magnitude and its day of year.
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
            if ignore_winter_months:
                rolling_mean_df = rolling_mean_df[
                    rolling_mean_df["month-day"].between("02-01", "07-01")
                ]
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
