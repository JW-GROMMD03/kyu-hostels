from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from .models import Booking, Commission
from .serializers import BookingSerializer, CommissionSerializer
from apps.notifications.tasks import send_booking_notifications, expire_booking_task
from apps.payments.models import PaymentConfirmation
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsStudent, IsOwner, IsAdmin

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsStudent()]
        elif self.action in ['confirm_payment', 'emergency_contact']:
            return [IsAuthenticated()]
        elif self.action == 'mark_commission_paid':
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]
    
    def create(self, request, *args, **kwargs):
        hostel_id = request.data.get('hostel_id')
        
        # Check if hostel is available
        from apps.hostels.models import Hostel
        hostel = Hostel.objects.get(id=hostel_id)
        
        if not hostel.is_available or hostel.is_reserved:
            return Response(
                {'error': 'Hostel is not available for booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create booking
        booking = Booking.objects.create(
            student=request.user,
            hostel=hostel,
            commission_amount=hostel.rent * 0.1,  # 10% commission
            status='reserved'
        )
        
        # Mark hostel as reserved
        hostel.is_reserved = True
        hostel.reserved_until = timezone.now() + timedelta(hours=1)
        hostel.save()
        
        # Share student phone with owner (encrypted)
        owner = hostel.owner.user
        # In production, encrypt this
        booking.student_phone_shared = True
        booking.save()
        
        # Send notifications
        send_booking_notifications.delay(booking.id)
        
        # Schedule expiration task
        expire_booking_task.apply_async(
            args=[booking.id],
            eta=timezone.now() + timedelta(hours=1)
        )
        
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None):
        booking = self.get_object()
        
        if booking.student != request.user and not request.user.is_admin:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Record payment confirmation
        PaymentConfirmation.objects.create(
            booking=booking,
            student=request.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        booking.payment_confirmed_by_student = True
        booking.save()
        
        # Notify admin
        from apps.notifications.tasks import notify_admin_payment_confirmed
        notify_admin_payment_confirmed.delay(booking.id)
        
        return Response({'status': 'payment confirmed'})
    
    @action(detail=True, methods=['post'])
    def emergency_contact(self, request, pk=None):
        booking = self.get_object()
        
        if booking.student != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        booking.emergency_contact_used = True
        booking.emergency_contact_time = timezone.now()
        booking.save()
        
        # Send emergency notification
        from apps.notifications.tasks import send_emergency_notification
        send_emergency_notification.delay(booking.id)
        
        return Response({'status': 'emergency contact notified'})
    
    @action(detail=True, methods=['post'])
    def mark_commission_paid(self, request, pk=None):
        booking = self.get_object()
        
        if not request.user.is_admin:
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        
        booking.commission_paid = True
        booking.commission_paid_by_admin = True
        booking.save()
        
        # Update owner's commission record
        owner = booking.hostel.owner
        owner.commission_paid += booking.commission_amount
        owner.save()
        
        # Create commission record
        Commission.objects.create(
            booking=booking,
            amount=booking.commission_amount,
            is_paid=True,
            paid_by=request.user,
            paid_at=timezone.now(),
            payment_method=request.data.get('payment_method', 'cash'),
            transaction_id=request.data.get('transaction_id', '')
        )
        
        return Response({'status': 'commission marked as paid'})