// Initialize the Leaflet map centered on Chennai
var map = L.map('map').setView([13.0827, 80.2707], 11);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

// Fetch NDVI data and plot flower-themed circle markers
fetch('/api/ndvi')
  .then(response => response.json())
  .then(data => {
    data.forEach(point => {
      // Color coding based on NDVI value
      var color = point.ndvi > 0.7 ? '#2d6a4f' : point.ndvi > 0.6 ? '#a7d129' : '#f2b5d4';

      L.circleMarker([point.latitude, point.longitude], {
        radius: 10,
        color: color,
        fillColor: color,
        fillOpacity: 0.7,
        weight: 3
      }).addTo(map)
        .bindPopup(`
          <strong>NDVI:</strong> ${point.ndvi.toFixed(2)}<br>
          <em>Location:</em> (${point.latitude.toFixed(3)}, ${point.longitude.toFixed(3)})`
        );
    });
  })
  .catch(error => console.error('Error loading NDVI data:', error));
