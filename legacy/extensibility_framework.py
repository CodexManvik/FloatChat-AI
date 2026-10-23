"""
Extensibility Framework for FloatChat
Supports future integration of BGC, glider, buoys, and satellite datasets
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import pandas as pd
from sqlalchemy import create_engine, text
import config

class DatasetProcessor(ABC):
    """Abstract base class for different oceanographic dataset processors"""
    
    @abstractmethod
    def get_dataset_type(self) -> str:
        """Return the type of dataset (e.g., 'argo', 'glider', 'satellite')"""
        pass
    
    @abstractmethod
    def get_schema_definition(self) -> Dict[str, str]:
        """Return the database schema for this dataset type"""
        pass
    
    @abstractmethod
    def process_raw_data(self, file_path: str) -> pd.DataFrame:
        """Process raw data file and return standardized DataFrame"""
        pass
    
    @abstractmethod
    def get_query_templates(self) -> Dict[str, str]:
        """Return NL-to-SQL templates specific to this dataset"""
        pass
    
    @abstractmethod
    def get_visualization_config(self) -> Dict[str, Any]:
        """Return visualization configuration for this dataset"""
        pass

class ARGOProcessor(DatasetProcessor):
    """Current ARGO float processor - already implemented"""
    
    def get_dataset_type(self) -> str:
        return "argo_floats"
    
    def get_schema_definition(self) -> Dict[str, str]:
        return {
            "floats": """
                CREATE TABLE floats (
                    float_id VARCHAR(20) PRIMARY KEY,
                    wmo_id INTEGER,
                    deployment_date DATE,
                    deployment_lat FLOAT,
                    deployment_lon FLOAT,
                    status VARCHAR(20) DEFAULT 'ACTIVE',
                    dataset_type VARCHAR(20) DEFAULT 'argo'
                );
            """,
            "profiles": """
                CREATE TABLE profiles (
                    profile_id SERIAL PRIMARY KEY,
                    float_id VARCHAR(20) REFERENCES floats(float_id),
                    cycle_number INTEGER,
                    profile_date TIMESTAMP,
                    profile_lat FLOAT,
                    profile_lon FLOAT,
                    dataset_type VARCHAR(20) DEFAULT 'argo'
                );
            """,
            "measurements": """
                CREATE TABLE measurements (
                    id SERIAL PRIMARY KEY,
                    profile_id INTEGER REFERENCES profiles(profile_id),
                    platform_id VARCHAR(20),
                    time TIMESTAMP,
                    lat FLOAT,
                    lon FLOAT,
                    depth FLOAT,
                    temperature FLOAT,
                    salinity FLOAT,
                    oxygen FLOAT,
                    ph FLOAT,
                    chlorophyll FLOAT,
                    dataset_type VARCHAR(20) DEFAULT 'argo'
                );
            """
        }
    
    def process_raw_data(self, file_path: str) -> pd.DataFrame:
        # Current ARGO processing logic
        pass
    
    def get_query_templates(self) -> Dict[str, str]:
        return {
            "depth_profile": "SELECT depth, AVG(temperature) FROM measurements WHERE dataset_type='argo' GROUP BY depth",
            "float_summary": "SELECT platform_id, COUNT(*) FROM measurements WHERE dataset_type='argo' GROUP BY platform_id"
        }
    
    def get_visualization_config(self) -> Dict[str, Any]:
        return {
            "map_columns": ["lat", "lon", "temperature", "salinity"],
            "profile_columns": ["depth", "temperature", "salinity"],
            "time_column": "time",
            "platform_column": "platform_id"
        }

class GliderProcessor(DatasetProcessor):
    """Processor for autonomous underwater glider data"""
    
    def get_dataset_type(self) -> str:
        return "gliders"
    
    def get_schema_definition(self) -> Dict[str, str]:
        return {
            "gliders": """
                CREATE TABLE gliders (
                    glider_id VARCHAR(20) PRIMARY KEY,
                    deployment_date DATE,
                    deployment_lat FLOAT,
                    deployment_lon FLOAT,
                    mission_name VARCHAR(100),
                    institution VARCHAR(100),
                    dataset_type VARCHAR(20) DEFAULT 'glider'
                );
            """,
            "glider_profiles": """
                CREATE TABLE glider_profiles (
                    profile_id SERIAL PRIMARY KEY,
                    glider_id VARCHAR(20) REFERENCES gliders(glider_id),
                    profile_time TIMESTAMP,
                    profile_lat FLOAT,
                    profile_lon FLOAT,
                    dive_number INTEGER,
                    dataset_type VARCHAR(20) DEFAULT 'glider'
                );
            """,
            "glider_measurements": """
                CREATE TABLE glider_measurements (
                    id SERIAL PRIMARY KEY,
                    profile_id INTEGER REFERENCES glider_profiles(profile_id),
                    platform_id VARCHAR(20),
                    time TIMESTAMP,
                    lat FLOAT,
                    lon FLOAT,
                    depth FLOAT,
                    temperature FLOAT,
                    salinity FLOAT,
                    oxygen FLOAT,
                    chlorophyll FLOAT,
                    turbidity FLOAT,
                    current_u FLOAT,
                    current_v FLOAT,
                    dataset_type VARCHAR(20) DEFAULT 'glider'
                );
            """
        }
    
    def process_raw_data(self, file_path: str) -> pd.DataFrame:
        # Glider-specific processing logic
        # Handle continuous profiling data, navigation, etc.
        pass
    
    def get_query_templates(self) -> Dict[str, str]:
        return {
            "transect_analysis": """
                SELECT lat, lon, AVG(temperature), AVG(salinity) 
                FROM glider_measurements 
                WHERE dataset_type='glider' AND glider_id = %s
                GROUP BY lat, lon ORDER BY time
            """,
            "dive_comparison": """
                SELECT dive_number, AVG(temperature), AVG(oxygen)
                FROM glider_profiles gp
                JOIN glider_measurements gm ON gp.profile_id = gm.profile_id
                WHERE dataset_type='glider'
                GROUP BY dive_number ORDER BY dive_number
            """
        }
    
    def get_visualization_config(self) -> Dict[str, Any]:
        return {
            "map_columns": ["lat", "lon", "temperature", "salinity"],
            "profile_columns": ["depth", "temperature", "salinity", "oxygen"],
            "transect_columns": ["lat", "lon", "temperature"],
            "time_column": "time",
            "platform_column": "glider_id"
        }

class BuoyProcessor(DatasetProcessor):
    """Processor for moored buoy and surface drifter data"""
    
    def get_dataset_type(self) -> str:
        return "buoys"
    
    def get_schema_definition(self) -> Dict[str, str]:
        return {
            "buoys": """
                CREATE TABLE buoys (
                    buoy_id VARCHAR(20) PRIMARY KEY,
                    buoy_type VARCHAR(50), -- 'moored', 'drifter', 'weather'
                    deployment_date DATE,
                    deployment_lat FLOAT,
                    deployment_lon FLOAT,
                    water_depth FLOAT,
                    dataset_type VARCHAR(20) DEFAULT 'buoy'
                );
            """,
            "buoy_measurements": """
                CREATE TABLE buoy_measurements (
                    id SERIAL PRIMARY KEY,
                    buoy_id VARCHAR(20) REFERENCES buoys(buoy_id),
                    platform_id VARCHAR(20),
                    time TIMESTAMP,
                    lat FLOAT,
                    lon FLOAT,
                    depth FLOAT,
                    temperature FLOAT,
                    salinity FLOAT,
                    sea_surface_height FLOAT,
                    wave_height FLOAT,
                    wind_speed FLOAT,
                    wind_direction FLOAT,
                    air_temperature FLOAT,
                    air_pressure FLOAT,
                    dataset_type VARCHAR(20) DEFAULT 'buoy'
                );
            """
        }
    
    def process_raw_data(self, file_path: str) -> pd.DataFrame:
        # Buoy-specific processing logic
        # Handle time series data, meteorological parameters
        pass
    
    def get_query_templates(self) -> Dict[str, str]:
        return {
            "surface_conditions": """
                SELECT DATE_TRUNC('day', time) as date,
                       AVG(sea_surface_height) as avg_ssh,
                       AVG(wave_height) as avg_wave_height,
                       AVG(wind_speed) as avg_wind_speed
                FROM buoy_measurements 
                WHERE dataset_type='buoy' AND buoy_type='moored'
                GROUP BY DATE_TRUNC('day', time) ORDER BY date
            """,
            "drifter_tracks": """
                SELECT buoy_id, time, lat, lon, temperature
                FROM buoy_measurements 
                WHERE dataset_type='buoy' AND buoy_type='drifter'
                ORDER BY buoy_id, time
            """
        }
    
    def get_visualization_config(self) -> Dict[str, Any]:
        return {
            "map_columns": ["lat", "lon", "temperature", "sea_surface_height"],
            "time_series_columns": ["time", "temperature", "wave_height", "wind_speed"],
            "track_columns": ["lat", "lon", "time"],
            "time_column": "time",
            "platform_column": "buoy_id"
        }

class SatelliteProcessor(DatasetProcessor):
    """Processor for satellite oceanographic data"""
    
    def get_dataset_type(self) -> str:
        return "satellite"
    
    def get_schema_definition(self) -> Dict[str, str]:
        return {
            "satellite_missions": """
                CREATE TABLE satellite_missions (
                    mission_id VARCHAR(20) PRIMARY KEY,
                    mission_name VARCHAR(100),
                    satellite_name VARCHAR(100),
                    instrument VARCHAR(100),
                    start_date DATE,
                    end_date DATE,
                    dataset_type VARCHAR(20) DEFAULT 'satellite'
                );
            """,
            "satellite_data": """
                CREATE TABLE satellite_data (
                    id SERIAL PRIMARY KEY,
                    mission_id VARCHAR(20) REFERENCES satellite_missions(mission_id),
                    platform_id VARCHAR(20),
                    time TIMESTAMP,
                    lat FLOAT,
                    lon FLOAT,
                    sea_surface_temperature FLOAT,
                    sea_surface_height FLOAT,
                    chlorophyll_a FLOAT,
                    sea_ice_concentration FLOAT,
                    wind_speed FLOAT,
                    significant_wave_height FLOAT,
                    data_quality INTEGER,
                    dataset_type VARCHAR(20) DEFAULT 'satellite'
                );
            """
        }
    
    def process_raw_data(self, file_path: str) -> pd.DataFrame:
        # Satellite-specific processing logic
        # Handle gridded data, quality flags, temporal composites
        pass
    
    def get_query_templates(self) -> Dict[str, str]:
        return {
            "sst_climatology": """
                SELECT DATE_TRUNC('month', time) as month,
                       AVG(sea_surface_temperature) as avg_sst,
                       STDDEV(sea_surface_temperature) as std_sst
                FROM satellite_data 
                WHERE dataset_type='satellite' AND data_quality >= 3
                GROUP BY DATE_TRUNC('month', time) ORDER BY month
            """,
            "regional_analysis": """
                SELECT 
                    FLOOR(lat/5)*5 as lat_bin,
                    FLOOR(lon/5)*5 as lon_bin,
                    AVG(sea_surface_temperature) as avg_sst,
                    AVG(chlorophyll_a) as avg_chl
                FROM satellite_data 
                WHERE dataset_type='satellite'
                GROUP BY FLOOR(lat/5)*5, FLOOR(lon/5)*5
            """
        }
    
    def get_visualization_config(self) -> Dict[str, Any]:
        return {
            "map_columns": ["lat", "lon", "sea_surface_temperature", "chlorophyll_a"],
            "gridded_columns": ["lat", "lon", "sea_surface_temperature"],
            "time_series_columns": ["time", "sea_surface_temperature", "chlorophyll_a"],
            "time_column": "time",
            "platform_column": "mission_id"
        }

class ExtensibilityManager:
    """Manages multiple dataset processors and provides unified interface"""
    
    def __init__(self):
        self.processors = {
            "argo": ARGOProcessor(),
            "glider": GliderProcessor(),
            "buoy": BuoyProcessor(),
            "satellite": SatelliteProcessor()
        }
        self.engine = create_engine(config.DATABASE_URL)
    
    def register_processor(self, name: str, processor: DatasetProcessor):
        """Register a new dataset processor"""
        self.processors[name] = processor
    
    def get_available_datasets(self) -> List[str]:
        """Get list of available dataset types"""
        return list(self.processors.keys())
    
    def create_unified_schema(self):
        """Create database schema for all registered processors"""
        
        # Create unified tables that can handle multiple dataset types
        unified_schema = """
        -- Unified platforms table (floats, gliders, buoys, satellites)
        CREATE TABLE IF NOT EXISTS platforms (
            platform_id VARCHAR(50) PRIMARY KEY,
            platform_type VARCHAR(20), -- 'argo', 'glider', 'buoy', 'satellite'
            platform_name VARCHAR(100),
            deployment_date DATE,
            deployment_lat FLOAT,
            deployment_lon FLOAT,
            status VARCHAR(20),
            institution VARCHAR(100),
            dataset_type VARCHAR(20)
        );
        
        -- Unified observations table
        CREATE TABLE IF NOT EXISTS observations (
            id SERIAL PRIMARY KEY,
            platform_id VARCHAR(50) REFERENCES platforms(platform_id),
            observation_time TIMESTAMP,
            lat FLOAT,
            lon FLOAT,
            depth FLOAT,
            -- Physical parameters
            temperature FLOAT,
            salinity FLOAT,
            pressure FLOAT,
            -- BGC parameters
            oxygen FLOAT,
            ph FLOAT,
            chlorophyll FLOAT,
            nitrate FLOAT,
            -- Satellite parameters
            sea_surface_height FLOAT,
            sea_ice_concentration FLOAT,
            -- Meteorological parameters
            wind_speed FLOAT,
            wind_direction FLOAT,
            wave_height FLOAT,
            air_temperature FLOAT,
            air_pressure FLOAT,
            -- Quality and metadata
            data_quality INTEGER,
            processing_level VARCHAR(10),
            dataset_type VARCHAR(20),
            source_file VARCHAR(200)
        );
        
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_observations_platform ON observations(platform_id);
        CREATE INDEX IF NOT EXISTS idx_observations_time ON observations(observation_time);
        CREATE INDEX IF NOT EXISTS idx_observations_location ON observations(lat, lon);
        CREATE INDEX IF NOT EXISTS idx_observations_dataset ON observations(dataset_type);
        """
        
        with self.engine.connect() as conn:
            for statement in unified_schema.split(';'):
                if statement.strip():
                    conn.execute(text(statement))
            conn.commit()
    
    def get_unified_query_templates(self) -> Dict[str, str]:
        """Get query templates that work across all dataset types"""
        return {
            "multi_dataset_comparison": """
                SELECT 
                    dataset_type,
                    COUNT(*) as observation_count,
                    AVG(temperature) as avg_temperature,
                    AVG(salinity) as avg_salinity,
                    MIN(observation_time) as start_date,
                    MAX(observation_time) as end_date
                FROM observations 
                GROUP BY dataset_type
                ORDER BY observation_count DESC;
            """,
            
            "cross_platform_validation": """
                SELECT 
                    DATE_TRUNC('month', observation_time) as month,
                    dataset_type,
                    AVG(temperature) as avg_temp,
                    COUNT(*) as obs_count
                FROM observations 
                WHERE temperature IS NOT NULL
                GROUP BY DATE_TRUNC('month', observation_time), dataset_type
                ORDER BY month, dataset_type;
            """,
            
            "regional_multi_sensor": """
                SELECT 
                    FLOOR(lat/2)*2 as lat_bin,
                    FLOOR(lon/2)*2 as lon_bin,
                    dataset_type,
                    AVG(temperature) as avg_temp,
                    AVG(chlorophyll) as avg_chl,
                    COUNT(*) as obs_count
                FROM observations 
                WHERE lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s
                GROUP BY FLOOR(lat/2)*2, FLOOR(lon/2)*2, dataset_type;
            """
        }
    
    def process_new_dataset(self, dataset_type: str, file_path: str) -> bool:
        """Process and ingest a new dataset"""
        if dataset_type not in self.processors:
            raise ValueError(f"Unknown dataset type: {dataset_type}")
        
        processor = self.processors[dataset_type]
        
        try:
            # Process raw data
            df = processor.process_raw_data(file_path)
            
            # Standardize column names for unified schema
            standardized_df = self._standardize_dataframe(df, dataset_type)
            
            # Insert into unified tables
            standardized_df.to_sql('observations', self.engine, if_exists='append', index=False)
            
            return True
            
        except Exception as e:
            print(f"Error processing {dataset_type} dataset: {e}")
            return False
    
    def _standardize_dataframe(self, df: pd.DataFrame, dataset_type: str) -> pd.DataFrame:
        """Standardize DataFrame columns for unified schema"""
        
        # Add dataset_type column
        df['dataset_type'] = dataset_type
        
        # Standardize time column
        time_columns = ['time', 'observation_time', 'datetime', 'date_time']
        for col in time_columns:
            if col in df.columns:
                df['observation_time'] = pd.to_datetime(df[col])
                break
        
        # Standardize platform ID
        platform_columns = ['platform_id', 'float_id', 'glider_id', 'buoy_id', 'mission_id']
        for col in platform_columns:
            if col in df.columns:
                df['platform_id'] = df[col]
                break
        
        return df

# Usage example and integration points
def setup_extensible_system():
    """Setup the extensible system for multiple dataset types"""
    
    manager = ExtensibilityManager()
    
    # Create unified schema
    manager.create_unified_schema()
    
    print("✅ Extensible system ready for:")
    for dataset_type in manager.get_available_datasets():
        print(f"   • {dataset_type.upper()} data")
    
    return manager

if __name__ == "__main__":
    # Test the extensibility framework
    manager = setup_extensible_system()
    
    print("\n🔮 Future Dataset Integration Ready:")
    print("• ARGO Floats (current)")
    print("• Autonomous Gliders") 
    print("• Moored & Drifting Buoys")
    print("• Satellite Observations")
    print("• Custom Dataset Types")