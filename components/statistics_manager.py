"""
Statistics Manager Component for ARGO Float Dashboard

This component handles statistical analysis, data quality assessment,
and summary displays for oceanographic data.
"""

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class StatisticsManager:
    """Manages statistical analysis and data quality assessment for ARGO data."""
    
    def __init__(self):
        """Initialize the statistics manager."""
        self.quality_flags = {
            0: "No QC performed",
            1: "Good data", 
            2: "Probably good data",
            3: "Bad data that are potentially correctable",
            4: "Bad data",
            5: "Value changed",
            6: "Not used",
            7: "Not used", 
            8: "Interpolated value",
            9: "Missing value"
        }
        
        self.quality_colors = {
            0: "#808080",  # Gray
            1: "#00FF00",  # Green
            2: "#90EE90",  # Light Green
            3: "#FFA500",  # Orange
            4: "#FF0000",  # Red
            5: "#FFFF00",  # Yellow
            6: "#800080",  # Purple
            7: "#800080",  # Purple
            8: "#00FFFF",  # Cyan
            9: "#000000"   # Black
        }
    
    def generate_dataset_summary(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate comprehensive dataset summary statistics.
        
        Args:
            data: DataFrame containing ARGO float data
            
        Returns:
            Dictionary containing summary statistics
        """
        try:
            if data.empty:
                return {
                    'total_floats': 0,
                    'total_profiles': 0,
                    'total_measurements': 0,
                    'date_range': None,
                    'geographic_coverage': None,
                    'depth_coverage': None,
                    'parameters': []
                }
            
            summary = {}
            
            # Basic counts
            summary['total_floats'] = data['float_id'].nunique() if 'float_id' in data.columns else 0
            summary['total_profiles'] = data['profile_id'].nunique() if 'profile_id' in data.columns else len(data)
            summary['total_measurements'] = len(data)
            
            # Temporal coverage
            if 'date' in data.columns:
                date_col = pd.to_datetime(data['date'])
                summary['date_range'] = {
                    'start': date_col.min(),
                    'end': date_col.max(),
                    'span_days': (date_col.max() - date_col.min()).days
                }
            else:
                summary['date_range'] = None
            
            # Geographic coverage
            if 'latitude' in data.columns and 'longitude' in data.columns:
                summary['geographic_coverage'] = {
                    'lat_min': data['latitude'].min(),
                    'lat_max': data['latitude'].max(),
                    'lon_min': data['longitude'].min(),
                    'lon_max': data['longitude'].max(),
                    'lat_span': data['latitude'].max() - data['latitude'].min(),
                    'lon_span': data['longitude'].max() - data['longitude'].min()
                }
            else:
                summary['geographic_coverage'] = None
            
            # Depth coverage
            if 'depth' in data.columns:
                summary['depth_coverage'] = {
                    'min_depth': data['depth'].min(),
                    'max_depth': data['depth'].max(),
                    'mean_depth': data['depth'].mean(),
                    'depth_span': data['depth'].max() - data['depth'].min()
                }
            else:
                summary['depth_coverage'] = None
            
            # Available parameters
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            parameter_columns = [col for col in numeric_columns 
                               if col not in ['latitude', 'longitude', 'depth', 'profile_id', 'float_id']]
            summary['parameters'] = list(parameter_columns)
            
            # Data quality overview
            if 'quality_flag' in data.columns:
                quality_counts = data['quality_flag'].value_counts()
                summary['quality_overview'] = {
                    'flags': quality_counts.to_dict(),
                    'good_data_percentage': (
                        (quality_counts.get(1, 0) + quality_counts.get(2, 0)) / len(data) * 100
                        if len(data) > 0 else 0
                    )
                }
            else:
                summary['quality_overview'] = None
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating dataset summary: {e}")
            return {}
    
    def calculate_parameter_statistics(self, data: pd.DataFrame, parameter: str) -> Dict[str, float]:
        """
        Calculate statistical measures for a specific parameter.
        
        Args:
            data: DataFrame containing the data
            parameter: Name of the parameter column
            
        Returns:
            Dictionary containing statistical measures
        """
        try:
            if parameter not in data.columns or data[parameter].empty:
                return {}
            
            values = data[parameter].dropna()
            
            if len(values) == 0:
                return {}
            
            stats = {
                'count': len(values),
                'mean': float(values.mean()),
                'median': float(values.median()),
                'std': float(values.std()),
                'min': float(values.min()),
                'max': float(values.max()),
                'q25': float(values.quantile(0.25)),
                'q75': float(values.quantile(0.75)),
                'range': float(values.max() - values.min()),
                'coefficient_of_variation': float(values.std() / values.mean()) if values.mean() != 0 else 0
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating statistics for {parameter}: {e}")
            return {}
    
    def assess_data_quality(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Assess data quality and identify issues.
        
        Args:
            data: DataFrame containing ARGO data
            
        Returns:
            Dictionary containing quality assessment results
        """
        try:
            assessment = {
                'overall_score': 0,
                'issues': [],
                'recommendations': [],
                'quality_flags_summary': {},
                'missing_data_analysis': {},
                'outlier_analysis': {}
            }
            
            if data.empty:
                assessment['issues'].append("No data available for quality assessment")
                return assessment
            
            # Quality flags analysis
            if 'quality_flag' in data.columns:
                flag_counts = data['quality_flag'].value_counts()
                total_records = len(data)
                
                assessment['quality_flags_summary'] = {
                    'flag_distribution': flag_counts.to_dict(),
                    'good_data_percentage': (
                        (flag_counts.get(1, 0) + flag_counts.get(2, 0)) / total_records * 100
                    ),
                    'bad_data_percentage': (
                        (flag_counts.get(3, 0) + flag_counts.get(4, 0)) / total_records * 100
                    )
                }
                
                # Quality score based on good data percentage
                good_percentage = assessment['quality_flags_summary']['good_data_percentage']
                if good_percentage >= 90:
                    assessment['overall_score'] = 5
                elif good_percentage >= 80:
                    assessment['overall_score'] = 4
                elif good_percentage >= 70:
                    assessment['overall_score'] = 3
                elif good_percentage >= 60:
                    assessment['overall_score'] = 2
                else:
                    assessment['overall_score'] = 1
                
                # Add issues based on quality flags
                if flag_counts.get(4, 0) > total_records * 0.1:
                    assessment['issues'].append(f"High percentage of bad data: {flag_counts.get(4, 0)/total_records*100:.1f}%")
                
                if flag_counts.get(9, 0) > total_records * 0.2:
                    assessment['issues'].append(f"High percentage of missing values: {flag_counts.get(9, 0)/total_records*100:.1f}%")
            
            # Missing data analysis
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            missing_analysis = {}
            
            for col in numeric_columns:
                missing_count = data[col].isna().sum()
                missing_percentage = (missing_count / len(data)) * 100
                missing_analysis[col] = {
                    'missing_count': missing_count,
                    'missing_percentage': missing_percentage
                }
                
                if missing_percentage > 50:
                    assessment['issues'].append(f"High missing data in {col}: {missing_percentage:.1f}%")
            
            assessment['missing_data_analysis'] = missing_analysis
            
            # Outlier detection using IQR method
            outlier_analysis = {}
            for col in numeric_columns:
                if col in ['latitude', 'longitude', 'depth']:
                    continue
                    
                values = data[col].dropna()
                if len(values) > 0:
                    Q1 = values.quantile(0.25)
                    Q3 = values.quantile(0.75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    
                    outliers = values[(values < lower_bound) | (values > upper_bound)]
                    outlier_percentage = (len(outliers) / len(values)) * 100
                    
                    outlier_analysis[col] = {
                        'outlier_count': len(outliers),
                        'outlier_percentage': outlier_percentage,
                        'lower_bound': lower_bound,
                        'upper_bound': upper_bound
                    }
                    
                    if outlier_percentage > 5:
                        assessment['issues'].append(f"High outlier percentage in {col}: {outlier_percentage:.1f}%")
            
            assessment['outlier_analysis'] = outlier_analysis
            
            # Generate recommendations
            if assessment['overall_score'] < 3:
                assessment['recommendations'].append("Consider filtering out bad quality data before analysis")
            
            if len(assessment['issues']) == 0:
                assessment['recommendations'].append("Data quality appears good for analysis")
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error assessing data quality: {e}")
            return {'overall_score': 0, 'issues': [f"Error in quality assessment: {str(e)}"]}
    
    def create_quality_flag_visualization(self, data: pd.DataFrame) -> go.Figure:
        """
        Create visualization of quality flags distribution.
        
        Args:
            data: DataFrame containing quality flag data
            
        Returns:
            Plotly figure showing quality flag distribution
        """
        try:
            if 'quality_flag' in data.columns:
                flag_counts = data['quality_flag'].value_counts().sort_index()
                
                # Map flags to descriptions
                flag_labels = [f"{flag}: {self.quality_flags.get(flag, 'Unknown')}" 
                              for flag in flag_counts.index]
                colors = [self.quality_colors.get(flag, '#808080') for flag in flag_counts.index]
                
                fig = go.Figure(data=[
                    go.Bar(
                        x=flag_labels,
                        y=flag_counts.values,
                        marker_color=colors,
                        text=flag_counts.values,
                        textposition='auto'
                    )
                ])
                
                fig.update_layout(
                    title="Data Quality Flags Distribution",
                    xaxis_title="Quality Flag",
                    yaxis_title="Number of Records",
                    showlegend=False,
                    height=400
                )
                
                fig.update_xaxes(tickangle=45)
                
                return fig
            else:
                # Create empty figure with message
                fig = go.Figure()
                fig.add_annotation(
                    text="No quality flag data available",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, xanchor='center', yanchor='middle',
                    showarrow=False, font_size=16
                )
                fig.update_layout(
                    title="Data Quality Flags Distribution",
                    height=400
                )
                return fig
                
        except Exception as e:
            logger.error(f"Error creating quality flag visualization: {e}")
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error creating visualization: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False, font_size=16
            )
            return fig
    
    def create_statistics_summary_plot(self, data: pd.DataFrame, parameters: List[str]) -> go.Figure:
        """
        Create summary statistics visualization for multiple parameters.
        
        Args:
            data: DataFrame containing the data
            parameters: List of parameter names to analyze
            
        Returns:
            Plotly figure showing statistics summary
        """
        try:
            if not parameters or data.empty:
                fig = go.Figure()
                fig.add_annotation(
                    text="No parameters selected or no data available",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, xanchor='center', yanchor='middle',
                    showarrow=False, font_size=16
                )
                return fig
            
            # Calculate statistics for each parameter
            stats_data = []
            for param in parameters:
                if param in data.columns:
                    stats = self.calculate_parameter_statistics(data, param)
                    if stats:
                        stats['parameter'] = param
                        stats_data.append(stats)
            
            if not stats_data:
                fig = go.Figure()
                fig.add_annotation(
                    text="No valid statistics calculated",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, xanchor='center', yanchor='middle',
                    showarrow=False, font_size=16
                )
                return fig
            
            stats_df = pd.DataFrame(stats_data)
            
            # Create subplots for different statistics
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Mean Values', 'Standard Deviation', 'Data Range', 'Data Count'),
                specs=[[{"secondary_y": False}, {"secondary_y": False}],
                       [{"secondary_y": False}, {"secondary_y": False}]]
            )
            
            # Mean values
            fig.add_trace(
                go.Bar(x=stats_df['parameter'], y=stats_df['mean'], name='Mean'),
                row=1, col=1
            )
            
            # Standard deviation
            fig.add_trace(
                go.Bar(x=stats_df['parameter'], y=stats_df['std'], name='Std Dev'),
                row=1, col=2
            )
            
            # Range (max - min)
            fig.add_trace(
                go.Bar(x=stats_df['parameter'], y=stats_df['range'], name='Range'),
                row=2, col=1
            )
            
            # Data count
            fig.add_trace(
                go.Bar(x=stats_df['parameter'], y=stats_df['count'], name='Count'),
                row=2, col=2
            )
            
            fig.update_layout(
                title="Parameter Statistics Summary",
                height=600,
                showlegend=False
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating statistics summary plot: {e}")
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error creating visualization: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False, font_size=16
            )
            return fig
    
    def render_dataset_overview(self, data: pd.DataFrame) -> None:
        """
        Render dataset overview section in Streamlit.
        
        Args:
            data: DataFrame containing ARGO data
        """
        try:
            st.subheader("📊 Dataset Overview")
            
            summary = self.generate_dataset_summary(data)
            
            if not summary:
                st.warning("No data available for summary")
                return
            
            # Create metrics columns
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Floats", summary.get('total_floats', 0))
            
            with col2:
                st.metric("Total Profiles", summary.get('total_profiles', 0))
            
            with col3:
                st.metric("Total Measurements", summary.get('total_measurements', 0))
            
            with col4:
                if summary.get('quality_overview'):
                    good_percentage = summary['quality_overview']['good_data_percentage']
                    st.metric("Good Data %", f"{good_percentage:.1f}%")
                else:
                    st.metric("Good Data %", "N/A")
            
            # Temporal and geographic coverage
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Temporal Coverage**")
                if summary.get('date_range'):
                    date_range = summary['date_range']
                    st.write(f"Start: {date_range['start'].strftime('%Y-%m-%d')}")
                    st.write(f"End: {date_range['end'].strftime('%Y-%m-%d')}")
                    st.write(f"Span: {date_range['span_days']} days")
                else:
                    st.write("No temporal data available")
            
            with col2:
                st.write("**Geographic Coverage**")
                if summary.get('geographic_coverage'):
                    geo = summary['geographic_coverage']
                    st.write(f"Latitude: {geo['lat_min']:.2f}° to {geo['lat_max']:.2f}°")
                    st.write(f"Longitude: {geo['lon_min']:.2f}° to {geo['lon_max']:.2f}°")
                    st.write(f"Area: {geo['lat_span']:.1f}° × {geo['lon_span']:.1f}°")
                else:
                    st.write("No geographic data available")
            
            # Available parameters
            if summary.get('parameters'):
                st.write("**Available Parameters**")
                st.write(", ".join(summary['parameters']))
            
        except Exception as e:
            logger.error(f"Error rendering dataset overview: {e}")
            st.error(f"Error displaying dataset overview: {str(e)}")
    
    def render_data_quality_assessment(self, data: pd.DataFrame) -> None:
        """
        Render data quality assessment section in Streamlit.
        
        Args:
            data: DataFrame containing ARGO data
        """
        try:
            st.subheader("🔍 Data Quality Assessment")
            
            assessment = self.assess_data_quality(data)
            
            # Overall quality score
            col1, col2 = st.columns([1, 3])
            
            with col1:
                score = assessment.get('overall_score', 0)
                if score >= 4:
                    st.success(f"Quality Score: {score}/5")
                elif score >= 3:
                    st.warning(f"Quality Score: {score}/5")
                else:
                    st.error(f"Quality Score: {score}/5")
            
            with col2:
                if assessment.get('issues'):
                    st.write("**Issues Identified:**")
                    for issue in assessment['issues']:
                        st.write(f"• {issue}")
                else:
                    st.success("No major quality issues identified")
            
            # Quality flags visualization
            if 'quality_flag' in data.columns:
                st.write("**Quality Flags Distribution**")
                quality_fig = self.create_quality_flag_visualization(data)
                st.plotly_chart(quality_fig, use_container_width=True)
            
            # Missing data analysis
            if assessment.get('missing_data_analysis'):
                st.write("**Missing Data Analysis**")
                missing_data = []
                for param, info in assessment['missing_data_analysis'].items():
                    missing_data.append({
                        'Parameter': param,
                        'Missing Count': info['missing_count'],
                        'Missing %': f"{info['missing_percentage']:.1f}%"
                    })
                
                if missing_data:
                    missing_df = pd.DataFrame(missing_data)
                    st.dataframe(missing_df, use_container_width=True)
            
            # Recommendations
            if assessment.get('recommendations'):
                st.write("**Recommendations**")
                for rec in assessment['recommendations']:
                    st.info(rec)
            
        except Exception as e:
            logger.error(f"Error rendering data quality assessment: {e}")
            st.error(f"Error displaying data quality assessment: {str(e)}")
    
    def render_parameter_statistics(self, data: pd.DataFrame) -> None:
        """
        Render parameter statistics section in Streamlit.
        
        Args:
            data: DataFrame containing ARGO data
        """
        try:
            st.subheader("📈 Parameter Statistics")
            
            # Get numeric parameters
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            parameter_columns = [col for col in numeric_columns 
                               if col not in ['latitude', 'longitude', 'depth', 'profile_id', 'float_id']]
            
            if not parameter_columns:
                st.warning("No numeric parameters available for statistical analysis")
                return
            
            # Parameter selection
            selected_params = st.multiselect(
                "Select parameters for statistical analysis:",
                parameter_columns,
                default=parameter_columns[:3] if len(parameter_columns) >= 3 else parameter_columns
            )
            
            if not selected_params:
                st.info("Please select parameters to view statistics")
                return
            
            # Statistics table
            stats_data = []
            for param in selected_params:
                stats = self.calculate_parameter_statistics(data, param)
                if stats:
                    stats_data.append({
                        'Parameter': param,
                        'Count': stats['count'],
                        'Mean': f"{stats['mean']:.3f}",
                        'Median': f"{stats['median']:.3f}",
                        'Std Dev': f"{stats['std']:.3f}",
                        'Min': f"{stats['min']:.3f}",
                        'Max': f"{stats['max']:.3f}",
                        'Range': f"{stats['range']:.3f}"
                    })
            
            if stats_data:
                stats_df = pd.DataFrame(stats_data)
                st.dataframe(stats_df, use_container_width=True)
                
                # Statistics visualization
                st.write("**Statistics Visualization**")
                stats_fig = self.create_statistics_summary_plot(data, selected_params)
                st.plotly_chart(stats_fig, use_container_width=True)
            
        except Exception as e:
            logger.error(f"Error rendering parameter statistics: {e}")
            st.error(f"Error displaying parameter statistics: {str(e)}")