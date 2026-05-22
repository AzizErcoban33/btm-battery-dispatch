import json
import base64
import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from django.shortcuts import render
from energy.models import SolarReading, LoadReading, GridPrice
from energy.dispatch import run_dispatch


def weekly_report(request):
    #  Fetch all 3 series from DB 
    solar_qs  = SolarReading.objects.all()
    load_qs   = LoadReading.objects.all()
    price_qs  = GridPrice.objects.all()

    # Build lookup dicts keyed by timestamp
    solar_map = {r.timestamp: r.solar_kw          for r in solar_qs}
    load_map  = {r.timestamp: r.load_kw           for r in load_qs}
    price_map = {r.timestamp: r.price_eur_per_kwh for r in price_qs}

    # Use price timestamps as master index (672 slots)
    timestamps = sorted(price_map.keys())

    solar_kws = [solar_map.get(ts, 0.0) for ts in timestamps]
    load_kws  = [load_map.get(ts,  0.0) for ts in timestamps]
    prices    = [price_map[ts]          for ts in timestamps]

    #  Run dispatch engine 
    results = run_dispatch(timestamps, solar_kws, load_kws, prices)

    # ── Weekly summary stats ──
    total_grid_cost       = sum(r.grid_cost_eur       for r in results)
    total_no_battery_cost = sum(r.no_battery_cost_eur for r in results)
    total_saving          = total_no_battery_cost - total_grid_cost

    total_charged_kwh    = sum(r.solar_to_battery_kw * 0.25 for r in results)
    total_discharged_kwh = sum(r.battery_to_load_kw  * 0.25 for r in results)

    total_solar_kwh    = sum(r.solar_kw    * 0.25 for r in results)
    total_curtailed_kwh = sum(r.curtailed_kw * 0.25 for r in results)
    solar_used_kwh     = total_solar_kwh - total_curtailed_kwh
    self_consumption_pct = (
        (solar_used_kwh / total_solar_kwh * 100) if total_solar_kwh > 0 else 0
    )

    #  Chart data for Chart.js 
    labels     = [r.timestamp.strftime('%Y-%m-%d %H:%M') for r in results]
    soc_data   = [round(r.soc_end * 100, 1)   for r in results]
    solar_data = [round(r.solar_kw, 1)         for r in results]
    load_data  = [round(r.load_kw, 1)          for r in results]
    grid_data  = [round(r.grid_to_load_kw, 1)  for r in results]

    context = {
        'total_grid_cost':       round(total_grid_cost, 2),
        'total_no_battery_cost': round(total_no_battery_cost, 2),
        'total_saving':          round(total_saving, 2),
        'total_charged_kwh':     round(total_charged_kwh, 1),
        'total_discharged_kwh':  round(total_discharged_kwh, 1),
        'self_consumption_pct':  round(self_consumption_pct, 1),
        'chart_labels':          json.dumps(labels),
        'soc_data':              json.dumps(soc_data),
        'solar_data':            json.dumps(solar_data),
        'load_data':             json.dumps(load_data),
        'grid_data':             json.dumps(grid_data),
    }
    return render(request, 'energy/weekly_report.html', context)