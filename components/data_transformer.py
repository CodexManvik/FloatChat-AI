"""
Data transformation utilities for API responses
Converts API data into formats suitable for visualization
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DataTransformer:
    """Transforms API response data for dashboard consumption"""
    
    @staticmethod
    def profiles_to_dataframe(profiles_data: List[dict]) -> pd.DataFrame:
        """Convert profile data from API to pandas DataFrame"""
        if not profiles_data:
            return pd.DataFrame()
        
        try:
            df = pd.DataFrame(profiles_data)
            
            # Convert time columns to datetime
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], errors='coerce')
            
            # Ensure numeric columns are properly typed
            numeric_columns = ['lat', 'lon', 'depth', 'temperature', 'salinity', 
                             'oxygen', 'ph', 'chlorophyll', 'pressure']
            
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Sort by float_id, then by depth for proper profile ordering
            if 'float_id' in df.columns and 'depth' in df.columns:
                df = df.sort_values(['float_id', 'depth'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error converting profiles to DataFrame: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def extract_float_locations(profiles_data: List[dict]) -> pd.DataFrame:
        """Extract unique float locations for mapping"""
        if not profiles_data:
            return pd.DataFrame()
        
        try:
            df = pd.DataFrame(profiles_data)
            
            if 'float_id' not in df.columns or 'lat' not in df.columns or 'lon' not in df.columns:
                return pd.DataFrame()
            
            # Get latest position for each float
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], errors='coerce')
                float_locations = df.groupby('float_id').apply(
                    lambda x: x.loc[x['time'].idxmax()] if not x['time'].isna().all() else x.iloc[0]
                ).reset_index(drop=True)
            else:
                float_locations = df.groupby('float_id').first().reset_index()
            
            # Ensure required columns exist
            required_cols = ['float_id', 'lat', 'lon']
            for col in required_cols:
                if col not in float_locations.columns:
                    float_locations[col] = np.nan
            
            # Add metadata columns if available
            metadata_cols = ['wmo_id', 'cycle_number', 'profile_date']
            for col in metadata_cols:
                if col not in float_locations.columns:
                    float_locations[col] = np.nan
            
            return float_locations[float_locations['lat'].notna() & float_locations['lon'].notna()]
            
        except Exception as e:
            logger.error(f"Error extracting float locations: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def create_trajectory_data(profiles_data: List[dict], float_id: str) -> pd.DataFrame:
        """Create trajectory data for a specific float"""
        if not profiles_data:
            return pd.DataFrame()
        
        try:
            df = pd.DataFrame(profiles_data)
            
            # Filter for specific float
            if 'float_id' in df.columns:
                df = df[df['float_id'] == float_id]
            
            if df.empty:
                return pd.DataFrame()
            
            # Convert time and sort
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], errors='coerce')
                df = df.sort_values('time')
            
            # Get unique positions (one per profile/time)
            if 'profile_id' in df.columns:
                trajectory = df.groupby('profile_id').first().reset_index()
            else:
                trajectory = df.drop_duplicates(['lat', 'lon', 'time']).reset_index(drop=True)
            
            # Ensure required columns
            required_cols = ['lat', 'lon']
            if not all(col in trajectory.columns for col in required_cols):
                return pd.DataFrame()
            
            # Remove rows with missing coordinates
            trajectory = trajectory[trajectory['lat'].notna() & trajectory['lon'].notna()]
            
            return trajectory
            
        except Exception as e:
            logger.error(f"Error creating trajectory data: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def prepare_profile_plot_data(profiles_data: List[dict], float_id: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """Prepare data for profile plotting (T-S diagrams, depth profiles)"""
        if not profiles_data:
            return {}
        
        try:
            df = pd.DataFrame(profiles_data)
            
            # Filter by float if specified
            if float_id and 'float_id' in df.columns:
                df = df[df['float_id'] == float_id]
            
            if df.empty:
                return {}
            
            # Convert numeric columns
            numeric_columns = ['depth', 'temperature', 'salinity', 'oxygen', 'ph', 'chlorophyll']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove rows with missing depth
            if 'depth' in df.columns:
                df = df[df['depth'].notna()]
            
            result = {}
            
            # Temperature-depth profile
            if 'temperature' in df.columns and 'depth' in df.columns:
                temp_data = df[['depth', 'temperature']].dropna()
                if not temp_data.empty:
                    result['temperature_depth'] = temp_data.sort_values('depth')
            
            # Salinity-depth profile
            if 'salinity' in df.columns and 'depth' in df.columns:
                sal_data = df[['depth', 'salinity']].dropna()
                if not sal_data.empty:
                    result['salinity_depth'] = sal_data.sort_values('depth')
            
            # T-S diagram
            if 'temperature' in df.columns and 'salinity' in df.columns:
                ts_data = df[['temperature', 'salinity', 'depth']].dropna()
                if not ts_data.empty:
                    result['temperature_salinity'] = ts_data
            
            # BGC profiles
            bgc_params = ['oxygen', 'ph', 'chlorophyll']
            for param in bgc_params:
                if param in df.columns and 'depth' in df.columns:
                    bgc_data = df[['depth', param]].dropna()
                    if not bgc_data.empty:
                        result[f'{param}_depth'] = bgc_data.sort_values('depth')
            
            return result
            
        except Exception as e:
            logger.error(f"Error preparing profile plot data: {e}")
            return {}
    
    @staticmethod
    def extract_metadata_for_chat(query_response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format metadata from RAG query response for chat display"""
        metadata = {
            'query_type': 'unknown',
            'data_count': 0,
            'postgres_ids': [],
            'float_ids': [],
            'has_sql_results': False
        }
        
        try:
            # Extract from retrieved_metadata
            if 'retrieved_metadata' in query_response:
                retrieved_meta = query_response['retrieved_metadata']
                if retrieved_meta:
                    # Get postgres IDs for data retrieval
                    postgres_ids = []
                    float_ids = set()
                    
                    for meta in retrieved_meta:
                        if isinstance(meta, dict):
                            if 'postgres_id' in meta:
                                postgres_ids.append(meta['postgres_id'])
                            if 'float_id' in meta:
                                float_ids.add(meta['float_id'])
                            if 'query_type' in meta:
                                metadata['query_type'] = meta['query_type']
                    
                    metadata['postgres_ids'] = postgres_ids
                    metadata['float_ids'] = list(float_ids)
                    metadata['data_count'] = len(postgres_ids)
            
            # Check for SQL results
            if 'sql_results' in query_response and query_response['sql_results']:
                metadata['has_sql_results'] = True
                metadata['sql_data_count'] = len(query_response['sql_results'])
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting chat metadata: {e}")
            return metadata
    
    @staticmethod
    def sql_results_to_dataframe(sql_results: List[dict]) -> pd.DataFrame:
        """Convert SQL results to DataFrame for visualization"""
        if not sql_results:
            return pd.DataFrame()
        
        try:
            df = pd.DataFrame(sql_results)
            
            # Convert numeric columns
            for col in df.columns:
                if col in ['temperature', 'salinity', 'depth', 'avg_temperature', 'avg_salinity', 
                          'min_depth', 'max_depth', 'measurement_count', 'total_profiles']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Convert date columns
            date_columns = ['month', 'profile_date', 'date']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            return df
            
        except Exception as e:
            logger.error(f"Error converting SQL results to DataFrame: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> bool:
        """Validate latitude and longitude coordinates"""
        try:
            return (-90 <= lat <= 90) and (-180 <= lon <= 180)
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def filter_by_geographic_bounds(df: pd.DataFrame, bounds: Dict[str, float]) -> pd.DataFrame:
        """Filter DataFrame by geographic bounding box"""
        if df.empty or 'lat' not in df.columns or 'lon' not in df.columns:
            return df
        
        try:
            required_keys = ['north', 'south', 'east', 'west']
            if not all(key in bounds for key in required_keys):
                return df
            
            filtered = df[
                (df['lat'] >= bounds['south']) & 
                (df['lat'] <= bounds['north']) &
                (df['lon'] >= bounds['west']) & 
                (df['lon'] <= bounds['east'])
            ]
            
            return filtered
            
        except Exception as e:
            logger.error(f"Error filtering by geographic bounds: {e}")
            return df