from flask import Flask, request, jsonify, render_template
import ee
import logging
import math
from datetime import datetime
import traceback
import concurrent.futures
import time
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Earth Engine with your project
try:
    ee.Initialize(project='hacknite-25')
    logger.info("Earth Engine initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Earth Engine: {str(e)}")
    raise

app = Flask(__name__)

# Cache for repeated requests
@lru_cache(maxsize=128)
def get_cached_modis_data(start_date, end_date, west, south, east, north):
    """Cache MODIS data for repeated requests"""
    region = ee.Geometry.Rectangle([west, south, east, north])
    
    modis_collection = ee.ImageCollection('MODIS/061/MCD12Q1').filterDate(start_date, end_date)
    modis_size = modis_collection.size().getInfo()
    
    if modis_size == 0:
        # Use cached broader range
        modis_collection = ee.ImageCollection('MODIS/061/MCD12Q1').filterDate('2020-01-01', '2023-12-31')
    
    return modis_collection.mean().select('LC_Type1').rename('vegetation')

@app.route('/')
def home():
    return render_template('index1.html')

def validate_date_format(date_string):
    """Validate and format date string"""
    try:
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
        
        if latMin >= latMax:
            raise ValueError("latMin must be less than latMax")
        
        if lonMin >= lonMax:
            logger.warning(f"Longitude boundary crosses dateline: lonMin={lonMin}, lonMax={lonMax}")
        
        return lonMin, latMin, lonMax, latMax
    except (KeyError, ValueError) as e:
        logger.error(f"Coordinate validation error: {str(e)}")
        raise

def is_point_in_boundary(lon, lat, west, south, east, north):
    """Check if a point is within the boundary"""
    return west <= lon <= east and south <= lat <= north

def calculate_optimized_sampling_params(west, south, east, north):
    """Calculate optimized sampling parameters for speed"""
    # Calculate area in square kilometers
    lat_center = (north + south) / 2
    lon_km_per_deg = 111.32 * abs(math.cos(math.radians(lat_center)))
    lat_km_per_deg = 110.54
    area_km2 = abs(east - west) * abs(north - south) * lon_km_per_deg * lat_km_per_deg
    
    # Optimized sampling for speed vs accuracy balance
    if area_km2 < 500:  # Very small area
        scale = 500
        num_pixels = 5000
        passes = 2
    elif area_km2 < 2000:  # Small area
        scale = 750
        num_pixels = 8000
        passes = 2
    elif area_km2 < 10000:  # Medium area
        scale = 1000
        num_pixels = 12000
        passes = 3
    else:  # Large area
        scale = 1500
        num_pixels = 15000
        passes = 3
    
    logger.info(f"Area: {area_km2:.2f} km² -> Scale: {scale}m, Samples: {num_pixels}, Passes: {passes}")
    return scale, num_pixels, area_km2, passes

def parallel_sampling(combined, region, scale, num_pixels, seed_offset=0):
    """Parallel sampling function for concurrent execution"""
    try:
        samples = combined.sample(
            region=region,
            scale=scale,
            numPixels=num_pixels,
            geometries=True,
            seed=42 + seed_offset
        )
        return samples
    except Exception as e:
        logger.warning(f"Parallel sampling failed: {str(e)}")
        return None

@app.route('/get_optimal_location', methods=['POST'])
def get_optimal_location():
    start_time = time.time()
    try:
        logger.info("Received request for optimal location")
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
            
        boundary = data.get('boundary')
        time_range = data.get('time')
        plant_type = data.get('plant_type')

        # Quick validation
        if not boundary or not time_range or not plant_type:
            missing_fields = []
            if not boundary: missing_fields.append('boundary')
            if not time_range: missing_fields.append('time')
            if not plant_type: missing_fields.append('plant_type')
            return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

        # Parse coordinates
        try:
            lonMin, latMin, lonMax, latMax = validate_coordinates(boundary)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Parse dates
        try:
            start_date = validate_date_format(time_range["start"])
            end_date = validate_date_format(time_range["end"])
        except (KeyError, ValueError) as e:
            return jsonify({"error": f"Invalid date format: {str(e)}"}), 400

        # Handle coordinate ordering
        west, east, south, north = lonMin, lonMax, latMin, latMax
        
        if west > east and abs(west - east) < 180:
            west, east = east, west
        if south > north:
            south, north = north, south
        
        region = ee.Geometry.Rectangle([west, south, east, north])

        # Fast MODIS data retrieval with caching
        try:
            vegetation = get_cached_modis_data(start_date, end_date, west, south, east, north)
        except Exception as e:
            logger.error(f"Error getting MODIS data: {str(e)}")
            return jsonify({"error": f"Failed to process land cover data: {str(e)}"}), 500

        # Plant-specific processing (optimized)
        if plant_type.lower() == "wind":
            try:
                era5 = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(start_date, end_date).filterBounds(region)
                
                # Check if data exists quickly
                if era5.size().getInfo() == 0:
                    return jsonify({"error": "No wind data found for the specified date range and region"}), 404

                # Simplified wind speed calculation
                era5_mean = era5.mean()
                wind_speed = era5_mean.expression(
                    'sqrt(pow(u, 2) + pow(v, 2))',
                    {
                        'u': era5_mean.select('u_component_of_wind_10m'),
                        'v': era5_mean.select('v_component_of_wind_10m')
                    }
                ).rename('wind_speed')

                # Simplified urban penalty (skip WorldCover for speed)
                composite = wind_speed.subtract(vegetation.multiply(0.05)).rename('score')
                best_value_band = 'wind_speed'
                combined = wind_speed.addBands(vegetation).addBands(composite)
                
            except Exception as e:
                return jsonify({"error": f"Failed to process wind data: {str(e)}"}), 500

        elif plant_type.lower() == "solar":
            try:
                # Try NASA POWER first, fallback to ERA5 quickly
                try:
                    power = ee.ImageCollection("NASA/POWER/DAILY_AGGR").filterDate(start_date, end_date).filterBounds(region)
                    if power.size().getInfo() > 0:
                        solar = power.select("ALLSKY_SFC_SW_DWN").mean().rename("solar_value")
                    else:
                        raise Exception("No NASA POWER data")
                except:
                    # Quick fallback to ERA5
                    era5_solar = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(start_date, end_date).filterBounds(region)
                    if era5_solar.size().getInfo() == 0:
                        return jsonify({"error": "No solar data found"}), 404
                    solar = era5_solar.select("surface_net_solar_radiation_sum").mean().rename("solar_value")
                
                composite = solar.subtract(vegetation.multiply(0.05)).rename("score")
                best_value_band = "solar_value"
                combined = solar.addBands(vegetation).addBands(composite)
                
            except Exception as e:
                return jsonify({"error": f"Failed to process solar data: {str(e)}"}), 500
        else:
            return jsonify({"error": f"Invalid plant type: {plant_type}"}), 400

        # Optimized sampling strategy
        scale, num_pixels, area_km2, passes = calculate_optimized_sampling_params(west, south, east, north)
        
        logger.info(f"Starting optimized {passes}-pass sampling...")
        all_samples_list = []
        
        # Pass 1: Primary sampling (always)
        samples1 = combined.sample(
            region=region,
            scale=scale,
            numPixels=num_pixels,
            geometries=True,
            seed=42
        )
        
        sample_size1 = samples1.size().getInfo()
        if sample_size1 > 0:
            all_samples_list.append(samples1)
        
        # Pass 2: Center focus (if passes >= 2)
        if passes >= 2 and sample_size1 > 0:
            margin_lon = (east - west) * 0.3
            margin_lat = (north - south) * 0.3
            
            center_region = ee.Geometry.Rectangle([
                west + margin_lon, south + margin_lat,
                east - margin_lon, north - margin_lat
            ])
            
            samples2 = combined.sample(
                region=center_region,
                scale=scale // 2,
                numPixels=num_pixels // 3,
                geometries=True,
                seed=123
            )
            
            sample_size2 = samples2.size().getInfo()
            if sample_size2 > 0:
                all_samples_list.append(samples2)
        
        # Pass 3: Edge sampling (if passes >= 3 and area is large enough)
        if passes >= 3 and area_km2 > 2000:
            edge_width = min((east - west) * 0.15, (north - south) * 0.15)
            
            # Only sample 2 edges for speed
            edge_regions = [
                ee.Geometry.Rectangle([west, south, west + edge_width, north]),  # Left
                ee.Geometry.Rectangle([west, north - edge_width, east, north])   # Top
            ]
            
            for i, edge_region in enumerate(edge_regions):
                try:
                    samples_edge = combined.sample(
                        region=edge_region,
                        scale=scale,
                        numPixels=num_pixels // 10,
                        geometries=True,
                        seed=200 + i
                    )
                    
                    if samples_edge.size().getInfo() > 0:
                        all_samples_list.append(samples_edge)
                except:
                    pass  # Skip failed edge sampling
        
        # Combine samples
        if len(all_samples_list) == 0:
            return jsonify({"error": "No valid samples found"}), 404
        
        all_samples = all_samples_list[0]
        for samples in all_samples_list[1:]:
            all_samples = all_samples.merge(samples)
        
        total_sample_size = all_samples.size().getInfo()
        
        # Quick top candidate evaluation (limit to 200 for speed)
        sorted_samples = all_samples.sort('score', False)
        top_candidates = sorted_samples.limit(min(200, total_sample_size)).getInfo()
        
        # Find optimal point
        optimal_point = None
        best_properties = None
        
        for feature in top_candidates['features']:
            coords = feature['geometry']['coordinates']
            lon, lat = coords[0], coords[1]
            
            if is_point_in_boundary(lon, lat, west, south, east, north):
                optimal_point = {"lat": lat, "lon": lon}
                best_properties = feature['properties']
                break
        
        if optimal_point is None:
            return jsonify({"error": "No valid locations found within boundary"}), 404

        # Build response
        processing_time = time.time() - start_time
        
        result = {
            "optimal_point": optimal_point,
            "value": best_properties.get(best_value_band),
            "vegetation": best_properties.get('vegetation'),
            "score": best_properties.get('score'),
            "plant_type": plant_type.lower(),
            "performance_stats": {
                "total_samples": total_sample_size,
                "processing_time_seconds": round(processing_time, 2),
                "resolution_meters": scale,
                "area_km2": round(area_km2, 2),
                "passes_completed": len(all_samples_list),
                "candidates_evaluated": len(top_candidates['features'])
            },
            "date_range": {"start": start_date, "end": end_date},
            "boundary": {
                "west": west, "south": south, "east": east, "north": north
            }
        }
        
        logger.info(f"Request completed in {processing_time:.2f}s with {total_sample_size} samples")
        return jsonify(result)

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Error after {processing_time:.2f}s: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        start_time = time.time()
        ee.Number(1).getInfo()
        response_time = time.time() - start_time
        return jsonify({
            "status": "healthy", 
            "earth_engine": "connected",
            "response_time_ms": round(response_time * 1000, 2)
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    logger.info("Starting optimized Flask application...")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule} [{', '.join(rule.methods)}]")
    
    app.run(debug=True, port=5050, host='0.0.0.0')