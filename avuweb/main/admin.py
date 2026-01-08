from django.contrib import admin
from avuweb.main.models import UserProfile, StaticPage, Subscription, CouponCode, SubscriptionEvent


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


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'amount', 'payment_frequency', 'last_payment_date', 'next_payment_date')
    list_filter = ('status', 'payment_frequency', 'created_at', 'last_synced_at')
    search_fields = ('user__email', 'mercado_pago_subscription_id')
    readonly_fields = ('mercado_pago_subscription_id', 'mercado_pago_updated_at', 'created_at', 'last_synced_at')

    fieldsets = (
        ('Usuario', {
            'fields': ('user',)
        }),
        ('Mercado Pago', {
            'fields': ('mercado_pago_subscription_id', 'preapproval_id', 'mercado_pago_updated_at')
        }),
        ('Detalles de Pago', {
            'fields': ('status', 'payment_frequency', 'amount')
        }),
        ('Fechas', {
            'fields': ('last_payment_date', 'next_payment_date', 'created_at', 'last_synced_at')
        }),
        ('Reintentos', {
            'fields': ('failed_payment_count',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return False


@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_used', 'user', 'expires_at', 'created_by', 'created_at')
    list_filter = ('is_used', 'expires_at', 'created_at')
    search_fields = ('code', 'user__email')
    readonly_fields = ('code', 'created_at', 'used_at')

    fieldsets = (
        ('Código', {
            'fields': ('code',)
        }),
        ('Uso', {
            'fields': ('user', 'is_used', 'used_at')
        }),
        ('Expiración', {
            'fields': ('expires_at',)
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'event_type', 'processed', 'created_at')
    list_filter = ('event_type', 'processed', 'created_at')
    search_fields = ('subscription__user__email', 'mercado_pago_event_id')
    readonly_fields = ('subscription', 'event_type', 'mercado_pago_event_id', 'payload', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

