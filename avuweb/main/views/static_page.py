from django.shortcuts import render, get_object_or_404
from html import unescape
from avuweb.main.models import StaticPage


def static_page(request, slug):
    """Vista para renderizar páginas estáticas por slug."""
    page = get_object_or_404(StaticPage, slug=slug)
    page.content = unescape(page.content)
    return render(request, 'main/static_page.html', {'page': page})
