"""
Interactive Map Visualization Component
Displays ARGO float locations, trajectories, and geographic data using Plotly
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
from dashboard_config import dashboard_config

logger = logging.getLogger(__name__)

class InteractiveMap:
    """Interactive map component for ARGO float visualization"""
    
    def __init__(self):
        self.config = dashboard_config
        self.default_center = self.config.DEFAULT_MAP_CENTER
        self.default_zoom = self.config.DEFAULT_MAP_ZOOM
        
    def create_base_map(self, center: Optional[Tuple[float, float]] = None, zoom: Optional[int] = None) -> go.Figure:
        """Create base map with oceanographic styling"""
        
        if center is None:
            center = self.default_center
        if zoom is None:
            zoom = self.default_zoom
            
        fig = go.Figure()
        
        # Configure map layout with oceanographic theme
        fig.update_layout(
            geo=dict(
                projection_type='natural earth',
                showland=True,
                landcolor='rgb(243, 243, 243)',
                coastlinecolor='rgb(204, 204, 204)',
                showocean=True,
                oceancolor='rgb(230, 245, 255)',
                showlakes=True,
                lakecolor='rgb(230, 245, 255)',
                showrivers=True,
                rivercolor='rgb(230, 245, 255)',
                center=dict(lat=center[0], lon=center[1]),
                projection_scale=zoom/3,
                showframe=False,
                showcoastlines=True,
                bgcolor='rgba(0,0,0,0)'
            ),
            title=dict(
                text="ARGO Float Locations",
                x=0.5,
                font=dict(size=20, color=self.config.GOVERNMENT_COLORS['primary'])
            ),
            margin=dict(l=0, r=0, t=50, b=0),
            height=600,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return fig
    
    def add_float_markers(self, fig: go.Figure, float_data: pd.DataFrame, 
                         show_labels: bool = True, cluster_distance: float = 2.0) -> go.Figure:
        """Add ARGO float markers to the map with clustering support"""
        
        if float_data.empty:
            return fig
        
        # Ensure required columns exist
        required_cols = ['lat', 'lon', 'float_id']
        if not all(col in float_data.columns for col in required_cols):
            logger.error(f"Missing required columns. Need: {required_cols}")
            return fig
        
        # Remove invalid coordinates
        valid_data = float_data[
            (float_data['lat'].between(-90, 90)) & 
            (float_data['lon'].between(-180, 180)) &
            float_data['lat'].notna() & 
            float_data['lon'].notna()
        ].copy()
        
        if valid_data.empty:
            return fig
        
        # Cluster nearby floats if requested
        if cluster_distance > 0:
            clustered_data = self._cluster_floats(valid_data, cluster_distance)
        else:
            clustered_data = valid_data
        
        # Create hover text
        hover_text = []
        for _, row in clustered_data.iterrows():
            if 'cluster_size' in row and row['cluster_size'] > 1:
                # Clustered marker
                text = f"<b>Float Cluster</b><br>"
                text += f"Floats: {int(row['cluster_size'])}<br>"
                text += f"Location: {row['lat']:.3f}°, {row['lon']:.3f}°"
            else:
                # Individual float
                text = f"<b>Float {row['float_id']}</b><br>"
                text += f"Location: {row['lat']:.3f}°, {row['lon']:.3f}°<br>"
                
                if 'wmo_id' in row and pd.notna(row['wmo_id']):
                    text += f"WMO ID: {int(row['wmo_id'])}<br>"
                
                if 'cycle_number' in row and pd.notna(row['cycle_number']):
                    text += f"Cycle: {int(row['cycle_number'])}<br>"
                
                if 'profile_date' in row and pd.notna(row['profile_date']):
                    if isinstance(row['profile_date'], str):
                        text += f"Last Profile: {row['profile_date']}<br>"
                    else:
                        text += f"Last Profile: {row['profile_date'].strftime('%Y-%m-%d')}<br>"
            
            hover_text.append(text)
        
        # Determine marker sizes and colors
        if 'cluster_size' in clustered_data.columns:
            # Size based on cluster size
            sizes = np.where(clustered_data['cluster_size'] > 1, 
                           np.minimum(clustered_data['cluster_size'] * 3 + 8, 25),
                           12)
            colors = np.where(clustered_data['cluster_size'] > 1, 
                            'orange', self.config.GOVERNMENT_COLORS['primary'])
        else:
            sizes = [12] * len(clustered_data)
            colors = [self.config.GOVERNMENT_COLORS['primary']] * len(clustered_data)
        
        # Add scatter trace
        fig.add_trace(go.Scattergeo(
            lon=clustered_data['lon'],
            lat=clustered_data['lat'],
            mode='markers',
            marker=dict(
                size=sizes,
                color=colors,
                line=dict(width=2, color='white'),
                opacity=0.8,
                sizemode='diameter'
            ),
            text=hover_text,
            hovertemplate='%{text}<extra></extra>',
            name='ARGO Floats',
            customdata=clustered_data[['float_id']].values if 'float_id' in clustered_data.columns else None
        ))
        
        return fig
    
    def add_trajectories(self, fig: go.Figure, trajectory_data: pd.DataFrame, 
                        float_ids: Optional[List[str]] = None, max_trajectories: int = 10) -> go.Figure:
        """Add float trajectory paths with temporal coloring"""
        
        if trajectory_data.empty:
            return fig
        
        # Filter by specific float IDs if provided
        if float_ids:
            trajectory_data = trajectory_data[trajectory_data['float_id'].isin(float_ids)]
        
        # Limit number of trajectories for performance
        unique_floats = trajectory_data['float_id'].unique()
        if len(unique_floats) > max_trajectories:
            unique_floats = unique_floats[:max_trajectories]
            trajectory_data = trajectory_data[trajectory_data['float_id'].isin(unique_floats)]
        
        # Color palette for trajectories
        colors = px.colors.qualitative.Set3
        
        for i, float_id in enumerate(unique_floats):
            float_traj = trajectory_data[trajectory_data['float_id'] == float_id].copy()
            
            if len(float_traj) < 2:  # Need at least 2 points for a trajectory
                continue
            
            # Sort by time if available
            if 'time' in float_traj.columns:
                float_traj = float_traj.sort_values('time')
            elif 'profile_date' in float_traj.columns:
                float_traj = float_traj.sort_values('profile_date')
            
            # Remove invalid coordinates
            float_traj = float_traj[
                (float_traj['lat'].between(-90, 90)) & 
                (float_traj['lon'].between(-180, 180)) &
                float_traj['lat'].notna() & 
                float_traj['lon'].notna()
            ]
            
            if len(float_traj) < 2:
                continue
            
            color = colors[i % len(colors)]
            
            # Add trajectory line
            fig.add_trace(go.Scattergeo(
                lon=float_traj['lon'],
                lat=float_traj['lat'],
                mode='lines+markers',
                line=dict(width=2, color=color),
                marker=dict(size=6, color=color, opacity=0.7),
                name=f'Float {float_id}',
                hovertemplate=f'<b>Float {float_id}</b><br>' +
                             'Lat: %{lat:.3f}°<br>' +
                             'Lon: %{lon:.3f}°<extra></extra>',
                showlegend=True
            ))
            
            # Add start and end markers
            if len(float_traj) > 0:
                # Start marker (green)
                fig.add_trace(go.Scattergeo(
                    lon=[float_traj.iloc[0]['lon']],
                    lat=[float_traj.iloc[0]['lat']],
                    mode='markers',
                    marker=dict(size=10, color='green', symbol='circle', 
                               line=dict(width=2, color='white')),
                    name=f'{float_id} Start',
                    hovertemplate=f'<b>Float {float_id} - Start</b><br>' +
                                 'Lat: %{lat:.3f}°<br>' +
                                 'Lon: %{lon:.3f}°<extra></extra>',
                    showlegend=False
                ))
                
                # End marker (red)
                fig.add_trace(go.Scattergeo(
                    lon=[float_traj.iloc[-1]['lon']],
                    lat=[float_traj.iloc[-1]['lat']],
                    mode='markers',
                    marker=dict(size=10, color='red', symbol='circle',
                               line=dict(width=2, color='white')),
                    name=f'{float_id} End',
                    hovertemplate=f'<b>Float {float_id} - Latest</b><br>' +
                                 'Lat: %{lat:.3f}°<br>' +
                                 'Lon: %{lon:.3f}°<extra></extra>',
                    showlegend=False
                ))
        
        return fig
    
    def add_geographic_regions(self, fig: go.Figure, regions: Dict[str, Dict]) -> go.Figure:
        """Add predefined geographic regions as overlays"""
        
        for region_name, region_data in regions.items():
            if 'bounds' in region_data:
                bounds = region_data['bounds']
                
                # Create rectangle for region
                fig.add_trace(go.Scattergeo(
                    lon=[bounds['west'], bounds['east'], bounds['east'], bounds['west'], bounds['west']],
                    lat=[bounds['south'], bounds['south'], bounds['north'], bounds['north'], bounds['south']],
                    mode='lines',
                    line=dict(width=2, color=region_data.get('color', 'red'), dash='dash'),
                    name=region_name,
                    hovertemplate=f'<b>{region_name}</b><extra></extra>',
                    showlegend=True
                ))
        
        return fig
    
    def handle_map_interactions(self, fig: go.Figure) -> Dict[str, Any]:
        """Handle map click and selection events"""
        
        # This will be enhanced with Streamlit's plotly_events when available
        # For now, return basic interaction data
        
        return {
            'selected_floats': [],
            'clicked_location': None,
            'zoom_level': self.default_zoom,
            'center': self.default_center
        }
    
    def _cluster_floats(self, float_data: pd.DataFrame, distance_threshold: float) -> pd.DataFrame:
        """Simple clustering of nearby floats for better visualization"""
        
        if len(float_data) <= 1:
            return float_data
        
        clustered_data = []
        processed = set()
        
        for idx, row in float_data.iterrows():
            if idx in processed:
                continue
            
            # Find nearby floats
            distances = np.sqrt(
                (float_data['lat'] - row['lat'])**2 + 
                (float_data['lon'] - row['lon'])**2
            )
            
            nearby_indices = distances[distances <= distance_threshold].index
            nearby_floats = float_data.loc[nearby_indices]
            
            if len(nearby_floats) > 1:
                # Create cluster
                cluster_center_lat = nearby_floats['lat'].mean()
                cluster_center_lon = nearby_floats['lon'].mean()
                
                cluster_row = row.copy()
                cluster_row['lat'] = cluster_center_lat
                cluster_row['lon'] = cluster_center_lon
                cluster_row['cluster_size'] = len(nearby_floats)
                cluster_row['float_id'] = f"Cluster_{len(clustered_data)}"
                
                clustered_data.append(cluster_row)
                processed.update(nearby_indices)
            else:
                # Individual float
                individual_row = row.copy()
                individual_row['cluster_size'] = 1
                clustered_data.append(individual_row)
                processed.add(idx)
        
        return pd.DataFrame(clustered_data)
    
    def create_density_heatmap(self, float_data: pd.DataFrame, resolution: int = 50) -> go.Figure:
        """Create a density heatmap of float locations"""
        
        if float_data.empty or 'lat' not in float_data.columns or 'lon' not in float_data.columns:
            return self.create_base_map()
        
        # Remove invalid coordinates
        valid_data = float_data[
            (float_data['lat'].between(-90, 90)) & 
            (float_data['lon'].between(-180, 180)) &
            float_data['lat'].notna() & 
            float_data['lon'].notna()
        ]
        
        if valid_data.empty:
            return self.create_base_map()
        
        # Create base map
        fig = self.create_base_map()
        
        # Add density heatmap
        fig.add_trace(go.Densitymapbox(
            lat=valid_data['lat'],
            lon=valid_data['lon'],
            z=[1] * len(valid_data),  # Equal weight for all points
            radius=20,
            colorscale='Blues',
            showscale=True,
            colorbar=dict(title="Float Density"),
            hovertemplate='Density: %{z}<extra></extra>'
        ))
        
        # Update layout for mapbox
        fig.update_layout(
            mapbox=dict(
                style='open-street-map',
                center=dict(lat=self.default_center[0], lon=self.default_center[1]),
                zoom=self.default_zoom-1
            ),
            height=600
        )
        
        return fig
    
    def get_predefined_regions(self) -> Dict[str, Dict]:
        """Get predefined oceanographic regions"""
        
        return {
            "Indian Ocean": {
                "bounds": {"north": 30, "south": -60, "east": 120, "west": 20},
                "color": "blue",
                "description": "Indian Ocean region with high ARGO coverage"
            },
            "Arabian Sea": {
                "bounds": {"north": 25, "south": 5, "east": 75, "west": 50},
                "color": "green", 
                "description": "Arabian Sea - monsoon influenced region"
            },
            "Bay of Bengal": {
                "bounds": {"north": 22, "south": 5, "east": 95, "west": 80},
                "color": "orange",
                "description": "Bay of Bengal - river influenced region"
            },
            "Equatorial Indian Ocean": {
                "bounds": {"north": 10, "south": -10, "east": 100, "west": 50},
                "color": "red",
                "description": "Equatorial region with strong currents"
            }
        }
    
    def render_map_controls(self) -> Dict[str, Any]:
        """Render map control widgets and return settings"""
        
        st.subheader("🗺️ Map Controls")
        
        col1, col2 = st.columns(2)
        
        with col1:
            show_trajectories = st.checkbox("Show Trajectories", value=False, key="show_traj")
            show_clusters = st.checkbox("Cluster Nearby Floats", value=True, key="cluster_floats")
            show_regions = st.checkbox("Show Regions", value=False, key="show_regions")
        
        with col2:
            map_style = st.selectbox(
                "Map Style",
                ["Oceanographic", "Satellite", "Terrain", "Simple"],
                key="map_style"
            )
            
            max_floats = st.slider(
                "Max Floats to Display",
                min_value=10,
                max_value=500,
                value=100,
                step=10,
                key="max_floats"
            )
        
        # Advanced controls in expander
        with st.expander("Advanced Map Settings"):
            cluster_distance = st.slider(
                "Clustering Distance (degrees)",
                min_value=0.5,
                max_value=5.0,
                value=2.0,
                step=0.5,
                key="cluster_distance"
            )
            
            trajectory_limit = st.slider(
                "Max Trajectories",
                min_value=1,
                max_value=20,
                value=10,
                key="traj_limit"
            )
            
            show_density = st.checkbox("Show Density Heatmap", value=False, key="show_density")
        
        return {
            "show_trajectories": show_trajectories,
            "show_clusters": show_clusters,
            "show_regions": show_regions,
            "map_style": map_style,
            "max_floats": max_floats,
            "cluster_distance": cluster_distance if show_clusters else 0,
            "trajectory_limit": trajectory_limit,
            "show_density": show_density
        }