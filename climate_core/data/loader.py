"""Normalise raw source data into a common shape for the statistics layer.

Replaces ``dataIO/dataloader.py``. The original had two bugs: it referenced
``self.csv_path`` (never set) and never returned/assigned the loaded frame in
all branches. This version is total: it always produces ``self.df`` or raises.
"""

from __future__ import annotations

import pandas as pd


class DataLoader:
    """Wraps a time series (from a DataFrame or CSV path) and records which
    columns hold the date and the value of interest.

    Args:
        source: a ``pandas.DataFrame`` or a path to a CSV file.
        date_column: name of the column holding dates.
        value_column: name of the column holding the measured value
            (discharge, SWE, etc.).
    """

    def __init__(self, source, date_column: str, value_column: str):
        self.source = source
        self._name_of_date_column = date_column
        self._name_of_Q_column = value_column
        self.df = self._load()

    def _load(self) -> pd.DataFrame:
        if isinstance(self.source, pd.DataFrame):
            df = self.source.copy()
        elif isinstance(self.source, str):
            df = pd.read_csv(self.source)
        else:
            raise TypeError(
                "DataLoader source must be a pandas.DataFrame or a CSV path string, "
                f"got {type(self.source).__name__}."
            )

        for col in (self._name_of_date_column, self._name_of_Q_column):
            if col not in df.columns:
                raise KeyError(f"Column {col!r} not found in data (columns: {list(df.columns)}).")

        # Coerce the value column to numeric, turning non-numeric entries into NaN.
        df[self._name_of_Q_column] = pd.to_numeric(df[self._name_of_Q_column], errors="coerce")
        return df
