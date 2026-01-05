from django.contrib import admin
from avuweb.main.models import UserProfile, StaticPage


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'full_name', 'created_at')
    list_filter = ('user_type', 'created_at')
    search_fields = ('user__email', 'full_name', 'identity_number', 'rut')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Usuario', {
            'fields': ('user',)
        }),
        ('Tipo de Usuario', {
            'fields': ('user_type',)
        }),
        ('Información General', {
            'fields': ('full_name', 'address')
        }),
        ('Socio', {
            'fields': ('identity_number', 'phone_number'),
            'classes': ('collapse',)
        }),
        ('Empresa', {
            'fields': ('rut',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StaticPage)
class StaticPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'slug', 'updated_at')
    list_filter = ('category', 'updated_at', 'created_at')
    search_fields = ('title', 'slug', 'content')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Información', {
            'fields': ('title', 'slug', 'category')
        }),
        ('Contenido', {
            'fields': ('content',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

