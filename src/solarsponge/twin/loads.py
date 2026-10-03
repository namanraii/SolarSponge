"""Flexible-load physics and default (uncoordinated) schedules."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from solarsponge.config import Settings
from solarsponge.timeutil import hhmm_to_slot

RHO = 1000.0
G = 9.81


def pump_energy_kwh(volume_m3: float, head_m: float, eta: float) -> float:
    """Hydraulic energy at the meter: E = ρ g H V / (η · 3.6e6)."""
    return (RHO * G * head_m * volume_m3) / (eta * 3.6e6)


def volume_from_energy_m3(energy_kwh: float, head_m: float, eta: float) -> float:
    return energy_kwh * eta * 3.6e6 / (RHO * G * head_m)


@dataclass
class FlexLoad:
    load_id: str
    name: str
    kind: str
    power_kw: float
    energy_kwh: float
    window: tuple[int, int]
    min_run: int = 1
    max_starts: int = 4
    default_on: np.ndarray | None = None
    t_init: float | None = None
    temp_band: tuple[float, float] | None = None
    thermal_mass: float | None = None
    ua: float | None = None
    cop: float | None = None
    occupancy: tuple[int, int] | None = None
    deficit_init_mm: float | None = None
    max_depletion_mm: float | None = None
    et_mm: np.ndarray | None = None
    rain_mm: np.ndarray | None = None
    irrig_mm_per_on_slot: float | None = None
    soc_init: float | None = None
    soc_target: float | None = None
    battery_kwh: float | None = None
    charging_eff: float | None = None
    departure_slot: int | None = None
    t_amb: np.ndarray | None = None
    params: dict = field(default_factory=dict)


def _window_mask(window: tuple[int, int], T: int) -> np.ndarray:
    lo, hi = window
    m = np.zeros(T, dtype=int)
    m[lo : hi + 1] = 1
    return m


def _fill_window(window: tuple[int, int], T: int, slots: int) -> np.ndarray:
    on = np.zeros(T, dtype=int)
    lo, hi = window
    n = min(slots, hi - lo + 1)
    on[lo : lo + n] = 1
    return on


def build_flex_loads(settings: Settings, T: int, weather: dict | None = None) -> list[FlexLoad]:
    cfg = settings.time
    loads: list[FlexLoad] = []
    et = weather["et0_mm"] if weather is not None else np.full(T, 0.04)
    rain = weather["rain_mm"] if weather is not None else np.zeros(T)
    temp = weather["temp_c"] if weather is not None else np.full(T, 28.0)

    p = settings.loads.pump_cluster
    cluster_kw = p.pumps_per_cluster * p.pump_kw
    area_ha = p.pumps_per_cluster * p.area_ha_per_pump
    et_day_mm = float(et.sum()) * p.kc_crop_coeff
    # 1 mm on 1 ha = 10 m³; irrigation efficiency raises the water that must be pumped
    volume_m3 = (et_day_mm * 10.0 * area_ha) / max(p.irrigation_eff, 1e-6)
    e_kwh = pump_energy_kwh(volume_m3, p.head_m, p.wire_to_water_eff)
    allowed = (hhmm_to_slot(p.allowed_window[0], cfg), hhmm_to_slot(p.allowed_window[1], cfg))
    default_w = (hhmm_to_slot(p.default_window[0], cfg), hhmm_to_slot(p.default_window[1], cfg))
    irrig_mm = 0.0
    if cluster_kw > 0:
        v_slot = volume_from_energy_m3(cluster_kw * cfg.dt_h, p.head_m, p.wire_to_water_eff)
        irrig_mm = (v_slot * p.irrigation_eff) / max(area_ha * 10.0, 1e-6)

    for i in range(p.count_clusters):
        slots_needed = int(np.ceil(e_kwh / (cluster_kw * cfg.dt_h)))
        loads.append(
            FlexLoad(
                load_id=f"pump_cluster_{chr(65 + i)}",
                name=f"Pump cluster {chr(65 + i)}",
                kind="pump",
                power_kw=cluster_kw,
                energy_kwh=e_kwh,
                window=allowed,
                min_run=p.min_run_slots,
                max_starts=p.max_starts_per_day,
                default_on=_fill_window(default_w, T, slots_needed),
                deficit_init_mm=10.0,
                max_depletion_mm=p.max_depletion_mm,
                et_mm=et * p.kc_crop_coeff,
                rain_mm=rain,
                irrig_mm_per_on_slot=irrig_mm,
                params={"area_ha": area_ha, "head_m": p.head_m},
            )
        )

    c = settings.loads.cold_store
    loads.append(
        FlexLoad(
            load_id="cold_store_1",
            name="Cold store 1",
            kind="cold_store",
            power_kw=c.compressor_kw,
            energy_kwh=c.compressor_kw * 8 * cfg.dt_h,  # nominal; thermal band is the hard constraint
            window=(0, T - 1),
            min_run=c.min_run_slots,
            max_starts=c.max_starts_per_day,
            default_on=_thermostat_default(T, band=tuple(c.temp_band_c), t_init=c.t_init_c, kind="cool"),
            t_init=c.t_init_c,
            temp_band=(c.temp_band_c[0], c.temp_band_c[1]),
            thermal_mass=c.thermal_mass_kwh_per_c,
            ua=c.ua_kw_per_c,
            cop=c.cop,
            t_amb=temp,
        )
    )

    e = settings.loads.ev_depot
    power = e.vehicles * e.charger_kw
    need_kwh = e.vehicles * e.battery_kwh * (e.target_soc - e.arrival_soc) / max(e.charging_eff, 1e-6)
    dep = hhmm_to_slot(e.departure_window[0], cfg)
    # Charge overnight until morning departure; window is all hours before departure plus evening.
    default_w = (hhmm_to_slot(e.default_window[0], cfg), hhmm_to_slot(e.default_window[1], cfg))
    slots_needed = int(np.ceil(need_kwh / (power * cfg.dt_h)))
    loads.append(
        FlexLoad(
            load_id="ev_depot",
            name="EV depot",
            kind="ev_depot",
            power_kw=power,
            energy_kwh=need_kwh,
            window=(0, T - 1),
            min_run=2,
            max_starts=4,
            default_on=_fill_window(default_w, T, slots_needed),
            soc_init=e.arrival_soc,
            soc_target=e.target_soc,
            battery_kwh=e.vehicles * e.battery_kwh,
            charging_eff=e.charging_eff,
            departure_slot=dep,
        )
    )

    h = settings.loads.hvac_precool
    occ = (hhmm_to_slot(h.occupancy[0], cfg), hhmm_to_slot(h.occupancy[1], cfg))
    default = np.zeros(T, dtype=int)
    default[occ[0] : occ[1] + 1] = 1
    loads.append(
        FlexLoad(
            load_id="hvac_precool",
            name="Commercial HVAC pre-cool",
            kind="hvac",
            power_kw=h.flexible_kw,
            energy_kwh=h.flexible_kw * 6 * cfg.dt_h,
            window=(max(0, occ[0] - 8), occ[1]),
            min_run=2,
            max_starts=8,
            default_on=default,
            t_init=h.t_init_c,
            temp_band=(h.comfort_band_c[0], h.comfort_band_c[1]),
            thermal_mass=h.thermal_mass_kwh_per_c,
            ua=h.ua_kw_per_c,
            cop=3.0,
            occupancy=occ,
            t_amb=temp + 4.0,
        )
    )
    return loads


def _thermostat_default(T: int, band: tuple[float, float], t_init: float, kind: str) -> np.ndarray:
    """Simple cycling default: on for 1 h, off for 1 h during the day."""
    on = np.zeros(T, dtype=int)
    for t in range(T):
        on[t] = 1 if (t // 4) % 2 == 0 else 0
    return on


def simulate_thermal(load: FlexLoad, on: np.ndarray, dt_h: float) -> np.ndarray:
    T = len(on)
    temp = np.zeros(T)
    t = load.t_init if load.t_init is not None else 4.0
    c = load.thermal_mass or 100.0
    ua = load.ua or 5.0
    cop = load.cop or 2.5
    amb = load.t_amb if load.t_amb is not None else np.full(T, 30.0)
    cool = load.power_kw * cop
    for i in range(T):
        q_cool = cool * on[i] if load.kind in {"cold_store", "hvac"} else 0.0
        # cooling reduces temperature
        dt = dt_h * ((-q_cool + ua * (amb[i] - t)) / c)
        t = t + dt
        temp[i] = t
    return temp


def simulate_soil(load: FlexLoad, on: np.ndarray) -> np.ndarray:
    T = len(on)
    d = np.zeros(T)
    deficit = load.deficit_init_mm or 0.0
    et = load.et_mm if load.et_mm is not None else np.zeros(T)
    rain = load.rain_mm if load.rain_mm is not None else np.zeros(T)
    irr = load.irrig_mm_per_on_slot or 0.0
    for i in range(T):
        deficit = deficit + et[i] - rain[i] - irr * on[i]
        deficit = max(0.0, deficit)
        d[i] = deficit
    return d


def simulate_soc(load: FlexLoad, on: np.ndarray, dt_h: float) -> np.ndarray:
    T = len(on)
    s = np.zeros(T)
    soc = load.soc_init or 0.3
    cap = load.battery_kwh or 1.0
    eff = load.charging_eff or 0.92
    for i in range(T):
        soc = soc + on[i] * load.power_kw * dt_h * eff / cap
        soc = min(1.0, soc)
        s[i] = soc
    return s


def power_from_on(loads: list[FlexLoad], on: np.ndarray) -> np.ndarray:
    """on shape (n_loads, T)."""
    T = on.shape[1]
    p = np.zeros(T)
    for i, L in enumerate(loads):
        p += L.power_kw * on[i]
    return p
