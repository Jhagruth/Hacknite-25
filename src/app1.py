from flask import Flask, request, jsonify, render_template
import ee

# Initialize the Earth Engine API with your project.
ee.Initialize(project='hacknite-25')

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index1.html')

@app.route('/get_optimal_location', methods=['POST'])
def get_optimal_location():
    data = request.get_json()
    boundary = data.get('boundary')
    time_range = data.get('time')
    plant_type = data.get('plant_type')  # Expected values: "wind" or "solar"
    
    if not boundary or not time_range or not plant_type:
        return jsonify({"error": "Missing required boundary, time range, or plant type data"}), 400
    
    try:
        lonMin = float(boundary["lonMin"])
        latMin = float(boundary["latMin"])
        lonMax = float(boundary["lonMax"])
        latMax = float(boundary["latMax"])
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid boundary values provided"}), 400

    start_date = time_range["start"]
    end_date = time_range["end"]
    
    # Define the region using the boundary coordinates.
    region = ee.Geometry.Rectangle([lonMin, latMin, lonMax, latMax])
    
    # --- Compute Vegetation ---
    modis_collection = ee.ImageCollection('MODIS/006/MCD12Q1').filterDate(start_date, end_date)
    if modis_collection.size().getInfo() == 0:
        return jsonify({"error": "No MODIS images found for the specified time range."}), 404
    modis_mean = modis_collection.mean()
    band_names = modis_mean.bandNames().getInfo()
    if 'LC_Type1' not in band_names:
        return jsonify({"error": "MODIS dataset does not contain band 'LC_Type1'."}), 404
    vegetation = modis_mean.select('LC_Type1').rename('vegetation')
    
    composite = None
    combined = None
    best_value_band = None
    
    if plant_type.lower() == "wind":
        # --- Compute Wind Speed ---
        era5 = ee.ImageCollection('ECMWF/ERA5/DAILY').filterDate(start_date, end_date)
        era5_mean = era5.mean()
        wind_speed = era5_mean.expression(
            'sqrt(pow(u, 2) + pow(v, 2))',
            {
                'u': era5_mean.select('u_component_of_wind_10m'),
                'v': era5_mean.select('v_component_of_wind_10m')
            }
        ).rename('wind_speed')
        
        # --- Compute Urbanization ---
        # ESA WorldCover is an ImageCollection, so we need to filter it and get a single image
        world_cover = ee.ImageCollection("ESA/WorldCover/v100").filterBounds(region).first()
        
        # Check if we got a valid image from the collection
        if world_cover is None:
            return jsonify({"error": "No ESA WorldCover image found for the specified region."}), 404
        
        # Mask urban areas (class 30 in ESA WorldCover represents built-up land)
        urban_mask = world_cover.eq(30)  # Built-up areas (class 30 in ESA WorldCover)

        # Penalty for proximity to urban areas
        urban_distance = urban_mask.multiply(10000)  # Example penalty of 10,000 units for being in urban areas

        composite = wind_speed.subtract(vegetation).subtract(urban_distance).rename('score')
        best_value_band = 'wind_speed'
        combined = wind_speed.addBands(vegetation).addBands(urban_distance).addBands(composite)
    
    elif plant_type.lower() == "solar":
        # --- Compute Solar Radiation using MERRA-2 ---
        merra = ee.ImageCollection("NASA/GEOS-5/MERRA2") \
                    .filterDate(start_date, end_date) \
                    .filterBounds(region)
        if merra.size().getInfo() == 0:
            return jsonify({"error": "No MERRA2 images found for the specified time range and region."}), 404
        merra_mean = merra.mean()
        band_names = merra_mean.bandNames().getInfo()
        if "SWGDN" not in band_names:
            return jsonify({"error": "MERRA2 dataset does not contain 'SWGDN'."}), 404
        solar_value = merra_mean.select("SWGDN").rename("solar_value")
        composite = solar_value.subtract(vegetation).rename('score')
        best_value_band = 'solar_value'
        combined = solar_value.addBands(vegetation).addBands(composite)
    
    else:
        return jsonify({"error": "Invalid plant type. Use 'wind' or 'solar'."}), 400
    
    # --- Sampling & Finding the Optimal Point ---
    samples = combined.sample(region=region, scale=5000, numPixels=500, geometries=True)
    sorted_samples = samples.sort('score', False)
    best_sample = ee.Feature(sorted_samples.first())
    
    coords = best_sample.geometry().coordinates().getInfo()  # [lon, lat]
    best_value = best_sample.get(best_value_band).getInfo()
    best_veg = best_sample.get('vegetation').getInfo()
    best_score = best_sample.get('score').getInfo()
    
    # Compute center (optional, for reference)
    center_lat = (latMin + latMax) / 2
    center_lon = (lonMin + lonMax) / 2
    
    result = {
        "optimal_point": {"lat": coords[1], "lon": coords[0]},
        "value": best_value,
        "vegetation": best_veg,
        "score": best_score,
        "center": {"lat": center_lat, "lon": center_lon},
        "plant_type": plant_type.lower()
    }
    
    return jsonify(result)

if __name__ == '__main__':
    print(app.url_map)
    app.run(debug=True)
