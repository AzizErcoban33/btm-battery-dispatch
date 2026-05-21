from django.core.management.base import BaseCommand
from django.conf import settings
from energy.models import SolarReading, LoadReading, GridPrice


class Command(BaseCommand):
    help = 'Fetch solar data, generate load and grid prices, save to DB'

    def handle(self, *args, **kwargs):
        self.stdout.write('Clearing old data...')
        SolarReading.objects.all().delete()
        LoadReading.objects.all().delete()
        GridPrice.objects.all().delete()

        self.stdout.write('Ingesting solar data...')
        self._ingest_solar()

        self.stdout.write('Generating load data...')
        self._generate_load()

        self.stdout.write('Generating grid prices...')
        self._generate_prices()

        self.stdout.write(self.style.SUCCESS('All data ingested successfully!'))

    def _ingest_solar(self):
        import requests
        import pandas as pd
        from datetime import timezone

        url = 'https://www.renewables.ninja/api/data/pv'
        headers = {'Authorization': f'Token {settings.NINJA_API_TOKEN}'}
        params = {
            'lat': 34.675,
            'lon': 33.044,
            'date_from': '2024-07-01',
            'date_to': '2024-07-07',
            'dataset': 'merra2',
            'capacity': 200,
            'system_loss': 0.1,
            'tracking': 0,
            'tilt': 35,
            'azim': 180,
            'format': 'json',
        }

        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        # Parse into a DataFrame
        df = pd.DataFrame.from_dict(data['data'], orient='index')
        df.index = pd.to_datetime(df.index.astype(float), unit='ms', utc=True)

        # Resample from hourly to 15-min using linear interpolation
        df = df.resample('15min').interpolate(method='linear')

        # Save to DB
        objs = [
            SolarReading(
                timestamp=ts.to_pydatetime().replace(tzinfo=timezone.utc),
                solar_kw=float(row['electricity'])
            )
            for ts, row in df.iterrows()
        ]
        SolarReading.objects.bulk_create(objs)
        self.stdout.write(f'  Saved {len(objs)} solar readings')

    def _generate_load(self):
        import pandas as pd
        import numpy as np
        from datetime import timezone

        timestamps = pd.date_range(
            start='2024-07-01 00:00', 
            end='2024-07-07 23:45', 
            freq='15min', 
            tz='UTC'
        )

        loads = []
        for ts in timestamps:
            hour = ts.hour
            is_weekend = ts.dayofweek >= 5  # Saturday=5, Sunday=6

            # Base load — hotel never fully shuts down (kitchen, reception, lifts)
            base = 60.0

            # Morning ramp up — breakfast, guests waking
            if 6 <= hour < 9:
                base += 40 * ((hour - 6) / 3)

            # Daytime — cooling kicks in hard on hot Cyprus afternoon
            elif 9 <= hour < 14:
                base += 40 + 30 * ((hour - 9) / 5)

            # Peak afternoon cooling — hottest part of day
            elif 14 <= hour < 18:
                base += 80

            # Evening — restaurant, bar, guests back from beach
            elif 18 <= hour < 23:
                base += 60

            # Night — most guests asleep, minimal load
            else:
                base += 10

            # Weekends busier — higher occupancy
            if is_weekend:
                base *= 1.15

            loads.append(base)

        # Scale so weekly peak hits exactly 200 kW
        loads = np.array(loads)
        loads = loads * (200.0 / loads.max())

        objs = [
            LoadReading(
                timestamp=ts.to_pydatetime(),
                load_kw=float(kw)
            )
            for ts, kw in zip(timestamps, loads)
        ]
        LoadReading.objects.bulk_create(objs)
        self.stdout.write(f'  Saved {len(objs)} load readings')


    def _generate_prices(self):
        import pandas as pd
        from datetime import timezone

        timestamps = pd.date_range(
            start='2024-07-01 00:00',
            end='2024-07-07 23:45',
            freq='15min',
            tz='UTC'
        )

        # Cyprus is UTC+3 in summer (EEST)
        # Day rate 09:00-23:00 local = 06:00-20:00 UTC
        DAY_RATE = 0.30
        NIGHT_RATE = 0.15

        objs = [
            GridPrice(
                timestamp=ts.to_pydatetime(),
                price_eur_per_kwh=DAY_RATE if 6 <= ts.hour < 20 else NIGHT_RATE
            )
            for ts in timestamps
        ]
        GridPrice.objects.bulk_create(objs)
        self.stdout.write(f'  Saved {len(objs)} price readings')