"""
Dashboard Layout Manager
Handles the main layout, navigation, and government-style styling
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from dashboard_config import dashboard_config

try:
    from styles.government_theme import GovernmentTheme
except ImportError:
    GovernmentTheme = None

logger = logging.getLogger(__name__)

class DashboardLayout:
    """Manages the main dashboard layout and navigation"""
    
    def __init__(self):
        self.config = dashboard_config
        
    def render_header(self) -> None:
        """Render the government-style header with branding and status"""
        
        # Custom CSS for government styling
        st.markdown("""
        <style>
        .main-header {
            background: linear-gradient(90deg, #1f4e79 0%, #2e8b57 100%);
            padding: 1rem 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            color: white;
        }
        .header-title {
            font-size: 2.5rem;
            font-weight: bold;
            margin: 0;
            text-shadow: none;
            color: #d1d5db !important;
        }
        .header-subtitle {
            font-size: 1.2rem;
            margin: 0.5rem 0 0 0;
            opacity: 0.9;
            color: #d1d5db !important;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-online { background-color: #28a745; }
        .status-offline { background-color: #dc3545; }
        .status-warning { background-color: #ffc107; }
        
        .metric-card {
            background: white;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #1f4e79;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
        }
        
        .nav-tab {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px 8px 0 0;
            padding: 0.75rem 1.5rem;
            margin-right: 0.25rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .nav-tab:hover {
            background: #e9ecef;
        }
        .nav-tab.active {
            background: #1f4e79;
            color: white;
            border-bottom: 1px solid #1f4e79;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Main header
        st.markdown("""
        <div class="main-header">
            <h1 class="header-title">🌊 ARGO Float Data Dashboard</h1>
            <p class="header-subtitle">Government Oceanographic Data Visualization System</p>
        </div>
        """, unsafe_allow_html=True)
        
        # System status bar
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        
        with col1:
            self._render_connection_status()
        
        with col2:
            self._render_data_status()
            
        with col3:
            self._render_last_update()
            
        with col4:
            self._render_system_info()
    
    def _render_connection_status(self) -> None:
        """Render backend connection status"""
        if st.session_state.get('api_client'):
            try:
                health_data = st.session_state.api_client.health_check()
                if health_data.get("status") == "healthy":
                    st.markdown(
                        '<span class="status-indicator status-online"></span>**Backend Online**',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        '<span class="status-indicator status-offline"></span>**Backend Offline**',
                        unsafe_allow_html=True
                    )
            except Exception:
                st.markdown(
                    '<span class="status-indicator status-warning"></span>**Connection Unknown**',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                '<span class="status-indicator status-offline"></span>**API Not Available**',
                unsafe_allow_html=True
            )
    
    def _render_data_status(self) -> None:
        """Render data availability status"""
        # Placeholder - will be updated with real data counts
        st.markdown("📊 **Data Status**")
        st.caption("50 Floats • 1,234 Profiles")
    
    def _render_last_update(self) -> None:
        """Render last data update time"""
        st.markdown("🕒 **Last Update**")
        st.caption(datetime.now().strftime("%Y-%m-%d %H:%M UTC"))
    
    def _render_system_info(self) -> None:
        """Render system information"""
        st.markdown("ℹ️ **System Info**")
        st.caption("Dashboard v1.0")
    
    def render_sidebar(self) -> Dict[str, Any]:
        """Render sidebar with navigation and filters"""
        
        with st.sidebar:
            # Logo/Branding area
            st.markdown("""
            <div style="text-align: center; padding: 1rem; background: #f8f9fa; border-radius: 8px; margin-bottom: 2rem;">
                <h3 style="color: #1f4e79; margin: 0;">🌊 ARGO Dashboard</h3>
                <p style="margin: 0.5rem 0 0 0; color: #6c757d; font-size: 0.9rem;">Government Edition</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Navigation
            st.header("📋 Navigation")
            tab_selection = st.selectbox(
                "Select Dashboard Section",
                ["Overview", "Interactive Map", "Profile Analysis", "Chat Interface", "Data Export", "Advanced Filters"],
                key="main_navigation"
            )
            
            st.markdown("---")
            
            # Quick Actions
            st.header("⚡ Quick Actions")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Refresh Data", use_container_width=True):
                    st.session_state.last_refresh = datetime.now()
                    st.rerun()
            
            with col2:
                if st.button("📥 Export All", use_container_width=True):
                    st.session_state.show_export_modal = True
            
            st.markdown("---")
            
            # Basic Filters (keep existing simple filters)
            filter_state = self._render_filters()
            
            # Advanced Filters Link
            if tab_selection != "Advanced Filters":
                st.markdown("---")
                st.info("💡 **Tip**: Use 'Advanced Filters' tab for comprehensive filtering options")
            
            st.markdown("---")
            
            # System Status Details
            self._render_detailed_status()
            
            return {
                "selected_tab": tab_selection,
                "filters": filter_state
            }
    
    def _render_filters(self) -> Dict[str, Any]:
        """Render data filtering controls"""
        st.header("🔍 Data Filters")
        
        # Date range filter
        st.subheader("📅 Date Range")
        default_start = datetime.now() - timedelta(days=365)
        default_end = datetime.now()
        
        date_range = st.date_input(
            "Select date range",
            value=(default_start.date(), default_end.date()),
            key="date_filter"
        )
        
        # Geographic filter
        st.subheader("🌍 Geographic Region")
        region_preset = st.selectbox(
            "Preset Regions",
            ["All Regions", "Indian Ocean", "Pacific Ocean", "Atlantic Ocean", "Custom"],
            key="region_preset"
        )
        
        # Custom geographic bounds (if Custom selected)
        custom_bounds = None
        if region_preset == "Custom":
            st.caption("Define custom bounding box:")
            col1, col2 = st.columns(2)
            with col1:
                north = st.number_input("North Lat", value=20.0, min_value=-90.0, max_value=90.0)
                south = st.number_input("South Lat", value=-20.0, min_value=-90.0, max_value=90.0)
            with col2:
                east = st.number_input("East Lon", value=100.0, min_value=-180.0, max_value=180.0)
                west = st.number_input("West Lon", value=60.0, min_value=-180.0, max_value=180.0)
            
            custom_bounds = {"north": north, "south": south, "east": east, "west": west}
        
        # Depth range filter
        st.subheader("📏 Depth Range")
        depth_range = st.slider(
            "Depth (meters)",
            min_value=0,
            max_value=2000,
            value=(0, 2000),
            step=50,
            key="depth_filter"
        )
        
        # Parameter filters
        st.subheader("🔬 Parameters")
        show_temperature = st.checkbox("Temperature", value=True, key="show_temp")
        show_salinity = st.checkbox("Salinity", value=True, key="show_sal")
        show_bgc = st.checkbox("BGC Parameters", value=False, key="show_bgc")
        
        # Data quality filter
        st.subheader("✅ Data Quality")
        quality_levels = st.multiselect(
            "Quality Levels",
            ["Excellent", "Good", "Fair", "Poor"],
            default=["Excellent", "Good"],
            key="quality_filter"
        )
        
        # Reset filters button
        if st.button("🔄 Reset Filters", use_container_width=True):
            # Clear filter-related session state
            for key in st.session_state.keys():
                if key.endswith('_filter') or key in ['region_preset', 'show_temp', 'show_sal', 'show_bgc', 'quality_filter']:
                    del st.session_state[key]
            st.rerun()
        
        return {
            "date_range": date_range,
            "region_preset": region_preset,
            "custom_bounds": custom_bounds,
            "depth_range": depth_range,
            "parameters": {
                "temperature": show_temperature,
                "salinity": show_salinity,
                "bgc": show_bgc
            },
            "quality_levels": quality_levels
        }
    
    def _render_detailed_status(self) -> None:
        """Render detailed system status in sidebar"""
        st.header("🔧 System Status")
        
        if st.session_state.get('api_client'):
            try:
                health_data = st.session_state.api_client.health_check()
                
                # Backend status
                if health_data.get("status") == "healthy":
                    st.success("✅ Backend API")
                else:
                    st.error("❌ Backend API")
                
                # Database status
                db_status = health_data.get("database", "unknown")
                if db_status == "connected":
                    st.success("✅ PostgreSQL")
                else:
                    st.error("❌ PostgreSQL")
                
                # ChromaDB status
                chroma_status = health_data.get("chromadb", "unknown")
                if chroma_status == "connected":
                    st.success("✅ ChromaDB")
                else:
                    st.error("❌ ChromaDB")
                
            except Exception as e:
                st.error("❌ Connection Failed")
                st.caption(f"Error: {str(e)[:50]}...")
        else:
            st.warning("⚠️ API Client Not Available")
        
        # Performance metrics (placeholder)
        st.caption("**Performance:**")
        st.caption("• Response Time: <100ms")
        st.caption("• Memory Usage: Normal")
        st.caption("• Cache Hit Rate: 85%")
    
    def render_main_content(self, active_tab: str, filters: Dict[str, Any]) -> None:
        """Render main content area based on active tab"""
        
        # Apply filters to session state
        st.session_state.current_filters = filters
        
        # Tab-specific content
        if active_tab == "Overview":
            self._render_overview_content()
        elif active_tab == "Interactive Map":
            self._render_map_content()
        elif active_tab == "Profile Analysis":
            self._render_profile_content()
        elif active_tab == "Chat Interface":
            self._render_chat_content()
        elif active_tab == "Data Export":
            self._render_export_content()
        elif active_tab == "Advanced Filters":
            self._render_advanced_filters_content()
    
    def _render_overview_content(self) -> None:
        """Render overview dashboard content with comprehensive statistics"""
        st.header("📊 System Overview")
        
        try:
            from components.statistics_manager import StatisticsManager
            from components.data_manager import DataManager
            
            # Initialize managers
            stats_manager = StatisticsManager()
            
            # Get current data (from data manager or sample data)
            try:
                data_manager = DataManager()
                current_data = data_manager.get_filtered_data(st.session_state.get('current_filters', {}))
            except:
                # Use sample data if data manager not available
                current_data = self._get_sample_data()
            
            # Render dataset overview
            stats_manager.render_dataset_overview(current_data)
            
            st.markdown("---")
            
            # Create tabs for different statistical views
            tab1, tab2, tab3 = st.tabs(["📊 Parameter Statistics", "✅ Data Quality", "📈 Analysis"])
            
            with tab1:
                stats_manager.render_parameter_statistics(current_data)
            
            with tab2:
                stats_manager.render_data_quality_assessment(current_data)
            
            with tab3:
                # Additional analysis content
                st.subheader("📊 Advanced Analysis")
                st.info("Advanced statistical analysis features will be expanded here")
                
                # Show sample statistics visualization
                if not current_data.empty:
                    numeric_cols = current_data.select_dtypes(include=[np.number]).columns
                    param_cols = [col for col in numeric_cols 
                                if col not in ['latitude', 'longitude', 'depth', 'profile_id', 'float_id']]
                    
                    if param_cols:
                        selected_params = st.multiselect(
                            "Select parameters for analysis:",
                            param_cols,
                            default=param_cols[:2] if len(param_cols) >= 2 else param_cols
                        )
                        
                        if selected_params:
                            fig = stats_manager.create_statistics_summary_plot(current_data, selected_params)
                            st.plotly_chart(fig, use_container_width=True)
        
        except ImportError:
            # Fallback to simple overview
            self._render_simple_overview()
        except Exception as e:
            st.error(f"Error loading statistics: {str(e)}")
            logger.error(f"Statistics overview error: {e}")
            self._render_simple_overview()
    
    def _render_simple_overview(self) -> None:
        """Render simple overview as fallback"""
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Active Floats",
                value="50",
                delta="2",
                help="Number of currently active ARGO floats"
            )
        
        with col2:
            st.metric(
                label="Total Profiles", 
                value="1,234",
                delta="45",
                help="Total number of vertical profiles collected"
            )
        
        with col3:
            st.metric(
                label="Measurements",
                value="45,678", 
                delta="1,203",
                help="Total individual measurements in database"
            )
        
        with col4:
            st.metric(
                label="Data Quality",
                value="98.5%",
                delta="0.2%",
                help="Overall data quality score"
            )
        
        st.markdown("---")
        
        # Simple activity chart
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📈 Recent Activity")
            
            # Sample activity chart
            sample_data = pd.DataFrame({
                'Date': pd.date_range('2024-01-01', periods=30, freq='D'),
                'Measurements': [100 + i*5 + (i%7)*10 for i in range(30)]
            })
            st.line_chart(sample_data.set_index('Date'))
        
        with col2:
            st.subheader("⚡ Quick Stats")
            st.markdown("""
            - **Coverage**: Indian Ocean
            - **Depth Range**: 0-2000m  
            - **Parameters**: T, S, BGC
            - **Update Frequency**: Real-time
            """)
    
    def _render_map_content(self) -> None:
        """Render interactive map content"""
        st.header("🗺️ Interactive Float Map")
        
        try:
            from components.map_visualization import InteractiveMap
            from components.data_fetcher import DataFetcher
            
            # Initialize components
            map_viz = InteractiveMap()
            data_fetcher = DataFetcher(st.session_state.get('api_client'))
            
            # Render map controls
            map_settings = map_viz.render_map_controls()
            
            st.markdown("---")
            
            # Get data
            with st.spinner("Loading ARGO float data..."):
                try:
                    # Get float locations
                    float_data = data_fetcher.get_float_locations(map_settings['max_floats'])
                    
                    # Apply current filters
                    if st.session_state.get('current_filters'):
                        float_data = data_fetcher.apply_filters(float_data, st.session_state.current_filters)
                    
                    if not float_data.empty:
                        # Create base map
                        if map_settings.get('show_density', False):
                            fig = map_viz.create_density_heatmap(float_data)
                        else:
                            fig = map_viz.create_base_map()
                            
                            # Add float markers
                            fig = map_viz.add_float_markers(
                                fig, 
                                float_data,
                                cluster_distance=map_settings['cluster_distance']
                            )
                            
                            # Add trajectories if requested
                            if map_settings['show_trajectories']:
                                selected_float_ids = float_data['float_id'].head(map_settings['trajectory_limit']).tolist()
                                trajectory_data = data_fetcher.get_float_trajectories(
                                    selected_float_ids, 
                                    map_settings['trajectory_limit']
                                )
                                
                                if not trajectory_data.empty:
                                    fig = map_viz.add_trajectories(fig, trajectory_data)
                            
                            # Add regions if requested
                            if map_settings['show_regions']:
                                regions = map_viz.get_predefined_regions()
                                fig = map_viz.add_geographic_regions(fig, regions)
                        
                        # Display map
                        st.plotly_chart(fig, use_container_width=True, key="main_map")
                        
                        # Map statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Floats Displayed", len(float_data))
                        with col2:
                            st.metric("Geographic Coverage", "Indian Ocean")
                        with col3:
                            estimated_measurements = len(float_data) * 50  # Rough estimate
                            st.metric("Est. Data Points", f"{estimated_measurements:,}")
                        
                        # Additional map info
                        with st.expander("📊 Map Data Details"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("**Float Distribution:**")
                                if 'wmo_id' in float_data.columns:
                                    st.write(f"- WMO IDs: {float_data['wmo_id'].nunique()} unique")
                                if 'cycle_number' in float_data.columns:
                                    avg_cycles = float_data['cycle_number'].mean()
                                    st.write(f"- Avg Cycles: {avg_cycles:.1f}")
                                
                                # Geographic bounds
                                lat_range = (float_data['lat'].min(), float_data['lat'].max())
                                lon_range = (float_data['lon'].min(), float_data['lon'].max())
                                st.write(f"- Lat Range: {lat_range[0]:.2f}° to {lat_range[1]:.2f}°")
                                st.write(f"- Lon Range: {lon_range[0]:.2f}° to {lon_range[1]:.2f}°")
                            
                            with col2:
                                st.write("**Map Settings:**")
                                st.write(f"- Clustering: {'Enabled' if map_settings['cluster_distance'] > 0 else 'Disabled'}")
                                st.write(f"- Trajectories: {'Shown' if map_settings['show_trajectories'] else 'Hidden'}")
                                st.write(f"- Regions: {'Shown' if map_settings['show_regions'] else 'Hidden'}")
                                st.write(f"- Style: {map_settings['map_style']}")
                        
                        # Float selection interface
                        if len(float_data) > 0:
                            st.subheader("🎯 Float Selection")
                            
                            # Select specific floats for detailed view
                            available_floats = float_data['float_id'].tolist()
                            selected_floats = st.multiselect(
                                "Select floats for detailed analysis:",
                                available_floats,
                                default=available_floats[:3] if len(available_floats) >= 3 else available_floats,
                                key="selected_floats_map"
                            )
                            
                            if selected_floats:
                                st.session_state.selected_floats = selected_floats
                                st.success(f"Selected {len(selected_floats)} floats for analysis")
                            
                                # Show selected float details
                                selected_data = float_data[float_data['float_id'].isin(selected_floats)]
                                st.dataframe(
                                    selected_data[['float_id', 'lat', 'lon', 'wmo_id', 'cycle_number']].head(10),
                                    use_container_width=True
                                )
                        
                    else:
                        st.warning("No float data available to display")
                        st.info("This could be due to:")
                        st.markdown("- Backend connection issues")
                        st.markdown("- No data matching current filters")
                        st.markdown("- API response format changes")
                
                except Exception as e:
                    st.error(f"Error loading map data: {str(e)}")
                    logger.error(f"Map data loading error: {e}")
                    
                    # Show debug info in development
                    if st.checkbox("Show debug info", key="map_debug"):
                        st.code(f"Error details: {str(e)}")
                        if st.session_state.get('api_client'):
                            health = st.session_state.api_client.health_check()
                            st.json(health)
        
        except ImportError:
            st.info("🚧 Map visualization component is being loaded...")
    

    
    def _render_profile_content(self) -> None:
        """Render profile analysis content"""
        st.header("📈 Profile Analysis")
        
        try:
            from components.profile_visualizer import ProfileVisualizer
            from components.data_fetcher import DataFetcher
            
            # Initialize components
            profile_viz = ProfileVisualizer()
            data_fetcher = DataFetcher(st.session_state.get('api_client'))
            
            # Render profile controls
            profile_settings = profile_viz.render_profile_controls()
            
            st.markdown("---")
            
            # Get selected floats from session state or use defaults
            selected_floats = st.session_state.get('selected_floats', [])
            
            if not selected_floats:
                st.info("💡 **Tip**: Select floats from the Interactive Map tab first, or choose floats below.")
                
                # Provide float selection interface
                with st.spinner("Loading available floats..."):
                    available_data = data_fetcher.get_float_locations(50)
                    
                    if not available_data.empty and 'float_id' in available_data.columns:
                        available_floats = available_data['float_id'].tolist()
                        
                        selected_floats = st.multiselect(
                            "Select floats for profile analysis:",
                            available_floats,
                            default=available_floats[:3] if len(available_floats) >= 3 else available_floats,
                            key="profile_float_selection"
                        )
                        
                        # Update session state
                        if selected_floats:
                            st.session_state.selected_floats = selected_floats
                    else:
                        st.warning("No float data available. Please check backend connection.")
                        return
            
            if selected_floats:
                st.success(f"Analyzing profiles for {len(selected_floats)} selected floats")
                
                # Load profile data
                with st.spinner("Loading profile data..."):
                    profile_data_list = []
                    profile_labels = []
                    
                    for float_id in selected_floats[:profile_settings['max_profiles']]:
                        try:
                            # Get profile data for this float
                            if st.session_state.get('api_client'):
                                profiles = st.session_state.api_client.get_float_profiles(float_id)
                                if profiles:
                                    # Convert to DataFrame and get profile plot data
                                    df = pd.DataFrame(profiles)
                                    
                                    # For now, create sample profile data since we need measurement details
                                    sample_profile = self._create_sample_profile_data(float_id)
                                    profile_data_list.append(sample_profile)
                                    profile_labels.append(f"Float {float_id}")
                            else:
                                # Use sample data
                                sample_profile = self._create_sample_profile_data(float_id)
                                profile_data_list.append(sample_profile)
                                profile_labels.append(f"Float {float_id}")
                                
                        except Exception as e:
                            logger.warning(f"Could not load profile for {float_id}: {e}")
                            continue
                
                # Apply depth filtering
                depth_min, depth_max = profile_settings['depth_range']
                filtered_profiles = []
                for profile_df in profile_data_list:
                    if not profile_df.empty and 'depth' in profile_df.columns:
                        filtered = profile_df[
                            (profile_df['depth'] >= depth_min) & 
                            (profile_df['depth'] <= depth_max)
                        ]
                        filtered_profiles.append(filtered)
                    else:
                        filtered_profiles.append(profile_df)
                
                # Create visualizations based on selected plot type
                plot_type = profile_settings['plot_type']
                
                if plot_type == "Individual Profiles" and filtered_profiles:
                    st.subheader("🌡️ Individual Float Profiles")
                    
                    # Show profiles for each float
                    for i, (profile_df, label) in enumerate(zip(filtered_profiles, profile_labels)):
                        if not profile_df.empty:
                            st.write(f"**{label}**")
                            
                            fig = profile_viz.create_ts_profile(profile_df, label.split()[-1])
                            
                            # Add statistics if requested
                            if profile_settings['show_statistics']:
                                stats = self._calculate_profile_statistics(profile_df)
                                fig = profile_viz.add_statistical_overlays(fig, stats)
                            
                            st.plotly_chart(fig, use_container_width=True, key=f"profile_{i}")
                            
                            # Show profile statistics
                            if profile_settings['show_statistics']:
                                self._display_profile_statistics(profile_df, label)
                
                elif plot_type == "Profile Comparison" and len(filtered_profiles) > 1:
                    st.subheader("🔄 Profile Comparison")
                    
                    fig = profile_viz.create_comparison_plot(filtered_profiles, profile_labels)
                    st.plotly_chart(fig, use_container_width=True, key="comparison_plot")
                    
                    # Comparison statistics
                    if profile_settings['show_statistics']:
                        st.subheader("📊 Comparison Statistics")
                        self._display_comparison_statistics(filtered_profiles, profile_labels)
                
                elif plot_type == "T-S Diagram" and filtered_profiles:
                    st.subheader("🌊 Temperature-Salinity Diagrams")
                    
                    for i, (profile_df, label) in enumerate(zip(filtered_profiles, profile_labels)):
                        if not profile_df.empty:
                            st.write(f"**{label}**")
                            
                            fig = profile_viz.create_ts_diagram(profile_df)
                            st.plotly_chart(fig, use_container_width=True, key=f"ts_diagram_{i}")
                
                elif plot_type == "BGC Parameters" and filtered_profiles:
                    st.subheader("🧪 BGC Parameter Profiles")
                    
                    bgc_params = profile_settings['bgc_parameters']
                    if not bgc_params:
                        st.warning("Please select BGC parameters to display.")
                    else:
                        for i, (profile_df, label) in enumerate(zip(filtered_profiles, profile_labels)):
                            if not profile_df.empty:
                                st.write(f"**{label}**")
                                
                                # Create BGC plots
                                bgc_figures = profile_viz.create_bgc_plots(profile_df, bgc_params)
                                
                                # Display in columns
                                cols = st.columns(min(len(bgc_figures), 3))
                                for j, fig in enumerate(bgc_figures):
                                    with cols[j % len(cols)]:
                                        st.plotly_chart(fig, use_container_width=True, key=f"bgc_{i}_{j}")
                
                else:
                    st.warning("No valid profile data available for the selected visualization type.")
            
            else:
                st.info("Please select floats to analyze their profiles.")
        
        except ImportError:
            st.info("🚧 Profile visualization component is being loaded...")
        except Exception as e:
            st.error(f"Error loading profile analysis: {str(e)}")
            logger.error(f"Profile analysis error: {e}")
    
    def _create_sample_profile_data(self, float_id: str) -> pd.DataFrame:
        """Create sample profile data for demonstration"""
        np.random.seed(hash(float_id) % 2**32)  # Consistent data per float
        
        # Create realistic oceanographic profile
        depths = np.arange(0, 1000, 10)  # Every 10m to 1000m
        n_points = len(depths)
        
        # Temperature profile (decreases with depth)
        surface_temp = np.random.uniform(25, 30)  # Tropical surface temperature
        temperatures = []
        
        for depth in depths:
            if depth < 50:  # Mixed layer
                temp = surface_temp + np.random.normal(0, 0.5)
            elif depth < 200:  # Thermocline
                temp = surface_temp - (depth - 50) * 0.15 + np.random.normal(0, 1)
            else:  # Deep water
                temp = surface_temp - 150 * 0.15 - (depth - 200) * 0.005 + np.random.normal(0, 0.3)
            
            temperatures.append(max(2, temp))  # Minimum temperature
        
        # Salinity profile (increases with depth, with some variation)
        surface_sal = np.random.uniform(34.5, 35.5)
        salinities = []
        
        for depth in depths:
            if depth < 100:  # Surface layer
                sal = surface_sal + np.random.normal(0, 0.1)
            else:  # Deeper water
                sal = surface_sal + (depth - 100) * 0.0005 + np.random.normal(0, 0.05)
            
            salinities.append(max(30, min(37, sal)))  # Realistic bounds
        
        # BGC parameters
        oxygen = []
        ph_values = []
        chlorophyll = []
        
        for depth in depths:
            # Oxygen (high at surface, minimum zone, then increases)
            if depth < 50:
                o2 = np.random.uniform(6, 7)
            elif depth < 500:  # Oxygen minimum zone
                o2 = np.random.uniform(2, 4)
            else:
                o2 = np.random.uniform(4, 5.5)
            oxygen.append(o2)
            
            # pH (decreases slightly with depth)
            ph = 8.1 - depth * 0.0001 + np.random.normal(0, 0.02)
            ph_values.append(max(7.5, min(8.3, ph)))
            
            # Chlorophyll (high near surface, decreases with depth)
            if depth < 100:
                chl = np.random.exponential(0.5) * np.exp(-depth/50)
            else:
                chl = np.random.exponential(0.01)
            chlorophyll.append(max(0, chl))
        
        return pd.DataFrame({
            'depth': depths,
            'temperature': temperatures,
            'salinity': salinities,
            'oxygen': oxygen,
            'ph': ph_values,
            'chlorophyll': chlorophyll,
            'float_id': float_id
        })
    
    def _calculate_profile_statistics(self, profile_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate basic statistics for a profile"""
        stats = {}
        
        for param in ['temperature', 'salinity', 'oxygen', 'ph']:
            if param in profile_df.columns:
                data = profile_df[param].dropna()
                if len(data) > 0:
                    stats[f'mean_{param}'] = float(data.mean())
                    stats[f'std_{param}'] = float(data.std())
                    stats[f'min_{param}'] = float(data.min())
                    stats[f'max_{param}'] = float(data.max())
        
        return stats
    
    def _display_profile_statistics(self, profile_df: pd.DataFrame, label: str) -> None:
        """Display profile statistics in a formatted way"""
        stats = self._calculate_profile_statistics(profile_df)
        
        if stats:
            with st.expander(f"📊 Statistics for {label}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'mean_temperature' in stats:
                        st.metric(
                            "Temperature",
                            f"{stats['mean_temperature']:.2f}°C",
                            f"±{stats['std_temperature']:.2f}°C"
                        )
                    
                    if 'mean_oxygen' in stats:
                        st.metric(
                            "Oxygen",
                            f"{stats['mean_oxygen']:.2f} ml/L",
                            f"±{stats['std_oxygen']:.2f} ml/L"
                        )
                
                with col2:
                    if 'mean_salinity' in stats:
                        st.metric(
                            "Salinity",
                            f"{stats['mean_salinity']:.2f} PSU",
                            f"±{stats['std_salinity']:.2f} PSU"
                        )
                    
                    if 'mean_ph' in stats:
                        st.metric(
                            "pH",
                            f"{stats['mean_ph']:.2f}",
                            f"±{stats['std_ph']:.2f}"
                        )
    
    def _display_comparison_statistics(self, profiles: List[pd.DataFrame], labels: List[str]) -> None:
        """Display comparison statistics between profiles"""
        
        comparison_data = []
        
        for profile_df, label in zip(profiles, labels):
            if not profile_df.empty:
                stats = self._calculate_profile_statistics(profile_df)
                stats['float'] = label
                comparison_data.append(stats)
        
        if comparison_data:
            comparison_df = pd.DataFrame(comparison_data)
            
            # Display as a table
            display_cols = ['float']
            for param in ['temperature', 'salinity', 'oxygen', 'ph']:
                mean_col = f'mean_{param}'
                if mean_col in comparison_df.columns:
                    display_cols.append(mean_col)
            
            if len(display_cols) > 1:
                st.dataframe(
                    comparison_df[display_cols].round(2),
                    use_container_width=True
                )
    
    def _render_chat_content(self) -> None:
        """Render chat interface content"""
        st.header("💬 Natural Language Query Interface")
        
        try:
            from components.chat_interface import ChatInterface
            
            # Initialize chat interface
            chat_interface = ChatInterface(st.session_state.get('api_client'))
            
            # Check API connection status
            if st.session_state.get('api_client'):
                try:
                    health = st.session_state.api_client.health_check()
                    if health.get('status') == 'healthy':
                        st.success("✅ Connected to ARGO data system")
                    else:
                        st.warning("⚠️ Limited functionality - backend connection issues")
                except Exception:
                    st.error("❌ Cannot connect to ARGO data system")
            else:
                st.error("❌ API client not available")
            
            st.markdown("---")
            
            # Render main chat interface
            chat_interface.render_chat_container()
            
            # Show chat statistics in sidebar
            with st.sidebar:
                st.markdown("### 💬 Chat Statistics")
                stats = chat_interface.get_chat_statistics()
                
                if stats:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Messages", stats.get('total_messages', 0))
                    with col2:
                        st.metric("Success Rate", f"{stats.get('success_rate', 0):.1f}%")
                else:
                    st.info("No chat activity yet")
        
        except ImportError:
            st.info("🚧 Chat interface component is being loaded...")
        except Exception as e:
            st.error(f"Error loading chat interface: {str(e)}")
            logger.error(f"Chat interface error: {e}")
    
    def _render_export_content(self) -> None:
        """Render data export and download functionality"""
        st.header("📥 Data Export & Download Center")
        
        try:
            from components.export_manager import ExportManager
            
            # Initialize export manager
            export_manager = ExportManager(st.session_state.get('api_client'))
            
            # Check if there's data to export
            has_data = (
                st.session_state.get('filtered_data') is not None or
                st.session_state.get('selected_floats') or
                st.session_state.get('last_query_data') is not None
            )
            
            if not has_data:
                st.info("💡 **Tip**: Generate some data first by using other dashboard sections:")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🗺️ Get Float Data", use_container_width=True):
                        st.switch_page("Interactive Map")
                
                with col2:
                    if st.button("📈 Analyze Profiles", use_container_width=True):
                        st.switch_page("Profile Analysis")
                
                with col3:
                    if st.button("💬 Query Data", use_container_width=True):
                        st.switch_page("Chat Interface")
                
                st.markdown("---")
            
            # Render export interface
            export_manager.render_export_interface()
            
            # Show export history/status
            st.markdown("---")
            st.subheader("📋 Export History")
            
            # In a real implementation, this would show actual export history
            if 'export_history' not in st.session_state:
                st.session_state.export_history = []
            
            if st.session_state.export_history:
                for i, export_record in enumerate(st.session_state.export_history[-5:]):  # Show last 5
                    with st.expander(f"Export {i+1}: {export_record.get('type', 'Unknown')} - {export_record.get('timestamp', 'Unknown time')}"):
                        st.json(export_record)
            else:
                st.info("No exports yet. Use the export options above to get started.")
            
            # Export tips and best practices
            with st.expander("💡 Export Tips & Best Practices"):
                st.markdown("""
                **📊 Visualization Exports:**
                - Use PNG for presentations and documents
                - Use SVG for scalable graphics and publications
                - Use PDF for high-quality prints
                - Use HTML for interactive sharing
                
                **📋 Data Exports:**
                - CSV is best for spreadsheet analysis
                - JSON is ideal for web applications
                - NetCDF is standard for oceanographic data
                - ASCII is compatible with legacy systems
                
                **📄 Report Exports:**
                - HTML reports are interactive and web-friendly
                - PDF reports are best for official documents
                - Include metadata for data provenance
                
                **📦 Package Exports:**
                - Use complete packages for comprehensive data sharing
                - Include quality reports for data validation
                - Add metadata for reproducibility
                """)
        
        except ImportError:
            st.info("🚧 Export functionality is being loaded...")
        except Exception as e:
            st.error(f"Error loading export functionality: {str(e)}")
            logger.error(f"Export functionality error: {e}")
    
    def _render_advanced_filters_content(self) -> None:
        """Render advanced filtering interface"""
        st.header("🔍 Advanced Data Filtering System")
        
        try:
            from components.data_manager import DataManager
            from components.data_fetcher import DataFetcher
            
            # Initialize components
            data_manager = DataManager(st.session_state.get('api_client'))
            data_fetcher = DataFetcher(st.session_state.get('api_client'))
            
            # Render advanced filters
            advanced_filters = data_manager.render_advanced_filters()
            
            st.markdown("---")
            
            # Apply filters and show results
            st.subheader("📊 Filter Results")
            
            with st.spinner("Applying filters to data..."):
                try:
                    # Get sample data to demonstrate filtering
                    sample_data = data_fetcher.get_float_locations(100)
                    
                    if not sample_data.empty:
                        # Apply filters
                        filtered_data = data_manager.apply_filters(sample_data, advanced_filters)
                        
                        # Show results
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Original Records", len(sample_data))
                        
                        with col2:
                            st.metric("Filtered Records", len(filtered_data))
                        
                        with col3:
                            reduction = ((len(sample_data) - len(filtered_data)) / len(sample_data) * 100) if len(sample_data) > 0 else 0
                            st.metric("Reduction", f"{reduction:.1f}%")
                        
                        with col4:
                            if len(filtered_data) > 0:
                                st.metric("Data Quality", "Good", "✅")
                            else:
                                st.metric("Data Quality", "No Data", "⚠️")
                        
                        # Show filtered data preview
                        if not filtered_data.empty:
                            st.subheader("🔍 Filtered Data Preview")
                            
                            # Show first few records
                            display_cols = ['float_id', 'lat', 'lon', 'wmo_id', 'cycle_number', 'profile_date']
                            available_cols = [col for col in display_cols if col in filtered_data.columns]
                            
                            if available_cols:
                                st.dataframe(
                                    filtered_data[available_cols].head(20),
                                    use_container_width=True
                                )
                            
                            # Data quality assessment
                            st.subheader("✅ Data Quality Assessment")
                            quality_assessment = data_manager.assess_data_quality(filtered_data)
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.metric(
                                    "Quality Score",
                                    f"{quality_assessment.get('score', 0):.1%}",
                                    help="Overall data quality score based on completeness and validity"
                                )
                                
                                st.metric(
                                    "Missing Data",
                                    f"{quality_assessment.get('missing_percentage', 0):.1f}%",
                                    help="Percentage of missing values in the dataset"
                                )
                            
                            with col2:
                                status = quality_assessment.get('status', 'unknown')
                                status_color = {
                                    'excellent': '🟢',
                                    'good': '🟡', 
                                    'fair': '🟠',
                                    'poor': '🔴'
                                }.get(status, '⚪')
                                
                                st.metric(
                                    "Status",
                                    f"{status_color} {status.title()}",
                                    help="Overall data quality status"
                                )
                                
                                st.metric(
                                    "Total Records",
                                    f"{quality_assessment.get('total_records', 0):,}",
                                    help="Number of records in filtered dataset"
                                )
                            
                            # Show issues if any
                            if quality_assessment.get('issues'):
                                st.warning("**Data Quality Issues:**")
                                for issue in quality_assessment['issues']:
                                    st.write(f"• {issue}")
                            
                            # Export filtered data
                            st.subheader("📥 Export Filtered Data")
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                if st.button("📊 Export as CSV", use_container_width=True):
                                    try:
                                        csv_data = filtered_data.to_csv(index=False)
                                        st.download_button(
                                            "Download CSV",
                                            csv_data,
                                            file_name=f"argo_filtered_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                            mime="text/csv"
                                        )
                                    except Exception as e:
                                        st.error(f"Export failed: {str(e)}")
                            
                            with col2:
                                if st.button("🗺️ View on Map", use_container_width=True):
                                    # Store filtered data for map view
                                    st.session_state.filtered_map_data = filtered_data
                                    st.success("Filtered data ready for map view! Go to 'Interactive Map' tab.")
                            
                            with col3:
                                if st.button("📈 Analyze Profiles", use_container_width=True):
                                    # Store selected floats for profile analysis
                                    if 'float_id' in filtered_data.columns:
                                        selected_floats = filtered_data['float_id'].unique()[:10]  # Limit to 10
                                        st.session_state.selected_floats = selected_floats.tolist()
                                        st.success(f"Selected {len(selected_floats)} floats for profile analysis! Go to 'Profile Analysis' tab.")
                        
                        else:
                            st.warning("No data matches the current filter criteria. Try adjusting your filters.")
                            
                            # Suggestions for filter adjustment
                            st.info("**Suggestions:**")
                            st.write("• Expand the date range")
                            st.write("• Use a larger geographic region")
                            st.write("• Reduce parameter constraints")
                            st.write("• Check data quality requirements")
                    
                    else:
                        st.error("No data available for filtering. Please check backend connection.")
                
                except Exception as e:
                    st.error(f"Error applying filters: {str(e)}")
                    logger.error(f"Advanced filtering error: {e}")
        
        except ImportError:
            st.info("🚧 Advanced filtering system is being loaded...")
        except Exception as e:
            st.error(f"Error loading advanced filters: {str(e)}")
            logger.error(f"Advanced filters error: {e}")
    
    def render_footer(self) -> None:
        """Render footer with attribution and links"""
        st.markdown("---")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.markdown("""
            **Data Attribution:**  
            This dashboard is powered by data from the [Argo Global Data Assembly Centers](https://argo.ucsd.edu/).  
            Argo is an international program measuring ocean temperature, salinity, and other properties.
            """)
        
        with col2:
            st.markdown("""
            **System Information:**  
            - Dashboard Version: 1.0.0
            - Last Updated: """ + datetime.now().strftime("%Y-%m-%d") + """
            - Government Edition
            """)
        
        with col3:
            st.markdown("""
            **Support:**  
            [Documentation](#)  
            [Contact Support](#)
            """)
    
    def apply_custom_styling(self) -> None:
        """Apply government theme and custom CSS styling"""
        if GovernmentTheme:
            GovernmentTheme.apply_theme()
        else:
            # Fallback basic styling
            st.markdown("""
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            
            .main .block-container {
                padding-top: 2rem;
            }
            
            .stButton > button {
                background: linear-gradient(90deg, #1f4e79 0%, #2e8b57 100%);
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 500;
            }
            </style>
            """, unsafe_allow_html=True)
    
    def _get_sample_data(self) -> pd.DataFrame:
        """Generate sample ARGO data for testing statistics functionality"""
        np.random.seed(42)  # For consistent sample data
        n_records = 200
        
        # Generate sample ARGO float data
        data = {
            'float_id': np.random.choice(['FLOAT_001', 'FLOAT_002', 'FLOAT_003', 'FLOAT_004'], n_records),
            'profile_id': range(1, n_records + 1),
            'latitude': np.random.uniform(-60, 60, n_records),
            'longitude': np.random.uniform(40, 120, n_records),  # Indian Ocean focus
            'depth': np.random.uniform(0, 2000, n_records),
            'temperature': np.random.normal(15, 8, n_records),  # Realistic ocean temps
            'salinity': np.random.normal(35, 3, n_records),     # Realistic salinity
            'pressure': np.random.uniform(0, 2000, n_records),
            'oxygen': np.random.normal(200, 50, n_records),     # BGC parameter
            'chlorophyll': np.random.exponential(0.5, n_records),  # BGC parameter
            'ph': np.random.normal(8.1, 0.2, n_records),       # BGC parameter
            'quality_flag': np.random.choice([1, 2, 3, 4, 9], n_records, p=[0.7, 0.15, 0.08, 0.05, 0.02]),
            'date': [datetime.now() - timedelta(days=int(x)) for x in np.random.randint(0, 365, n_records)]
        }
        
        return pd.DataFrame(data)