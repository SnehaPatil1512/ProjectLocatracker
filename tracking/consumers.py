# import json
# import math
# from channels.generic.websocket import AsyncWebsocketConsumer
# from channels.db import database_sync_to_async
# from .models import TrackingSession
# from django.utils import timezone
# from datetime import datetime
# from django.utils.dateparse import parse_datetime


# class TrackingConsumer(AsyncWebsocketConsumer):

#     async def connect(self):
#         user = self.scope["user"]
#         if not user.is_authenticated:
#             await self.close()
#             return

#         self.user = user
#         await self.accept()

#     async def disconnect(self, close_code):
#         print("WebSocket Closed")
        
#     def parse_timestamp(self, ts):
#         if not ts:
#             return timezone.now()

#         parsed = parse_datetime(ts)

#         if parsed is None:
#             return timezone.now()

#         if timezone.is_naive(parsed):
#             parsed = timezone.make_aware(parsed)

#         return parsed

#     async def receive(self, text_data):
#         try:
#             data = json.loads(text_data)
#             session_id = data.get("session_id")

#             session = await self.get_session(session_id)
#             if not session:
#                 return

#             if "locations" in data:
#                 await self.save_location_batch(session, data["locations"])
#             else:
#                 await self.save_location(
#                     session,
#                     data.get("lat"),
#                     data.get("lng"),
#                     data.get("mode", "bike"),
#                     data.get("timestamp")
#                 )

#         except Exception as e:
#             print("WebSocket receive error:", e)

#     # ---------------- DB HELPERS ----------------

#     @database_sync_to_async
#     def get_session(self, session_id):
#         try:
#             return TrackingSession.objects.get(
#                 id=session_id,
#                 user=self.user 
#             )
#         except TrackingSession.DoesNotExist:
#             return None

#     # ---------------- DISTANCE FORMULA ----------------

#     def haversine(self, lat1, lng1, lat2, lng2):
#         R = 6371000  

#         lat1 = math.radians(lat1)
#         lng1 = math.radians(lng1)
#         lat2 = math.radians(lat2)
#         lng2 = math.radians(lng2)

#         dlat = lat2 - lat1
#         dlng = lng2 - lng1
        

#         a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
#         return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

#     # ---------------- SINGLE POINT SAVE ----------------

#     @database_sync_to_async
#     def save_location(self, session, lat, lng, mode="bike", timestamp=None):

#         try:
#             lat = float(lat)
#             lng = float(lng)
#         except:
#             return

#         try:
#             if timestamp:
#                 timestamp = self.parse_timestamp(timestamp)
#             else:
#                 timestamp = timezone.now()
#         except:
#             timestamp = timezone.now()

#         if session.last_lat == lat and session.last_lng == lng:
#             return

#         # Calculate distance from last point
#         distance_increment = 0
#         if session.last_lat is not None and session.last_lng is not None:
#             distance_increment = self.haversine(session.last_lat, session.last_lng, lat, lng)

#             min_distance = {"walk": 8, "bike": 12, "car": 25}.get(mode, 2)
#             if distance_increment < min_distance:
#                 return

 
#         time_increment = 0
#         if session.last_timestamp:
#             time_increment = (timestamp - session.last_timestamp).total_seconds()

#             if time_increment < 0:
#                 return
     
#             if time_increment > 300:
#                 time_increment = 60  

#         # Update totals
#         session.total_distance += distance_increment
#         session.total_time += time_increment

#         # Store location data
#         locations = session.locations or []
#         locations.append({
#             "lat": lat,
#             "lng": lng,
#             "mode": mode,
#             "timestamp": str(timestamp),
#             "distance_increment": distance_increment,
#             "time_increment": time_increment
#         })
#         session.locations = locations   

#         # Update last position
#         session.last_lat = lat
#         session.last_lng = lng
#         session.last_timestamp = timestamp

#         session.save()

#     # ---------------- BATCH SAVE ----------------

#     @database_sync_to_async
#     def save_location_batch(self, session, points):
#         for loc in points:
#             try:
#                 lat = float(loc.get("lat"))
#                 lng = float(loc.get("lng"))
#                 mode = loc.get("mode", "bike")
#                 timestamp = loc.get("timestamp")

#                 self.save_location_sync(session, lat, lng, mode, timestamp)

#             except:
#                 continue

#         session.save()

#     # Helper for batch
#     def save_location_sync(self, session, lat, lng, mode, timestamp):

#         try:
#             if timestamp:
#                 timestamp = self.parse_timestamp(timestamp)
#             else:
#                 timestamp = timezone.now()
#         except:
#             timestamp = timezone.now()

#         if session.last_lat == lat and session.last_lng == lng:
#             return

#         distance_increment = 0
#         if session.last_lat is not None and session.last_lng is not None:
#             distance_increment = self.haversine(session.last_lat, session.last_lng, lat, lng)

#             min_distance = {"walk": 8, "bike": 12, "car": 25}.get(mode, 2)
#             if distance_increment < min_distance:
#                 return

#         time_increment = 0
#         if session.last_timestamp:
#             time_increment = (timestamp - session.last_timestamp).total_seconds()
#             if time_increment < 0:
#                 return

#             if time_increment > 300:
#                 time_increment = 60  

#         # Update totals
#         session.total_distance += distance_increment
#         session.total_time += time_increment

#         # Store location data
#         locations = session.locations or []
#         locations.append({
#             "lat": lat,
#             "lng": lng,
#             "mode": mode,
#             "timestamp": str(timestamp),
#             "distance_increment": distance_increment,
#             "time_increment": time_increment
#         })
#         session.locations = locations

#         # Update last position
#         session.last_lat = lat
#         session.last_lng = lng
#         session.last_timestamp = timestamp


import json
import math
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import TrackingSession
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.contrib.auth.models import User

class TrackingConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return

        self.user = user
        await self.accept()

    async def disconnect(self, close_code):
        print("WebSocket Closed")


    def parse_timestamp(self, ts):
        if not ts:
            return timezone.now()

        parsed = parse_datetime(ts)

        if parsed is None:
            return timezone.now()

        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)

        return parsed


    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            session_id = data.get("session_id")

            session = await self.get_session(session_id)
            if not session:
                return

            if "locations" in data:
                await self.save_location_batch(session, data["locations"])
            else:
                await self.save_location(
                    session,
                    data.get("lat"),
                    data.get("lng"),
                    data.get("mode", "bike"),
                    data.get("timestamp")
                )

        except Exception as e:
            print("WebSocket receive error:", e)


    @database_sync_to_async
    def get_session(self, session_id):
        try:
            return TrackingSession.objects.get(
                id=session_id,
                user=self.user
            )
        except TrackingSession.DoesNotExist:
            return None



    def haversine(self, lat1, lng1, lat2, lng2):
        R = 6371000  # meters

        lat1, lng1, lat2, lng2 = map(
            math.radians, [lat1, lng1, lat2, lng2]
        )

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1)
            * math.cos(lat2)
            * math.sin(dlng / 2) ** 2
        )

        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


    def process_point(self, session, lat, lng, mode="bike", timestamp=None):

        try:
            lat = float(lat)
            lng = float(lng)
        except:
            return False

        timestamp = self.parse_timestamp(timestamp)

        # Ignore exact duplicate
        if session.last_lat == lat and session.last_lng == lng:
            return False

        distance_increment = 0
        time_increment = 0

        # Distance
        if session.last_lat is not None and session.last_lng is not None:
            distance_increment = self.haversine(
                session.last_lat,
                session.last_lng,
                lat,
                lng
            )

            min_distance = {
                "walk": 8,
                "bike": 12,
                "car": 25
            }.get(mode, 2)

            if distance_increment < min_distance:
                return False

        # Time
        if session.last_timestamp:
            time_increment = (
                timestamp - session.last_timestamp
            ).total_seconds()

            if time_increment < 0:
                return False

            # Cap unrealistic time jumps
            if time_increment > 300:
                time_increment = 60

        session.total_distance += distance_increment
        session.total_time += time_increment

        locations = session.locations or []
        locations.append({
            "lat": lat,
            "lng": lng,
            "mode": mode,
            "timestamp": str(timestamp),
            "distance_increment": distance_increment,
            "time_increment": time_increment
        })
        session.locations = locations

        session.last_lat = lat
        session.last_lng = lng
        session.last_timestamp = timestamp

        return True


    @database_sync_to_async
    def save_location(self, session, lat, lng, mode="bike", timestamp=None):
        updated = self.process_point(
            session, lat, lng, mode, timestamp
        )

        if updated:
            session.save()


    @database_sync_to_async
    def save_location_batch(self, session, points):
        updated = False

        for loc in points:
            try:
                result = self.process_point(
                    session,
                    loc.get("lat"),
                    loc.get("lng"),
                    loc.get("mode", "bike"),
                    loc.get("timestamp")
                )

                if result:
                    updated = True

            except:
                continue

        if updated:
            session.save()