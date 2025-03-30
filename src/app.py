from flask import Flask, render_template, request, jsonify
import ee
import json
import logging

# Initialize the Earth Engine API
ee.Initialize(project='hacknite-25')

# Setup logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Function to get optimal locations based on power type, location, and time
def get_optimal_locations(power_type, location, time):
    # Parse the start and end date from the 'time' input
    start_date = time.get('start')
    end_date = time.get('end')

    # Validate date input format
    if not start_date or not end_date:
        return {"error": "Invalid time input. Please provide both start and end dates."}
    
    # Validate location input
    if not location or not location.get('lat') or not location.get('lon'):
        return {"error": "Invalid location input. Please provide both 'lat' and 'lon'."}
    
    lat = location['lat']
    lon = location['lon']
    
    # Validate latitude and longitude ranges
    if lat < -90 or lat > 90:
        return {"error": "Latitude must be between -90 and 90 degrees."}
    if lon < -180 or lon > 180:
        return {"error": "Longitude must be between -180 and 180 degrees."}
    
    # Create a point geometry based on the location (lat, lon)
    point = ee.Geometry.Point([lon, lat])
    
    # Solar functionality using updated MODIS dataset
    if power_type == "solar":
        try:
            solar_data = ee.ImageCollection("MODIS/061/MOD11A1") \
                .filterDate(ee.Date(start_date), ee.Date(end_date)) \
                .select("LST_Day_1km")  # Select appropriate band for day-time land surface temperature
            
            data_size = solar_data.size().getInfo()
            logging.debug(f"Solar data size: {data_size}")  # Log the data size
            
            if data_size == 0:
                return {"error": "No solar data available for the selected time range."}
            
            # Average the data over the time range
            solar_avg = solar_data.mean()
            solar_resampled = solar_avg.resample('bicubic')
            
            # Sample the solar data at the input location
            solar_value = solar_resampled.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=1000  # Use a more appropriate scale (in meters)
            )
            
            solar_value_info = solar_value.getInfo()
            logging.debug(f"Solar value info: {solar_value_info}")  # Debug log
            
            if solar_value_info and 'LST_Day_1km' in solar_value_info:
                return {
                    "lat": location['lat'],
                    "lon": location['lon'],
                    "solar_value": solar_value_info.get('LST_Day_1km', 'No Data Available')
                }
            else:
                return {
                    "lat": location['lat'],
                    "lon": location['lon'],
                    "solar_value": 'No Data Available'
                }
        
        except Exception as e:
            logging.error(f"Error in solar data processing: {str(e)}")
            return {"error": f"Error in solar data processing: {str(e)}"}
    
    # Wind functionality using ERA5
    if power_type == "wind":
        try:
            # Access ERA5 wind data (m/s) - 10m wind speed
            wind_data = ee.ImageCollection("ECMWF/ERA5/DAILY") \
                .filterDate(ee.Date(start_date), ee.Date(end_date)) \
                .select("u_component_of_wind_10m", "v_component_of_wind_10m")  # Select appropriate bands
            
            wind_data_size = wind_data.size().getInfo()
            logging.debug(f"Wind data size: {wind_data_size}")  # Debug: Check the number of available wind data images
            
            if wind_data_size == 0:
                return {"error": "No wind data available for the selected time range."}
            
            # Compute wind speed (magnitude) using u_component_of_wind_10m and v_component_of_wind_10m
            wind_speed = wind_data.map(lambda image: image.expression(
                'sqrt(u*u + v*v)', {'u': image.select('u_component_of_wind_10m'), 'v': image.select('v_component_of_wind_10m')}
            ))
            
            # Calculate the average wind speed for the given time period
            wind_speed_avg = wind_speed.mean()
            
            # Sample the wind speed data at the input location
            wind_value = wind_speed_avg.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=1000  # Adjust scale to your needs
            )
            
            wind_value_info = wind_value.getInfo()
            logging.debug(f"Wind value info: {wind_value_info}")  # Debug log
            
            # Ensure the returned value is parsed correctly
            if 'mean' in wind_value_info:
                return {
                    "lat": location['lat'],
                    "lon": location['lon'],
                    "wind_speed": wind_value_info['mean']
                }
            else:
                return {
                    "lat": location['lat'],
                    "lon": location['lon'],
                    "wind_speed": 'No Data Available'
                }
        
        except Exception as e:
            logging.error(f"Error in wind data processing: {str(e)}")
            return {"error": f"Error in wind data processing: {str(e)}"}
    
    # Thermal functionality using MODIS Land Surface Temperature (LST)
    if power_type == "thermal":
        try:
            # Access MODIS LST data (Land Surface Temperature) - daytime temperature
            thermal_data = ee.ImageCollection("MODIS/061/MOD11A1") \
                .filterDate(ee.Date(start_date), ee.Date(end_date)) \
                .select("LST_Day_1km")  # Use daytime LST data
            
            thermal_data_size = thermal_data.size().getInfo()
            logging.debug(f"Thermal data size: {thermal_data_size}")  # Debug: Check the number of available thermal data images
            
            if thermal_data_size == 0:
                return {"error": "No thermal data available for the selected time range."}
            
            # Average the thermal data over the time range
            thermal_avg = thermal_data.mean()
            
            # Resample the image to match the point location more closely
            thermal_resampled = thermal_avg.resample('bicubic')
            
            # Sample the thermal data at the input location
            thermal_value = thermal_resampled.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=1000  # Adjust scale to your needs
            )
            
            thermal_value_info = thermal_value.getInfo()
            logging.debug(f"Thermal value info: {thermal_value_info}")  # Debug log
            
            if thermal_value_info and 'LST_Day_1km' in thermal_value_info:
                return {
                    "lat": location['lat'],
                    "lon": location['lon'],
                    "thermal_value": thermal_value_info.get('LST_Day_1km', 'No Data Available')
                }
            else:
                return {
                    "lat": location['lat'],
                    "lon": location['lon'],
                    "thermal_value": 'No Data Available'
                }
        
        except Exception as e:
            logging.error(f"Error in thermal data processing: {str(e)}")
            return {"error": f"Error in thermal data processing: {str(e)}"}
    
    return {"message": "Invalid power type"}


# Route to render the main page with a map
@app.route('/')
def index():
    return render_template('index.html')

# Route to get optimal locations based on input
@app.route('/get_optimal_locations', methods=['POST'])
def get_locations():
    try:
        # Validate input data
        if not request.json or not request.json.get('power_type') or not request.json.get('location') or not request.json.get('time'):
            return jsonify({"error": "Missing required fields in the request body. Ensure 'power_type', 'location', and 'time' are included."})
        
        # Debug: Log the incoming request data
        logging.debug(f"Incoming request data: {request.json}")
        
        power_type = request.json['power_type']
        location = request.json['location']
        time = request.json['time']
        
        # Get optimal locations for power plant type
        result = get_optimal_locations(power_type, location, time)
        
        # Debug: Log the result
        logging.debug(f"Result: {result}")
        
        return jsonify(result)
    
    except Exception as e:
        logging.error(f"An error occurred while processing the request: {str(e)}")
        return jsonify({"error": f"An error occurred while processing the request: {str(e)}"})


if __name__ == '__main__':
    app.run(debug=True)
