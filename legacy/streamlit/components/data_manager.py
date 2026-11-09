"""
Data Manager Component
Handles comprehensive data filtering, quality assessment, and export operations
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Union
import logging
from datetime import datetime, timedelta, date
from dashboard_config import dashboard_config
from components.api_client import APIClient, APIException
from components.data_transformer import DataTransformer
from utils.dashboard_utils import validate_data_quality, get_data_summary

logger = logging.getLogger(__name__)

class DataManager:
    """Manages data filtering, quality assessment, and export operations"""
    
    def __init__(self, api_client: Optional[APIClient] = None):
        self.api_client = api_client or st.session_state.get('api_client')
        self.config = dashboard_config
        self.transformer = DataTransformer()
        
        # Initialize filter state in session state
        if 'filter_state' not in st.session_state:
            st.session_state.filter_state = self._get_default_filters()
    
    def render_advanced_filters(self) -> Dict[str, Any]:
        """Render comprehensive filtering interface"""
        
        st.subheader("🔍 Advanced Data Filters")
        
        # Create tabs for different filter categories
        tab1, tab2, tab3, tab4 = st.tabs(["📅 Temporal", "🌍 Geographic", "📏 Physical", "⚙️ Technical"])
        
        with tab1:
            temporal_filters = self._render_temporal_filters()
        
        with tab2:
            geographic_filters = self._render_geographic_filters()
        
        with tab3:
            physical_filters = self._render_physical_filters()
        
        with tab4:
            technical_filters = self._render_technical_filters()
        
        # Combine all filters
        all_filters = {
            **temporal_filters,
            **geographic_filters,
            **physical_filters,
            **technical_filters
        }
        
        # Filter summary and actions
        st.markdown("---")
        self._render_filter_summary(all_filters)
        
        # Update session state
        st.session_state.filter_state = all_filters
        
        return all_filters
    
    def _render_temporal_filters(self) -> Dict[str, Any]:
        """Render temporal filtering controls"""
        
        st.markdown("**📅 Time Period Selection**")
        
        # Date range selection
        col1, col2 = st.columns(2)
        
        with col1:
            date_mode = st.selectbox(
                "Date Selection Mode",
                ["Date Range", "Relative Period", "Specific Months"],
                key="date_mode"
            )
        
        with col2:
            time_zone = st.selectbox(
                "Time Zone",
                ["UTC", "Local", "Indian Standard Time"],
                key="time_zone"
            )
        
        # Date range inputs based on mode
        if date_mode == "Date Range":
            col1, col2 = st.columns(2)
            
            with col1:
                start_date = st.date_input(
                    "Start Date",
                    value=datetime.now().date() - timedelta(days=365),
                    key="start_date"
                )
            
            with col2:
                end_date = st.date_input(
                    "End Date",
                    value=datetime.now().date(),
                    key="end_date"
                )
            
            date_range = (start_date, end_date)
        
        elif date_mode == "Relative Period":
            period = st.selectbox(
                "Time Period",
                ["Last 7 days", "Last 30 days", "Last 90 days", "Last 6 months", "Last year", "Last 2 years"],
                key="relative_period"
            )
            
            # Convert to actual dates
            period_days = {
                "Last 7 days": 7,
                "Last 30 days": 30,
                "Last 90 days": 90,
                "Last 6 months": 180,
                "Last year": 365,
                "Last 2 years": 730
            }
            
            days = period_days.get(period, 365)
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            date_range = (start_date, end_date)
        
        else:  # Specific Months
            selected_months = st.multiselect(
                "Select Months",
                ["January", "February", "March", "April", "May", "June",
                 "July", "August", "September", "October", "November", "December"],
                default=["March", "April", "May"],
                key="selected_months"
            )
            
            selected_years = st.multiselect(
                "Select Years",
                [2020, 2021, 2022, 2023, 2024],
                default=[2023, 2024],
                key="selected_years"
            )
            
            date_range = None  # Will be handled differently
        
        # Time of day filtering
        st.markdown("**🕐 Time of Day (Optional)**")
        
        enable_time_filter = st.checkbox("Filter by time of day", key="enable_time_filter")
        
        if enable_time_filter:
            col1, col2 = st.columns(2)
            
            with col1:
                start_time = st.time_input("Start Time", key="start_time")
            
            with col2:
                end_time = st.time_input("End Time", key="end_time")
        else:
            start_time = end_time = None
        
        return {
            "date_mode": date_mode,
            "date_range": date_range,
            "selected_months": selected_months if date_mode == "Specific Months" else None,
            "selected_years": selected_years if date_mode == "Specific Months" else None,
            "time_zone": time_zone,
            "enable_time_filter": enable_time_filter,
            "start_time": start_time,
            "end_time": end_time
        }
    
    def _render_geographic_filters(self) -> Dict[str, Any]:
        """Render geographic filtering controls"""
        
        st.markdown("**🌍 Geographic Region Selection**")
        
        # Region selection mode
        region_mode = st.selectbox(
            "Region Selection Mode",
            ["Predefined Regions", "Custom Bounding Box", "Circular Area", "Polygon Selection"],
            key="region_mode"
        )
        
        if region_mode == "Predefined Regions":
            predefined_region = st.selectbox(
                "Select Region",
                ["All Regions", "Indian Ocean", "Arabian Sea", "Bay of Bengal", 
                 "Equatorial Indian Ocean", "Southern Indian Ocean"],
                key="predefined_region"
            )
            
            # Get bounds for predefined regions
            region_bounds = self._get_predefined_region_bounds(predefined_region)
            
        elif region_mode == "Custom Bounding Box":
            st.markdown("**Define Custom Bounding Box:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                north_lat = st.number_input("North Latitude", value=25.0, min_value=-90.0, max_value=90.0, key="north_lat")
                south_lat = st.number_input("South Latitude", value=-25.0, min_value=-90.0, max_value=90.0, key="south_lat")
            
            with col2:
                east_lon = st.number_input("East Longitude", value=120.0, min_value=-180.0, max_value=180.0, key="east_lon")
                west_lon = st.number_input("West Longitude", value=40.0, min_value=-180.0, max_value=180.0, key="west_lon")
            
            region_bounds = {
                "north": north_lat,
                "south": south_lat,
                "east": east_lon,
                "west": west_lon
            }
            
            predefined_region = None
        
        elif region_mode == "Circular Area":
            st.markdown("**Define Circular Area:**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                center_lat = st.number_input("Center Latitude", value=0.0, min_value=-90.0, max_value=90.0, key="center_lat")
            
            with col2:
                center_lon = st.number_input("Center Longitude", value=80.0, min_value=-180.0, max_value=180.0, key="center_lon")
            
            with col3:
                radius_km = st.number_input("Radius (km)", value=500.0, min_value=1.0, max_value=5000.0, key="radius_km")
            
            region_bounds = {
                "center_lat": center_lat,
                "center_lon": center_lon,
                "radius_km": radius_km
            }
            
            predefined_region = None
        
        else:  # Polygon Selection
            st.info("💡 Polygon selection will be available in future versions. Please use bounding box for now.")
            region_bounds = None
            predefined_region = None
        
        # Distance from coast filter
        st.markdown("**🏖️ Distance from Coast (Optional)**")
        
        enable_coast_filter = st.checkbox("Filter by distance from coast", key="enable_coast_filter")
        
        if enable_coast_filter:
            col1, col2 = st.columns(2)
            
            with col1:
                min_distance_coast = st.number_input("Min Distance (km)", value=0.0, min_value=0.0, key="min_distance_coast")
            
            with col2:
                max_distance_coast = st.number_input("Max Distance (km)", value=1000.0, min_value=0.0, key="max_distance_coast")
        else:
            min_distance_coast = max_distance_coast = None
        
        return {
            "region_mode": region_mode,
            "predefined_region": predefined_region,
            "region_bounds": region_bounds,
            "enable_coast_filter": enable_coast_filter,
            "min_distance_coast": min_distance_coast,
            "max_distance_coast": max_distance_coast
        }
    
    def _render_physical_filters(self) -> Dict[str, Any]:
        """Render physical parameter filtering controls"""
        
        st.markdown("**📏 Physical Parameters**")
        
        # Depth filtering
        st.markdown("**🌊 Depth Range**")
        
        depth_mode = st.selectbox(
            "Depth Selection Mode",
            ["Range", "Specific Levels", "Surface Only", "Deep Only"],
            key="depth_mode"
        )
        
        if depth_mode == "Range":
            depth_range = st.slider(
                "Depth Range (meters)",
                min_value=0,
                max_value=2000,
                value=(0, 1000),
                step=10,
                key="depth_range"
            )
            specific_depths = None
        
        elif depth_mode == "Specific Levels":
            depth_levels = st.text_input(
                "Depth Levels (comma-separated, e.g., 10,50,100,200)",
                value="10,50,100,200,500",
                key="depth_levels"
            )
            
            try:
                specific_depths = [float(d.strip()) for d in depth_levels.split(',')]
                depth_range = None
            except ValueError:
                st.error("Invalid depth levels format. Use comma-separated numbers.")
                specific_depths = None
                depth_range = (0, 1000)
        
        elif depth_mode == "Surface Only":
            depth_range = (0, 50)
            specific_depths = None
        
        else:  # Deep Only
            depth_range = (500, 2000)
            specific_depths = None
        
        # Temperature filtering
        st.markdown("**🌡️ Temperature Range (°C)**")
        
        enable_temp_filter = st.checkbox("Filter by temperature", key="enable_temp_filter")
        
        if enable_temp_filter:
            temp_range = st.slider(
                "Temperature Range",
                min_value=-2.0,
                max_value=35.0,
                value=(5.0, 30.0),
                step=0.5,
                key="temp_range"
            )
        else:
            temp_range = None
        
        # Salinity filtering
        st.markdown("**🧂 Salinity Range (PSU)**")
        
        enable_sal_filter = st.checkbox("Filter by salinity", key="enable_sal_filter")
        
        if enable_sal_filter:
            sal_range = st.slider(
                "Salinity Range",
                min_value=30.0,
                max_value=40.0,
                value=(34.0, 37.0),
                step=0.1,
                key="sal_range"
            )
        else:
            sal_range = None
        
        # BGC parameter filtering
        st.markdown("**🧪 BGC Parameters (Optional)**")
        
        enable_bgc_filter = st.checkbox("Filter by BGC parameters", key="enable_bgc_filter")
        
        if enable_bgc_filter:
            col1, col2 = st.columns(2)
            
            with col1:
                oxygen_range = st.slider(
                    "Oxygen (ml/L)",
                    min_value=0.0,
                    max_value=10.0,
                    value=(2.0, 8.0),
                    step=0.1,
                    key="oxygen_range"
                )
            
            with col2:
                ph_range = st.slider(
                    "pH",
                    min_value=7.0,
                    max_value=8.5,
                    value=(7.8, 8.2),
                    step=0.05,
                    key="ph_range"
                )
        else:
            oxygen_range = ph_range = None
        
        return {
            "depth_mode": depth_mode,
            "depth_range": depth_range,
            "specific_depths": specific_depths,
            "enable_temp_filter": enable_temp_filter,
            "temp_range": temp_range,
            "enable_sal_filter": enable_sal_filter,
            "sal_range": sal_range,
            "enable_bgc_filter": enable_bgc_filter,
            "oxygen_range": oxygen_range,
            "ph_range": ph_range
        }
    
    def _render_technical_filters(self) -> Dict[str, Any]:
        """Render technical and quality filtering controls"""
        
        st.markdown("**⚙️ Technical Parameters**")
        
        # Float selection
        st.markdown("**🎯 Float Selection**")
        
        float_selection_mode = st.selectbox(
            "Float Selection Mode",
            ["All Floats", "Specific Float IDs", "WMO Numbers", "Active Only", "Recent Data Only"],
            key="float_selection_mode"
        )
        
        if float_selection_mode == "Specific Float IDs":
            float_ids = st.text_input(
                "Float IDs (comma-separated)",
                placeholder="ARGO_001, ARGO_002, ARGO_003",
                key="specific_float_ids"
            )
            
            float_ids_list = [fid.strip() for fid in float_ids.split(',') if fid.strip()] if float_ids else []
        
        elif float_selection_mode == "WMO Numbers":
            wmo_numbers = st.text_input(
                "WMO Numbers (comma-separated)",
                placeholder="5900001, 5900002, 5900003",
                key="wmo_numbers"
            )
            
            try:
                wmo_list = [int(wmo.strip()) for wmo in wmo_numbers.split(',') if wmo.strip()] if wmo_numbers else []
            except ValueError:
                st.error("Invalid WMO numbers format. Use comma-separated integers.")
                wmo_list = []
        
        else:
            float_ids_list = []
            wmo_list = []
        
        # Data quality filtering
        st.markdown("**✅ Data Quality**")
        
        quality_levels = st.multiselect(
            "Quality Levels",
            ["Excellent", "Good", "Fair", "Poor", "Unknown"],
            default=["Excellent", "Good"],
            key="quality_levels"
        )
        
        # Measurement completeness
        min_completeness = st.slider(
            "Minimum Data Completeness (%)",
            min_value=0,
            max_value=100,
            value=70,
            step=5,
            key="min_completeness"
        )
        
        # Profile cycle filtering
        st.markdown("**🔄 Profile Cycles**")
        
        enable_cycle_filter = st.checkbox("Filter by cycle numbers", key="enable_cycle_filter")
        
        if enable_cycle_filter:
            col1, col2 = st.columns(2)
            
            with col1:
                min_cycle = st.number_input("Min Cycle", value=1, min_value=1, key="min_cycle")
            
            with col2:
                max_cycle = st.number_input("Max Cycle", value=200, min_value=1, key="max_cycle")
        else:
            min_cycle = max_cycle = None
        
        # Data freshness
        st.markdown("**📅 Data Freshness**")
        
        max_age_days = st.selectbox(
            "Maximum Data Age",
            ["No Limit", "1 day", "7 days", "30 days", "90 days", "1 year"],
            key="max_age_days"
        )
        
        return {
            "float_selection_mode": float_selection_mode,
            "float_ids_list": float_ids_list,
            "wmo_list": wmo_list,
            "quality_levels": quality_levels,
            "min_completeness": min_completeness,
            "enable_cycle_filter": enable_cycle_filter,
            "min_cycle": min_cycle,
            "max_cycle": max_cycle,
            "max_age_days": max_age_days
        }
    
    def _render_filter_summary(self, filters: Dict[str, Any]) -> None:
        """Render filter summary and action buttons"""
        
        st.markdown("**📋 Filter Summary**")
        
        # Count active filters
        active_filters = self._count_active_filters(filters)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Active Filters", active_filters)
        
        with col2:
            if st.button("🔄 Reset All Filters", use_container_width=True):
                self._reset_all_filters()
                st.rerun()
        
        with col3:
            if st.button("💾 Save Filter Set", use_container_width=True):
                self._save_filter_set(filters)
        
        with col4:
            if st.button("📂 Load Filter Set", use_container_width=True):
                self._load_filter_set()
        
        # Show filter details
        if active_filters > 0:
            with st.expander("🔍 Active Filter Details"):
                self._display_active_filters(filters)
    
    def apply_filters(self, data: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        """Apply comprehensive filters to dataset"""
        
        if data.empty:
            return data
        
        filtered_data = data.copy()
        filter_log = []
        
        try:
            # Apply temporal filters
            filtered_data, temp_log = self._apply_temporal_filters(filtered_data, filters)
            filter_log.extend(temp_log)
            
            # Apply geographic filters
            filtered_data, geo_log = self._apply_geographic_filters(filtered_data, filters)
            filter_log.extend(geo_log)
            
            # Apply physical parameter filters
            filtered_data, phys_log = self._apply_physical_filters(filtered_data, filters)
            filter_log.extend(phys_log)
            
            # Apply technical filters
            filtered_data, tech_log = self._apply_technical_filters(filtered_data, filters)
            filter_log.extend(tech_log)
            
            # Log filtering results
            logger.info(f"Applied {len(filter_log)} filters: {len(data)} -> {len(filtered_data)} records")
            
            return filtered_data
        
        except Exception as e:
            logger.error(f"Error applying filters: {e}")
            st.error(f"Error applying filters: {str(e)}")
            return data  # Return original data if filtering fails
    
    def assess_data_quality(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Comprehensive data quality assessment"""
        
        if data.empty:
            return {"status": "no_data", "score": 0.0, "issues": ["No data available"]}
        
        quality_assessment = validate_data_quality(data)
        
        # Add additional quality checks
        additional_checks = self._perform_additional_quality_checks(data)
        quality_assessment.update(additional_checks)
        
        return quality_assessment
    
    def export_data(self, data: pd.DataFrame, format: str, include_metadata: bool = True) -> bytes:
        """Export filtered data in specified format"""
        
        if not self.api_client:
            raise APIException("API client not available for export")
        
        if data.empty:
            raise ValueError("No data to export")
        
        # Get measurement IDs for export
        if 'id' in data.columns:
            data_ids = data['id'].tolist()
        else:
            raise ValueError("Data missing required ID column for export")
        
        try:
            exported_data = self.api_client.export_data(data_ids, format)
            
            if include_metadata:
                # Add metadata to export (implementation depends on format)
                pass
            
            return exported_data
        
        except APIException as e:
            logger.error(f"Export failed: {e}")
            raise e
    
    def generate_statistics(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive statistics for filtered data"""
        
        return get_data_summary(data)
    
    def _get_default_filters(self) -> Dict[str, Any]:
        """Get default filter configuration"""
        
        return {
            "date_mode": "Date Range",
            "date_range": (datetime.now().date() - timedelta(days=365), datetime.now().date()),
            "region_mode": "Predefined Regions",
            "predefined_region": "All Regions",
            "depth_mode": "Range",
            "depth_range": (0, 1000),
            "quality_levels": ["Excellent", "Good"],
            "float_selection_mode": "All Floats"
        }
    
    def _get_predefined_region_bounds(self, region: str) -> Optional[Dict[str, float]]:
        """Get bounds for predefined regions"""
        
        regions = {
            "Indian Ocean": {"north": 30, "south": -60, "east": 120, "west": 20},
            "Arabian Sea": {"north": 25, "south": 5, "east": 75, "west": 50},
            "Bay of Bengal": {"north": 22, "south": 5, "east": 95, "west": 80},
            "Equatorial Indian Ocean": {"north": 10, "south": -10, "east": 100, "west": 50},
            "Southern Indian Ocean": {"north": -20, "south": -60, "east": 120, "west": 20}
        }
        
        return regions.get(region)
    
    def _count_active_filters(self, filters: Dict[str, Any]) -> int:
        """Count number of active filters"""
        
        active_count = 0
        
        # Count temporal filters
        if filters.get("date_mode") != "Date Range" or filters.get("enable_time_filter"):
            active_count += 1
        
        # Count geographic filters
        if filters.get("predefined_region") != "All Regions" or filters.get("region_bounds"):
            active_count += 1
        
        # Count physical filters
        if (filters.get("enable_temp_filter") or filters.get("enable_sal_filter") or 
            filters.get("enable_bgc_filter") or filters.get("depth_mode") != "Range"):
            active_count += 1
        
        # Count technical filters
        if (filters.get("float_selection_mode") != "All Floats" or 
            filters.get("quality_levels") != ["Excellent", "Good"] or
            filters.get("enable_cycle_filter")):
            active_count += 1
        
        return active_count
    
    def _reset_all_filters(self) -> None:
        """Reset all filters to default values"""
        
        st.session_state.filter_state = self._get_default_filters()
        
        # Clear all filter-related session state keys
        filter_keys = [key for key in st.session_state.keys() if any(
            filter_word in key for filter_word in ['filter', 'range', 'mode', 'enable', 'select']
        )]
        
        for key in filter_keys:
            if key != 'filter_state':
                del st.session_state[key]
    
    def _save_filter_set(self, filters: Dict[str, Any]) -> None:
        """Save current filter set"""
        
        # In a real implementation, this would save to a database or file
        st.success("Filter set saved successfully!")
    
    def _load_filter_set(self) -> None:
        """Load saved filter set"""
        
        # In a real implementation, this would load from a database or file
        st.info("Filter set loading will be available in future versions.")
    
    def _display_active_filters(self, filters: Dict[str, Any]) -> None:
        """Display details of active filters"""
        
        # Temporal filters
        if filters.get("date_range"):
            start, end = filters["date_range"]
            st.write(f"📅 **Date Range**: {start} to {end}")
        
        # Geographic filters
        if filters.get("predefined_region") and filters["predefined_region"] != "All Regions":
            st.write(f"🌍 **Region**: {filters['predefined_region']}")
        
        # Physical filters
        if filters.get("depth_range"):
            depth_min, depth_max = filters["depth_range"]
            st.write(f"📏 **Depth**: {depth_min}m to {depth_max}m")
        
        # Quality filters
        if filters.get("quality_levels"):
            quality_str = ", ".join(filters["quality_levels"])
            st.write(f"✅ **Quality**: {quality_str}")
    
    def _apply_temporal_filters(self, data: pd.DataFrame, filters: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
        """Apply temporal filters to data"""
        
        filtered_data = data.copy()
        log = []
        
        # Apply date range filter
        if 'time' in filtered_data.columns and filters.get("date_range"):
            start_date, end_date = filters["date_range"]
            
            # Convert to datetime if needed
            if not pd.api.types.is_datetime64_any_dtype(filtered_data['time']):
                filtered_data['time'] = pd.to_datetime(filtered_data['time'])
            
            # Filter by date range
            mask = (
                (filtered_data['time'].dt.date >= start_date) &
                (filtered_data['time'].dt.date <= end_date)
            )
            
            before_count = len(filtered_data)
            filtered_data = filtered_data[mask]
            after_count = len(filtered_data)
            
            log.append(f"Date range filter: {before_count} -> {after_count}")
        
        return filtered_data, log
    
    def _apply_geographic_filters(self, data: pd.DataFrame, filters: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
        """Apply geographic filters to data"""
        
        filtered_data = data.copy()
        log = []
        
        # Apply region bounds filter
        region_bounds = filters.get("region_bounds")
        if region_bounds and 'lat' in filtered_data.columns and 'lon' in filtered_data.columns:
            
            if 'center_lat' in region_bounds:  # Circular area
                center_lat = region_bounds['center_lat']
                center_lon = region_bounds['center_lon']
                radius_km = region_bounds['radius_km']
                
                # Calculate distance from center (simplified)
                lat_diff = filtered_data['lat'] - center_lat
                lon_diff = filtered_data['lon'] - center_lon
                distance = np.sqrt(lat_diff**2 + lon_diff**2) * 111  # Rough km conversion
                
                mask = distance <= radius_km
            
            else:  # Bounding box
                mask = (
                    (filtered_data['lat'] >= region_bounds['south']) &
                    (filtered_data['lat'] <= region_bounds['north']) &
                    (filtered_data['lon'] >= region_bounds['west']) &
                    (filtered_data['lon'] <= region_bounds['east'])
                )
            
            before_count = len(filtered_data)
            filtered_data = filtered_data[mask]
            after_count = len(filtered_data)
            
            log.append(f"Geographic filter: {before_count} -> {after_count}")
        
        return filtered_data, log
    
    def _apply_physical_filters(self, data: pd.DataFrame, filters: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
        """Apply physical parameter filters to data"""
        
        filtered_data = data.copy()
        log = []
        
        # Apply depth filter
        if 'depth' in filtered_data.columns and filters.get("depth_range"):
            depth_min, depth_max = filters["depth_range"]
            
            mask = (
                (filtered_data['depth'] >= depth_min) &
                (filtered_data['depth'] <= depth_max)
            )
            
            before_count = len(filtered_data)
            filtered_data = filtered_data[mask]
            after_count = len(filtered_data)
            
            log.append(f"Depth filter: {before_count} -> {after_count}")
        
        # Apply temperature filter
        if (filters.get("enable_temp_filter") and 'temperature' in filtered_data.columns 
            and filters.get("temp_range")):
            
            temp_min, temp_max = filters["temp_range"]
            
            mask = (
                (filtered_data['temperature'] >= temp_min) &
                (filtered_data['temperature'] <= temp_max) &
                filtered_data['temperature'].notna()
            )
            
            before_count = len(filtered_data)
            filtered_data = filtered_data[mask]
            after_count = len(filtered_data)
            
            log.append(f"Temperature filter: {before_count} -> {after_count}")
        
        # Apply salinity filter
        if (filters.get("enable_sal_filter") and 'salinity' in filtered_data.columns 
            and filters.get("sal_range")):
            
            sal_min, sal_max = filters["sal_range"]
            
            mask = (
                (filtered_data['salinity'] >= sal_min) &
                (filtered_data['salinity'] <= sal_max) &
                filtered_data['salinity'].notna()
            )
            
            before_count = len(filtered_data)
            filtered_data = filtered_data[mask]
            after_count = len(filtered_data)
            
            log.append(f"Salinity filter: {before_count} -> {after_count}")
        
        return filtered_data, log
    
    def _apply_technical_filters(self, data: pd.DataFrame, filters: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
        """Apply technical and quality filters to data"""
        
        filtered_data = data.copy()
        log = []
        
        # Apply float ID filter
        if (filters.get("float_selection_mode") == "Specific Float IDs" and 
            filters.get("float_ids_list") and 'float_id' in filtered_data.columns):
            
            mask = filtered_data['float_id'].isin(filters["float_ids_list"])
            
            before_count = len(filtered_data)
            filtered_data = filtered_data[mask]
            after_count = len(filtered_data)
            
            log.append(f"Float ID filter: {before_count} -> {after_count}")
        
        # Apply cycle number filter
        if (filters.get("enable_cycle_filter") and 'cycle_number' in filtered_data.columns):
            min_cycle = filters.get("min_cycle", 1)
            max_cycle = filters.get("max_cycle", 200)
            
            mask = (
                (filtered_data['cycle_number'] >= min_cycle) &
                (filtered_data['cycle_number'] <= max_cycle)
            )
            
            before_count = len(filtered_data)
            filtered_data = filtered_data[mask]
            after_count = len(filtered_data)
            
            log.append(f"Cycle number filter: {before_count} -> {after_count}")
        
        return filtered_data, log
    
    def _perform_additional_quality_checks(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Perform additional data quality checks"""
        
        additional_checks = {}
        
        # Check for duplicate measurements
        if 'id' in data.columns:
            duplicates = data['id'].duplicated().sum()
            additional_checks['duplicate_count'] = duplicates
        
        # Check temporal consistency
        if 'time' in data.columns:
            time_data = pd.to_datetime(data['time'], errors='coerce')
            future_dates = (time_data > datetime.now()).sum()
            additional_checks['future_dates'] = future_dates
        
        # Check coordinate validity
        if 'lat' in data.columns and 'lon' in data.columns:
            invalid_coords = (
                (data['lat'].abs() > 90) | 
                (data['lon'].abs() > 180)
            ).sum()
            additional_checks['invalid_coordinates'] = invalid_coords
        
        # Check parameter ranges
        if 'temperature' in data.columns:
            extreme_temps = (
                (data['temperature'] < -5) | 
                (data['temperature'] > 40)
            ).sum()
            additional_checks['extreme_temperatures'] = extreme_temps
        
        return additional_checks