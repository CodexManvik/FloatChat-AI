"""
Unit tests for Map Visualization Component
"""

import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from components.map_visualization import InteractiveMap

class TestInteractiveMap:
    """Test cases for InteractiveMap class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.map_viz = InteractiveMap()
        
        # Sample float data
        self.sample_float_data = pd.DataFrame({
            'float_id': ['ARGO_001', 'ARGO_002', 'ARGO_003'],
            'lat': [10.5, 15.2, -5.8],
            'lon': [75.3, 80.1, 85.7],
            'wmo_id': [5900001, 5900002, 5900003],
            'cycle_number': [45, 67, 23],
            'profile_date': [
                datetime.now() - timedelta(days=1),
                datetime.now() - timedelta(days=5),
                datetime.now() - timedelta(days=10)
            ]
        })
        
        # Sample trajectory data
        self.sample_trajectory_data = pd.DataFrame({
            'float_id': ['ARGO_001', 'ARGO_001', 'ARGO_001', 'ARGO_002', 'ARGO_002'],
            'lat': [10.0, 10.2, 10.5, 15.0, 15.2],
            'lon': [75.0, 75.1, 75.3, 80.0, 80.1],
            'time': [
                datetime.now() - timedelta(days=20),
                datetime.now() - timedelta(days=10),
                datetime.now() - timedelta(days=1),
                datetime.now() - timedelta(days=15),
                datetime.now() - timedelta(days=5)
            ]
        })
    
    def test_init(self):
        """Test map initialization"""
        assert self.map_viz.default_center == (0.0, 80.0)
        assert self.map_viz.default_zoom == 3
    
    def test_create_base_map(self):
        """Test base map creation"""
        fig = self.map_viz.create_base_map()
        
        assert isinstance(fig, go.Figure)
        assert fig.layout.geo is not None
        assert fig.layout.geo.projection_type == 'natural earth'
        assert fig.layout.title.text == "ARGO Float Locations"
    
    def test_create_base_map_custom_center(self):
        """Test base map with custom center and zoom"""
        custom_center = (20.0, 70.0)
        custom_zoom = 5
        
        fig = self.map_viz.create_base_map(center=custom_center, zoom=custom_zoom)
        
        assert fig.layout.geo.center.lat == custom_center[0]
        assert fig.layout.geo.center.lon == custom_center[1]
    
    def test_add_float_markers_empty_data(self):
        """Test adding markers with empty data"""
        fig = self.map_viz.create_base_map()
        empty_data = pd.DataFrame()
        
        result_fig = self.map_viz.add_float_markers(fig, empty_data)
        
        # Should return original figure unchanged
        assert len(result_fig.data) == 0
    
    def test_add_float_markers_valid_data(self):
        """Test adding markers with valid data"""
        fig = self.map_viz.create_base_map()
        
        result_fig = self.map_viz.add_float_markers(fig, self.sample_float_data)
        
        # Should have added one trace for markers
        assert len(result_fig.data) == 1
        assert result_fig.data[0].type == 'scattergeo'
        assert len(result_fig.data[0].lon) == 3
        assert len(result_fig.data[0].lat) == 3
    
    def test_add_float_markers_invalid_coordinates(self):
        """Test handling of invalid coordinates"""
        fig = self.map_viz.create_base_map()
        
        # Data with invalid coordinates
        invalid_data = pd.DataFrame({
            'float_id': ['ARGO_001', 'ARGO_002', 'ARGO_003'],
            'lat': [95.0, 15.2, np.nan],  # Invalid: >90, NaN
            'lon': [75.3, 200.0, 85.7],   # Invalid: >180
            'wmo_id': [5900001, 5900002, 5900003]
        })
        
        result_fig = self.map_viz.add_float_markers(fig, invalid_data)
        
        # Should only plot the valid coordinate (middle one is invalid due to lon>180)
        assert len(result_fig.data) == 0 or len(result_fig.data[0].lon) == 0
    
    def test_add_trajectories_empty_data(self):
        """Test adding trajectories with empty data"""
        fig = self.map_viz.create_base_map()
        empty_data = pd.DataFrame()
        
        result_fig = self.map_viz.add_trajectories(fig, empty_data)
        
        # Should return original figure unchanged
        assert len(result_fig.data) == 0
    
    def test_add_trajectories_valid_data(self):
        """Test adding trajectories with valid data"""
        fig = self.map_viz.create_base_map()
        
        result_fig = self.map_viz.add_trajectories(fig, self.sample_trajectory_data)
        
        # Should have added traces for trajectories and start/end markers
        # 2 floats * 3 traces each (trajectory + start + end) = 6 traces
        assert len(result_fig.data) == 6
    
    def test_add_trajectories_single_point(self):
        """Test trajectories with single points (should be skipped)"""
        fig = self.map_viz.create_base_map()
        
        single_point_data = pd.DataFrame({
            'float_id': ['ARGO_001'],
            'lat': [10.0],
            'lon': [75.0],
            'time': [datetime.now()]
        })
        
        result_fig = self.map_viz.add_trajectories(fig, single_point_data)
        
        # Should not add any traces for single points
        assert len(result_fig.data) == 0
    
    def test_cluster_floats(self):
        """Test float clustering functionality"""
        # Create data with some close floats
        close_floats = pd.DataFrame({
            'float_id': ['ARGO_001', 'ARGO_002', 'ARGO_003', 'ARGO_004'],
            'lat': [10.0, 10.1, 10.05, 20.0],  # First 3 are close, last is far
            'lon': [75.0, 75.1, 75.05, 85.0],
            'wmo_id': [5900001, 5900002, 5900003, 5900004]
        })
        
        clustered = self.map_viz._cluster_floats(close_floats, distance_threshold=0.2)
        
        # Should have fewer rows than original (clustering occurred)
        assert len(clustered) < len(close_floats)
        assert 'cluster_size' in clustered.columns
    
    def test_get_predefined_regions(self):
        """Test predefined regions"""
        regions = self.map_viz.get_predefined_regions()
        
        assert isinstance(regions, dict)
        assert 'Indian Ocean' in regions
        assert 'Arabian Sea' in regions
        
        # Check region structure
        indian_ocean = regions['Indian Ocean']
        assert 'bounds' in indian_ocean
        assert 'color' in indian_ocean
        assert 'description' in indian_ocean
        
        bounds = indian_ocean['bounds']
        assert all(key in bounds for key in ['north', 'south', 'east', 'west'])
    
    def test_add_geographic_regions(self):
        """Test adding geographic regions to map"""
        fig = self.map_viz.create_base_map()
        regions = {
            'Test Region': {
                'bounds': {'north': 20, 'south': 10, 'east': 80, 'west': 70},
                'color': 'red'
            }
        }
        
        result_fig = self.map_viz.add_geographic_regions(fig, regions)
        
        # Should have added one trace for the region
        assert len(result_fig.data) == 1
        assert result_fig.data[0].type == 'scattergeo'
        assert result_fig.data[0].mode == 'lines'
    
    def test_create_density_heatmap_empty_data(self):
        """Test density heatmap with empty data"""
        empty_data = pd.DataFrame()
        
        fig = self.map_viz.create_density_heatmap(empty_data)
        
        # Should return base map
        assert isinstance(fig, go.Figure)
    
    def test_create_density_heatmap_valid_data(self):
        """Test density heatmap with valid data"""
        fig = self.map_viz.create_density_heatmap(self.sample_float_data)
        
        assert isinstance(fig, go.Figure)
        # Should have mapbox layout for density map
        assert fig.layout.mapbox is not None
    
    def test_handle_map_interactions(self):
        """Test map interaction handling"""
        fig = self.map_viz.create_base_map()
        
        interactions = self.map_viz.handle_map_interactions(fig)
        
        assert isinstance(interactions, dict)
        assert 'selected_floats' in interactions
        assert 'clicked_location' in interactions
        assert 'zoom_level' in interactions
        assert 'center' in interactions

if __name__ == "__main__":
    pytest.main([__file__])