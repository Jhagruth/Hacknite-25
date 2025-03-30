from flask import Flask, render_template_string
import ee
import folium
import osmnx as ox
import numpy as np
from geopy.distance import geodesic

# ---------------------------
# Authenticate and Initialize Earth Engine
# ---------------------------
ee.Authenticate()  # Follow the on-screen instructions (first time only)
ee.Initialize(project='hacknite-25')

# Define Karnataka Region (Bounding Box)
karnataka_bbox = ee.Geometry.Rectangle([74.0, 11.5, 78.5, 15.5])

# ---------------------------
# AI Agent Class for Solar Site Selection (Synthetic Data)
# ---------------------------
class SolarSiteAI:
    def __init__(self):
        self.karnataka_bbox = karnataka_bbox
        self.sites = self.generate_synthetic_sites()
        self.filtered_sites = self.process_sites()

    def generate_synthetic_sites(self):
        """Generate synthetic locations for solar power sites."""
        return [
            {"lat": 13.5, "lon": 75.5},
            {"lat": 14.2, "lon": 76.3},
            {"lat": 12.8, "lon": 77.1},
            {"lat": 13.9, "lon": 75.8},
            {"lat": 14.1, "lon": 76.7},
        ]

    def process_sites(self):
        """Process and filter synthetic sites with infrastructure cost and solar data."""
        suitable_land, flat_land, solar_radiation = self.get_environmental_data()
        roads, power_lines = self.get_infrastructure_data()
        filtered_sites = []
        for site in self.sites:
            site["cost"] = self.calculate_infra_cost(site, roads, power_lines)
            # For demonstration, use synthetic solar radiation data
            site["solar_radiation"] = np.random.uniform(4, 6)
            filtered_sites.append(site)
        return filtered_sites

    def get_environmental_data(self):
        """Retrieve and process geospatial datasets from Earth Engine."""
        # Land Cover - keep only barren (90), shrubland (30), and grassland (40)
        land_cover = ee.Image("ESA/WorldCover/v100").clip(self.karnataka_bbox)
        suitable_land = land_cover.updateMask(
            land_cover.eq(90).Or(land_cover.eq(30)).Or(land_cover.eq(40))
        )
        # Elevation & Slope - avoid steep terrain
        elevation = ee.Image("USGS/SRTMGL1_003").clip(self.karnataka_bbox)
        slope = ee.Terrain.slope(elevation)
        flat_land = slope.updateMask(slope.lte(10))
        # Solar Radiation - NASA POWER SSE Dataset (average)
        solar_radiation = ee.ImageCollection("NASA/POWER/SSE").filterBounds(self.karnataka_bbox).mean()
        return suitable_land, flat_land, solar_radiation
    
    def get_infrastructure_data(self):
        """Retrieve roads and power line data from OpenStreetMap using OSMnx."""
        # Define a small bounding box to reduce the load
        north, south, east, west = 14.5, 14.0, 75.5, 75.0
        
        # Correct usage of the function. Ensure the tags are passed correctly
        # Use a single argument for the tags
        roads = ox.features_from_bbox((north, south, east, west), {"highway": True})
        power_lines = ox.features_from_bbox((north, south, east, west), {"power": True})
        
        return roads, power_lines



    def calculate_infra_cost(self, site, roads, power_lines):
        """Calculate cost estimation based on distance to roads and power grid."""
        site_coords = (site["lat"], site["lon"])
        # Calculate distance to nearest road
        road_coords = [(geom.y, geom.x) for geom in roads.geometry if hasattr(geom, "x")]
        road_distances = [geodesic(site_coords, rc).km for rc in road_coords] if road_coords else [np.inf]
        min_road_distance = min(road_distances)
        # Calculate distance to nearest power line
        power_coords = [(geom.y, geom.x) for geom in power_lines.geometry if hasattr(geom, "x")]
        power_distances = [geodesic(site_coords, pc).km for pc in power_coords] if power_coords else [np.inf]
        min_power_distance = min(power_distances)
        # Sample cost function
        return (min_road_distance * 1000) + (min_power_distance * 2000)

    def display_map(self):
        """Visualize locations on an interactive map using Folium."""
        # Create a Folium map centered on Karnataka (approximate center lat, lon)
        m = folium.Map(location=[13.0, 76.0], zoom_start=7)
        # Add markers for each filtered site
        for site in self.filtered_sites:
            folium.Marker(
                location=[site["lat"], site["lon"]],
                popup=f"Cost: ₹{site['cost']:,.2f} | Solar: {site['solar_radiation']:.2f} kWh/m²",
                icon=folium.Icon(color="green", icon="bolt")
            ).add_to(m)
        return m

# ---------------------------
# Flask App Setup
# ---------------------------
app = Flask(__name__)

@app.route('/')
def index():
    # Initialize our AI agent and get the interactive map
    ai_agent = SolarSiteAI()
    folium_map = ai_agent.display_map()
    map_html = folium_map._repr_html_()  # Get HTML representation of the map

    # HTML template with inline CSS
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Solar Power Plant Site Selection</title>
      <style>
          body { font-family: Arial, sans-serif; background-color: #f2f2f2; margin: 0; padding: 0; }
          header { background-color: #4CAF50; color: white; padding: 10px 20px; text-align: center; }
          #map { width: 100%; height: 80vh; margin: 20px auto; border: 2px solid #4CAF50; }
          footer { background-color: #4CAF50; color: white; text-align: center; padding: 10px 20px; position: fixed; bottom: 0; width: 100%; }
      </style>
    </head>
    <body>
      <header>
        <h1>Solar Power Plant Site Selection AI</h1>
      </header>
      <div id="map">
        {{ map_html | safe }}
      </div>
      <footer>
        <p>&copy; 2025 Solar AI Hackathon</p>
      </footer>
    </body>
    </html>
    """
    return render_template_string(html_template, map_html=map_html)

# ---------------------------
# Run the Flask app
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
