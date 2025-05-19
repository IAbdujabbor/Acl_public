from django.db import models


class PvElectricity(models.Model):  # ✅ Class name should be in PascalCase
    month = models.CharField(max_length=20)
    time = models.TimeField()
    electricity = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)  # Allow null and blank values

    @staticmethod
    def get_unique_months():
        # Fetch distinct months, normalize case, strip spaces, and return sorted list
        months = PvElectricity.objects.values_list('month', flat=True).distinct()
        unique_months = sorted(set(month.strip().capitalize() for month in months if month))
        return unique_months

    #distinct_months = YourModelName.objects.values('month').distinct()

    class Meta:
        ordering = ["month", "time"]  # ✅ Ensures correct ordering

    def __str__(self):
        return f"{self.month} - {self.time} - {self.electricity if self.electricity is not None else 'No Data'}"
