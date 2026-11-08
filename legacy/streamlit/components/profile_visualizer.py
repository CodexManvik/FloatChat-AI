"""
Profile Visualization Component
Creates oceanographic profile plots for temperature, salinity, and BGC parameters
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from datetime import datetime
from dashboard_config import dashboard_config
from utils.dashboard_utils import format_oceanographic_units, create_color_scale

logger = logging.getLogger(__name__)

class ProfileVisualizer:
    """Creates oceanographic profile visualizations"""
    
    def __init__(self):
        self.config = dashboard_config
        self.colors = self.config.GOVERNMENT_COLORS
        
    def create_ts_profile(self, profile_data: pd.DataFrame, float_id: Optional[str] = None) -> go.Figure:
        """Create temperature-salinity-depth profile plots"""
        
        if profile_data.empty:
            return self._create_empty_plot("No profile data available")
        
        # Ensure required columns exist
        required_cols = ['depth', 'temperature', 'salinity']
        missing_cols = [col for col in required_cols if col not in profile_data.columns]
        if missing_cols:
            return self._create_empty_plot(f"Missing columns: {', '.join(missing_cols)}")
        
        # Remove rows with missing critical data
        clean_data = profile_data.dropna(subset=['depth']).copy()
        if clean_data.empty:
            return self._create_empty_plot("No valid depth data")
        
        # Sort by depth for proper profile display
        clean_data = clean_data.sort_values('depth')
        
        # Create subplot with secondary y-axis
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Temperature Profile', 'Salinity Profile'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}]],
            horizontal_spacing=0.1
        )
        
        # Temperature profile
        temp_data = clean_data.dropna(subset=['temperature'])
        if not temp_data.empty:
            fig.add_trace(
                go.Scatter(
                    x=temp_data['temperature'],
                    y=-temp_data['depth'],  # Negative for oceanographic convention
                    mode='lines+markers',
                    name='Temperature',
                    line=dict(color=self.colors['primary'], width=3),
                    marker=dict(size=6, color=self.colors['primary']),
                    hovertemplate='<b>Temperature Profile</b><br>' +
                                 'Depth: %{y:.1f}m<br>' +
                                 'Temperature: %{x:.2f}°C<extra></extra>'
                ),
                row=1, col=1
            )
        
        # Salinity profile
        sal_data = clean_data.dropna(subset=['salinity'])
        if not sal_data.empty:
            fig.add_trace(
                go.Scatter(
                    x=sal_data['salinity'],
                    y=-sal_data['depth'],  # Negative for oceanographic convention
                    mode='lines+markers',
                    name='Salinity',
                    line=dict(color=self.colors['secondary'], width=3),
                    marker=dict(size=6, color=self.colors['secondary']),
                    hovertemplate='<b>Salinity Profile</b><br>' +
                                 'Depth: %{y:.1f}m<br>' +
                                 'Salinity: %{x:.2f} PSU<extra></extra>'
                ),
                row=1, col=2
            )
        
        # Update layout
        title_text = f"Oceanographic Profile - {float_id}" if float_id else "Oceanographic Profile"
        
        fig.update_layout(
            title=dict(
                text=title_text,
                x=0.5,
                font=dict(size=18, color=self.colors['primary'])
            ),
            height=600,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        # Update x and y axes
        fig.update_xaxes(title_text="Temperature (°C)", row=1, col=1, gridcolor='lightgray')
        fig.update_xaxes(title_text="Salinity (PSU)", row=1, col=2, gridcolor='lightgray')
        fig.update_yaxes(title_text="Depth (m)", row=1, col=1, gridcolor='lightgray')
        fig.update_yaxes(title_text="Depth (m)", row=1, col=2, gridcolor='lightgray')
        
        return fig
    
    def create_comparison_plot(self, profiles: List[pd.DataFrame], 
                             profile_labels: Optional[List[str]] = None) -> go.Figure:
        """Create multi-profile comparison overlays"""
        
        if not profiles or all(df.empty for df in profiles):
            return self._create_empty_plot("No profile data for comparison")
        
        # Color palette for different profiles
        colors = px.colors.qualitative.Set3
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Temperature Comparison', 'Salinity Comparison'),
            horizontal_spacing=0.1
        )
        
        for i, profile_data in enumerate(profiles):
            if profile_data.empty:
                continue
            
            # Get label for this profile
            if profile_labels and i < len(profile_labels):
                label = profile_labels[i]
            else:
                label = f"Profile {i+1}"
            
            color = colors[i % len(colors)]
            
            # Clean and sort data
            clean_data = profile_data.dropna(subset=['depth']).sort_values('depth')
            
            # Temperature comparison
            temp_data = clean_data.dropna(subset=['temperature'])
            if not temp_data.empty:
                fig.add_trace(
                    go.Scatter(
                        x=temp_data['temperature'],
                        y=-temp_data['depth'],
                        mode='lines+markers',
                        name=f'{label} - Temp',
                        line=dict(color=color, width=2),
                        marker=dict(size=4, color=color),
                        hovertemplate=f'<b>{label}</b><br>' +
                                     'Depth: %{y:.1f}m<br>' +
                                     'Temperature: %{x:.2f}°C<extra></extra>'
                    ),
                    row=1, col=1
                )
            
            # Salinity comparison
            sal_data = clean_data.dropna(subset=['salinity'])
            if not sal_data.empty:
                fig.add_trace(
                    go.Scatter(
                        x=sal_data['salinity'],
                        y=-sal_data['depth'],
                        mode='lines+markers',
                        name=f'{label} - Sal',
                        line=dict(color=color, width=2, dash='dot'),
                        marker=dict(size=4, color=color, symbol='square'),
                        hovertemplate=f'<b>{label}</b><br>' +
                                     'Depth: %{y:.1f}m<br>' +
                                     'Salinity: %{x:.2f} PSU<extra></extra>'
                    ),
                    row=1, col=2
                )
        
        # Update layout
        fig.update_layout(
            title=dict(
                text="Profile Comparison Analysis",
                x=0.5,
                font=dict(size=18, color=self.colors['primary'])
            ),
            height=600,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        # Update axes
        fig.update_xaxes(title_text="Temperature (°C)", row=1, col=1, gridcolor='lightgray')
        fig.update_xaxes(title_text="Salinity (PSU)", row=1, col=2, gridcolor='lightgray')
        fig.update_yaxes(title_text="Depth (m)", row=1, col=1, gridcolor='lightgray')
        fig.update_yaxes(title_text="Depth (m)", row=1, col=2, gridcolor='lightgray')
        
        return fig
    
    def create_bgc_plots(self, bgc_data: pd.DataFrame, parameters: Optional[List[str]] = None) -> List[go.Figure]:
        """Create BGC parameter visualization plots"""
        
        if bgc_data.empty:
            return [self._create_empty_plot("No BGC data available")]
        
        # Default BGC parameters to plot
        if parameters is None:
            parameters = ['oxygen', 'ph', 'chlorophyll']
        
        # Filter to available parameters
        available_params = [p for p in parameters if p in bgc_data.columns]
        
        if not available_params:
            return [self._create_empty_plot("No BGC parameters available")]
        
        figures = []
        
        for param in available_params:
            fig = self._create_single_bgc_plot(bgc_data, param)
            figures.append(fig)
        
        return figures
    
    def _create_single_bgc_plot(self, data: pd.DataFrame, parameter: str) -> go.Figure:
        """Create a single BGC parameter plot"""
        
        # Clean data
        clean_data = data.dropna(subset=['depth', parameter]).sort_values('depth')
        
        if clean_data.empty:
            return self._create_empty_plot(f"No valid {parameter} data")
        
        # Get parameter-specific settings
        param_config = self._get_bgc_parameter_config(parameter)
        
        fig = go.Figure()
        
        # Add main profile line
        fig.add_trace(
            go.Scatter(
                x=clean_data[parameter],
                y=-clean_data['depth'],
                mode='lines+markers',
                name=param_config['name'],
                line=dict(color=param_config['color'], width=3),
                marker=dict(size=6, color=param_config['color']),
                hovertemplate=f'<b>{param_config["name"]} Profile</b><br>' +
                             'Depth: %{y:.1f}m<br>' +
                             f'{param_config["name"]}: %{{x:.{param_config["precision"]}f}} {param_config["unit"]}<extra></extra>'
            )
        )
        
        # Add reference lines if applicable
        if 'reference_lines' in param_config:
            for ref_line in param_config['reference_lines']:
                fig.add_vline(
                    x=ref_line['value'],
                    line_dash="dash",
                    line_color="gray",
                    annotation_text=ref_line['label'],
                    annotation_position="top"
                )
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f"{param_config['name']} Depth Profile",
                x=0.5,
                font=dict(size=16, color=self.colors['primary'])
            ),
            xaxis_title=f"{param_config['name']} ({param_config['unit']})",
            yaxis_title="Depth (m)",
            height=500,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor='lightgray'),
            yaxis=dict(gridcolor='lightgray')
        )
        
        return fig
    
    def create_ts_diagram(self, profile_data: pd.DataFrame) -> go.Figure:
        """Create Temperature-Salinity diagram with depth coloring"""
        
        if profile_data.empty:
            return self._create_empty_plot("No T-S data available")
        
        # Clean data
        ts_data = profile_data.dropna(subset=['temperature', 'salinity', 'depth'])
        
        if ts_data.empty:
            return self._create_empty_plot("No valid T-S data")
        
        fig = go.Figure()
        
        # Create T-S scatter plot with depth coloring
        fig.add_trace(
            go.Scatter(
                x=ts_data['salinity'],
                y=ts_data['temperature'],
                mode='markers+lines',
                marker=dict(
                    size=8,
                    color=ts_data['depth'],
                    colorscale='Viridis_r',  # Reverse so shallow is yellow, deep is purple
                    colorbar=dict(
                        title=dict(text="Depth (m)", side="right")
                    ),
                    line=dict(width=1, color='white')
                ),
                line=dict(width=2, color='rgba(100,100,100,0.5)'),
                name='T-S Profile',
                hovertemplate='<b>T-S Diagram</b><br>' +
                             'Salinity: %{x:.2f} PSU<br>' +
                             'Temperature: %{y:.2f}°C<br>' +
                             'Depth: %{marker.color:.1f}m<extra></extra>'
            )
        )
        
        # Add density contours if data is sufficient
        if len(ts_data) > 10:
            self._add_density_contours(fig, ts_data)
        
        # Update layout
        fig.update_layout(
            title=dict(
                text="Temperature-Salinity Diagram",
                x=0.5,
                font=dict(size=16, color=self.colors['primary'])
            ),
            xaxis_title="Salinity (PSU)",
            yaxis_title="Temperature (°C)",
            height=500,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor='lightgray'),
            yaxis=dict(gridcolor='lightgray')
        )
        
        return fig
    
    def add_statistical_overlays(self, fig: go.Figure, stats: Dict[str, Any]) -> go.Figure:
        """Add statistical overlays to existing plots"""
        
        if not stats:
            return fig
        
        # Add mean lines
        if 'mean_temperature' in stats:
            fig.add_vline(
                x=stats['mean_temperature'],
                line_dash="dash",
                line_color="red",
                annotation_text=f"Mean: {stats['mean_temperature']:.2f}°C",
                annotation_position="top"
            )
        
        if 'mean_salinity' in stats:
            fig.add_vline(
                x=stats['mean_salinity'],
                line_dash="dash",
                line_color="blue",
                annotation_text=f"Mean: {stats['mean_salinity']:.2f} PSU",
                annotation_position="top"
            )
        
        # Add standard deviation bands
        if 'std_temperature' in stats and 'mean_temperature' in stats:
            mean_temp = stats['mean_temperature']
            std_temp = stats['std_temperature']
            
            fig.add_vrect(
                x0=mean_temp - std_temp,
                x1=mean_temp + std_temp,
                fillcolor="red",
                opacity=0.1,
                line_width=0,
                annotation_text="±1σ"
            )
        
        return fig
    
    def _create_empty_plot(self, message: str) -> go.Figure:
        """Create an empty plot with a message"""
        
        fig = go.Figure()
        
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            xanchor='center', yanchor='middle',
            font=dict(size=16, color='gray'),
            showarrow=False
        )
        
        fig.update_layout(
            title="Profile Visualization",
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        
        return fig
    
    def _get_bgc_parameter_config(self, parameter: str) -> Dict[str, Any]:
        """Get configuration for BGC parameters"""
        
        configs = {
            'oxygen': {
                'name': 'Dissolved Oxygen',
                'unit': 'ml/L',
                'color': '#1f77b4',
                'precision': 2,
                'reference_lines': [
                    {'value': 2.0, 'label': 'Hypoxic threshold'},
                    {'value': 6.0, 'label': 'Well-oxygenated'}
                ]
            },
            'ph': {
                'name': 'pH',
                'unit': '',
                'color': '#ff7f0e',
                'precision': 2,
                'reference_lines': [
                    {'value': 8.1, 'label': 'Surface ocean pH'}
                ]
            },
            'chlorophyll': {
                'name': 'Chlorophyll-a',
                'unit': 'mg/m³',
                'color': '#2ca02c',
                'precision': 3
            },
            'nitrate': {
                'name': 'Nitrate',
                'unit': 'μmol/kg',
                'color': '#d62728',
                'precision': 1
            },
            'backscatter': {
                'name': 'Backscatter',
                'unit': 'm⁻¹',
                'color': '#9467bd',
                'precision': 4
            }
        }
        
        return configs.get(parameter, {
            'name': parameter.title(),
            'unit': '',
            'color': '#17becf',
            'precision': 2
        })
    
    def _add_density_contours(self, fig: go.Figure, ts_data: pd.DataFrame) -> None:
        """Add density contours to T-S diagram"""
        
        try:
            # Create a grid for density calculation
            sal_range = np.linspace(ts_data['salinity'].min(), ts_data['salinity'].max(), 50)
            temp_range = np.linspace(ts_data['temperature'].min(), ts_data['temperature'].max(), 50)
            
            sal_grid, temp_grid = np.meshgrid(sal_range, temp_range)
            
            # Simplified density calculation (UNESCO 1983 approximation)
            # This is a simplified version - in production, use proper seawater library
            density = 1000 + 0.8 * (sal_grid - 35) - 0.2 * (temp_grid - 15)
            
            # Add contour lines
            fig.add_trace(
                go.Contour(
                    x=sal_range,
                    y=temp_range,
                    z=density,
                    showscale=False,
                    contours=dict(
                        showlabels=True,
                        labelfont=dict(size=10, color='gray')
                    ),
                    line=dict(color='gray', width=1),
                    opacity=0.3,
                    name='Density (kg/m³)'
                )
            )
        
        except Exception as e:
            logger.warning(f"Could not add density contours: {e}")
    
    def render_profile_controls(self) -> Dict[str, Any]:
        """Render profile visualization controls"""
        
        st.subheader("📈 Profile Controls")
        
        col1, col2 = st.columns(2)
        
        with col1:
            plot_type = st.selectbox(
                "Plot Type",
                ["Individual Profiles", "Profile Comparison", "T-S Diagram", "BGC Parameters"],
                key="profile_plot_type"
            )
            
            show_statistics = st.checkbox("Show Statistics", value=True, key="show_stats")
            
        with col2:
            depth_range = st.slider(
                "Depth Range (m)",
                min_value=0,
                max_value=2000,
                value=(0, 1000),
                step=50,
                key="profile_depth_range"
            )
            
            smooth_profiles = st.checkbox("Smooth Profiles", value=False, key="smooth_profiles")
        
        # BGC parameter selection
        if plot_type == "BGC Parameters":
            st.subheader("BGC Parameters")
            bgc_params = st.multiselect(
                "Select Parameters",
                ["oxygen", "ph", "chlorophyll", "nitrate", "backscatter"],
                default=["oxygen", "ph", "chlorophyll"],
                key="bgc_params"
            )
        else:
            bgc_params = []
        
        # Profile comparison settings
        if plot_type == "Profile Comparison":
            max_profiles = st.slider(
                "Max Profiles to Compare",
                min_value=2,
                max_value=10,
                value=5,
                key="max_comparison_profiles"
            )
        else:
            max_profiles = 5
        
        return {
            "plot_type": plot_type,
            "show_statistics": show_statistics,
            "depth_range": depth_range,
            "smooth_profiles": smooth_profiles,
            "bgc_parameters": bgc_params,
            "max_profiles": max_profiles
        }