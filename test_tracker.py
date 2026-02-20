#!/usr/bin/env python
"""
Location Tracker Testing Script
Tests distance calculation accuracy, time tracking, and real-time features
"""

import os
import sys
import django
import json
import time
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'locatracker.settings')
django.setup()

from tracking.models import TrackingSession
from tracking.consumers import TrackingConsumer
from django.contrib.auth.models import User
from django.utils import timezone
from django.test import TestCase


class LocationTrackerTester:
    def __init__(self):
        self.consumer = TrackingConsumer()
        self.test_user = User.objects.get(username='testuser')

    def test_distance_calculation(self):
        """Test Haversine distance calculation accuracy"""
        print("🧪 Testing Distance Calculation...")

        # Test cases with known distances
        test_cases = [
            # Delhi to Mumbai (approx 1400km) - corrected coordinates
            {"from": [28.6139, 77.2090], "to": [19.0760, 72.8777], "expected_km": 1150, "tolerance": 100},  # More realistic expectation
            # Short distance (100m)
            {"from": [28.6139, 77.2090], "to": [28.6148, 77.2090], "expected_km": 0.1, "tolerance": 0.01},
            # Medium distance (10km)
            {"from": [28.6139, 77.2090], "to": [28.7039, 77.2090], "expected_km": 10, "tolerance": 1},
        ]

        for i, case in enumerate(test_cases):
            lat1, lng1 = case["from"]
            lat2, lng2 = case["to"]
            expected = case["expected_km"]
            tolerance = case["tolerance"]

            calculated = self.consumer.haversine(lat1, lng1, lat2, lng2) / 1000  # Convert to km

            if abs(calculated - expected) <= tolerance:
                print(f"  ✅ Test {i+1}: {calculated:.2f}km (expected: {expected}km) - PASS")
            else:
                print(f"  ❌ Test {i+1}: {calculated:.2f}km (expected: {expected}km) - FAIL")

    def test_session_creation(self):
        """Test session creation and basic functionality"""
        print("\n🧪 Testing Session Creation...")

        # Create a test session
        session = TrackingSession.objects.create(
            user=self.test_user,
            mode="walk",
            started_at=timezone.now()
        )

        print(f"  ✅ Session created: {session.id}")

        # Test location saving using the sync helper method
        now = timezone.now()
        self.consumer.save_location_sync(session, 28.6139, 77.2090, "walk", now.isoformat())

        session.refresh_from_db()
        if len(session.locations) == 1:
            print("  ✅ Location saved successfully")
        else:
            print(f"  ❌ Location save failed: {len(session.locations)} locations")

        # Clean up
        session.delete()
        print("  ✅ Test session cleaned up")

    def test_minimum_distance_filtering(self):
        """Test that minimum distance filtering works"""
        print("\n🧪 Testing Minimum Distance Filtering...")

        session = TrackingSession.objects.create(
            user=self.test_user,
            mode="walk",
            started_at=timezone.now()
        )

        base_time = timezone.now()

        # Add first point
        self.consumer.save_location_sync(session, 28.6139, 77.2090, "walk", base_time.isoformat())

        # Try to add very close points (should be filtered)
        close_points = [
            (28.6139001, 77.2090001, "walk"),  # ~0.01m away - should be filtered
        ]

        for lat, lng, mode in close_points:
            self.consumer.save_location_sync(session, lat, lng, mode, (base_time + timedelta(seconds=1)).isoformat())

        # Add a point that's far enough (should be saved)
        self.consumer.save_location_sync(session, 28.6140, 77.2090, "walk", (base_time + timedelta(seconds=2)).isoformat())  # ~11m away

        session.refresh_from_db()

        # Should have 2 locations (first one + the far one), close one filtered
        if len(session.locations) == 2:
            print("  ✅ Minimum distance filtering working (walk mode: 1m)")
        else:
            print(f"  ❌ Filtering failed: {len(session.locations)} locations saved (expected: 2)")

        session.delete()

    def test_time_calculation(self):
        """Test time calculation accuracy"""
        print("\n🧪 Testing Time Calculation...")

        session = TrackingSession.objects.create(
            user=self.test_user,
            started_at=timezone.now(),
            mode="walk"
        )

        base_time = timezone.now()

        # Add locations with time gaps - make sure they're far enough apart
        locations = [
            (28.6139, 77.2090, base_time),                                    # Point 1
            (28.6140, 77.2090, base_time + timedelta(seconds=30)),          # Point 2: 30s later, ~11m away
            (28.6150, 77.2090, base_time + timedelta(seconds=60)),          # Point 3: 60s later, ~111m away
        ]

        for lat, lng, timestamp in locations:
            self.consumer.save_location_sync(session, lat, lng, "walk", timestamp.isoformat())

        session.refresh_from_db()

        # Expected time: 60 seconds (from first to last location)
        expected_time = 60.0
        if abs(session.total_time - expected_time) < 2:  # Allow 2 second tolerance
            print(f"  ✅ Time calculation accurate: {session.total_time}s (expected: {expected_time}s)")
        else:
            print(f"  ❌ Time calculation error: {session.total_time}s (expected: {expected_time}s)")

        session.delete()

    def test_batch_processing(self):
        """Test batch location processing"""
        print("\n🧪 Testing Batch Processing...")

        session = TrackingSession.objects.create(
            user=self.test_user,
            started_at=timezone.now()
        )

        # Create batch data
        base_time = timezone.now()
        batch_data = [
            {"lat": 28.6139, "lng": 77.2090, "mode": "walk", "time": base_time.isoformat()},
            {"lat": 28.6140, "lng": 77.2090, "mode": "walk", "time": (base_time + timedelta(seconds=10)).isoformat()},
            {"lat": 28.6150, "lng": 77.2090, "mode": "walk", "time": (base_time + timedelta(seconds=20)).isoformat()},
        ]

        # Process batch using sync method
        for loc in batch_data:
            self.consumer.save_location_sync(session, loc["lat"], loc["lng"], loc["mode"], loc["time"])

        session.refresh_from_db()

        if len(session.locations) >= 2:  # Should have at least 2 points
            print(f"  ✅ Batch processing working: {len(session.locations)} locations saved")
        else:
            print(f"  ❌ Batch processing failed: {len(session.locations)} locations saved")

        session.delete()

    def test_mode_specific_settings(self):
        """Test that different modes have different filtering"""
        print("\n🧪 Testing Mode-Specific Settings...")

        modes = ["walk", "bike", "car"]
        results = {}

        for mode in modes:
            session = TrackingSession.objects.create(
                user=self.test_user,
                mode=mode,
                started_at=timezone.now()
            )

            base_time = timezone.now()

            # Add first point
            self.consumer.save_location_sync(session, 28.6139, 77.2090, mode, base_time.isoformat())

            # Try to add close points (should be filtered based on mode)
            if mode == "walk":
                # For walk, 1m should be filtered
                self.consumer.save_location_sync(session, 28.61391, 77.2090, mode, (base_time + timedelta(seconds=1)).isoformat())
                # Add valid point
                self.consumer.save_location_sync(session, 28.6140, 77.2090, mode, (base_time + timedelta(seconds=2)).isoformat())
            elif mode == "bike":
                # For bike, 2m should be filtered
                self.consumer.save_location_sync(session, 28.61392, 77.2090, mode, (base_time + timedelta(seconds=1)).isoformat())
                # Add valid point
                self.consumer.save_location_sync(session, 28.6140, 77.2090, mode, (base_time + timedelta(seconds=2)).isoformat())
            elif mode == "car":
                # For car, 5m should be filtered
                self.consumer.save_location_sync(session, 28.61395, 77.2090, mode, (base_time + timedelta(seconds=1)).isoformat())
                # Add valid point
                self.consumer.save_location_sync(session, 28.6140, 77.2090, mode, (base_time + timedelta(seconds=2)).isoformat())

            session.refresh_from_db()
            results[mode] = len(session.locations)
            session.delete()

        # Check results - each should have 2 points (first + valid one)
        expected = {"walk": 2, "bike": 2, "car": 2}
        if results == expected:
            print("  ✅ Mode-specific filtering working correctly")
        else:
            print(f"  ❌ Mode filtering failed: {results} (expected: {expected})")

    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Location Tracker Tests\n")
        print("=" * 50)

        self.test_distance_calculation()
        self.test_session_creation()
        self.test_minimum_distance_filtering()
        self.test_time_calculation()
        self.test_batch_processing()
        self.test_mode_specific_settings()

        print("\n" + "=" * 50)
        print("✅ All automated tests completed!")
        print("\n📋 Next: Test manually in browser")


if __name__ == "__main__":
    tester = LocationTrackerTester()
    tester.run_all_tests()