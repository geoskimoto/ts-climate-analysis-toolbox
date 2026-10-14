"""Pydantic request/response models — the API contract for the frontend.

Pydantic v2. These shapes are what the single-site explorer consumes:
site metadata, the climatology envelope, and the per-water-year trend series
(center-of-timing, volumes, peak) each with a Mann-Kendall verdict.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# --------------------------------------------------------------------------- #
# Sites
# --------------------------------------------------------------------------- #
class SiteOut(BaseModel):
    site_no: str
    name: str
    basin: str
    state: str
    lat: float | None = None
    long: float | None = None
    drainage_area_sqmi: float | None = None
    elevation_ft: float | None = None


# --------------------------------------------------------------------------- #
# Analysis request
# --------------------------------------------------------------------------- #
class SeasonalWindow(BaseModel):
    label: str = Field(..., examples=["Summer (Jul–Sep)"])
    begin_month_day: str = Field(..., pattern=r"^\d{2}-\d{2}$", examples=["07-01"])
    end_month_day: str = Field(..., pattern=r"^\d{2}-\d{2}$", examples=["09-30"])


DEFAULT_SEASONAL_WINDOWS = [
    SeasonalWindow(label="Fall (Oct–Dec)", begin_month_day="10-01", end_month_day="12-31"),
    SeasonalWindow(label="Winter (Jan–Mar)", begin_month_day="01-01", end_month_day="03-31"),
    SeasonalWindow(label="Spring (Apr–Jun)", begin_month_day="04-01", end_month_day="06-30"),
    SeasonalWindow(label="Summer (Jul–Sep)", begin_month_day="07-01", end_month_day="09-30"),
]


class AnalysisRequest(BaseModel):
    site_no: str = Field(..., examples=["13340000"])
    start_date: date | None = Field(None, description="Defaults to the start of the site record.")
    end_date: date | None = Field(None, description="Defaults to today.")
    threshold_percent: float = Field(0.5, gt=0, lt=1, description="Center-of-timing fraction.")
    alpha: float = Field(0.10, gt=0, lt=1, description="Mann-Kendall significance level.")
    peak_window_size: int = Field(7, ge=1, le=60, description="Rolling-mean window (days) for peak.")
    ignore_winter_months: bool = Field(
        False, description="Restrict the peak search to Feb–Jun (ignore rain-on-snow spikes)."
    )
    seasonal_windows: list[SeasonalWindow] | None = None
    include_hydrograph: bool = Field(
        True, description="Include per-water-year daily curves for the hydrograph plot."
    )
    min_days_per_water_year: int = Field(
        350, ge=1, le=366, description="Drop water years with fewer measured days than this."
    )


# --------------------------------------------------------------------------- #
# Analysis response
# --------------------------------------------------------------------------- #
class MannKendall(BaseModel):
    trend: str  # 'increasing' | 'decreasing' | 'no trend'
    significant: bool
    p_value: float
    z: float
    tau: float
    s: float
    var_s: float
    slope: float  # Sen's slope, units per year
    intercept: float


class ClimatologyPoint(BaseModel):
    day_of_year: int
    month_day: str
    mean: float | None
    median: float | None
    q25: float | None
    q75: float | None
    std: float | None


class TimingPoint(BaseModel):
    water_year: int
    day_of_year: int
    date: str
    month_day: str


class VolumePoint(BaseModel):
    water_year: int
    volume_maf: float


class PeakPoint(BaseModel):
    water_year: int
    day_of_year: int
    value: float


class CenterOfTiming(BaseModel):
    threshold_percent: float
    mk_timing: MannKendall
    mk_volume: MannKendall
    points: list[TimingPoint]


class TotalVolume(BaseModel):
    mk: MannKendall
    points: list[VolumePoint]


class SeasonalVolume(BaseModel):
    label: str
    begin_month_day: str
    end_month_day: str
    mk: MannKendall
    points: list[VolumePoint]


class Peak(BaseModel):
    window_size: int
    ignore_winter_months: bool
    mk_magnitude: MannKendall
    mk_timing: MannKendall
    points: list[PeakPoint]


class HydrographYear(BaseModel):
    water_year: int
    day_of_year: list[int]
    value: list[float | None]


class AnalysisMeta(BaseModel):
    site: SiteOut
    value_label: str
    units: str
    record_start: str
    record_end: str
    n_water_years: int
    water_years: list[int]


class AnalysisResult(BaseModel):
    meta: AnalysisMeta
    climatology: list[ClimatologyPoint]
    center_of_timing: CenterOfTiming
    total_volume: TotalVolume
    seasonal_volumes: list[SeasonalVolume]
    peak: Peak
    hydrograph: list[HydrographYear] | None = None


# --------------------------------------------------------------------------- #
# Snow (SNOTEL)
# --------------------------------------------------------------------------- #
class SnotelSiteOut(BaseModel):
    station_triplet: str
    station_id: str
    name: str
    state: str
    lat: float | None = None
    long: float | None = None
    elevation_ft: float | None = None
    huc: str | None = None
    begin_date: str | None = None
    end_date: str | None = None


class SnowAnalysisRequest(BaseModel):
    station_triplet: str = Field(..., examples=["302:OR:SNTL"])
    start_date: date | None = None
    end_date: date | None = None
    benchmark_month_day: str = Field("04-01", pattern=r"^\d{2}-\d{2}$", description="SWE benchmark date.")
    alpha: float = Field(0.10, gt=0, lt=1)
    include_hydrograph: bool = True
    min_days_per_water_year: int = Field(300, ge=1, le=366)


class ValuePoint(BaseModel):
    water_year: int
    value: float


class SnowPeak(BaseModel):
    mk_magnitude: MannKendall | None
    mk_timing: MannKendall | None
    points: list[PeakPoint]


class BenchmarkSwe(BaseModel):
    benchmark_month_day: str
    mk: MannKendall | None
    points: list[ValuePoint]


class MeltOut(BaseModel):
    mk: MannKendall | None
    points: list[TimingPoint]


class SnowAnalysisMeta(BaseModel):
    station: SnotelSiteOut
    value_label: str
    units: str
    record_start: str
    record_end: str
    n_water_years: int
    water_years: list[int]


class SnowAnalysisResult(BaseModel):
    meta: SnowAnalysisMeta
    climatology: list[ClimatologyPoint]
    peak_swe: SnowPeak
    april1_swe: BenchmarkSwe
    melt_out: MeltOut
    hydrograph: list[HydrographYear] | None = None


# --------------------------------------------------------------------------- #
# Paired snow <-> streamflow basin view (option "B")
# --------------------------------------------------------------------------- #
class SnotelCandidateOut(SnotelSiteOut):
    distance_miles: float
    elevation_diff_ft: float | None
    same_huc8: bool


class SeriesPoint(BaseModel):
    water_year: int
    value: float


class TrendSeries(BaseModel):
    key: str
    label: str
    unit: str
    kind: str  # 'value' | 'timing' -- how the frontend labels the y-axis
    warming_direction: str  # 'increasing' | 'decreasing' -- which way is a warming signal
    mk: MannKendall | None
    points: list[SeriesPoint]


class PairedWindow(BaseModel):
    start_water_year: int
    end_water_year: int
    n_water_years: int


class Corroboration(BaseModel):
    category: str  # 'corroborating' | 'mixed' | 'inconclusive'
    summary: str
    details: list[str]


class PairedRequest(BaseModel):
    site_no: str = Field(..., examples=["13340000"])
    station_triplet: str = Field(..., examples=["1142:ID:SNTL"])
    start_date: date | None = None
    end_date: date | None = None
    threshold_percent: float = Field(0.5, gt=0, lt=1)
    benchmark_month_day: str = Field("04-01", pattern=r"^\d{2}-\d{2}$")
    alpha: float = Field(0.10, gt=0, lt=1)


class PairedResult(BaseModel):
    gage: SiteOut
    station: SnotelSiteOut
    window: PairedWindow
    snow_trends: list[TrendSeries]
    streamflow_trends: list[TrendSeries]
    corroboration: Corroboration


# --------------------------------------------------------------------------- #
# Baseflow (USGS hydrograph separation)
# --------------------------------------------------------------------------- #
BaseflowMethod = Literal["lyne_hollick", "eckhardt", "local_minimum"]
DEFAULT_BASEFLOW_START = date(1995, 10, 1)
DEFAULT_BASEFLOW_END = date(2025, 9, 30)


class BaseflowRequest(BaseModel):
    site_no: str = Field(..., examples=["13340000"])
    start_date: date = Field(DEFAULT_BASEFLOW_START, description="Null means the default (WY1996 start).")
    end_date: date = Field(DEFAULT_BASEFLOW_END, description="Null means the default (WY2025 end).")
    methods: list[BaseflowMethod] = Field(
        default_factory=lambda: ["lyne_hollick", "eckhardt", "local_minimum"],
        description="Non-empty, unique separation methods.",
    )
    eckhardt_bfi_max: float = Field(0.80, gt=0, lt=1)
    alpha: float = Field(0.10, gt=0, lt=1, description="Mann-Kendall significance level.")
    example_water_year: int | None = Field(None, description="Null means the latest complete water year.")

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _null_means_default(cls, v, info):
        if v is None:
            return DEFAULT_BASEFLOW_START if info.field_name == "start_date" else DEFAULT_BASEFLOW_END
        return v

    @field_validator("methods")
    @classmethod
    def _methods_non_empty_unique(cls, v):
        if not v:
            raise ValueError("methods must not be empty")
        if len(set(v)) != len(v):
            raise ValueError("methods must be unique")
        return v

    @model_validator(mode="after")
    def _start_before_end(self):
        if not self.start_date < self.end_date:
            raise ValueError("start_date must be before end_date")
        return self


class TrendTest(BaseModel):
    """Permissive Mann-Kendall-style result; non-finite values are null."""

    trend: str
    significant: bool
    p_value: float | None = None
    z: float | None = None
    tau: float | None = None
    s: float | None = None
    var_s: float | None = None
    slope: float | None = None
    intercept: float | None = None


class HamedRao(BaseModel):
    """Autocorrelation-robust trend test; non-finite values are null."""

    trend: str
    significant: bool
    p_value: float | None = None
    tau: float | None = None
    slope: float | None = None


class BaseflowTrend(BaseModel):
    original: TrendTest
    hamed_rao: HamedRao
    slope_pct_per_decade: float | None = None


class RegulationOut(BaseModel):
    level: str
    reason: str


class BaseflowMeta(BaseModel):
    site: SiteOut
    units: str
    window_start: str
    window_end: str
    record_start: str
    record_end: str
    water_years: list[int]
    eckhardt_bfi_max: float
    alpha: float
    regulation: RegulationOut
    caveats: list[str]


class BaseflowMetricInfo(BaseModel):
    key: str
    label: str
    unit: str
    description: str


class SkippedRun(BaseModel):
    start: str
    end: str


class ExcludedWaterYear(BaseModel):
    water_year: int
    reason: str


class BaseflowQuality(BaseModel):
    n_interpolated: int
    skipped_runs: list[SkippedRun]
    excluded_water_years: list[ExcludedWaterYear]


class BaseflowYearMetrics(BaseModel):
    water_year: int
    bfi: float | None = None
    baseflow_af: float | None = None
    junjul_baseflow_cfs: float | None = None
    augsep_baseflow_cfs: float | None = None
    min7_baseflow_cfs: float | None = None
    baseflow_cot_dowy: float | None = None
    recession_k: float | None = None


class BaseflowMethodResult(BaseModel):
    method: str
    label: str
    quality: BaseflowQuality
    metrics: list[BaseflowYearMetrics]
    trends: dict[str, BaseflowTrend | None]


class BaseflowRangeRow(BaseModel):
    metric: str
    min: float | None = None
    median: float | None = None
    max: float | None = None
    n_sig_decreasing: int
    n_sig_increasing: int
    n_methods: int


class SkippedMethod(BaseModel):
    method: str
    reason: str


class BaseflowExample(BaseModel):
    water_year: int
    dates: list[str]
    flow_cfs: list[float | None]
    baseflow_cfs: dict[str, list[float | None]]


class BaseflowResult(BaseModel):
    meta: BaseflowMeta
    metric_info: list[BaseflowMetricInfo]
    methods: list[BaseflowMethodResult]
    method_range: list[BaseflowRangeRow]
    skipped_methods: list[SkippedMethod]
    example: BaseflowExample
