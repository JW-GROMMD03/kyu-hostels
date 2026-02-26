import json
from django.utils import timezone
from django.http import JsonResponse
from django.core.cache import cache
from django.db.models import Q
from .models import BlockedIP, AuditLog
from django.contrib.auth.models import AnonymousUser


class IPBlockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Check if IP is blocked
        blocked = BlockedIP.objects.filter(
            ip_address=ip
        ).filter(
            Q(is_permanent=True) | Q(expires_at__gt=timezone.now())
        ).first()
        
        if blocked:
            return JsonResponse({
                'error': 'Access denied',
                'reason': blocked.reason,
                'blocked_until': blocked.expires_at
            }, status=403)
        
        # Store IP in request for later use
        request.client_ip = ip
        
        response = self.get_response(request)
        return response


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Log important actions
        if request.method in ['POST', 'PUT', 'DELETE'] and not isinstance(request.user, AnonymousUser):
            if not request.path.startswith('/api/admin/audit-logs'):  # Avoid recursion
                try:
                    # Get request data (sanitize sensitive info)
                    data = {}
                    if request.method == 'POST':
                        if hasattr(request, 'data'):
                            data = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)
                        else:
                            data = dict(request.POST)
                        
                        # Remove sensitive fields
                        sensitive_fields = ['password', 'password_confirm', 'token', 'otp_code', 
                                          'old_password', 'new_password', 'new_password_confirm']
                        for field in sensitive_fields:
                            if field in data:
                                data[field] = '[REDACTED]'
                    
                    AuditLog.objects.create(
                        user=request.user if not isinstance(request.user, AnonymousUser) else None,
                        action_type='update' if request.method == 'PUT' else 'create' if request.method == 'POST' else 'delete',
                        ip_address=getattr(request, 'client_ip', request.META.get('REMOTE_ADDR')),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        endpoint=request.path,
                        method=request.method,
                        data=data
                    )
                except Exception as e:
                    # Log error but don't break the request
                    print(f"Audit log error: {e}")
        
        return response


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = {
            'api/auth/login': (5, 60),  # 5 requests per minute
            'api/auth/register': (3, 3600),  # 3 requests per hour
            'api/auth/verify-otp': (5, 60),
            'api/bookings/': (10, 3600),  # 10 bookings per hour
            'api/payments/': (5, 3600),  # 5 payment attempts per hour
        }
    
    def __call__(self, request):
        path = request.path
        ip = getattr(request, 'client_ip', request.META.get('REMOTE_ADDR'))
        
        # Check rate limits
        for endpoint, (limit, period) in self.rate_limits.items():
            if endpoint in path:
                cache_key = f'rate_limit_{ip}_{endpoint}'
                count = cache.get(cache_key, 0)
                
                if count >= limit:
                    return JsonResponse({
                        'error': 'Rate limit exceeded',
                        'retry_after': period
                    }, status=429)
                
                cache.set(cache_key, count + 1, timeout=period)
                break
        
        return self.get_response(request)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(self), microphone=(), camera=()'
        
        return response