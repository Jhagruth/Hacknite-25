# Novel Model to find an Optimal Location to set up a Sustainable Energy Power Plant

## Overview
This project implements a machine learning-based suitability model that integrates environmental and spatial data with Google Earth Engine APIs. The model utilises XGBoost for advanced predictions, incorporating polynomial features, hyperparameter tuning, and feature importance analysis.

## Data Sources
The following datasets were used in this project:

1. **MODIS/006/MCD12Q1** - Vegetation data
2. **ECMWF/ERA5/DAILY** - Wind speed data
3. **ESA/WorldCover/v100** - Urbanization data
4. **NASA/GEOS-5/MERRA2** - Solar radiation data

These datasets were accessed via Google Earth Engine (GEE) and preprocessed for training the model.


<img width="1800" alt="Screenshot 2025-03-30 at 1 09 15 PM" src="https://github.com/user-attachments/assets/a2a0e717-eaa4-4626-890c-6613c886cc6a" />

## Features and Methodology
- **Data Processing**: Extracted spatial data and normalized values using `MinMaxScaler`.
- **Feature Engineering**: Applied polynomial feature expansion.
- **Machine Learning Model**: Utilized XGBoost with hyperparameter tuning via GridSearchCV.
- **Evaluation**: Used R² scores and feature importance analysis.

## Installation
To run the project, install the required dependencies:
```bash
pip install pandas numpy scikit-learn xgboost flask geopandas osmnx geopy
```

## Running the Model
1. Ensure you have the required datasets preprocessed.
2. Run the model script:
```bash
python app.py
```
3. Access the Flask-based interface at `http://127.0.0.1:5000/`.


<img width="1800" alt="Screenshot 2025-03-30 at 12 52 12 PM" src="https://github.com/user-attachments/assets/d6f7e9b3-5cc6-45e7-945f-11eadd483614" />

## Citations
- **ChatGPT** - Assisted in model development and optimization.
- **Google Earth Engine** - Provided remote sensing datasets.

---
This project is open for improvements and contributions!
