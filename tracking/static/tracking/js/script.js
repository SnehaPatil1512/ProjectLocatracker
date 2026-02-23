const modeSettings = {
  walk: { profile: "foot-walking", minMove: 8, routeDelay: 2000, accuracyLimit: 35, animationDelay: 80 },
  bike: { profile: "cycling-regular", minMove: 12, routeDelay: 1500, accuracyLimit: 40, animationDelay: 50 },
  car: { profile: "driving-car", minMove: 25, routeDelay: 1200, accuracyLimit: 60, animationDelay: 30 }
};

let trackingMode = "bike";
let watchId = null;
let isTracking = false;
let lastRouteTime = 0;
let isFetchingRoute = false;
let marker = null;
let lastPoint = null;
let animationToken = 0;

let sessionId = null;
let socket = null;

let locationBuffer = [];
let offlineBuffer = [];
let lastSentTime = 0;
let isOnline = navigator.onLine;
let reconnectAttempts = 0;
const MAX_RECONNECT = 5;

const MAX_BUFFER_SIZE = 10;

// ----------- IN-APP BROWSER DETECTION -----------
function isInAppBrowser() {
  const ua = navigator.userAgent || navigator.vendor || window.opera;
  // Common in-app browser signatures
  return (
    /FBAN|FBAV|Instagram|Line|Twitter|Snapchat|WhatsApp|Messenger|WeChat|MiuiBrowser|OPR\//i.test(ua)
    || (window.navigator.standalone === false && /iPhone|iPad|iPod/.test(ua))
  );
}

// ----------- HTTPS & GEOLOCATION CHECK -----------
function checkEnvironment() {
  // Allow localhost and 127.0.0.1 for development
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (!isLocal && window.location.protocol !== 'https:') {
    showStatus(' Please use HTTPS for location tracking.', 'warn', 10000);
    return false;
  }
  if (!('geolocation' in navigator)) {
    showStatus('Geolocation not supported in this browser.', 'error', 10000);
    return false;
  }
  if (isInAppBrowser()) {
    showStatus('Please open this page in Chrome or Safari, not inside another app.', 'warn', 10000);
    return false;
  }
  return true;
}

// ---------------- GPS PERMISSION CHECK ----------------
async function checkGPSPermission() {
  if ('permissions' in navigator) {
    try {
      const result = await navigator.permissions.query({name: 'geolocation'});
      return result.state;
    } catch (e) {
      return 'unknown';
    }
  }
  return 'unknown';
}


// ---------------- MAP ----------------
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const latEl = document.getElementById("lat");
const lngEl = document.getElementById("lng");
const accuracyEl = document.getElementById("accuracy");
const statusEl = document.getElementById("status");
const lockStatusEl = document.getElementById("lock-status");
const unlockBtn = document.getElementById("unlockBtn");

// ----------- STATUS/ERROR DISPLAY -----------
function showStatus(msg, type = 'info', timeout = 0) {
  if (!statusEl) return;
  statusEl.textContent = msg;
  statusEl.style.color = (type === 'error') ? 'red' : (type === 'warn' ? 'orange' : 'green');
  if (timeout > 0) setTimeout(() => { statusEl.textContent = ''; }, timeout);
}



const map = L.map('map').setView([28.6139, 77.2090], 15);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
const canvasRenderer = L.canvas();

const polyline = L.polyline([], { color: "blue", weight: 4, opacity: 0.8, renderer: canvasRenderer }).addTo(map);


function metersBetween(a, b) {
  const R = 6371000;
  const dLat = (b[0] - a[0]) * Math.PI / 180;
  const dLng = (b[1] - a[1]) * Math.PI / 180;
  const lat1 = a[0] * Math.PI / 180;
  const lat2 = b[0] * Math.PI / 180;
  const x = Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLng/2)**2;
  return 2 * R * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

const csrfToken = getCookie('csrftoken');


async function getRoute(from, to) {
  try {
    const response = await fetch('/tracking/get-route/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        coordinates: [[from[1], from[0]], [to[1], to[0]]],
        profile: modeSettings[trackingMode].profile
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    if (!data.features || !data.features[0]) return null;
    return data.features[0].geometry.coordinates.map(c => [c[1], c[0]]);
  } catch (error) {
    console.error('Route fetch error:', error);
    return null;
  }
}

function createSocket() {
  return new Promise((resolve, reject) => {
 
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${protocol}://${window.location.host}/ws/tracking/`;

    showStatus("Connecting to server...", 'info');
    socket = new WebSocket(wsUrl);

    const connectionTimeout = setTimeout(() => {
      socket.close();
      showStatus("WebSocket connection timeout", 'error', 8000);
      reject(new Error("WebSocket connection timeout"));
    }, 10000);

    socket.onopen = () => {
        clearTimeout(connectionTimeout);
        reconnectAttempts = 0;
        showStatus("WebSocket Connected", 'info', 2000);
        if (offlineBuffer.length > 0) {
            socket.send(JSON.stringify({
                session_id: sessionId,
                locations: offlineBuffer
            }));
            offlineBuffer = [];
        }
        resolve();
    };

    socket.onerror = (err) => {
      clearTimeout(connectionTimeout);
      showStatus("WebSocket Error: " + (err.message || err), 'error', 8000);
      reject(err);
    };

    socket.onclose = (event) => {
      showStatus("WebSocket Closed: " + event.reason, 'warn', 8000);

      if (event.code !== 1000 && isTracking && reconnectAttempts < MAX_RECONNECT) {
        reconnectAttempts++;
        showStatus(`Reconnecting (${reconnectAttempts}/5)...`, 'warn', 3000);

        setTimeout(() => {
          createSocket().catch(err =>
            showStatus("Reconnection failed: " + err, 'error', 8000)
          );
        }, 3000);
      }
    };
  });
}


window.addEventListener('online', () => {
  isOnline = true;
  showStatus('Back online - syncing offline data', 'info', 4000);
  // Send offline buffer first when back online
  if (offlineBuffer.length > 0 && socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({
      session_id: sessionId,
      locations: offlineBuffer
    }));
    offlineBuffer = [];
  }
});

window.addEventListener('offline', () => {
  isOnline = false;
  showStatus('Gone offline - buffering locations', 'warn', 4000);
});

function sendLocation(lat, lng, accuracy) {
    // Only send if accuracy is acceptable
    if (accuracy > modeSettings[trackingMode].accuracyLimit) {
        console.log("Low accuracy skipped:", accuracy);
        return;
    }

    const locationData = {
        lat: lat,
        lng: lng,
        mode: trackingMode,
        accuracy: accuracy,
        timestamp: new Date().toISOString()
    };

    if (isOnline && socket && socket.readyState === WebSocket.OPEN) {
        locationBuffer.push(locationData);

        const shouldSend = locationBuffer.length >= MAX_BUFFER_SIZE ||
                          (Date.now() - lastSentTime) > 20000; 

        if (shouldSend) {
            socket.send(JSON.stringify({
                session_id: sessionId,
                locations: locationBuffer
            }));
            locationBuffer = [];
            lastSentTime = Date.now();
        }
    } else {
        // Store in offline buffer
        offlineBuffer.push(locationData);
        if (offlineBuffer.length > 50) {
            offlineBuffer = offlineBuffer.slice(-25); 
        }
        console.log(`Offline: buffered ${offlineBuffer.length} locations`);
    }
}


// ---------------- ANIMATION ----------------
function animateMarker(route) {
  animationToken++;
  const currentToken = animationToken;
  let i = 0;

  function step() {
    if (!isTracking || currentToken !== animationToken || i >= route.length) return;
    const point = route[i];
    marker.setLatLng(point);
    polyline.addLatLng(point);
    latEl.textContent = point[0].toFixed(6);
    lngEl.textContent = point[1].toFixed(6);
    accuracyEl.textContent = "Route";
    map.panTo(point, { animate: true });
    // Removed sendLocation call - only send real GPS points, not animation points
    i++;
    setTimeout(step, modeSettings[trackingMode].animationDelay);
  }
  step();
}

// ---------------- GPS HANDLER ----------------
let lastValidPosition = null;
let positionHistory = [];
const MAX_POSITION_HISTORY = 5;

async function handlePosition(position) {
  if (!isTracking) return;

  const lat = position.coords.latitude;
  const lng = position.coords.longitude;
  const accuracy = position.coords.accuracy;

  if (accuracy > 2000) {
    showStatus(`Location accuracy too low (${accuracy.toFixed(0)}m). Try moving to a better spot.`, 'warn', 6000);
    console.log("Low accuracy skipped:", accuracy);
    return;
  }

  const newPoint = [lat, lng];

  if (!marker) {
    marker = L.marker(newPoint).addTo(map);
    map.setView(newPoint, 17);
    lastPoint = newPoint;
    lastValidPosition = newPoint;
    polyline.addLatLng(newPoint);
    latEl.textContent = lat.toFixed(6);
    lngEl.textContent = lng.toFixed(6);
    accuracyEl.textContent = accuracy.toFixed(1) + "m";
    sendLocation(lat, lng, accuracy);
    return;
  }

  // Simple distance check
  const distance = metersBetween(lastPoint, newPoint);
  if (distance < modeSettings[trackingMode].minMove) return;

  // Update position
  lastPoint = newPoint;
  lastRouteTime = Date.now();

  marker.setLatLng(newPoint);
  polyline.addLatLng(newPoint);
  map.panTo(newPoint);
  latEl.textContent = newPoint[0].toFixed(6);
  lngEl.textContent = newPoint[1].toFixed(6);
  accuracyEl.textContent = accuracy.toFixed(1) + "m";
  sendLocation(newPoint[0], newPoint[1], accuracy);
}

// ---------------- START / STOP ----------------

startBtn.onclick = async () => {
  if (isTracking) return;
  startBtn.disabled = true;

  if (!checkEnvironment()) {
    startBtn.disabled = false;
    return;
  }

  try {

    const gpsPermission = await checkGPSPermission();
    if (gpsPermission === 'denied') {
      showStatus("GPS permission is required. Enable location in browser settings.", 'error', 6000);
      startBtn.disabled = false;
      return;
    }

    showStatus("Starting session...", 'info');
    const res = await fetch("/tracking/start/", {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken
      },
      credentials: "same-origin"
    });

    if (!res.ok) {
      showStatus("Failed to start session (" + res.status + ")", 'error', 6000);
      startBtn.disabled = false;
      return;
    }
    const data = await res.json();

    if (data.session_id) {
      sessionId = data.session_id;
    } else {
      showStatus("Session creation failed", 'error', 6000);
      startBtn.disabled = false;
      return;
    }

    try {
      await createSocket();
    } catch (wsErr) {
      showStatus("WebSocket failed: " + wsErr.message, 'error', 8000);
      startBtn.disabled = false;
      return;
    }

    polyline.setLatLngs([]);
    isTracking = true;
    stopBtn.disabled = false;

    // Reset stationary lock when starting new tracking session
    stationaryLock = false;
    stationaryLockTime = 0;
    stationaryDetectionCount = 0;
    lastMovementTime = 0;
    positionHistory = [];

    showStatus("GPS tracking started - acquiring location...", 'info', 4000);

    if (!navigator.geolocation) {
      showStatus("Geolocation not supported in this browser.", 'error', 8000);
      startBtn.disabled = false;
      return;
    }
    watchId = navigator.geolocation.watchPosition(
      handlePosition,
      (error) => {
        let errorMessage = "GPS tracking failed. ";

        switch(error.code) {
          case error.PERMISSION_DENIED:
            errorMessage += "Please enable location permissions.";
            break;
          case error.POSITION_UNAVAILABLE:
            errorMessage += "Location information unavailable.";
            break;
          case error.TIMEOUT:
            errorMessage += "Location request timed out.";
            break;
          default:
            errorMessage += "Unknown error occurred.";
        }

        showStatus(errorMessage, 'error', 8000);

        console.warn("Temporary GPS error, keeping session alive");
      },
      {
        enableHighAccuracy: true,
        maximumAge: 5000,       
        timeout: 10000           
      }
    );

  } catch (err) {
    showStatus("Start tracking failed: " + (err.message || err), 'error', 8000);
    startBtn.disabled = false;
  }
};


stopBtn.onclick = async () => {
  if (!isTracking) return;
  isTracking = false;
  animationToken++;
  if (watchId !== null) navigator.geolocation.clearWatch(watchId);
  if (locationBuffer.length > 0 && socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({
        session_id: sessionId,
        locations: locationBuffer
    }));
    locationBuffer = [];
}
  if (socket) socket.close();
  if (sessionId) {
    try {
      await fetch(`/tracking/stop/${sessionId}/`);
    } catch (e) {
        console.error("Error stopping session:", e)
    }
  }

  // Reset stationary lock and hide indicators
  stationaryLock = false;
  stationaryLockTime = 0;
  stationaryDetectionCount = 0;
  
  stopBtn.disabled = true;
  startBtn.disabled = false;
};

// Ensure stopBtn is enabled/disabled correctly on page load
if (isTracking) {
  stopBtn.disabled = false;
  startBtn.disabled = true;
} else {
  stopBtn.disabled = true;
  startBtn.disabled = false;
}



