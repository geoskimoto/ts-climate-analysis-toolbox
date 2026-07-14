"""climate_core -- detecting climate-change signals in PNW streamflow & snow.

Consolidated, tested replacement for the original ``dataIO`` /
``statisticscalculator`` / ``aggregate_stats`` notebook modules. This is the
library the web API sits on top of.

Typical use::

    from climate_core import USGSStreamflow, DataLoader, Streamflow

    raw = USGSStreamflow().get_data(sites="13340000",
                                    start_date="1950-10-01",
                                    end_date="2024-09-30")
    loader = DataLoader(raw, date_column="Date", value_column="Discharge")
    s = Streamflow(loader)
    s.calc_annual_runoff_threshold_day(percent=0.5)
    print(s.threshold_vol_dates_mann_kendall_test)   # center-of-timing trend
"""

from climate_core.data.loader import DataLoader
from climate_core.data.sources import (
    NRCSSnotel,
    USGSStreamflow,
    fetch_environment_canada,
)
from climate_core.stats.base import GeneralStatistics
from climate_core.stats.mk import mk_to_dict
from climate_core.stats.snow import Snow
from climate_core.stats.streamflow import Streamflow

__all__ = [
    "DataLoader",
    "USGSStreamflow",
    "NRCSSnotel",
    "fetch_environment_canada",
    "GeneralStatistics",
    "Streamflow",
    "Snow",
    "mk_to_dict",
]
