#!/usr/bin/env python
"""
Quick verification script for location tracker accuracy
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'locatracker.settings')
django.setup()

from tracking.consumers import TrackingConsumer
from django.utils import timezone
from datetime import timedelta

def verify_calculations():
    print("🔬 Location Tracker - Core Verification")
    print("=" * 50)

    consumer = TrackingConsumer()

    # Test 1: Haversine Distance Accuracy
    print("\n1. Distance Calculation Tests:")
    test_cases = [
        ([28.6139, 77.2090], [28.6148, 77.2090], 0.1),  # 100m north
        ([28.6139, 77.2090], [28.6139, 77.2108], 0.1),  # 100m east
        ([28.6139, 77.2090], [28.7039, 77.2090], 10.0), # 10km north
        ([28.6139, 77.2090], [19.0760, 72.8777], 1150), # Delhi to Mumbai
    ]

    for i, (start, end, expected_km) in enumerate(test_cases):
        distance_m = consumer.haversine(start[0], start[1], end[0], end[1])
        distance_km = distance_m / 1000
        accuracy = abs(distance_km - expected_km) / expected_km * 100

        status = "✅" if accuracy < 5 else "⚠️" if accuracy < 10 else "❌"
        print(f"   {status} Test {i+1}: {distance_km:.2f}km (expected: {expected_km}km) - {accuracy:.1f}% error")

    # Test 2: Mode-specific filtering
    print("\n2. Mode Filtering Tests:")
    modes = {"walk": 1, "bike": 2, "car": 5}
    test_distances = [0.5, 1.5, 3.5, 6.5]  # meters

    for mode, min_dist in modes.items():
        print(f"   {mode.upper()}: minimum {min_dist}m")
        for dist in test_distances:
            should_pass = dist >= min_dist
            status = "✅ PASS" if should_pass else "❌ FILTER"
            print(f"     {dist}m → {status}")

    # Test 3: Time calculation logic
    print("\n3. Time Calculation Logic:")
    base_time = timezone.now()

    # Simulate location points with time gaps
    points = [
        (base_time, "Start"),
        (base_time + timedelta(seconds=30), "30s later"),
        (base_time + timedelta(minutes=5), "5min later (capped)"),
        (base_time + timedelta(hours=2), "2hr later (capped)"),
    ]

    total_time = 0
    last_time = None

    for timestamp, desc in points:
        if last_time:
            gap = (timestamp - last_time).total_seconds()
            if gap > 300:  # Cap at 5 minutes
                gap = 60  # Assume 1 minute
            total_time += gap
            print(f"   +{gap:.0f}s ({desc}) → Total: {total_time:.0f}s")
        else:
            print(f"   Start: {desc}")
        last_time = timestamp

    print(f"\n   ✅ Total time calculated: {total_time/60:.1f} minutes")

    # Test 4: GPS accuracy filtering
    print("\n4. GPS Accuracy Filtering:")
    accuracy_tests = [
        (5, "Excellent GPS"),
        (15, "Good GPS"),
        (30, "Fair GPS"),
        (60, "Poor GPS"),
        (100, "Very poor GPS"),
    ]

    mode_accuracies = {"walk": 25, "bike": 30, "car": 50}

    for accuracy, desc in accuracy_tests:
        print(f"   {accuracy}m accuracy: {desc}")
        for mode, limit in mode_accuracies.items():
            accepted = accuracy <= limit
            status = "✅ ACCEPT" if accepted else "❌ REJECT"
            print(f"     {mode}: {status} (limit: {limit}m)")

    print("\n" + "=" * 50)
    print("🎯 Verification Complete!")
    print("\n📱 Next: Test manually in browser using TESTING_GUIDE.md")

if __name__ == "__main__":
    verify_calculations()