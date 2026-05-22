# energy/dispatch.py

# function that takes the 3 data series and returns dispatch decisions 
# for every 15-min slot.

# The logic for each slot in order:
# 1) Cover load with solar first
# 2) If solar > load → charge battery with the surplus
# 3) If load > solar → discharge battery to cover the gap
# 4) Anything still uncovered → draw from grid
# 5) Respect SoC limits (10%–95%), power cap (200kW), 88% efficiency
# 6) Can't export to grid → curtail excess solar if battery is full

from dataclasses import dataclass, field
from typing import List


# Battery constants
BATTERY_CAPACITY_KWH = 400.0
BATTERY_MAX_POWER_KW = 200.0
SOC_MIN = 0.10  # 10%
SOC_MAX = 0.95  # 95%
ROUND_TRIP_EFFICIENCY = 0.88
INTERVAL_HOURS = 0.25  # 15 minutes = 0.25 of an hour


@dataclass
class SlotResult:
    """Stores what happened in one 15-minute slot."""
    timestamp: object
    solar_kw: float
    load_kw: float
    grid_price: float

    solar_to_load_kw: float = 0.0    # solar energy used directly
    solar_to_battery_kw: float = 0.0 # solar energy stored
    battery_to_load_kw: float = 0.0  # battery energy discharged
    grid_to_load_kw: float = 0.0     # energy drawn from grid
    curtailed_kw: float = 0.0        # wasted solar

    soc_start: float = 0.0
    soc_end: float = 0.0

    grid_cost_eur: float = 0.0
    no_battery_cost_eur: float = 0.0


def run_dispatch(
    timestamps,
    solar_kws,
    load_kws,
    prices,
    battery_capacity_kwh: float = BATTERY_CAPACITY_KWH,
    battery_max_power_kw: float = BATTERY_MAX_POWER_KW,
) -> List[SlotResult]:
    """
    Run greedy battery dispatch over a week of 15-min slots.
    
    Priority order each slot:
    1. Solar covers load directly
    2. Surplus solar charges battery
    3. Battery discharges to cover remaining load
    4. Grid covers anything left
    5. Curtail solar if battery is full and load is met
    """
    results = []
    
    # Start battery at 50% charge
    soc = 0.50

    for ts, solar_kw, load_kw, price in zip(timestamps, solar_kws, load_kws, prices):
        result = SlotResult(
            timestamp=ts,
            solar_kw=solar_kw,
            load_kw=load_kw,
            grid_price=price,
            soc_start=soc,
        )

        remaining_load = load_kw
        remaining_solar = solar_kw

        # --- Step 1: Solar covers load directly ---
        direct = min(remaining_solar, remaining_load)
        result.solar_to_load_kw = direct
        remaining_solar -= direct
        remaining_load -= direct

        # --- Step 2: Surplus solar charges battery ---
        if remaining_solar > 0:
            # How much space is left in the battery?
            soc_headroom = (SOC_MAX - soc) * battery_capacity_kwh / INTERVAL_HOURS
            # Cap by max charge power
            max_charge_kw = min(battery_max_power_kw, soc_headroom)
            # Cap by available solar
            charge_kw = min(remaining_solar, max_charge_kw)
            charge_kw = max(charge_kw, 0.0)

            # Energy actually stored (efficiency loss on the way in)
            energy_stored_kwh = charge_kw * INTERVAL_HOURS * (ROUND_TRIP_EFFICIENCY ** 0.5)
            soc += energy_stored_kwh / battery_capacity_kwh

            result.solar_to_battery_kw = charge_kw
            remaining_solar -= charge_kw

        # --- Step 3: Curtail excess solar (can't export to grid) ---
        result.curtailed_kw = remaining_solar

        # --- Step 4: Battery discharges to cover remaining load ---
        if remaining_load > 0:
            # How much energy can we actually take out?
            soc_available = (soc - SOC_MIN) * battery_capacity_kwh / INTERVAL_HOURS
            max_discharge_kw = min(battery_max_power_kw, soc_available)
            discharge_kw = min(remaining_load, max_discharge_kw)
            discharge_kw = max(discharge_kw, 0.0)

            # Energy removed from battery (efficiency loss on the way out)
            energy_removed_kwh = discharge_kw * INTERVAL_HOURS / (ROUND_TRIP_EFFICIENCY ** 0.5)
            soc -= energy_removed_kwh / battery_capacity_kwh

            result.battery_to_load_kw = discharge_kw
            remaining_load -= discharge_kw

        # --- Step 5: Grid covers whatever is still needed ---
        result.grid_to_load_kw = remaining_load

        # --- Costs ---
        result.grid_cost_eur = remaining_load * INTERVAL_HOURS * price
        result.no_battery_cost_eur = load_kw * INTERVAL_HOURS * price

        result.soc_end = soc
        results.append(result)

    return results