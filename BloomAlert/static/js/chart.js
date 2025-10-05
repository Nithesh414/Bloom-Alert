// Fetch NDVI data and render a bar chart of NDVI values by location

fetch('/api/ndvi')
  .then(response => response.json())
  .then(data => {
    const ctx = document.createElement('canvas');
    document.querySelector('.dashboard-content').appendChild(ctx);

    const labels = data.map(point => `(${point.latitude.toFixed(2)}, ${point.longitude.toFixed(2)})`);
    const ndviValues = data.map(point => point.ndvi);

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'NDVI Bloom Index',
          data: ndviValues,
          backgroundColor: ndviValues.map(v =>
            v > 0.7 ? '#2d6a4f' :
              v > 0.6 ? '#a7d129' : '#f2b5d4'),
          borderColor: '#ffffff',
          borderWidth: 1
        }]
      },
      options: {
        scales: {
          y: {
            beginAtZero: true,
            max: 1,
            title: {
              display: true,
              text: 'NDVI Value'
            }
          },
          x: {
            title: {
              display: false
            }
          }
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            callbacks: {
              label: context => `NDVI: ${context.parsed.y.toFixed(2)}`
            }
          }
        }
      }
    });
  })
  .catch(error => console.error('Error loading NDVI for chart:', error));
