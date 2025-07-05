import React, { useState } from 'react';
import axios from 'axios';
import ReactMapGL, { Marker } from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

const App = () => {
  const [latMin, setLatMin] = useState('');
  const [latMax, setLatMax] = useState('');
  const [lonMin, setLonMin] = useState('');
  const [lonMax, setLonMax] = useState('');
  const [powerPlantType, setPowerPlantType] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [viewport, setViewport] = useState({
    latitude: 20,
    longitude: 78,
    zoom: 4,
    width: '100%',
    height: '500px'
  });

  const validateInputs = () => {
    const lat1 = parseFloat(latMin);
    const lat2 = parseFloat(latMax);
    const lon1 = parseFloat(lonMin);
    const lon2 = parseFloat(lonMax);

    if (isNaN(lat1) || isNaN(lat2) || isNaN(lon1) || isNaN(lon2)) {
      alert('Please enter valid numbers for all coordinates');
      return false;
    }

    if (lat1 >= lat2) {
      alert('Latitude Min must be less than Latitude Max');
      return false;
    }

    if (lon1 >= lon2) {
      alert('Longitude Min must be less than Longitude Max');
      return false;
    }

    if (!powerPlantType || (powerPlantType.toLowerCase() !== 'wind' && powerPlantType.toLowerCase() !== 'solar')) {
      alert('Please enter "wind" or "solar" for power plant type');
      return false;
    }

    if (!startDate || !endDate) {
      alert('Please select both start and end dates');
      return false;
    }

    if (new Date(startDate) >= new Date(endDate)) {
      alert('Start date must be before end date');
      return false;
    }

    return true;
  };

  const handleSubmit = async () => {
    if (!validateInputs()) return;

    setLoading(true);
    setResult(null);
    setLocations([]);

    try {
      console.log('Sending request with data:', {
        boundary: {
          lonMin: parseFloat(lonMin), // Fixed: longitude first
          latMin: parseFloat(latMin),
          lonMax: parseFloat(lonMax),
          latMax: parseFloat(latMax)
        },
        time: {
          start: startDate,
          end: endDate
        },
        plant_type: powerPlantType.toLowerCase()
      });

      const response = await axios.post('http://localhost:5050/get_optimal_location', {
        boundary: {
          lonMin: parseFloat(lonMin), // Fixed: longitude first
          latMin: parseFloat(latMin),
          lonMax: parseFloat(lonMax),
          latMax: parseFloat(latMax)
        },
        time: {
          start: startDate,
          end: endDate
        },
        plant_type: powerPlantType.toLowerCase()
      });

      const data = response.data;
      console.log('Response received:', data);
      
      const point = data.optimal_point;
      setLocations([{ lat: point.lat, lng: point.lon }]);
      setResult(data);

      setViewport({
        ...viewport,
        latitude: point.lat,
        longitude: point.lon,
        zoom: 10
      });

    } catch (error) {
      console.error('Error fetching data:', error);
      
      if (error.response?.data?.error) {
        alert(`Error: ${error.response.data.error}`);
      } else if (error.response?.status === 404) {
        alert('No data found for the specified parameters. Try adjusting your date range or location.');
      } else if (error.response?.status === 500) {
        alert('Server error. Please check the console for details.');
      } else {
        alert('Failed to fetch optimal location. Check console for details.');
      }
    } finally {
      setLoading(false);
    }
  };

  const fillSampleData = () => {
    // Sample data for testing - New York area
    setLatMin('40.4774');
    setLatMax('40.9176');
    setLonMin('-74.2591');
    setLonMax('-73.7004');
    setPowerPlantType('solar');
    setStartDate('2022-01-01');
    setEndDate('2022-12-31');
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h2>Optimal Energy Plant Location Finder</h2>
      
      <div style={{ marginBottom: '1rem', display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
        <input 
          type="number" 
          placeholder="Latitude Min (e.g., 40.4774)" 
          value={latMin} 
          onChange={(e) => setLatMin(e.target.value)}
          step="0.0001"
          style={{ padding: '8px', minWidth: '150px' }}
        />
        <input 
          type="number" 
          placeholder="Latitude Max (e.g., 40.9176)" 
          value={latMax} 
          onChange={(e) => setLatMax(e.target.value)}
          step="0.0001"
          style={{ padding: '8px', minWidth: '150px' }}
        />
        <input 
          type="number" 
          placeholder="Longitude Min (e.g., -74.2591)" 
          value={lonMin} 
          onChange={(e) => setLonMin(e.target.value)}
          step="0.0001"
          style={{ padding: '8px', minWidth: '150px' }}
        />
        <input 
          type="number" 
          placeholder="Longitude Max (e.g., -73.7004)" 
          value={lonMax} 
          onChange={(e) => setLonMax(e.target.value)}
          step="0.0001"
          style={{ padding: '8px', minWidth: '150px' }}
        />
        <select 
          value={powerPlantType} 
          onChange={(e) => setPowerPlantType(e.target.value)}
          style={{ padding: '8px', minWidth: '150px' }}
        >
          <option value="">Select Plant Type</option>
          <option value="solar">Solar</option>
          <option value="wind">Wind</option>
        </select>
        <input 
          type="date" 
          value={startDate} 
          onChange={(e) => setStartDate(e.target.value)}
          style={{ padding: '8px' }}
        />
        <input 
          type="date" 
          value={endDate} 
          onChange={(e) => setEndDate(e.target.value)}
          style={{ padding: '8px' }}
        />
        <button 
          onClick={handleSubmit} 
          disabled={loading}
          style={{ 
            padding: '8px 16px', 
            backgroundColor: loading ? '#ccc' : '#007bff', 
            color: 'white', 
            border: 'none', 
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? 'Searching...' : 'Get Optimal Location'}
        </button>
        <button 
          onClick={fillSampleData}
          style={{ 
            padding: '8px 16px', 
            backgroundColor: '#28a745', 
            color: 'white', 
            border: 'none', 
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Fill Sample Data
        </button>
      </div>

      {result && (
        <div style={{ 
          marginBottom: '1rem', 
          padding: '15px', 
          backgroundColor: '#f8f9fa', 
          borderRadius: '5px',
          border: '1px solid #dee2e6'
        }}>
          <h3>Results:</h3>
          <p><strong>Optimal Location:</strong> {result.optimal_point.lat.toFixed(4)}, {result.optimal_point.lon.toFixed(4)}</p>
          <p><strong>Plant Type:</strong> {result.plant_type}</p>
          <p><strong>Score:</strong> {result.score?.toFixed(2) || 'N/A'}</p>
          <p><strong>Primary Value:</strong> {result.value?.toFixed(2) || 'N/A'}</p>
          <p><strong>Vegetation Score:</strong> {result.vegetation?.toFixed(2) || 'N/A'}</p>
          <p><strong>Samples Analyzed:</strong> {result.sample_count || 'N/A'}</p>
          {result.urban_penalty && (
            <p><strong>Urban Penalty:</strong> {result.urban_penalty.toFixed(2)}</p>
          )}
        </div>
      )}

      <ReactMapGL
        {...viewport}
        mapboxApiAccessToken="pk.eyJ1IjoiamhhZ3J1dGgiLCJhIjoiY204dWc2Z2JqMGkxdzJrc2VlY2dhOHgyciJ9.XnMkDJuE2iId6ZkCkee8qQ"
        onViewportChange={(nextViewport) => setViewport(nextViewport)}
        mapStyle="mapbox://styles/mapbox/streets-v11"
      >
        {locations.map((location, index) => (
          <Marker key={index} latitude={location.lat} longitude={location.lng}>
            <div style={{ 
              color: 'red', 
              fontSize: '24px',
              textShadow: '2px 2px 4px rgba(0,0,0,0.5)'
            }}>
              {result?.plant_type === 'solar' ? '☀️' : '💨'}
            </div>
          </Marker>
        ))}
      </ReactMapGL>

      <div style={{ marginTop: '20px', fontSize: '12px', color: '#666' }}>
        <p><strong>Instructions:</strong></p>
        <ul>
          <li>Enter coordinates in decimal degrees (e.g., 40.7128 for latitude, -74.0060 for longitude)</li>
          <li>Make sure Min values are less than Max values</li>
          <li>Select a date range (broader ranges may work better)</li>
          <li>Choose either "solar" or "wind" for plant type</li>
          <li>Click "Fill Sample Data" to test with New York area coordinates</li>
        </ul>
      </div>
    </div>
  );
};

export default App;