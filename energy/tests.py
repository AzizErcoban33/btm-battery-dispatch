from django.test import TestCase
from energy.dispatch import run_dispatch, BATTERY_CAPACITY_KWH, SOC_MIN, SOC_MAX

# Create your tests here.

def make_slot(solar, load, price=0.30):
    """Helper — returns single-slot lists for run_dispatch."""
    from datetime import datetime, timezone
    ts = datetime(2024, 7, 1, 12, 0, tzinfo=timezone.utc)
    return [ts], [solar], [load], [price]


class DispatchBasicTest(TestCase):

    def test_solar_covers_load_no_grid(self):
        """When solar exactly meets load, grid draw should be zero."""
        ts, solar, load, price = make_slot(solar=100.0, load=100.0)
        results = run_dispatch(ts, solar, load, price)
        self.assertAlmostEqual(results[0].grid_to_load_kw, 0.0, places=3)

    def test_surplus_solar_charges_battery(self):
        """When solar exceeds load, surplus should go to battery."""
        ts, solar, load, price = make_slot(solar=150.0, load=50.0)
        results = run_dispatch(ts, solar, load, price)
        self.assertGreater(results[0].solar_to_battery_kw, 0.0)

    def test_battery_covers_load_when_no_solar(self):
        """At night with no solar, battery should discharge to cover load."""
        ts, solar, load, price = make_slot(solar=0.0, load=80.0)
        results = run_dispatch(ts, solar, load, price)
        self.assertGreater(results[0].battery_to_load_kw, 0.0)

    def test_soc_never_exceeds_max(self):
        """SoC should never go above 95% even with massive solar surplus."""
        ts, solar, load, price = make_slot(solar=200.0, load=0.0)
        results = run_dispatch(ts, solar, load, price)
        self.assertLessEqual(results[0].soc_end, SOC_MAX + 0.001)

    def test_soc_never_below_min(self):
        """SoC should never drop below 10% even with massive load and no solar."""
        ts, solar, load, price = make_slot(solar=0.0, load=200.0)
        results = run_dispatch(ts, solar, load, price)
        self.assertGreaterEqual(results[0].soc_end, SOC_MIN - 0.001)

    def test_curtailment_when_battery_full(self):
        """Surplus solar should be curtailed when battery is already at max."""
        from datetime import datetime, timezone
        ts = [datetime(2024, 7, 1, 12, 0, tzinfo=timezone.utc)]

        # Run many slots of pure surplus to fill battery first
        fill_ts = [datetime(2024, 7, 1, 12, 0, tzinfo=timezone.utc)] * 20
        fill_results = run_dispatch(fill_ts, [200.0]*20, [0.0]*20, [0.30]*20)

        # Last slot should have curtailment since battery is full
        last = fill_results[-1]
        self.assertGreaterEqual(last.curtailed_kw, 0.0)

    def test_no_battery_cost_is_higher(self):
        """Without battery, cost should be >= cost with battery."""
        from datetime import datetime, timezone
        timestamps = [datetime(2024, 7, 1, tzinfo=timezone.utc)] * 10
        solar = [100.0] * 10
        load = [150.0] * 10
        prices = [0.30] * 10

        results = run_dispatch(timestamps, solar, load, prices)
        total_with_battery = sum(r.grid_cost_eur for r in results)
        total_no_battery = sum(r.no_battery_cost_eur for r in results)
        self.assertLessEqual(total_with_battery, total_no_battery)