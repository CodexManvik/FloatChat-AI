"""
Data fetching utilities for dashboard components
Handles API calls and data preparation for visualizations
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
import logging
from datetime import datetime, timedelta
from components.api_client import APIClient, APIException
from components.data_transformer import DataTransformer

logger = logging.getLogger(__name__)

class DataFetcher:
    """Handles data fetching and caching for dashboard components"""
    
    def __init__(self, api_client: Optional[APIClient] = None):
        self.api_client = api_client or st.session_state.get('api_client')
        self.transformer = DataTransformer()
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_float_locations(_self, max_floats: int = 100) -> pd.DataFrame:
        """Get ARGO float locations for mapping"""
        
        if not _self.api_client:
            logger.warning("No API client available, returning sample data")
            return _self._create_sample_float_data(max_floats)
        
        try:
            # Try to get real data from a sample query
            # This is a workaround since we don't have a direct "get all floats" endpoint
            sample_query = "Show me ARGO float locations in the Indian Ocean"
            
            response = _self.api_client.query_rag_pipeline(sample_query)
            
            if response and response.retrieved_metadata:
                # Extract float IDs from metadata
                float_ids = set()
                postgres_ids = []
                
                for meta in response.retrieved_metadata:
                    if isinstance(meta, dict):
                        if 'float_id' in meta:
                            float_ids.add(meta['float_id'])
                        if 'postgres_id' in meta:
                            postgres_ids.append(meta['postgres_id'])
                
                if postgres_ids:
                    # Get detailed profile data
                    profiles_data = _self.api_client.get_profiles_by_ids(postgres_ids[:max_floats])
                    
                    if profiles_data:
                        # Convert to DataFrame and extract locations
                        df = _self.transformer.profiles_to_dataframe(profiles_data)
                        locations_df = _self.transformer.extract_float_locations(df)
                        
                        if not locations_df.empty:
                            logger.info(f"Retrieved {len(locations_df)} float locations from API")
                            return locations_df
            
            # Fallback to sample data if API doesn't return useful data
            logger.info("API data not available, using sample data")
            return _self._create_sample_float_data(max_floats)
            
        except APIException as e:
            logger.error(f"API error fetching float locations: {e}")
            st.error(f"Error fetching data: {str(e)}")
            return _self._create_sample_float_data(max_floats)
        
        except Exception as e:
            logger.error(f"Unexpected error fetching float locations: {e}")
            return _self._create_sample_float_data(max_floats)
    
    @st.cache_data(ttl=3600)
    def get_float_trajectories(_self, float_ids: Optional[List[str]] = None, max_trajectories: int = 10) -> pd.DataFrame:
        """Get trajectory data for specific floats"""
        
        if not _self.api_client:
            return _self._create_sample_trajectory_data(max_trajectories)
        
        try:
            trajectory_data = []
            
            # If no specific float IDs provided, get some from locations
            if not float_ids:
                locations_df = _self.get_float_locations(max_trajectories)
                if not locations_df.empty and 'float_id' in locations_df.columns:
                    float_ids = locations_df['float_id'].head(max_trajectories).tolist()
                else:
                    return _self._create_sample_trajectory_data(max_trajectories)
            
            # Get profiles for each float to build trajectories
            for float_id in float_ids[:max_trajectories]:
                try:
                    profiles = _self.api_client.get_float_profiles(float_id)
                    
                    if profiles:
                        # Convert to DataFrame
                        profiles_df = pd.DataFrame(profiles)
                        
                        # Create trajectory data
                        traj_df = _self.transformer.create_trajectory_data(profiles, float_id)
                        
                        if not traj_df.empty:
                            trajectory_data.append(traj_df)
                
                except APIException as e:
                    logger.warning(f"Could not get trajectory for float {float_id}: {e}")
                    continue
            
            if trajectory_data:
                combined_trajectories = pd.concat(trajectory_data, ignore_index=True)
                logger.info(f"Retrieved trajectories for {len(trajectory_data)} floats")
                return combined_trajectories
            else:
                return _self._create_sample_trajectory_data(max_trajectories)
        
        except Exception as e:
            logger.error(f"Error fetching trajectories: {e}")
            return _self._create_sample_trajectory_data(max_trajectories)
    
    @st.cache_data(ttl=1800)  # Cache for 30 minutes
    def get_system_statistics(_self) -> Dict[str, Any]:
        """Get system statistics for dashboard metrics"""
        
        if not _self.api_client:
            return _self._create_sample_statistics()
        
        try:
            # Try to get extensibility status which includes some stats
            status = _self.api_client.get_extensibility_status()
            
            if status and 'current_datasets' in status:
                # Extract what we can from the status
                stats = {
                    'total_floats': 50,  # Placeholder
                    'total_profiles': 1234,  # Placeholder
                    'total_measurements': 45678,  # Placeholder
                    'data_quality': 98.5,  # Placeholder
                    'last_update': datetime.now(),
                    'coverage_region': 'Indian Ocean',
                    'active_datasets': status.get('current_datasets', ['ARGO Floats'])
                }
                
                return stats
            
            return _self._create_sample_statistics()
        
        except Exception as e:
            logger.error(f"Error fetching system statistics: {e}")
            return _self._create_sample_statistics()
    
    def _create_sample_float_data(self, n_floats: int = 50) -> pd.DataFrame:
        """Create sample float data for demonstration"""
        np.random.seed(42)  # For consistent demo data
        
        # Focus on Indian Ocean region
        lat_range = (-30, 25)
        lon_range = (40, 120)
        
        data = []
        for i in range(n_floats):
            float_id = f"ARGO_{i+1:04d}"
            wmo_id = 5900000 + i
            
            # Random location in Indian Ocean
            lat = np.random.uniform(lat_range[0], lat_range[1])
            lon = np.random.uniform(lon_range[0], lon_range[1])
            
            # Random profile info
            cycle_number = np.random.randint(1, 200)
            profile_date = datetime.now() - timedelta(days=np.random.randint(0, 365))
            
            data.append({
                'float_id': float_id,
                'wmo_id': wmo_id,
                'lat': lat,
                'lon': lon,
                'cycle_number': cycle_number,
                'profile_date': profile_date
            })
        
        return pd.DataFrame(data)
    
    def _create_sample_trajectory_data(self, n_floats: int = 5) -> pd.DataFrame:
        """Create sample trajectory data for demonstration"""
        np.random.seed(42)
        
        trajectory_data = []
        
        # Create trajectories for specified number of floats
        for float_num in range(1, n_floats + 1):
            float_id = f"ARGO_{float_num:04d}"
            
            # Starting position in Indian Ocean
            start_lat = np.random.uniform(-20, 20)
            start_lon = np.random.uniform(50, 100)
            
            # Create trajectory with 10-20 points
            n_points = np.random.randint(10, 21)
            
            for point in range(n_points):
                # Simulate realistic ocean drift
                days_elapsed = point * 10  # 10 days between profiles
                
                # Add some realistic drift patterns
                lat_drift = np.sin(point * 0.3) * 0.5 + np.random.normal(0, 0.2)
                lon_drift = np.cos(point * 0.2) * 0.3 + np.random.normal(0, 0.3)
                
                lat = start_lat + (lat_drift * point * 0.1)
                lon = start_lon + (lon_drift * point * 0.1)
                
                # Ensure coordinates stay within Indian Ocean bounds
                lat = np.clip(lat, -30, 25)
                lon = np.clip(lon, 40, 120)
                
                profile_date = datetime.now() - timedelta(days=(n_points-point)*10)
                
                trajectory_data.append({
                    'float_id': float_id,
                    'lat': lat,
                    'lon': lon,
                    'time': profile_date,
                    'profile_date': profile_date,
                    'cycle_number': point + 1
                })
        
        return pd.DataFrame(trajectory_data)
    
    def _create_sample_statistics(self) -> Dict[str, Any]:
        """Create sample system statistics"""
        return {
            'total_floats': 50,
            'total_profiles': 1234,
            'total_measurements': 45678,
            'data_quality': 98.5,
            'last_update': datetime.now(),
            'coverage_region': 'Indian Ocean',
            'active_datasets': ['ARGO Floats'],
            'geographic_coverage': {
                'north': 25.0,
                'south': -30.0,
                'east': 120.0,
                'west': 40.0
            },
            'depth_coverage': {
                'min_depth': 0.0,
                'max_depth': 2000.0,
                'avg_depth': 500.0
            },
            'temporal_coverage': {
                'start_date': datetime.now() - timedelta(days=365),
                'end_date': datetime.now(),
                'total_days': 365
            }
        }
    
    def apply_filters(self, data: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        """Apply user-selected filters to data"""
        
        if data.empty:
            return data
        
        filtered_data = data.copy()
        
        try:
            # Date range filter
            if 'date_range' in filters and filters['date_range']:
                date_range = filters['date_range']
                if len(date_range) == 2 and 'profile_date' in filtered_data.columns:
                    start_date, end_date = date_range
                    
                    # Convert to datetime if needed
                    if 'profile_date' in filtered_data.columns:
                        filtered_data['profile_date'] = pd.to_datetime(filtered_data['profile_date'])
                        
                        # Filter by date range
                        mask = (
                            (filtered_data['profile_date'].dt.date >= start_date) &
                            (filtered_data['profile_date'].dt.date <= end_date)
                        )
                        filtered_data = filtered_data[mask]
            
            # Geographic bounds filter
            if 'custom_bounds' in filters and filters['custom_bounds']:
                bounds = filters['custom_bounds']
                if all(key in bounds for key in ['north', 'south', 'east', 'west']):
                    filtered_data = self.transformer.filter_by_geographic_bounds(filtered_data, bounds)
            
            # Depth range filter (if depth data available)
            if 'depth_range' in filters and 'depth' in filtered_data.columns:
                depth_min, depth_max = filters['depth_range']
                filtered_data = filtered_data[
                    (filtered_data['depth'] >= depth_min) & 
                    (filtered_data['depth'] <= depth_max)
                ]
            
            logger.info(f"Applied filters: {len(data)} -> {len(filtered_data)} records")
            return filtered_data
        
        except Exception as e:
            logger.error(f"Error applying filters: {e}")
            return data  # Return original data if filtering fails