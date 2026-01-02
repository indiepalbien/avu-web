from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def profile(request):
    """Display the user's profile page."""
    return render(request, "main/profile.html")
