# BTM Battery Dispatch — Limassol Hotel

A Django service that simulates behind-the-meter battery dispatch for a 4-star hotel in Limassol, Cyprus. It fetches real solar data, generates a synthetic hotel load, runs a greedy dispatch engine every 15 minutes, and serves a weekly report at `/reports/weekly/`.

Built as a take-home task for Neura Energy. Took approximately 1.5 hours.

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

1. Solar covers load directly — free energy first
2. Surplus solar charges battery — capped at 200 kW, 95% SoC ceiling
3. Excess solar curtailed if battery is full — no grid export allowed in Cyprus
4. Battery discharges to cover remaining load — capped at 200 kW, 10% SoC floor
5. Grid covers whatever remains — this is what costs money

Battery spec: 400 kWh capacity, 200 kW max power, 88% round-trip efficiency, initial SoC 50%.

### 3. Weekly Report — `/reports/weekly/`

- Grid cost with battery vs without (counterfactual)
- Weekly saving in €
- kWh charged and discharged
- Solar self-consumption %
- Interactive SoC curve (Chart.js)
- Daily energy summary bar chart (Solar / Load / Grid Draw per day)

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

For the week of 1–7 July 2024:

| Metric | Value |
|---|---|
| Grid cost without battery | €5,454 |
| Grid cost with battery | €3,362 |
| **Weekly saving** | **€2,092** |
| Solar charged to battery | 480.6 kWh |
| Battery discharged to load | 573.1 kWh |
| Solar self-consumption | 100% |

---

## One Thing That Surprised Me

The battery never exceeded ~35% SoC despite having 400 kWh of capacity and a 95% ceiling.

I expected to see the battery fully charge on sunny afternoons and then slowly drain overnight. Instead it barely got above 35% each day. The reason: the hotel load in Cyprus July is so heavy — air conditioning running at full power during the hottest part of the afternoon, pool pumps, kitchen — that the battery is being drained almost as fast as the solar is charging it. The battery never gets a chance to fill up.

This tells you something real: a 400 kWh battery might actually be undersized for this load profile. If you doubled the battery to 800 kWh, you'd likely see higher self-consumption and bigger savings. That observation directly motivated my "what to build next".

---

## What I'd Build Next

A **what-if form** — let the hotel manager vary battery size (200 / 400 / 600 / 800 kWh) and PV size (100 / 200 / 300 kWp) and instantly see how the weekly saving shifts.

The SoC observation makes this the most valuable next feature. The hotel already paid for a 400 kWh battery — but the data suggests they left money on the table by not going bigger. A simple what-if tool would let them quantify exactly how much, which is something they could show their financiers alongside the weekly report.

After that:
- **Night charging** — the current dispatch only charges from solar. Adding cheap night-rate grid charging (€0.15/kWh) and discharging at day rate (€0.30/kWh) would increase savings further
- **Real EAC commercial tariff** — the current TOU is a simplified residential proxy. Parsing the actual EAC commercial PDF would give more accurate savings numbers
- **LP-based optimal dispatch** — replace the greedy policy with a simple linear program (PuLP) that uses tomorrow's solar forecast to make smarter decisions today

---

## Project Structure

```
btm-battery-dispatch/
├── config/
│   ├── settings.py           # Django config, reads API token from .env
│   └── urls.py               # Routes to energy app
├── energy/
│   ├── models.py             # SolarReading, LoadReading, GridPrice
│   ├── dispatch.py           # Greedy battery dispatch engine (pure Python)
│   ├── views.py              # /reports/weekly/ view
│   ├── urls.py               # URL routing
│   ├── tests.py              # 7 unit tests on dispatch logic
│   └── management/
│       └── commands/
│           └── ingest_data.py  # Fetches solar, generates load & prices
├── templates/
│   └── energy/
│       └── weekly_report.html  # Chart.js interactive report
├── .env                      # API token — not committed
├── requirements.txt
└── README.md
```

---

## How I Used AI

I used Claude (claude.ai) throughout as a coding assistant — but I drove the architecture and every decision.

I set up the Django project structure myself, decided what models we needed and why, shaped the dispatch logic by specifying the priority order and constraints from the task spec, and directed what the report should show. Claude helped with the implementation details — writing boilerplate, debugging errors, configuring Chart.js, and generating test cases that I reviewed for correctness.

Where it helped most: diagnosing errors quickly (the renewables.ninja 403 auth issue, the Unix millisecond timestamp overflow) and writing Chart.js configuration.

Where it got in the way: it initially tried to embed Django template variables directly inside script tags which broke, and defaulted to matplotlib before I pushed for Chart.js. Easy to catch and correct.

The dynamic was me explaining what I wanted to build and why at each step, Claude implementing it, and me reviewing and adjusting. Like working with a fast junior developer where I was driving.

---

## Did I Enjoy It?

Yes — it is a genuinely interesting problem. The dispatch logic has real physical constraints (SoC limits, round-trip efficiency, no grid export) that make it more interesting than a typical CRUD task. Seeing the SoC chart appear with real NASA solar data for Limassol was satisfying, and the observation about the battery never exceeding 35% SoC made me want to keep going and build the what-if form.

---

## Tech Stack

- Python 3.13 / Django 4.2 / SQLite
- pandas, numpy — data manipulation and resampling
- requests — renewables.ninja API
- Chart.js 4.4 (CDN) — interactive charts
- python-decouple — `.env` file reading
