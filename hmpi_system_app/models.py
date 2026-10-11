from django.db import models


class Sample(models.Model):
    location = models.CharField(max_length=100)
    date = models.DateField()
    lead = models.FloatField()
    mercury = models.FloatField()
    cadmium = models.FloatField()
    arsenic = models.FloatField()
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.location} - {self.date}"
