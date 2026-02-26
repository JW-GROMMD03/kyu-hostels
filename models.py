from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import User, OwnerProfile

class Hostel(models.Model):
    HOSTEL_TYPES = (
        ('bedsitter', 'Bedsitter'),
        ('single', 'Single Room'),
        ('one_bedroom', 'One Bedroom'),
    )
    
    owner = models.ForeignKey(OwnerProfile, on_delete=models.CASCADE, related_name='hostels')
    name = models.CharField(max_length=200)
    description = models.TextField()
    hostel_type = models.CharField(max_length=20, choices=HOSTEL_TYPES)
    
    # Location
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.CharField(max_length=255)
    distance_from_university = models.FloatField(help_text="Distance in KM")
    
    # Pricing
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Amenities
    amenities = models.JSONField(default=list)
    images = models.JSONField(default=list)
    virtual_tour_url = models.URLField(blank=True)
    
    # Status
    is_available = models.BooleanField(default=True)
    is_reserved = models.BooleanField(default=False)
    reserved_until = models.DateTimeField(null=True, blank=True)
    
    # Metrics
    rating = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    total_reviews = models.IntegerField(default=0)
    views_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def calculate_fraud_score(self):
        # Calculate based on owner history, complaints, etc.
        base_score = self.owner.fraud_score
        complaints = Review.objects.filter(hostel=self, is_approved=True, is_complaint=True).count()
        return base_score + (complaints * 5)

class Availability(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='availability')
    date = models.DateField()
    is_available = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
class PriceHistory(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='price_history')
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    effective_date = models.DateField(auto_now_add=True)

class Review(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    is_complaint = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_reviews')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['hostel', 'user']