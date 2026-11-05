"""Values exchanged by the pure stress model."""
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class HistoryDay:
    """First-recorded load and calendar-day temperatures, as attested by the caller."""
    date: date
    peak_mw: float | None
    peak_hour_ending: int | None
    high_f: float | None
    morning_low_f: float | None
    complete: bool
    load_first_recorded: bool | None = None
    temperature_first_recorded: bool | None = None
    load_available_at: datetime | None = None
    temperature_available_at: datetime | None = None


@dataclass(frozen=True)
class Alert:
    date: date
    text: str


@dataclass(frozen=True)
class Features:
    """Prospective availability fields must be actual timezone-aware timestamps."""
    target_date: date
    high_f: float | None
    morning_low_f: float | None
    history: tuple[HistoryDay, ...]
    load_fresh: bool
    weather_fresh: bool
    alerts: tuple[Alert, ...] = ()
    mode: str = 'retrospective'
    issued_at: datetime | None = None
    weather_available_at: datetime | None = None


@dataclass(frozen=True)
class Definition:
    version: str
    sha256: str
    weather_point: str
    history_station: str
    history_years: int
    window_days: int
    heat_base_f: int
    cold_base_f: int
    hinge_min_nonzero_days: int
    watch_percentile: int
    strained_percentile: int
    severe_percentile: int
    analog_count: int
    settle_days: int
    alerts_annotation_only: bool


@dataclass(frozen=True)
class ForecastReceipt:
    """Sequential gate counts and calculation fallbacks for a forecast."""
    mode: str
    publication_availability: str
    issued_at: datetime | None = None
    history_evaluated: bool = False
    history_gates: dict[str, dict[str, int]] = field(default_factory=dict)
    analog_gates: dict[str, dict[str, int]] = field(default_factory=dict)
    sample_sizes: dict[str, int] = field(default_factory=dict)
    fallbacks: tuple[str, ...] = ()
    analog_dates: tuple[date, ...] = ()
    regression_coefficients: tuple[float, ...] | None = None
    active_hinges: tuple[str, ...] = ()
    initial_condition_number: float | None = None
    final_condition_number: float | None = None


@dataclass(frozen=True)
class Forecast:
    target_date: date
    definition_version: str
    definition_sha256: str
    peak_mw: float | None
    peak_hour_ending: int | None
    level: str | None
    thresholds_mw: tuple[float, float, float] | None
    no_call_reason: str | None
    alerts: tuple[str, ...]
    status: str | None = None
    receipt: ForecastReceipt | None = None

    def __post_init__(self):
        if self.status is None:
            scored = (self.no_call_reason is None and self.peak_mw is not None
                      and self.peak_hour_ending is not None and self.level is not None
                      and self.thresholds_mw is not None)
            object.__setattr__(self, 'status', 'SCORED' if scored else 'UNSCORED')
