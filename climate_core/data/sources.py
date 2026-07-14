"""Live data-source clients.

Consolidates the original ``dataIO/webservices.py`` clients into a single,
deduplicated module. Each client returns a tidy ``pandas.DataFrame`` with a
``Date`` column and one or more value columns, ready to hand to
:class:`climate_core.data.loader.DataLoader`.

Sources:
    * USGS NWIS Daily Values  -- streamflow / discharge
    * NRCS AWDB (SNOTEL)       -- snow water equivalent, precipitation, etc.
    * Environment Canada       -- transboundary BC streamflow / level

The original module carried two USGS classes (``usgs_streamflow`` and
``usgs_streamflow2``) that did the same thing; this keeps one clean
implementation.
"""

from __future__ import annotations

from functools import reduce
import io

import pandas as pd
import requests

DEFAULT_TIMEOUT = 60


class USGSStreamflow:
    """Fetch daily streamflow from the USGS NWIS Daily Values service.

    Docs / test console: https://waterservices.usgs.gov/
    """

    BASE_URL = "https://waterservices.usgs.gov/nwis/dv"

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.url: str | None = None
        self.response: requests.Response | None = None
        self.df: pd.DataFrame | None = None

    def build_url(
        self,
        sites: str = "09380000",
        start_date: str = "2010-10-01",
        end_date: str = "2023-10-01",
        site_status: str = "all",  # active | inactive | all
        parameter_cd: str = "00060",  # 00060 = discharge (cfs)
        file_format: str = "json",
    ) -> str:
        params = {
            "format": file_format,
            "sites": sites,
            "startDT": start_date,
            "endDT": end_date,
            "siteStatus": site_status,
            "parameterCd": parameter_cd,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        self.url = f"{self.BASE_URL}/?{query}"
        return self.url

    def get_data(
        self,
        sites: str = "09380000",
        start_date: str = "2010-10-01",
        end_date: str = "2023-10-01",
        site_status: str = "all",
        parameter_cd: str = "00060",
    ) -> pd.DataFrame:
        """Return a DataFrame with columns ``Date`` and ``Discharge``.

        Raises ``requests.HTTPError`` on a failed request and ``ValueError``
        if the response contains no time-series for the requested site.
        """
        url = self.build_url(sites, start_date, end_date, site_status, parameter_cd)
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        self.response = response

        series = response.json()["value"]["timeSeries"]
        if not series:
            raise ValueError(
                f"USGS returned no data for site(s) {sites} "
                f"between {start_date} and {end_date}."
            )

        df = pd.DataFrame(series[0]["values"][0]["value"])
        df["dateTime"] = pd.to_datetime(df["dateTime"]).dt.date
        df = df.rename(columns={"dateTime": "Date", "value": "Discharge"})
        df["Discharge"] = pd.to_numeric(df["Discharge"], errors="coerce")
        # USGS uses -999999 as a no-data sentinel.
        df.loc[df["Discharge"] <= -999998, "Discharge"] = pd.NA
        self.df = df[["Date", "Discharge"]]
        return self.df


class NRCSSnotel:
    """Fetch data from the NRCS AWDB REST API (SNOTEL network).

    Element codes: WTEQ (snow water equivalent), PREC (precipitation),
    SNWD (snow depth), TAVG/TMAX/TMIN (temperatures), etc.
    """

    BASE_URL = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.url: str | None = None
        self.response: requests.Response | None = None
        self.df: pd.DataFrame | None = None

    def build_url(
        self,
        begin_date: str,
        end_date: str,
        station_triplets: str,
        elements: list[str],
        central_tendency_type: str = "NONE",
        duration_type: str = "DAILY",
        period_ref: str = "END",
        return_flags: str = "false",
        return_original_values: str = "false",
        return_suspect_data: str = "false",
    ) -> str:
        params = {
            "beginDate": begin_date,
            "centralTendencyType": central_tendency_type,
            "duration": duration_type,
            "elements": ",".join(elements),
            "endDate": end_date,
            "periodRef": period_ref,
            "returnFlags": return_flags,
            "returnOriginalValues": return_original_values,
            "returnSuspectData": return_suspect_data,
            "stationTriplets": station_triplets,
        }
        self.url = self.BASE_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return self.url

    @staticmethod
    def _parse_response(response: requests.Response) -> pd.DataFrame | None:
        payload = response.json()
        if not payload:
            return None
        element_dfs = []
        for element_data in payload[0]["data"]:
            values = element_data["values"]
            element_code = element_data["stationElement"]["elementCode"]
            for entry in values:
                entry[element_code] = entry.pop("value")
            element_dfs.append(pd.DataFrame.from_dict(values))
        if not element_dfs:
            return None
        merged = reduce(lambda left, right: pd.merge(left, right, on="date"), element_dfs)
        merged = merged.rename(columns={"date": "Date"})
        return merged

    def get_data(
        self,
        begin_date: str,
        end_date: str,
        station_triplets: str,
        elements: list[str],
        **kwargs,
    ) -> pd.DataFrame | None:
        url = self.build_url(begin_date, end_date, station_triplets, elements, **kwargs)
        response = requests.get(url, params=None, timeout=self.timeout)
        response.raise_for_status()
        self.response = response
        self.df = self._parse_response(response)
        return self.df


def fetch_environment_canada(
    start_date: str,
    end_date: str,
    stations: list[str],
    parameters: list[str],
    timeout: int = DEFAULT_TIMEOUT,
) -> pd.DataFrame | None:
    """Fetch daily data from the Environment Canada Water Office inline CSV service.

    ``parameters`` may include ``level`` and ``flow``.
    """
    base_url = "https://wateroffice.ec.gc.ca/services/daily_data/csv/inline"
    station_params = "&".join(f"stations[]={s}" for s in stations)
    parameter_params = "&".join(f"parameters[]={p}" for p in parameters)
    url = f"{base_url}?{station_params}&{parameter_params}&start_date={start_date}&end_date={end_date}"

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return pd.read_csv(io.StringIO(response.content.decode("utf-8")))
