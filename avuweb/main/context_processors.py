from avuweb.main.models import StaticPage
from django.db.models import Q
from itertools import groupby


def static_pages(request):
    """Context processor que agrega páginas estáticas agrupadas por categoría."""
    pages = StaticPage.objects.all().order_by('category', 'title')
    
    # Agrupar por categoría
    grouped_pages = {}
    for category, pages_in_category in groupby(pages, key=lambda p: p.get_category_display()):
        grouped_pages[category] = list(pages_in_category)
    
    return {
        'static_pages': StaticPage.objects.all().order_by('category', 'title'),
        'static_pages_by_category': grouped_pages,
    }
