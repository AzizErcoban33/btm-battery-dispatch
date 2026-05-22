# BTM Battery Dispatch — Limassol Hotel

A Django service that simulates behind-the-meter battery dispatch for a 4-star hotel in Limassol, Cyprus. It fetches real solar data, generates a synthetic hotel load, runs a greedy dispatch engine every 15 minutes, and serves a weekly report at `/reports/weekly/`.

Built as a take-home task for Neura Energy. Took approximately 1.5 hours including stretch goals.

---

## Setup

```bash
git clone https://github.com/AzizErcoban33/btm-battery-dispatch.git
cd btm-battery-dispatch

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
```

Create a `.env` file in the root:
```
API_TOKEN=your_renewables_ninja_token_here

Get your free API token by registering at [renewables.ninja](https://www.renewables.ninja) and visiting your profile page.
```

Then run:
```bash
python manage.py migrate
python manage.py ingest_data
python manage.py runserver
```

Open **http://127.0.0.1:8000/reports/weekly/**

---

## Run Tests

```bash
python manage.py test
```

7 unit tests covering the dispatch logic — SoC limits, curtailment, battery discharge, grid cost savings.

---

## What It Does

### 1. Data — `python manage.py ingest_data`

Three 15-minute time series for the week of 1–7 July 2024, stored in SQLite.

| Series | Source | Notes |
|---|---|---|
| `solar_kw` | renewables.ninja API | Limassol (34.675°N, 33.044°E), 200 kWp, MERRA-2 dataset, hourly → 15-min via linear interpolation |
| `load_kw` | Synthetic | See assumptions below |
| `grid_price_eur_per_kwh` | Hardcoded TOU | €0.30 day / €0.15 night |

### 2. Dispatch — `energy/dispatch.py`

Greedy policy running at every 15-min slot in order:

0. **Night charging** — if night rate (€0.15) and SoC below 80% → charge from cheap grid
1. Solar covers load directly — free energy first
2. Surplus solar charges battery — capped at 200 kW, 95% SoC ceiling
3. Excess solar curtailed if battery is full — no grid export allowed in Cyprus
4. Battery discharges to cover remaining load — capped at 200 kW, 10% SoC floor
5. Grid covers whatever remains — this is what costs money

Battery spec: 400 kWh capacity, 200 kW max power, 88% round-trip efficiency, initial SoC 50%.

Night charging was added because the TOU tariff has a €0.15/kWh night rate vs €0.30/kWh day rate. The battery was sitting idle at 10% SoC overnight when it could be cheaply charging up ready for the next day. This is pure arbitrage — buy cheap at night, use expensive during the day — and increased weekly savings by ~€60.

### 3. Weekly Report — `/reports/weekly/`

- Grid cost with battery vs without (counterfactual)
- Weekly saving in €
- kWh charged and discharged
- Solar self-consumption %
- Interactive SoC curve (Chart.js)
- Daily energy summary bar chart (Solar / Load / Grid Draw per day)

### 4. What-If Analysis — `/reports/whatif/` ✅ Stretch goal

A form that lets you vary battery capacity (kWh) and PV system size (kWp) and instantly reruns the full dispatch simulation showing how weekly saving shifts vs the baseline. Useful for showing financiers how much more value a larger system would deliver.

---

## Assumptions

### Hotel Load Shape

No public 15-min dataset exists for a Cyprus hotel. I built a synthetic profile:

- **Base load 60 kW** — hotel never fully shuts down (reception, kitchen, lifts, refrigeration)
- **Morning ramp 06:00–09:00** — breakfast service, guests waking up
- **Daytime 09:00–14:00** — gradual increase as AC starts
- **Peak afternoon 14:00–18:00** — hottest part of the day in Cyprus July, maximum cooling load, pool pumps at full
- **Evening 18:00–23:00** — restaurant, bar, guests back from beach
- **Night 23:00–06:00** — minimal load, most guests asleep
- **Weekends ×1.15** — higher occupancy, more guests on-site during the day
- **Scaled so weekly peak = exactly 200 kW** as per task spec

DOE/OpenEI commercial hotel load shapes used as a sanity reference for the daily shape.

### Solar Resampling

renewables.ninja returns hourly data. Resampled to 15-min using **linear interpolation** (`pandas resample('15min').interpolate(method='linear')`). More realistic than forward-fill for solar which ramps smoothly rather than stepping.

### Grid Prices

Stylised 2-rate TOU modelled on EAC Code 02. Cyprus is UTC+3 in summer (EEST), so:
- Day rate €0.30/kWh → 09:00–23:00 local = 06:00–20:00 UTC
- Night rate €0.15/kWh → 23:00–09:00 local = 20:00–06:00 UTC

### Round-Trip Efficiency

Split evenly across charge and discharge: `0.88^0.5 ≈ 0.938` applied in each direction. Standard convention for LFP batteries.

### Initial SoC

Started at 50%. A full week of dispatch smooths out this assumption by day 2.

---

## Results

For the week of 1–7 July 2024 with baseline system (400 kWh battery, 200 kWp PV) including night charging:

| Metric | Value |
|---|---|
| Grid cost without battery | €5,454 |
| Grid cost with battery | €3,302 |
| **Weekly saving** | **€2,152** |
| Solar charged to battery | 385.7 kWh |
| Battery discharged to load | 9,012 kWh |
| Solar self-consumption | 98.7% |

**What-if finding:** A 100 kWh battery saves €150 less per week than the 400 kWh baseline — the smaller battery fills and empties too quickly to shift much energy. Scaling PV to 1000 kWp increases saving to €3,535 but drops self-consumption to 34.9% — the battery can't absorb all the extra solar.

---

## Stretch Goals

### What-If Form ✅ Built
Available at `/reports/whatif/`. Vary battery capacity and PV size, see how saving and self-consumption shift in real time. The delta vs baseline is shown in green (better) or red (worse).

### Night Charging ✅ Built
The task spec called for solar-first dispatch. But the TOU tariff has a €0.15/kWh night rate vs €0.30/kWh day rate, and the battery was sitting idle at 10% SoC all night. I added night charging as an obvious enhancement — charge cheaply overnight, discharge during expensive daytime hours. This increased weekly savings from €2,092 to €2,152.

### Real EAC Commercial Tariff ❌ Geo-blocked
Attempted to pull the commercial tariff PDF from eac.com.cy. The page returned a restricted access response even from within Cyprus. Fell back to the stylised 2-rate TOU as specified in the task. If access becomes available, the next step would be to parse the PDF (partly in Greek), extract the time bands and rates, store them as a separate tariff model, and rerun dispatch against it.

---

## One Thing That Surprised Me

The battery never exceeded ~35% SoC in the original solar-only dispatch, despite having 400 kWh of capacity and a 95% ceiling.

The reason: the hotel load in Cyprus July is so heavy — air conditioning running at full power during the hottest part of the afternoon, pool pumps, kitchen — that the battery is being drained almost as fast as the solar is charging it. The battery never gets a chance to fill up.

Adding night charging fixed this — the battery now starts each day at ~80% SoC and the SoC chart shows healthy full daily cycles. The weekend days (Saturday/Sunday) show visibly lower SoC peaks because the ×1.15 weekend load multiplier drains the battery faster.

---

## What I'd Build Next

**Real EAC commercial tariff** — the current TOU is a simplified residential proxy. The actual EAC commercial tariff has more complex time bands and demand charges. Parsing the real PDF and rerunning dispatch would give more accurate savings numbers for a real hotel. This was attempted but blocked.

After that:
- **LP-based optimal dispatch** — replace the greedy policy with a linear program (PuLP) that uses tomorrow's solar forecast to make smarter charge/discharge decisions today. The greedy policy makes locally optimal decisions but can miss globally better strategies — for example holding charge overnight if tomorrow will be cloudy
- **Live dispatch** — run the engine every 15 minutes against real meter readings rather than historical simulation. That's the actual product Neura builds
- **Multi-site** — the current architecture is single-hotel. Parameterise by site ID to handle a portfolio of properties

---

## Project Structure

```
btm-battery-dispatch/
├── config/
│   ├── settings.py           # Django config, reads API token from .env
│   └── urls.py               # Routes to energy app
├── energy/
│   ├── models.py             # SolarReading, LoadReading, GridPrice
│   ├── dispatch.py           # Greedy dispatch engine with night charging
│   ├── views.py              # /reports/weekly/ and /reports/whatif/ views
│   ├── urls.py               # URL routing
│   ├── tests.py              # 7 unit tests on dispatch logic
│   └── management/
│       └── commands/
│           └── ingest_data.py  # Fetches solar, generates load & prices
├── templates/
│   └── energy/
│       ├── weekly_report.html  # Chart.js interactive report
│       └── whatif.html         # What-if analysis form and results
├── .env                      # API token — not committed
├── requirements.txt
└── README.md
```

---

## How I Used AI

I used Claude (claude.ai) as a coding assistant throughout — like a fast junior developer sitting next to me. I drove every decision and Claude handled the implementation.

I set up the Django project structure myself — the project skeleton, app layout, models, and the overall architecture. While building each piece I used Claude to discuss what files and components we'd need next, talking through the reasoning before writing anything. Claude helped me think ahead about what was coming, not just what was in front of me.

For the actual coding, I shaped every decision: what models we needed and why, the dispatch priority order and constraints from the spec, what the report should show, when to use Chart.js over matplotlib, when to push back on suggestions that didn't fit. Claude wrote the implementation — boilerplate, debugging, chart configuration, test cases. I reviewed everything it produced and corrected it when it went wrong.

One good example of driving rather than following: the task mentioned night charging implicitly through the TOU tariff structure. Claude initially didn't include it. I recognised the opportunity, told Claude to add it, and it increased weekly savings from €2,092 to €2,152. That kind of domain reasoning came from me reading the spec carefully, not from the AI.

Where Claude helped most: diagnosing errors quickly (the renewables.ninja 403 auth issue, the Unix millisecond timestamp overflow) and writing Chart.js configuration which would have taken much longer manually.

Where it got in the way: it initially tried to embed Django template variables directly inside script tags which broke the page, and defaulted to matplotlib before I pushed for Chart.js. Easy to catch and correct — but worth noting that AI output always needs review.

---

## Did I Enjoy It?

Yes — it is a genuinely interesting problem. The dispatch logic has real physical constraints (SoC limits, round-trip efficiency, no grid export) that make it more interesting than a typical CRUD task. Seeing the SoC chart appear with real NASA solar data for Limassol was satisfying, and spotting that the battery was sitting idle at night and adding night charging to fix it was the most satisfying moment of the build.

---

## Tech Stack

- Python 3.13 / Django 4.2 / SQLite
- pandas, numpy — data manipulation and resampling
- requests — renewables.ninja API
- Chart.js 4.4 (CDN) — interactive charts
- python-decouple — `.env` file reading
