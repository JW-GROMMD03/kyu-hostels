# backend/apps/notifications/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_email_task(subject, message, recipient_list):
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            fail_silently=False,
        )
        logger.info(f"Email sent to {recipient_list}")
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")

@shared_task
def send_sms_task(to_phone, message):
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to_phone
        )
        logger.info(f"SMS sent to {to_phone}")
    except Exception as e:
        logger.error(f"SMS sending failed: {str(e)}")

@shared_task
def send_sms_otp(phone_number, otp_code):
    message = f"Your Kirinyaga Hostels verification code is: {otp_code}. Valid for 10 minutes."
    send_sms_task.delay(phone_number, message)

@shared_task
def notify_owner_booking(booking_id):
    from apps.bookings.models import Booking
    
    try:
        booking = Booking.objects.select_related('hostel__owner', 'student').get(id=booking_id)
        
        # Send email
        subject = f"New Booking Request - {booking.hostel.name}"
        message = f"""
        A student has requested to book your hostel: {booking.hostel.name}
        
        Student Details:
        Name: {booking.student.user.get_full_name()}
        Phone: {booking.student.user.phone_number}
        Check-in: {booking.check_in_date}
        Duration: {booking.duration_months} months
        
        The booking is reserved for 1 hour. Please prepare for the student's visit.
        """
        
        send_email_task.delay(
            subject,
            message,
            [booking.hostel.owner.user.email]
        )
        
        # Send SMS
        sms_message = f"New booking for {booking.hostel.name}. Student: {booking.student.user.phone_number}"
        send_sms_task.delay(booking.hostel.owner.user.phone_number, sms_message)
        
    except Exception as e:
        logger.error(f"Owner notification failed: {str(e)}")

@shared_task
def notify_admin_booking(booking_id):
    from apps.bookings.models import Booking
    
    try:
        booking = Booking.objects.select_related('hostel', 'student').get(id=booking_id)
        
        # Send email to admin
        subject = f"New Booking Created - {booking.hostel.name}"
        message = f"""
        A new booking has been created:
        
        Student: {booking.student.user.email}
        Hostel: {booking.hostel.name}
        Owner: {booking.hostel.owner.business_name}
        Amount: KES {booking.total_amount}
        Commission: KES {booking.commission_amount}
        
        The booking is reserved until {booking.reserved_until}
        """
        
        send_email_task.delay(
            subject,
            message,
            [settings.ADMIN_EMAIL]
        )
        
    except Exception as e:
        logger.error(f"Admin notification failed: {str(e)}")

@shared_task
def start_booking_timer(booking_id):
    from apps.bookings.models import Booking
    
    try:
        booking = Booking.objects.get(id=booking_id)
        
        # Check if still reserved
        if booking.status == 'reserved':
            booking.expire_reservation()
            
            # Notify student
            subject = "Booking Expired"
            message = f"""
            Your booking for {booking.hostel.name} has expired because the 1-hour reservation period has ended.
            Please create a new booking if you're still interested.
            """
            
            send_email_task.delay(
                subject,
                message,
                [booking.student.user.email]
            )
            
    except Exception as e:
        logger.error(f"Booking timer failed: {str(e)}")

@shared_task
def notify_admin_payment_confirmation(payment_id):
    from apps.bookings.models import PaymentConfirmation
    
    try:
        payment = PaymentConfirmation.objects.select_related('booking').get(id=payment_id)
        
        subject = "Payment Confirmation Pending Verification"
        message = f"""
        A student has confirmed payment for booking:
        
        Booking ID: {payment.booking.id}
        Amount: KES {payment.amount}
        Method: {payment.payment_method}
        Transaction ID: {payment.transaction_id}
        
        Please verify and mark commission as paid.
        """
        
        send_email_task.delay(
            subject,
            message,
            [settings.ADMIN_EMAIL]
        )
        
    except Exception as e:
        logger.error(f"Payment notification failed: {str(e)}")

@shared_task
def notify_admin_review(review_id):
    from apps.bookings.models import Review
    
    try:
        review = Review.objects.select_related('student', 'hostel').get(id=review_id)
        
        subject = "New Review Pending Approval"
        message = f"""
        A new review has been submitted:
        
        Student: {review.student.user.email}
        Hostel: {review.hostel.name}
        Rating: {review.overall_rating}
        
        Please review and approve/reject.
        """
        
        send_email_task.delay(
            subject,
            message,
            [settings.ADMIN_EMAIL]
        )
        
    except Exception as e:
        logger.error(f"Review notification failed: {str(e)}")

@shared_task
def calculate_fraud_scores():
    """Background task to calculate fraud scores for all owners and hostels"""
    from apps.accounts.models import OwnerProfile
    from apps.hostels.models import Hostel
    
    # Update owner fraud scores
    for owner in OwnerProfile.objects.all():
        # Calculate based on various factors
        score = 0
        
        # Check for multiple rejected bookings
        rejected_bookings = owner.hostels.filter(bookings__status='cancelled').count()
        if rejected_bookings > 5:
            score += 20
        
        # Check for complaints
        complaints = owner.hostels.filter(reviews__reported_count__gt=3).count()
        if complaints > 2:
            score += 30
        
        # Check for payment fraud
        fraud_payments = owner.hostels.filter(
            bookings__paymentconfirmations__fraud_attempt=True
        ).count()
        if fraud_payments > 0:
            score += 40
        
        owner.fraud_score = min(score, 100)
        owner.save()
        
        # Update hostels
        for hostel in owner.hostels.all():
            hostel.calculate_fraud_score()
    
    logger.info("Fraud scores calculated")

@shared_task
def send_weekly_reports():
    """Send weekly reports to admin"""
    from django.db.models import Sum, Count
    from datetime import timedelta
    
    week_ago = timezone.now() - timedelta(days=7)
    
    # Calculate stats
    new_bookings = Booking.objects.filter(created_at__gte=week_ago).count()
    new_users = User.objects.filter(date_joined__gte=week_ago).count()
    revenue = Booking.objects.filter(
        paid_at__gte=week_ago,
        commission_paid=True
    ).aggregate(total=Sum('commission_amount'))['total'] or 0
    
    subject = "Weekly Report - Kirinyaga Hostels"
    message = f"""
    Weekly Statistics (Last 7 days):
    
    New Bookings: {new_bookings}
    New Users: {new_users}
    Revenue: KES {revenue}
    
    Total active hostels: {Hostel.objects.filter(is_available=True).count()}
    Pending owner approvals: {OwnerProfile.objects.filter(is_approved=False).count()}
    Pending review approvals: {Review.objects.filter(is_approved=False).count()}
    """
    
    send_email_task.delay(
        subject,
        message,
        [settings.ADMIN_EMAIL]
    )
    
    logger.info("Weekly report sent")