from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import User, StudentProfile, OwnerProfile, AuditLog


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create appropriate profile based on user role"""
    if created and not instance.is_superuser:
        # Profile will be created during registration based on role
        pass


@receiver(post_save, sender=StudentProfile)
def student_profile_created(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            user=instance.user,
            action_type='create',
            ip_address='system',
            user_agent='system',
            endpoint='/internal/profile',
            method='SYSTEM',
            data={'profile_type': 'student'}
        )


@receiver(post_save, sender=OwnerProfile)
def owner_profile_created(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            user=instance.user,
            action_type='create',
            ip_address='system',
            user_agent='system',
            endpoint='/internal/profile',
            method='SYSTEM',
            data={'profile_type': 'owner'}
        )