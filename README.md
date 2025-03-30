# Solar Suitability AI Model

## Overview
This project implements a machine learning-based solar suitability model using environmental and spatial data. The model leverages XGBoost for advanced predictions, incorporating polynomial features, hyperparameter tuning, and feature importance analysis.

## Data Sources
The following datasets were used in this project:

1. **MODIS/006/MCD12Q1** - Vegetation data
2. **ECMWF/ERA5/DAILY** - Wind speed data
3. **ESA/WorldCover/v100** - Urbanization data
4. **NASA/GEOS-5/MERRA2** - Solar radiation data

These datasets were accessed via Google Earth Engine (GEE) and preprocessed for training the model.

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

## Citations
- **ChatGPT** - Assisted in model development and optimization.
- **Google Earth Engine** - Provided remote sensing datasets.

---
This project is open for improvements and contributions!
