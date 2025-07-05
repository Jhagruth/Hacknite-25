from flask import Flask, request, jsonify, render_template
import ee
import logging
from datetime import datetime
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Earth Engine with your project
try:
    ee.Initialize(project='hacknite-25')
    logger.info("Earth Engine initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Earth Engine: {str(e)}")
    raise

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index1.html')

def validate_date_format(date_string):
    """Validate and format date string"""
    try:
        # Try parsing common date formats
        formats = ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y']
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_string, fmt)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                continue
        raise ValueError(f"Invalid date format: {date_string}")
    except Exception as e:
        logger.error(f"Date validation error: {str(e)}")
        raise

def validate_coordinates(boundary):
    """Parse and validate boundary coordinates"""
    try:
        lonMin = float(boundary["lonMin"])
        latMin = float(boundary["latMin"])
        lonMax = float(boundary["lonMax"])
        latMax = float(boundary["latMax"])
        
        # Validate coordinate ranges
        if not (-180 <= lonMin <= 180) or not (-180 <= lonMax <= 180):
            raise ValueError("Longitude values must be between -180 and 180")
        if not (-90 <= latMin <= 90) or not (-90 <= latMax <= 90):
            raise ValueError("Latitude values must be between -90 and 90")
        
        # Validate bounding box logic
        if lonMin >= lonMax:
            raise ValueError("lonMin must be less than lonMax")
        if latMin >= latMax:
            raise ValueError("latMin must be less than latMax")
        
        logger.info(f"Validated coordinates: ({lonMin}, {latMin}) to ({lonMax}, {latMax})")
        return lonMin, latMin, lonMax, latMax
    except (KeyError, ValueError) as e:
        logger.error(f"Coordinate validation error: {str(e)}")
        raise

def is_point_in_boundary(lon, lat, lonMin, latMin, lonMax, latMax):
    """Check if a point is within the boundary"""
    return lonMin <= lon <= lonMax and latMin <= lat <= latMax

@app.route('/get_optimal_location', methods=['POST'])
def get_optimal_location():
    try:
        # Log the incoming request
        logger.info("Received request for optimal location")
        
        data = request.get_json()
        logger.debug(f"Request data: {data}")
        
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "No JSON data received"}), 400
            
        boundary = data.get('boundary')
        time_range = data.get('time')
        plant_type = data.get('plant_type')

        # Validate required fields
        if not boundary or not time_range or not plant_type:
            missing_fields = []
            if not boundary: missing_fields.append('boundary')
            if not time_range: missing_fields.append('time')
            if not plant_type: missing_fields.append('plant_type')
            
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            logger.error(error_msg)
            return jsonify({"error": error_msg}), 400

        # Parse and validate coordinates
        try:
            lonMin, latMin, lonMax, latMax = validate_coordinates(boundary)
            logger.info(f"Coordinates validated: ({lonMin}, {latMin}) to ({lonMax}, {latMax})")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Validate and parse dates
        try:
            start_date = validate_date_format(time_range["start"])
            end_date = validate_date_format(time_range["end"])
            logger.info(f"Date range: {start_date} to {end_date}")
        except (KeyError, ValueError) as e:
            return jsonify({"error": f"Invalid date format: {str(e)}"}), 400

        # Create region geometry - this ensures sampling is within boundary
        region = ee.Geometry.Rectangle([lonMin, latMin, lonMax, latMax])
        logger.info(f"Region created with bounds: {[lonMin, latMin, lonMax, latMax]}")

        # Get land cover from MODIS
        logger.info("Fetching MODIS land cover data...")
        try:
            modis_collection = ee.ImageCollection('MODIS/061/MCD12Q1').filterDate(start_date, end_date)
            modis_size = modis_collection.size().getInfo()
            logger.info(f"MODIS collection size: {modis_size}")
            
            if modis_size == 0:
                # Try a broader date range
                logger.warning("No MODIS images found, trying broader date range...")
                broader_start = '2020-01-01'
                broader_end = '2023-12-31'
                modis_collection = ee.ImageCollection('MODIS/061/MCD12Q1').filterDate(broader_start, broader_end)
                modis_size = modis_collection.size().getInfo()
                logger.info(f"MODIS collection size with broader range: {modis_size}")
                
                if modis_size == 0:
                    return jsonify({"error": "No MODIS land cover data available for this region"}), 404
            
            modis_mean = modis_collection.mean()
            vegetation = modis_mean.select('LC_Type1').rename('vegetation')
            logger.info("MODIS data processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing MODIS data: {str(e)}")
            return jsonify({"error": f"Failed to process land cover data: {str(e)}"}), 500

        composite = None
        best_value_band = None

        # ---------------- WIND ----------------
        if plant_type.lower() == "wind":
            logger.info("Processing wind energy data...")
            try:
                era5 = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(start_date, end_date).filterBounds(region)
                era5_size = era5.size().getInfo()
                logger.info(f"ERA5 collection size: {era5_size}")
                
                if era5_size == 0:
                    return jsonify({"error": "No wind data found for the specified date range and region"}), 404

                era5_mean = era5.mean()
                wind_speed = era5_mean.expression(
                    'sqrt(pow(u, 2) + pow(v, 2))',
                    {
                        'u': era5_mean.select('u_component_of_wind_10m'),
                        'v': era5_mean.select('v_component_of_wind_10m')
                    }
                ).rename('wind_speed')

                logger.info("Getting ESA WorldCover data...")
                world_cover = ee.ImageCollection("ESA/WorldCover/v100").filterBounds(region).first()
                
                # Create urban mask (50 = built-up areas in ESA WorldCover)
                urban_mask = world_cover.eq(50).multiply(1000)  # Penalty for urban areas
                
                # Create composite score (higher wind speed is better, subtract penalties)
                composite = wind_speed.subtract(vegetation.multiply(0.1)).subtract(urban_mask).rename('score')
                best_value_band = 'wind_speed'
                combined = wind_speed.addBands(vegetation).addBands(urban_mask.rename('urban_penalty')).addBands(composite)
                
                logger.info("Wind data processed successfully")

            except Exception as e:
                logger.error(f"Error processing wind data: {str(e)}")
                return jsonify({"error": f"Failed to process wind data: {str(e)}"}), 500

        # ---------------- SOLAR ----------------
        elif plant_type.lower() == "solar":
            logger.info("Processing solar energy data...")
            try:
                # Try the correct NASA POWER dataset
                power = ee.ImageCollection("NASA/POWER/DAILY_AGGR").filterDate(start_date, end_date).filterBounds(region)
                power_size = power.size().getInfo()
                logger.info(f"NASA POWER collection size: {power_size}")
                
                if power_size == 0:
                    logger.warning("No NASA POWER data found, trying alternative solar datasets...")
                    
                    # Try ERA5-Land solar radiation as alternative
                    try:
                        era5_solar = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(start_date, end_date).filterBounds(region)
                        era5_solar_size = era5_solar.size().getInfo()
                        logger.info(f"ERA5-Land collection size: {era5_solar_size}")
                        
                        if era5_solar_size == 0:
                            return jsonify({"error": "No solar data found for the specified date range and region"}), 404
                        
                        # Use surface net solar radiation from ERA5
                        solar = era5_solar.select("surface_net_solar_radiation_sum").mean().rename("solar_value")
                        logger.info("Using ERA5-Land solar radiation data")
                        
                    except Exception as era5_error:
                        logger.error(f"ERA5-Land solar data error: {str(era5_error)}")
                        return jsonify({"error": "Failed to access solar radiation data from available sources"}), 500
                        
                else:
                    # Use NASA POWER solar data
                    solar = power.select("ALLSKY_SFC_SW_DWN").mean().rename("solar_value")
                    logger.info("Using NASA POWER solar data")
                
                # Create composite score (higher solar irradiance is better, subtract vegetation penalty)
                composite = solar.subtract(vegetation.multiply(0.1)).rename("score")
                best_value_band = "solar_value"
                combined = solar.addBands(vegetation).addBands(composite)
                
                logger.info("Solar data processed successfully")

            except Exception as e:
                logger.error(f"Error processing solar data: {str(e)}")
                return jsonify({"error": f"Failed to process solar data: {str(e)}"}), 500

        else:
            return jsonify({"error": f"Invalid plant type: {plant_type}. Must be 'wind' or 'solar'"}), 400

        # Sample and rank - sampling is constrained to the region boundary
        logger.info("Sampling and ranking locations within boundary...")
        try:
            # The region parameter ensures all samples are within the defined boundary
            samples = combined.sample(
                region=region,  # This constrains sampling to the boundary
                scale=5000, 
                numPixels=1000,  # Increased sample size
                geometries=True,
                seed=42  # For reproducible results
            )
            
            sample_size = samples.size().getInfo()
            logger.info(f"Generated {sample_size} samples within boundary")
            
            if sample_size == 0:
                return jsonify({"error": "No valid samples found in the specified region"}), 404
            
            # Sort samples by score (best first)
            sorted_samples = samples.sort('score', False)
            
            # Get multiple top samples and find the first one that's definitely within boundary
            top_samples = sorted_samples.limit(10)  # Get top 10 samples
            top_samples_list = top_samples.getInfo()
            
            optimal_point = None
            best_properties = None
            
            # Check each top sample to ensure it's within boundary
            for feature in top_samples_list['features']:
                coords = feature['geometry']['coordinates']
                lon, lat = coords[0], coords[1]
                
                # Verify the point is within boundary
                if is_point_in_boundary(lon, lat, lonMin, latMin, lonMax, latMax):
                    optimal_point = {"lat": lat, "lon": lon}
                    best_properties = feature['properties']
                    logger.info(f"Found optimal location within boundary: ({lon}, {lat})")
                    break
                else:
                    logger.warning(f"Sample at ({lon}, {lat}) is outside boundary, trying next...")
            
            # If no point found within boundary, use the best sample anyway but log warning
            if optimal_point is None:
                logger.warning("No samples found within strict boundary, using best available sample")
                best_feature = ee.Feature(sorted_samples.first())
                coords = best_feature.geometry().coordinates().getInfo()
                optimal_point = {"lat": coords[1], "lon": coords[0]}
                best_properties = best_feature.toDictionary().getInfo()

            logger.info(f"Final optimal location: {optimal_point}")
            logger.debug(f"Properties: {best_properties}")

            result = {
                "optimal_point": optimal_point,
                "value": best_properties.get(best_value_band),
                "vegetation": best_properties.get('vegetation'),
                "score": best_properties.get('score'),
                "plant_type": plant_type.lower(),
                "sample_count": sample_size,
                "date_range": {"start": start_date, "end": end_date},
                "boundary": {
                    "lonMin": lonMin,
                    "latMin": latMin,
                    "lonMax": lonMax,
                    "latMax": latMax
                },
                "within_boundary": is_point_in_boundary(
                    optimal_point["lon"], 
                    optimal_point["lat"], 
                    lonMin, latMin, lonMax, latMax
                )
            }
            
            # Add plant-specific data
            if plant_type.lower() == "wind":
                result["urban_penalty"] = best_properties.get('urban_penalty', 0)
            
            logger.info("Request processed successfully - optimal location found")
            return jsonify(result)

        except Exception as e:
            logger.error(f"Error during sampling: {str(e)}")
            return jsonify({"error": f"Failed to sample locations: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"Unexpected error in get_optimal_location: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test Earth Engine connection
        ee.Number(1).getInfo()
        return jsonify({"status": "healthy", "earth_engine": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 error: {request.url}")
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    logger.info("Starting Flask application...")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule} [{', '.join(rule.methods)}]")
    
    app.run(debug=True, port=5050, host='0.0.0.0')