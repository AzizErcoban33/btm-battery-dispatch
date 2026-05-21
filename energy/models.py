from django.db import models

# Create your models here.

class SolarReading(models.Model):
    timestamp = models.DateTimeField()
    solar_kw = models.FloatField()

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.timestamp} — {self.solar_kw} kW"


class LoadReading(models.Model):
    timestamp = models.DateTimeField()
    load_kw = models.FloatField()

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.timestamp} — {self.load_kw} kW"


class GridPrice(models.Model):
    timestamp = models.DateTimeField()
    price_eur_per_kwh = models.FloatField()

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.timestamp} — €{self.price_eur_per_kwh}"