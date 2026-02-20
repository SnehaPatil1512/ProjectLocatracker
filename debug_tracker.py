#!/usr/bin/env python
"""
Debug script for location tracker
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'locatracker.settings')
django.setup()

from tracking.models import TrackingSession
from tracking.consumers import TrackingConsumer
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta

# Get or create test user (avoid DoesNotExist)
user, _ = User.objects.get_or_create(username='testuser')

# Create session
session = TrackingSession.objects.create(
    user=user,
    mode="walk",
    started_at=timezone.now()
)

consumer = TrackingConsumer()

print(f"Created session: {session.id}")
print(f"Initial last_lat: {session.last_lat}, last_lng: {session.last_lng}")

# Debug the save_location_sync method step by step
def debug_save_location_sync(session, lat, lng, mode, timestamp_str):
    print(f"\n--- Debug save_location_sync ---")
    print(f"Input: lat={lat}, lng={lng}, mode={mode}, timestamp={timestamp_str}")

    if timestamp_str:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    else:
        timestamp = timezone.now()
    print(f"Parsed timestamp: {timestamp}")

    # Skip if same as last location
    if session.last_lat == lat and session.last_lng == lng:
        print("❌ Same as last location, skipping")
        return

    print(f"session.last_lat: {session.last_lat}, session.last_lng: {session.last_lng}")

    # Calculate distance from last point
    distance_increment = 0
    if session.last_lat is not None and session.last_lng is not None:
        distance_increment = consumer.haversine(session.last_lat, session.last_lng, lat, lng)
        print(f"Distance from last point: {distance_increment}m")

        # Skip if too close to last location (adjust based on mode)
        min_distance = {"walk": 1, "bike": 2, "car": 5}.get(mode, 2)
        print(f"Min distance for {mode}: {min_distance}m")
        if distance_increment < min_distance:
            print(f"❌ Too close ({distance_increment}m < {min_distance}m), skipping")
            return
    else:
        print("First location (no previous point)")

    # Calculate time increment
    time_increment = 0
    if session.last_timestamp:
        time_increment = (timestamp - session.last_timestamp).total_seconds()
        print(f"Time from last point: {time_increment}s")
        # Skip if time went backwards (clock sync issues)
        if time_increment < 0:
            print("❌ Time went backwards, skipping")
            return
        # Cap maximum time gap (e.g., 5 minutes) to avoid huge jumps
        if time_increment > 300:
            time_increment = 60  # Assume 1 minute for long gaps
            print("Capped time gap to 60s")
    else:
        print("First location (no previous timestamp)")

    # Update totals
    session.total_distance += distance_increment
    session.total_time += time_increment
    print(f"Updated totals: distance={session.total_distance}, time={session.total_time}")

    # Store location data
    location_data = {
        "lat": lat,
        "lng": lng,
        "mode": mode,
        "time": str(timestamp),
        "distance_increment": distance_increment,
        "time_increment": time_increment
    }
    session.locations.append(location_data)
    print(f"Added location data: {location_data}")

    # Update last position
    session.last_lat = lat
    session.last_lng = lng
    session.last_timestamp = timestamp
    print(f"Updated last position: lat={lat}, lng={lng}, time={timestamp}")

    session.save()
    print("✅ Session saved")

# Try to save first location
print("\nSaving first location...")
debug_save_location_sync(session, 28.6139, 77.2090, "walk", timezone.now().isoformat())

session.refresh_from_db()
print(f"After save - locations count: {len(session.locations)}")
print(f"last_lat: {session.last_lat}, last_lng: {session.last_lng}")
print(f"total_distance: {session.total_distance}, total_time: {session.total_time}")

# Try to save second location (far enough away)
print("\nSaving second location...")
debug_save_location_sync(session, 28.6140, 77.2090, "walk", (timezone.now() + timedelta(seconds=10)).isoformat())

session.refresh_from_db()
print(f"After second save - locations count: {len(session.locations)}")
print(f"last_lat: {session.last_lat}, last_lng: {session.last_lng}")
print(f"total_distance: {session.total_distance}, total_time: {session.total_time}")

# Check what's in locations
print(f"\nLocations data: {session.locations}")

# Clean up
session.delete()
print("\nSession deleted")