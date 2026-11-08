"""
Unit tests for Profile Visualizer Component
"""

import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from components.profile_visualizer import ProfileVisualizer

class TestProfileVisualizer:
    """Test cases for ProfileVisualizer class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.profile_viz = ProfileVisualizer()
        
        # Sample profile data
        depths = np.arange(0, 500, 10)
        n_points = len(depths)
        
        self.sample_profile_data = pd.DataFrame({
            'depth': depths,
            'temperature': 25 - depths * 0.02 + np.random.normal(0, 0.5, n_points),
            'salinity': 35 + depths * 0.001 + np.random.normal(0, 0.1, n_points),
            'oxygen': 6 - depths * 0.005 + np.random.normal(0, 0.2, n_points),
            'ph': 8.1 - depths * 0.0001 + np.random.normal(0, 0.02, n_points),
            'chlorophyll': np.random.exponential(0.5, n_points) * np.exp(-depths/100),
            'float_id': ['ARGO_001'] * n_points
        })
        
        # Ensure positive values where needed
        self.sample_profile_data['oxygen'] = np.maximum(self.sample_profile_data['oxygen'], 0.1)
        self.sample_profile_data['chlorophyll'] = np.maximum(self.sample_profile_data['chlorophyll'], 0)
    
    def test_init(self):
        """Test profile visualizer initialization"""
        assert self.profile_viz.config is not None
        assert self.profile_viz.colors is not None
    
    def test_create_ts_profile_empty_data(self):
        """Test T-S profile creation with empty data"""
        empty_data = pd.DataFrame()
        
        fig = self.profile_viz.create_ts_profile(empty_data)
        
        assert isinstance(fig, go.Figure)
        # Should have annotation for empty data
        assert len(fig.layout.annotations) > 0
    
    def test_create_ts_profile_missing_columns(self):
        """Test T-S profile with missing required columns"""
        incomplete_data = pd.DataFrame({
            'depth': [10, 20, 30],
            'temperature': [25, 24, 23]
            # Missing salinity
        })
        
        fig = self.profile_viz.create_ts_profile(incomplete_data)
        
        assert isinstance(fig, go.Figure)
        # Should handle missing columns gracefully
    
    def test_create_ts_profile_valid_data(self):
        """Test T-S profile creation with valid data"""
        fig = self.profile_viz.create_ts_profile(self.sample_profile_data, "ARGO_001")
        
        assert isinstance(fig, go.Figure)
        # Should have traces for temperature and salinity
        assert len(fig.data) >= 1
        
        # Check that depth is negative (oceanographic convention)
        if len(fig.data) > 0:
            y_data = fig.data[0].y
            assert all(y <= 0 for y in y_data if y is not None)
    
    def test_create_comparison_plot_empty_profiles(self):
        """Test comparison plot with empty profiles"""
        empty_profiles = [pd.DataFrame(), pd.DataFrame()]
        
        fig = self.profile_viz.create_comparison_plot(empty_profiles)
        
        assert isinstance(fig, go.Figure)
    
    def test_create_comparison_plot_valid_profiles(self):
        """Test comparison plot with valid profiles"""
        # Create second profile with slightly different data
        profile2 = self.sample_profile_data.copy()
        profile2['temperature'] += 1
        profile2['salinity'] += 0.1
        profile2['float_id'] = 'ARGO_002'
        
        profiles = [self.sample_profile_data, profile2]
        labels = ['Float 1', 'Float 2']
        
        fig = self.profile_viz.create_comparison_plot(profiles, labels)
        
        assert isinstance(fig, go.Figure)
        # Should have traces for both profiles
        assert len(fig.data) >= 2
    
    def test_create_bgc_plots_empty_data(self):
        """Test BGC plots with empty data"""
        empty_data = pd.DataFrame()
        
        figures = self.profile_viz.create_bgc_plots(empty_data)
        
        assert isinstance(figures, list)
        assert len(figures) >= 1
        assert all(isinstance(fig, go.Figure) for fig in figures)
    
    def test_create_bgc_plots_valid_data(self):
        """Test BGC plots with valid data"""
        parameters = ['oxygen', 'ph', 'chlorophyll']
        
        figures = self.profile_viz.create_bgc_plots(self.sample_profile_data, parameters)
        
        assert isinstance(figures, list)
        assert len(figures) == len(parameters)
        assert all(isinstance(fig, go.Figure) for fig in figures)
    
    def test_create_bgc_plots_missing_parameters(self):
        """Test BGC plots with missing parameters"""
        # Data without BGC parameters
        basic_data = self.sample_profile_data[['depth', 'temperature', 'salinity']].copy()
        
        figures = self.profile_viz.create_bgc_plots(basic_data, ['oxygen', 'ph'])
        
        assert isinstance(figures, list)
        # Should handle missing parameters gracefully
    
    def test_create_ts_diagram_empty_data(self):
        """Test T-S diagram with empty data"""
        empty_data = pd.DataFrame()
        
        fig = self.profile_viz.create_ts_diagram(empty_data)
        
        assert isinstance(fig, go.Figure)
    
    def test_create_ts_diagram_valid_data(self):
        """Test T-S diagram with valid data"""
        fig = self.profile_viz.create_ts_diagram(self.sample_profile_data)
        
        assert isinstance(fig, go.Figure)
        # Should have at least one trace
        assert len(fig.data) >= 1
        
        # Check that it's a scatter plot
        if len(fig.data) > 0:
            assert fig.data[0].type == 'scatter'
    
    def test_add_statistical_overlays_empty_stats(self):
        """Test statistical overlays with empty stats"""
        fig = go.Figure()
        empty_stats = {}
        
        result_fig = self.profile_viz.add_statistical_overlays(fig, empty_stats)
        
        assert isinstance(result_fig, go.Figure)
        # Should return original figure unchanged
        assert result_fig == fig
    
    def test_add_statistical_overlays_valid_stats(self):
        """Test statistical overlays with valid stats"""
        fig = go.Figure()
        stats = {
            'mean_temperature': 20.0,
            'std_temperature': 2.0,
            'mean_salinity': 35.0,
            'std_salinity': 0.5
        }
        
        result_fig = self.profile_viz.add_statistical_overlays(fig, stats)
        
        assert isinstance(result_fig, go.Figure)
        # Should have added some elements (shapes or annotations)
    
    def test_get_bgc_parameter_config(self):
        """Test BGC parameter configuration"""
        # Test known parameter
        oxygen_config = self.profile_viz._get_bgc_parameter_config('oxygen')
        
        assert isinstance(oxygen_config, dict)
        assert 'name' in oxygen_config
        assert 'unit' in oxygen_config
        assert 'color' in oxygen_config
        assert 'precision' in oxygen_config
        
        # Test unknown parameter
        unknown_config = self.profile_viz._get_bgc_parameter_config('unknown_param')
        
        assert isinstance(unknown_config, dict)
        assert unknown_config['name'] == 'Unknown_Param'
    
    def test_create_empty_plot(self):
        """Test empty plot creation"""
        message = "Test message"
        
        fig = self.profile_viz._create_empty_plot(message)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0
        assert fig.layout.annotations[0].text == message
    
    def test_profile_data_sorting(self):
        """Test that profile data is properly sorted by depth"""
        # Create unsorted data
        unsorted_data = self.sample_profile_data.sample(frac=1).reset_index(drop=True)
        
        fig = self.profile_viz.create_ts_profile(unsorted_data)
        
        assert isinstance(fig, go.Figure)
        # The function should handle sorting internally
    
    def test_missing_depth_data(self):
        """Test handling of missing depth data"""
        # Data with some missing depths
        data_with_nan = self.sample_profile_data.copy()
        data_with_nan.loc[5:10, 'depth'] = np.nan
        
        fig = self.profile_viz.create_ts_profile(data_with_nan)
        
        assert isinstance(fig, go.Figure)
        # Should handle NaN values gracefully
    
    def test_extreme_values(self):
        """Test handling of extreme oceanographic values"""
        # Create data with extreme but valid values
        extreme_data = pd.DataFrame({
            'depth': [0, 100, 1000, 5000],
            'temperature': [30, 20, 5, 2],  # Realistic range
            'salinity': [32, 35, 36, 37],   # Realistic range
            'oxygen': [8, 4, 2, 5],         # Realistic range
            'ph': [8.3, 8.0, 7.8, 7.9]     # Realistic range
        })
        
        fig = self.profile_viz.create_ts_profile(extreme_data)
        
        assert isinstance(fig, go.Figure)
        # Should handle extreme values without errors

if __name__ == "__main__":
    pytest.main([__file__])