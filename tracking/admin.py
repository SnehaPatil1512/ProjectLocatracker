from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import TrackingSession


@admin.register(TrackingSession)
class TrackingSessionAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "mode",
        "started_at",
        "ended_at",
        "formatted_distance",
        "formatted_time",
        "view_map",
    )
    
    search_fields = ("user__username",)
    ordering = ("-started_at",)

    readonly_fields = (
        "user",
        "mode",
        "started_at",
        "ended_at",
        "formatted_distance",
        "formatted_time",
        "locations",
    )
    
    fields = (
        "user",
        "mode",
        "started_at",
        "ended_at",
        "formatted_distance",
        "formatted_time",
        "locations",
    )

    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.exclude(user__is_superuser=True)

    def view_map(self, obj):
        return format_html(
            '<a href="/session-map/{0}/" target="_blank">View Map</a>',
            obj.id
        )
    view_map.short_description = "Tracked Path"
    
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


    def formatted_distance(self, obj):
        if not obj.total_distance:
            return "0 KM"

        km = obj.total_distance / 1000
        return f"{km:.2f} KM"

    formatted_distance.short_description = "Total Distance"


    def formatted_time(self, obj):
        if not obj.total_time:
            return "00:00:00"

        total_seconds = int(obj.total_time)

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return f"{hours:02}:{minutes:02}:{seconds:02}"

    formatted_time.short_description = "Total Time"

