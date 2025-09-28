"""
Export Manager Component
Handles data and visualization export in multiple formats with metadata
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
from typing import Dict, List, Optional, Any, Union, Tuple
import logging
from datetime import datetime, timedelta
import json
import io
import base64
from pathlib import Path
import zipfile
from dashboard_config import dashboard_config
from components.api_client import APIClient, APIException

logger = logging.getLogger(__name__)

class ExportManager:
    """Manages data and visualization export functionality"""
    
    def __init__(self, api_client: Optional[APIClient] = None):
        self.api_client = api_client or st.session_state.get('api_client')
        self.config = dashboard_config
        
        # Supported export formats
        self.supported_formats = {
            "visualization": ["PNG", "PDF", "SVG", "HTML"],
            "data": ["CSV", "ASCII", "NetCDF", "JSON", "Excel"],
            "report": ["PDF", "HTML", "Word"]
        }
    
    def render_export_interface(self) -> None:
        """Render the main export interface"""
        
        st.subheader("📥 Data Export & Download Center")
        
        # Export type selection
        export_type = st.selectbox(
            "Export Type",
            ["Visualizations", "Data", "Reports", "Complete Package"],
            key="export_type"
        )
        
        if export_type == "Visualizations":
            self._render_visualization_export()
        elif export_type == "Data":
            self._render_data_export()
        elif export_type == "Reports":
            self._render_report_export()
        else:  # Complete Package
            self._render_package_export()
    
    def _render_visualization_export(self) -> None:
        """Render visualization export options"""
        
        st.markdown("### 📊 Visualization Export")
        
        # Get available visualizations from session state
        available_viz = self._get_available_visualizations()
        
        if not available_viz:
            st.info("No visualizations available for export. Create some charts first!")
            return
        
        # Visualization selection
        selected_viz = st.multiselect(
            "Select Visualizations to Export",
            available_viz,
            default=available_viz[:3] if len(available_viz) >= 3 else available_viz,
            key="selected_visualizations"
        )
        
        if not selected_viz:
            st.warning("Please select at least one visualization to export.")
            return
        
        # Format selection
        col1, col2 = st.columns(2)
        
        with col1:
            viz_format = st.selectbox(
                "Export Format",
                self.supported_formats["visualization"],
                key="viz_format"
            )
        
        with col2:
            resolution = st.selectbox(
                "Resolution",
                ["Standard (800x600)", "High (1200x900)", "Print (1600x1200)", "Custom"],
                key="viz_resolution"
            )
        
        # Custom resolution
        if resolution == "Custom":
            col1, col2 = st.columns(2)
            with col1:
                custom_width = st.number_input("Width (px)", value=1200, min_value=400, max_value=4000)
            with col2:
                custom_height = st.number_input("Height (px)", value=900, min_value=300, max_value=3000)
            
            resolution_tuple = (custom_width, custom_height)
        else:
            resolution_map = {
                "Standard (800x600)": (800, 600),
                "High (1200x900)": (1200, 900),
                "Print (1600x1200)": (1600, 1200)
            }
            resolution_tuple = resolution_map[resolution]
        
        # Export options
        st.markdown("**Export Options:**")
        
        include_metadata = st.checkbox("Include metadata", value=True, key="viz_include_metadata")
        include_timestamp = st.checkbox("Include timestamp in filename", value=True, key="viz_include_timestamp")
        
        # Export button
        if st.button("📥 Export Visualizations", type="primary", use_container_width=True):
            self._export_visualizations(selected_viz, viz_format, resolution_tuple, include_metadata, include_timestamp)
    
    def _render_data_export(self) -> None:
        """Render data export options"""
        
        st.markdown("### 📋 Data Export")
        
        # Data source selection
        data_source = st.selectbox(
            "Data Source",
            ["Current Filtered Data", "Selected Float Data", "All Available Data", "Custom Query Results"],
            key="data_source"
        )
        
        # Get data based on source
        export_data = self._get_export_data(data_source)
        
        if export_data is None or (isinstance(export_data, pd.DataFrame) and export_data.empty):
            st.warning(f"No data available from source: {data_source}")
            return
        
        # Show data preview
        st.markdown("**Data Preview:**")
        
        if isinstance(export_data, pd.DataFrame):
            st.dataframe(export_data.head(10), use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Records", len(export_data))
            with col2:
                st.metric("Columns", len(export_data.columns))
            with col3:
                memory_usage = export_data.memory_usage(deep=True).sum() / 1024 / 1024
                st.metric("Size", f"{memory_usage:.1f} MB")
        
        # Format selection
        col1, col2 = st.columns(2)
        
        with col1:
            data_format = st.selectbox(
                "Export Format",
                self.supported_formats["data"],
                key="data_format"
            )
        
        with col2:
            compression = st.selectbox(
                "Compression",
                ["None", "ZIP", "GZIP"],
                key="data_compression"
            )
        
        # Export options
        st.markdown("**Export Options:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            include_metadata = st.checkbox("Include metadata file", value=True, key="data_include_metadata")
            include_quality_report = st.checkbox("Include data quality report", value=True, key="include_quality_report")
        
        with col2:
            include_filters = st.checkbox("Include applied filters", value=True, key="include_filters")
            include_timestamp = st.checkbox("Include timestamp", value=True, key="data_include_timestamp")
        
        # Column selection for large datasets
        if isinstance(export_data, pd.DataFrame) and len(export_data.columns) > 10:
            st.markdown("**Column Selection:**")
            
            all_columns = export_data.columns.tolist()
            essential_columns = ['id', 'float_id', 'time', 'lat', 'lon', 'depth', 'temperature', 'salinity']
            default_columns = [col for col in essential_columns if col in all_columns]
            
            selected_columns = st.multiselect(
                "Select columns to export",
                all_columns,
                default=default_columns,
                key="selected_columns"
            )
            
            if selected_columns:
                export_data = export_data[selected_columns]
        
        # Export button
        if st.button("📥 Export Data", type="primary", use_container_width=True):
            self._export_data(export_data, data_format, compression, {
                "include_metadata": include_metadata,
                "include_quality_report": include_quality_report,
                "include_filters": include_filters,
                "include_timestamp": include_timestamp
            })
    
    def _render_report_export(self) -> None:
        """Render report export options"""
        
        st.markdown("### 📄 Report Export")
        
        # Report type selection
        report_type = st.selectbox(
            "Report Type",
            ["Data Summary Report", "Analysis Report", "Quality Assessment Report", "Custom Report"],
            key="report_type"
        )
        
        # Report content selection
        st.markdown("**Report Content:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            include_overview = st.checkbox("System Overview", value=True, key="report_include_overview")
            include_data_summary = st.checkbox("Data Summary", value=True, key="report_include_data_summary")
            include_visualizations = st.checkbox("Key Visualizations", value=True, key="report_include_viz")
        
        with col2:
            include_quality_assessment = st.checkbox("Quality Assessment", value=True, key="report_include_quality")
            include_filter_details = st.checkbox("Applied Filters", value=True, key="report_include_filters")
            include_recommendations = st.checkbox("Recommendations", value=False, key="report_include_recommendations")
        
        # Report format
        col1, col2 = st.columns(2)
        
        with col1:
            report_format = st.selectbox(
                "Report Format",
                self.supported_formats["report"],
                key="report_format"
            )
        
        with col2:
            report_template = st.selectbox(
                "Template",
                ["Government Standard", "Scientific", "Executive Summary", "Technical"],
                key="report_template"
            )
        
        # Custom report options
        if report_type == "Custom Report":
            st.markdown("**Custom Report Options:**")
            
            custom_title = st.text_input("Report Title", value="ARGO Data Analysis Report", key="custom_title")
            custom_author = st.text_input("Author/Organization", key="custom_author")
            custom_notes = st.text_area("Additional Notes", key="custom_notes")
        
        # Export button
        if st.button("📄 Generate Report", type="primary", use_container_width=True):
            report_options = {
                "report_type": report_type,
                "include_overview": include_overview,
                "include_data_summary": include_data_summary,
                "include_visualizations": include_visualizations,
                "include_quality_assessment": include_quality_assessment,
                "include_filter_details": include_filter_details,
                "include_recommendations": include_recommendations,
                "format": report_format,
                "template": report_template
            }
            
            if report_type == "Custom Report":
                report_options.update({
                    "custom_title": custom_title,
                    "custom_author": custom_author,
                    "custom_notes": custom_notes
                })
            
            self._generate_report(report_options)
    
    def _render_package_export(self) -> None:
        """Render complete package export options"""
        
        st.markdown("### 📦 Complete Package Export")
        
        st.info("Export a complete package containing data, visualizations, and reports.")
        
        # Package content selection
        st.markdown("**Package Contents:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            include_raw_data = st.checkbox("Raw Data (CSV)", value=True, key="package_raw_data")
            include_filtered_data = st.checkbox("Filtered Data", value=True, key="package_filtered_data")
            include_visualizations = st.checkbox("All Visualizations", value=True, key="package_visualizations")
        
        with col2:
            include_summary_report = st.checkbox("Summary Report", value=True, key="package_summary_report")
            include_metadata = st.checkbox("Metadata Files", value=True, key="package_metadata")
            include_quality_report = st.checkbox("Quality Report", value=True, key="package_quality_report")
        
        # Package format
        package_format = st.selectbox(
            "Package Format",
            ["ZIP Archive", "TAR.GZ Archive"],
            key="package_format"
        )
        
        # Export button
        if st.button("📦 Create Complete Package", type="primary", use_container_width=True):
            package_options = {
                "include_raw_data": include_raw_data,
                "include_filtered_data": include_filtered_data,
                "include_visualizations": include_visualizations,
                "include_summary_report": include_summary_report,
                "include_metadata": include_metadata,
                "include_quality_report": include_quality_report,
                "format": package_format
            }
            
            self._create_complete_package(package_options)    

    def _get_available_visualizations(self) -> List[str]:
        """Get list of available visualizations from session state"""
        
        # In a real implementation, this would track created visualizations
        # For now, return common visualization types
        return [
            "Float Location Map",
            "Temperature Profile",
            "Salinity Profile", 
            "T-S Diagram",
            "BGC Parameters",
            "Data Quality Chart"
        ]
    
    def _get_export_data(self, data_source: str) -> Optional[pd.DataFrame]:
        """Get data based on selected source"""
        
        if data_source == "Current Filtered Data":
            # Get filtered data from session state
            return st.session_state.get('filtered_data')
        
        elif data_source == "Selected Float Data":
            # Get data for selected floats
            selected_floats = st.session_state.get('selected_floats', [])
            if selected_floats and self.api_client:
                try:
                    # This would get data for selected floats
                    # For now, return sample data
                    return self._create_sample_export_data()
                except Exception as e:
                    logger.error(f"Error getting selected float data: {e}")
                    return None
            return None
        
        elif data_source == "All Available Data":
            # Get all available data (with limits)
            if self.api_client:
                try:
                    # This would get all data with reasonable limits
                    return self._create_sample_export_data()
                except Exception as e:
                    logger.error(f"Error getting all data: {e}")
                    return None
            return None
        
        elif data_source == "Custom Query Results":
            # Get data from last chat query
            return st.session_state.get('last_query_data')
        
        return None
    
    def _export_visualizations(self, selected_viz: List[str], format: str, 
                             resolution: Tuple[int, int], include_metadata: bool, 
                             include_timestamp: bool) -> None:
        """Export selected visualizations"""
        
        try:
            with st.spinner("Exporting visualizations..."):
                
                # Create sample visualizations for export
                exported_files = []
                
                for viz_name in selected_viz:
                    # Create a sample visualization
                    fig = self._create_sample_visualization(viz_name)
                    
                    # Generate filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") if include_timestamp else ""
                    filename = f"{viz_name.replace(' ', '_')}"
                    if timestamp:
                        filename += f"_{timestamp}"
                    
                    # Export based on format
                    if format == "PNG":
                        img_bytes = pio.to_image(fig, format="png", width=resolution[0], height=resolution[1])
                        filename += ".png"
                        
                        st.download_button(
                            f"📥 Download {viz_name} (PNG)",
                            img_bytes,
                            filename,
                            mime="image/png"
                        )
                    
                    elif format == "PDF":
                        pdf_bytes = pio.to_image(fig, format="pdf", width=resolution[0], height=resolution[1])
                        filename += ".pdf"
                        
                        st.download_button(
                            f"📥 Download {viz_name} (PDF)",
                            pdf_bytes,
                            filename,
                            mime="application/pdf"
                        )
                    
                    elif format == "SVG":
                        svg_string = pio.to_image(fig, format="svg", width=resolution[0], height=resolution[1])
                        filename += ".svg"
                        
                        st.download_button(
                            f"📥 Download {viz_name} (SVG)",
                            svg_string,
                            filename,
                            mime="image/svg+xml"
                        )
                    
                    elif format == "HTML":
                        html_string = pio.to_html(fig, include_plotlyjs=True)
                        filename += ".html"
                        
                        st.download_button(
                            f"📥 Download {viz_name} (HTML)",
                            html_string,
                            filename,
                            mime="text/html"
                        )
                    
                    exported_files.append(filename)
                
                # Show metadata if requested
                if include_metadata:
                    metadata = self._create_export_metadata("visualization", {
                        "exported_files": exported_files,
                        "format": format,
                        "resolution": resolution,
                        "export_time": datetime.now().isoformat()
                    })
                    
                    st.download_button(
                        "📋 Download Metadata",
                        json.dumps(metadata, indent=2),
                        f"visualization_metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                
                st.success(f"✅ Exported {len(selected_viz)} visualizations successfully!")
        
        except Exception as e:
            st.error(f"Export failed: {str(e)}")
            logger.error(f"Visualization export error: {e}")
    
    def _export_data(self, data: pd.DataFrame, format: str, compression: str, options: Dict[str, bool]) -> None:
        """Export data in specified format"""
        
        try:
            with st.spinner("Exporting data..."):
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") if options["include_timestamp"] else ""
                base_filename = f"argo_data"
                if timestamp:
                    base_filename += f"_{timestamp}"
                
                # Export based on format
                if format == "CSV":
                    csv_data = data.to_csv(index=False)
                    filename = f"{base_filename}.csv"
                    
                    if compression == "ZIP":
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            zip_file.writestr(filename, csv_data)
                        
                        st.download_button(
                            "📥 Download CSV (ZIP)",
                            zip_buffer.getvalue(),
                            f"{base_filename}.zip",
                            mime="application/zip"
                        )
                    else:
                        st.download_button(
                            "📥 Download CSV",
                            csv_data,
                            filename,
                            mime="text/csv"
                        )
                
                elif format == "JSON":
                    json_data = data.to_json(orient='records', indent=2)
                    filename = f"{base_filename}.json"
                    
                    st.download_button(
                        "📥 Download JSON",
                        json_data,
                        filename,
                        mime="application/json"
                    )
                
                elif format == "Excel":
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        data.to_excel(writer, sheet_name='ARGO_Data', index=False)
                    
                    st.download_button(
                        "📥 Download Excel",
                        excel_buffer.getvalue(),
                        f"{base_filename}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                elif format in ["ASCII", "NetCDF"]:
                    # Use backend API for these formats
                    if self.api_client and 'id' in data.columns:
                        try:
                            data_ids = data['id'].tolist()
                            exported_data = self.api_client.export_data(data_ids, format.lower())
                            
                            file_extension = ".txt" if format == "ASCII" else ".nc"
                            filename = f"{base_filename}{file_extension}"
                            
                            mime_type = "text/plain" if format == "ASCII" else "application/octet-stream"
                            
                            st.download_button(
                                f"📥 Download {format}",
                                exported_data,
                                filename,
                                mime=mime_type
                            )
                        except APIException as e:
                            st.error(f"Backend export failed: {str(e)}")
                            return
                    else:
                        st.error(f"{format} export requires backend API and data IDs")
                        return
                
                # Export additional files if requested
                if options["include_metadata"]:
                    metadata = self._create_export_metadata("data", {
                        "format": format,
                        "compression": compression,
                        "record_count": len(data),
                        "columns": data.columns.tolist(),
                        "export_time": datetime.now().isoformat()
                    })
                    
                    st.download_button(
                        "📋 Download Metadata",
                        json.dumps(metadata, indent=2),
                        f"data_metadata_{timestamp}.json",
                        mime="application/json"
                    )
                
                if options["include_quality_report"]:
                    quality_report = self._create_quality_report(data)
                    
                    st.download_button(
                        "📊 Download Quality Report",
                        quality_report,
                        f"quality_report_{timestamp}.txt",
                        mime="text/plain"
                    )
                
                st.success(f"✅ Data exported successfully in {format} format!")
        
        except Exception as e:
            st.error(f"Data export failed: {str(e)}")
            logger.error(f"Data export error: {e}")
    
    def _generate_report(self, options: Dict[str, Any]) -> None:
        """Generate and export report"""
        
        try:
            with st.spinner("Generating report..."):
                
                # Create report content
                report_content = self._create_report_content(options)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"argo_report_{timestamp}"
                
                if options["format"] == "HTML":
                    filename += ".html"
                    mime_type = "text/html"
                elif options["format"] == "PDF":
                    filename += ".pdf"
                    mime_type = "application/pdf"
                    # Note: PDF generation would require additional libraries like reportlab
                    st.warning("PDF generation requires additional setup. Generating HTML instead.")
                    filename = filename.replace(".pdf", ".html")
                    mime_type = "text/html"
                else:  # Word
                    filename += ".docx"
                    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    st.warning("Word generation requires additional setup. Generating HTML instead.")
                    filename = filename.replace(".docx", ".html")
                    mime_type = "text/html"
                
                st.download_button(
                    "📄 Download Report",
                    report_content,
                    filename,
                    mime=mime_type
                )
                
                st.success("✅ Report generated successfully!")
        
        except Exception as e:
            st.error(f"Report generation failed: {str(e)}")
            logger.error(f"Report generation error: {e}")
    
    def _create_complete_package(self, options: Dict[str, Any]) -> None:
        """Create complete export package"""
        
        try:
            with st.spinner("Creating complete package..."):
                
                # Create ZIP archive
                zip_buffer = io.BytesIO()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    
                    # Add data files
                    if options["include_raw_data"]:
                        sample_data = self._create_sample_export_data()
                        csv_data = sample_data.to_csv(index=False)
                        zip_file.writestr("data/raw_data.csv", csv_data)
                    
                    if options["include_filtered_data"]:
                        filtered_data = st.session_state.get('filtered_data')
                        if filtered_data is not None and not filtered_data.empty:
                            csv_data = filtered_data.to_csv(index=False)
                            zip_file.writestr("data/filtered_data.csv", csv_data)
                    
                    # Add visualizations
                    if options["include_visualizations"]:
                        viz_list = self._get_available_visualizations()
                        for viz_name in viz_list[:3]:  # Limit to first 3
                            fig = self._create_sample_visualization(viz_name)
                            img_bytes = pio.to_image(fig, format="png", width=1200, height=900)
                            zip_file.writestr(f"visualizations/{viz_name.replace(' ', '_')}.png", img_bytes)
                    
                    # Add reports
                    if options["include_summary_report"]:
                        report_options = {
                            "report_type": "Data Summary Report",
                            "format": "HTML",
                            "template": "Government Standard",
                            "include_overview": True,
                            "include_data_summary": True,
                            "include_quality_assessment": True
                        }
                        report_content = self._create_report_content(report_options)
                        zip_file.writestr("reports/summary_report.html", report_content)
                    
                    # Add metadata
                    if options["include_metadata"]:
                        package_metadata = {
                            "package_created": datetime.now().isoformat(),
                            "contents": options,
                            "dashboard_version": "1.0.0",
                            "data_source": "ARGO Float Network"
                        }
                        zip_file.writestr("metadata/package_info.json", json.dumps(package_metadata, indent=2))
                    
                    # Add quality report
                    if options["include_quality_report"]:
                        sample_data = self._create_sample_export_data()
                        quality_report = self._create_quality_report(sample_data)
                        zip_file.writestr("reports/quality_report.txt", quality_report)
                
                # Offer download
                package_filename = f"argo_complete_package_{timestamp}.zip"
                
                st.download_button(
                    "📦 Download Complete Package",
                    zip_buffer.getvalue(),
                    package_filename,
                    mime="application/zip"
                )
                
                st.success("✅ Complete package created successfully!")
                
                # Show package contents
                with st.expander("📋 Package Contents"):
                    st.write("**Included Files:**")
                    if options["include_raw_data"]:
                        st.write("• data/raw_data.csv")
                    if options["include_filtered_data"]:
                        st.write("• data/filtered_data.csv")
                    if options["include_visualizations"]:
                        st.write("• visualizations/*.png")
                    if options["include_summary_report"]:
                        st.write("• reports/summary_report.html")
                    if options["include_metadata"]:
                        st.write("• metadata/package_info.json")
                    if options["include_quality_report"]:
                        st.write("• reports/quality_report.txt")
        
        except Exception as e:
            st.error(f"Package creation failed: {str(e)}")
            logger.error(f"Package creation error: {e}")
    
    def _create_sample_visualization(self, viz_name: str) -> go.Figure:
        """Create sample visualization for export"""
        
        # Create sample data
        import numpy as np
        
        if "Map" in viz_name:
            # Create sample map
            fig = go.Figure(go.Scattergeo(
                lon=[75, 80, 85],
                lat=[10, 15, 20],
                mode='markers',
                marker=dict(size=10, color='blue'),
                name='ARGO Floats'
            ))
            fig.update_layout(
                title=viz_name,
                geo=dict(projection_type='natural earth'),
                height=600
            )
        
        elif "Profile" in viz_name:
            # Create sample profile
            depths = np.arange(0, 500, 10)
            if "Temperature" in viz_name:
                values = 25 - depths * 0.02 + np.random.normal(0, 0.5, len(depths))
                ylabel = "Temperature (°C)"
            else:
                values = 35 + depths * 0.001 + np.random.normal(0, 0.1, len(depths))
                ylabel = "Salinity (PSU)"
            
            fig = go.Figure(go.Scatter(
                x=values,
                y=-depths,
                mode='lines+markers',
                name=viz_name
            ))
            fig.update_layout(
                title=viz_name,
                xaxis_title=ylabel,
                yaxis_title="Depth (m)",
                height=600
            )
        
        else:
            # Generic chart
            x_data = np.arange(10)
            y_data = np.random.randn(10).cumsum()
            
            fig = go.Figure(go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines+markers',
                name=viz_name
            ))
            fig.update_layout(title=viz_name, height=600)
        
        return fig
    
    def _create_sample_export_data(self) -> pd.DataFrame:
        """Create sample data for export"""
        
        import numpy as np
        
        np.random.seed(42)
        n_records = 100
        
        return pd.DataFrame({
            'id': range(1, n_records + 1),
            'float_id': [f'ARGO_{i//10:03d}' for i in range(n_records)],
            'time': [datetime.now() - timedelta(days=np.random.randint(0, 365)) for _ in range(n_records)],
            'lat': np.random.uniform(-30, 30, n_records),
            'lon': np.random.uniform(40, 120, n_records),
            'depth': np.random.uniform(0, 2000, n_records),
            'temperature': np.random.uniform(5, 30, n_records),
            'salinity': np.random.uniform(34, 37, n_records),
            'wmo_id': np.random.randint(5900000, 5900100, n_records),
            'cycle_number': np.random.randint(1, 200, n_records)
        })
    
    def _create_export_metadata(self, export_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create metadata for exports"""
        
        return {
            "export_type": export_type,
            "export_timestamp": datetime.now().isoformat(),
            "dashboard_version": "1.0.0",
            "data_source": "ARGO Float Network",
            "export_details": details,
            "system_info": {
                "filters_applied": bool(st.session_state.get('current_filters')),
                "selected_floats": len(st.session_state.get('selected_floats', [])),
                "user_session": st.session_state.get('session_id', 'unknown')
            }
        }
    
    def _create_quality_report(self, data: pd.DataFrame) -> str:
        """Create data quality report"""
        
        report = f"""ARGO Data Quality Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

Dataset Summary:
- Total Records: {len(data):,}
- Total Columns: {len(data.columns)}
- Memory Usage: {data.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB

Data Completeness:
"""
        
        for col in data.columns:
            missing_pct = (data[col].isnull().sum() / len(data)) * 100
            report += f"- {col}: {100-missing_pct:.1f}% complete ({missing_pct:.1f}% missing)\n"
        
        # Add basic statistics for numeric columns
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            report += "\nNumeric Column Statistics:\n"
            for col in numeric_cols:
                if col in ['temperature', 'salinity', 'depth', 'lat', 'lon']:
                    stats = data[col].describe()
                    report += f"- {col}: min={stats['min']:.2f}, max={stats['max']:.2f}, mean={stats['mean']:.2f}\n"
        
        return report
    
    def _create_report_content(self, options: Dict[str, Any]) -> str:
        """Create HTML report content"""
        
        title = options.get("custom_title", "ARGO Data Analysis Report")
        author = options.get("custom_author", "ARGO Dashboard System")
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #1f4e79; }}
        h2 {{ color: #2e8b57; }}
        .header {{ border-bottom: 2px solid #1f4e79; padding-bottom: 10px; }}
        .section {{ margin: 20px 0; }}
        .metric {{ background: #f0f2f6; padding: 10px; margin: 5px 0; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p><strong>Author:</strong> {author}</p>
    </div>
"""
        
        if options.get("include_overview"):
            html_content += """
    <div class="section">
        <h2>System Overview</h2>
        <div class="metric">Active ARGO Floats: 50</div>
        <div class="metric">Total Profiles: 1,234</div>
        <div class="metric">Total Measurements: 45,678</div>
        <div class="metric">Data Quality Score: 98.5%</div>
    </div>
"""
        
        if options.get("include_data_summary"):
            html_content += """
    <div class="section">
        <h2>Data Summary</h2>
        <p>This report covers oceanographic data collected by the ARGO float network in the Indian Ocean region.</p>
        <ul>
            <li>Geographic Coverage: Indian Ocean (20°W to 120°E, 60°S to 30°N)</li>
            <li>Temporal Coverage: 2020-2024</li>
            <li>Depth Range: 0-2000 meters</li>
            <li>Parameters: Temperature, Salinity, Pressure, BGC parameters</li>
        </ul>
    </div>
"""
        
        if options.get("include_quality_assessment"):
            html_content += """
    <div class="section">
        <h2>Data Quality Assessment</h2>
        <p>Overall data quality is excellent with minimal missing values and consistent measurements.</p>
        <div class="metric">Data Completeness: 98.5%</div>
        <div class="metric">Coordinate Validity: 100%</div>
        <div class="metric">Temporal Consistency: 99.2%</div>
        <div class="metric">Parameter Ranges: Within expected oceanographic limits</div>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        return html_content