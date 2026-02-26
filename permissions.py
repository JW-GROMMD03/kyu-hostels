from rest_framework import permissions


class IsStudent(permissions.BasePermission):
    """
    Allows access only to students.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'student_profile')


class IsOwner(permissions.BasePermission):
    """
    Allows access only to hostel owners.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'owner_profile')


class IsVerifiedOwner(permissions.BasePermission):
    """
    Allows access only to approved owners.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not hasattr(request.user, 'owner_profile'):
            return False
        return request.user.owner_profile.is_approved


class IsAdmin(permissions.BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        return obj.owner.user == request.user


class IsStudentOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow students to create bookings/reviews.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return hasattr(request.user, 'student_profile')


class HasVerifiedPhone(permissions.BasePermission):
    """
    Allows access only to users with verified phone numbers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_phone_verified