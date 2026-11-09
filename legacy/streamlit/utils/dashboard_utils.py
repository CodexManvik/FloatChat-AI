"""
Utility functions for the Streamlit dashboard
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def init_session_state():
    """Initialize Streamlit session state variables"""
    default_state = {
        'initialized': True,
        'api_client': None,
        'chat_history': [],
        'selected_floats': [],
        'filter_state': {
            'date_range': (datetime.now() - timedelta(days=365), datetime.now()),
            'depth_range': (0.0, 2000.0),
            'geographic_bounds': None,
            'quality_flags': ['good', 'excellent']
        },
        'current_data': None,
        'last_query': None,
        'export_data': None
    }
    
    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value

def format_scientific_notation(value: float, precision: int = 2) -> str:
    """Format numbers in scientific notation for oceanographic data"""
    if pd.isna(value):
        return "N/A"
    
    if abs(value) < 0.01 or abs(value) >= 1000:
        return f"{value:.{precision}e}"
    else:
        return f"{value:.{precision}f}"

def format_oceanographic_units(value: float, parameter: str) -> str:
    """Format values with appropriate oceanographic units"""
    if pd.isna(value):
        return "N/A"
    
    unit_map = {
        'temperature': '°C',
        'salinity': 'PSU',
        'depth': 'm',
        'pressure': 'dbar',
        'oxygen': 'ml/L',
        'ph': '',
        'chlorophyll': 'mg/m³',
        'nitrate': 'μmol/kg'
    }
    
    unit = unit_map.get(parameter.lower(), '')
    
    if parameter.lower() == 'ph':
        return f"{value:.2f}"
    elif parameter.lower() in ['depth', 'pressure']:
        return f"{value:.0f} {unit}"
    else:
        return f"{value:.2f} {unit}"

def create_color_scale(parameter: str) -> str:
    """Get appropriate color scale for oceanographic parameters"""
    color_scales = {
        'temperature': 'RdYlBu_r',
        'salinity': 'Blues',
        'oxygen': 'Viridis',
        'ph': 'RdYlGn',
        'chlorophyll': 'Greens',
        'depth': 'Deep_r'
    }
    
    return color_scales.get(parameter.lower(), 'Viridis')

def validate_data_quality(data: pd.DataFrame) -> Dict[str, Any]:
    """Assess data quality and return quality metrics"""
    if data.empty:
        return {"status": "no_data", "score": 0.0, "issues": ["No data available"]}
    
    issues = []
    total_cells = data.size
    missing_cells = data.isnull().sum().sum()
    
    # Calculate missing data percentage
    missing_percentage = (missing_cells / total_cells) * 100
    
    if missing_percentage > 50:
        issues.append(f"High missing data: {missing_percentage:.1f}%")
    elif missing_percentage > 20:
        issues.append(f"Moderate missing data: {missing_percentage:.1f}%")
    
    # Check for outliers in numeric columns
    numeric_cols = data.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if col in ['temperature', 'salinity', 'depth']:
            q1 = data[col].quantile(0.25)
            q3 = data[col].quantile(0.75)
            iqr = q3 - q1
            outliers = data[(data[col] < q1 - 1.5*iqr) | (data[col] > q3 + 1.5*iqr)]
            
            if len(outliers) > len(data) * 0.05:  # More than 5% outliers
                issues.append(f"Potential outliers in {col}: {len(outliers)} values")
    
    # Calculate overall quality score
    quality_score = max(0.0, 1.0 - (missing_percentage / 100) - (len(issues) * 0.1))
    
    # Determine quality status
    if quality_score >= 0.95:
        status = "excellent"
    elif quality_score >= 0.85:
        status = "good"
    elif quality_score >= 0.70:
        status = "fair"
    else:
        status = "poor"
    
    return {
        "status": status,
        "score": quality_score,
        "missing_percentage": missing_percentage,
        "total_records": len(data),
        "issues": issues
    }

def create_download_link(data: bytes, filename: str, mime_type: str) -> str:
    """Create a download link for data export"""
    import base64
    
    b64_data = base64.b64encode(data).decode()
    return f'<a href="data:{mime_type};base64,{b64_data}" download="{filename}">Download {filename}</a>'

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero"""
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def format_timestamp(timestamp: datetime) -> str:
    """Format timestamp for display"""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

def get_data_summary(data: pd.DataFrame) -> Dict[str, Any]:
    """Generate summary statistics for a dataset"""
    if data.empty:
        return {"error": "No data available"}
    
    numeric_cols = data.select_dtypes(include=[np.number]).columns
    summary = {
        "total_records": len(data),
        "columns": len(data.columns),
        "numeric_columns": len(numeric_cols),
        "date_range": None,
        "statistics": {}
    }
    
    # Date range if time column exists
    if 'time' in data.columns:
        summary["date_range"] = {
            "start": data['time'].min(),
            "end": data['time'].max()
        }
    
    # Statistics for numeric columns
    for col in numeric_cols:
        if col in ['temperature', 'salinity', 'depth', 'oxygen', 'ph']:
            col_data = data[col].dropna()
            if len(col_data) > 0:
                summary["statistics"][col] = {
                    "mean": float(col_data.mean()),
                    "median": float(col_data.median()),
                    "std": float(col_data.std()),
                    "min": float(col_data.min()),
                    "max": float(col_data.max()),
                    "count": int(len(col_data))
                }
    
    return summary