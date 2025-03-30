import React, { useState } from 'react';
import axios from 'axios';
import ReactMapGL, { Marker } from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

const App = () => {
  const [continent, setContinent] = useState('');
  const [powerPlantType, setPowerPlantType] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [locations, setLocations] = useState([]);

  const handleSubmit = async () => {
    try {
      const response = await axios.post('http://localhost:5000/get-optimal-locations', {
        continent,
        powerPlantType,
        startDate,
        endDate
      });

      // Process and store locations
      setLocations(response.data.locations);  // Assume the response contains a list of optimal locations
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  return (
    <div>
      <h1>Optimal Energy Plant Locations</h1>
      <div>
        <input 
          type="text" 
          placeholder="Continent" 
          value={continent} 
          onChange={(e) => setContinent(e.target.value)} 
        />
        <input 
          type="text" 
          placeholder="Power Plant Type (wind, solar)" 
          value={powerPlantType} 
          onChange={(e) => setPowerPlantType(e.target.value)} 
        />
        <input 
          type="date" 
          value={startDate} 
          onChange={(e) => setStartDate(e.target.value)} 
        />
        <input 
          type="date" 
          value={endDate} 
          onChange={(e) => setEndDate(e.target.value)} 
        />
        <button onClick={handleSubmit}>Get Optimal Locations</button>
      </div>

      {/* Display Map with optimal locations */}
      <ReactMapGL
        initialViewState={{
          longitude: 0,
          latitude: 0,
          zoom: 2
        }}
        style={{ width: '100%', height: '500px' }}
        mapboxAccessToken='your-mapbox-token'
      >
        {locations.map((location, index) => (
          <Marker key={index} latitude={location.lat} longitude={location.lng}>
            <div style={{ color: 'red' }}>📍</div>
          </Marker>
        ))}
      </ReactMapGL>
    </div>
  );
};

export default App;
