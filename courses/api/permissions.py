from rest_framework.permissions import BasePermission


class IsEnrolled(BasePermission):
    """
    Custom permission to check if the user is enrolled in the course.
    """

    def has_object_permission(self, request, view, obj):
        # Check if the user is enrolled in the course
        return obj.students.filter(id=request.user.id).exists()
