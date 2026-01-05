from django.db import models
from ckeditor.fields import RichTextField


class StaticPage(models.Model):
    """
    Modelo para páginas estáticas editables (FAQ, Sobre nosotros, etc.)
    Los admins pueden editar el contenido HTML a través del Django admin.
    """
    CATEGORY_CHOICES = [
        ('informacion', 'Información'),
        ('politicas', 'Políticas'),
        ('recursos', 'Recursos'),
        ('otros', 'Otros'),
    ]
    
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='informacion',
        help_text="Categoría para el menú"
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Identificador único para la URL (ej: 'faq', 'sobre-nosotros')"
    )
    title = models.CharField(
        max_length=200,
        help_text="Título de la página que se mostrará en la interfaz"
    )
    content = RichTextField(
        help_text="Contenido de la página con editor visual WYSIWYG"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Página Estática"
        verbose_name_plural = "Páginas Estáticas"
        ordering = ['category', 'title']

    def __str__(self):
        return self.title
