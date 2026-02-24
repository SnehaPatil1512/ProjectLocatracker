from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import TrackingSession
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout
from django.conf import settings
import requests
import json
import time


@login_required(login_url='/accounts/login/')
def tracking_page(request):
    if request.user.is_superuser:
        return redirect('/admin/')  
    return render(request, 'tracking/index.html')

def home(request):
    if request.user.is_authenticated:
        return redirect('tracking_page')
    return render(request, 'tracking/home.html')

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def start_tracking(request):
    if request.user.is_superuser:
        return JsonResponse({"error": "Superusers cannot start tracking"}, status=403)

    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=400)
    
    session = TrackingSession.objects.create(
        user=request.user,
        started_at=timezone.now()
    )

    return JsonResponse({"session_id": session.id})


@login_required
def get_route(request):
    """Proxy endpoint for OpenRouteService API to hide API key"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        coordinates = data.get('coordinates')
        profile = data.get('profile', 'driving-car')

        if not coordinates or len(coordinates) != 2:
            return JsonResponse({'error': 'Invalid coordinates'}, status=400)

        # Create cache key for route
        cache_key = f"route_{profile}_{coordinates[0][0]}_{coordinates[0][1]}_{coordinates[1][0]}_{coordinates[1][1]}"

        # Simple in-memory cache with timestamp
        if hasattr(get_route, '_cache') and cache_key in get_route._cache:
            cached_data = get_route._cache[cache_key]
            if time.time() - cached_data['timestamp'] < 3600:  # Cache for 1 hour
                return JsonResponse(cached_data['data'])

        # Call ORS API with server-side key
        ors_url = f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
        headers = {
            "Authorization": settings.ORS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {"coordinates": coordinates}

        response = requests.post(ors_url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            route_data = response.json()

            # Cache the result
            if not hasattr(get_route, '_cache'):
                get_route._cache = {}
            get_route._cache[cache_key] = {
                'data': route_data,
                'timestamp': time.time()
            }

            # Limit cache size
            if len(get_route._cache) > 100:
                oldest_key = min(get_route._cache.keys(),
                               key=lambda k: get_route._cache[k]['timestamp'])
                del get_route._cache[oldest_key]

            return JsonResponse(route_data)
        else:
            return JsonResponse({'error': 'Routing service error'}, status=response.status_code)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except requests.RequestException:
        return JsonResponse({'error': 'Service unavailable'}, status=503)


@login_required
def stop_tracking(request, session_id):
    try:
        session = TrackingSession.objects.get(id=session_id, user=request.user)

        now = timezone.now()

        # Calculate total session duration (from start to stop)
        if session.started_at:
            total_session_time = (now - session.started_at).total_seconds()
            # Only update total_time if it's less than session duration
            # (handles cases where tracking was paused/stopped)
            if total_session_time > session.total_time:
                session.total_time = total_session_time

        # Ensure final time calculation from last location
        if session.last_timestamp and session.last_timestamp < now:
            final_gap = (now - session.last_timestamp).total_seconds()
            # Only add if it's a reasonable gap (less than 10 minutes)
            if final_gap > 0 and final_gap < 600:
                session.total_time += final_gap

        session.ended_at = now
        session.save()

        return JsonResponse({
            "status": "stopped",
            "total_distance_km": round(session.total_distance / 1000, 2),
            "total_time_hours": round(session.total_time / 3600, 2),
            "average_speed_kmh": round((session.total_distance / 1000) / (session.total_time / 3600), 2) if session.total_time > 0 else 0
        })

    except TrackingSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)



# ---------------- Admin Map View ----------------
@login_required
def session_map(request, session_id):
    session = get_object_or_404(TrackingSession, id=session_id)

    # Security: Only allow users to view their own sessions (or admins)
    if not request.user.is_superuser and session.user != request.user:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    # Get start location (first location if available)
    start_lat = None
    start_lng = None
    if session.locations and len(session.locations) > 0:
        start_lat = session.locations[0].get('lat')
        start_lng = session.locations[0].get('lng')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            "session_id": session.id,
            "locations": session.locations,
            "user": session.user.username,
            "total_distance": session.total_distance,
            "total_time": session.total_time,
            "start_lat": start_lat,
            "start_lng": start_lng,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None
        })

    return render(request, "tracking/session_map.html", {
        "session": session,
        "locations": session.locations,
        "start_lat": start_lat,
        "start_lng": start_lng
    })
    

@login_required
def my_tracks(request):
    sessions = TrackingSession.objects.filter(
        user=request.user,
        ended_at__isnull=False
    ).order_by('-started_at')

    for s in sessions:
        s.distance_km = round(s.total_distance / 1000, 2)
        s.time_hours = round(s.total_time / 3600, 2)

    return render(request, "tracking/my_tracks.html", {
        "sessions": sessions
    })
    
@csrf_exempt
def logout_on_tab_close(request):
    if request.user.is_authenticated and request.user.is_staff:
        logout(request)
    return JsonResponse({"status": "logged out"})
