"""
Dashboard-specific configuration
Extends the main config with Streamlit-specific settings
"""

import config
from typing import Tuple, Dict, Any

class DashboardConfig:
    """Configuration class for Streamlit dashboard"""
    
    # API Configuration
    API_BASE_URL: str = "http://localhost:8000"
    API_TIMEOUT: int = 30
    
    # Map Configuration
    DEFAULT_MAP_CENTER: Tuple[float, float] = (0.0, 80.0)  # Indian Ocean center
    DEFAULT_MAP_ZOOM: int = 3
    MAP_STYLE: str = "open-street-map"
    
    # Chat Configuration
    MAX_QUERY_LENGTH: int = 500
    CHAT_HISTORY_LIMIT: int = 50
    
    # Performance Configuration
    CACHE_TTL: int = 3600  # 1 hour in seconds
    MAX_EXPORT_SIZE: int = 100000  # Maximum records for export
    PAGINATION_SIZE: int = 1000
    
    # Visualization Configuration
    DEFAULT_COLORSCALE: str = "viridis"
    TEMPERATURE_COLORSCALE: str = "RdYlBu_r"
    SALINITY_COLORSCALE: str = "Blues"
    
    # Government Styling
    GOVERNMENT_COLORS: Dict[str, str] = {
        "primary": "#1f4e79",
        "secondary": "#2e8b57", 
        "accent": "#ff6b35",
        "background": "#ffffff",
        "surface": "#f0f2f6",
        "text": "#262730"
    }
    
    # Data Quality Thresholds
    QUALITY_THRESHOLDS: Dict[str, float] = {
        "excellent": 0.95,
        "good": 0.85,
        "fair": 0.70,
        "poor": 0.50
    }
    
    # Export Configuration
    SUPPORTED_EXPORT_FORMATS: Dict[str, str] = {
        "png": "image/png",
        "pdf": "application/pdf", 
        "svg": "image/svg+xml",
        "csv": "text/csv",
        "ascii": "text/plain",
        "netcdf": "application/octet-stream"
    }
    
    @classmethod
    def get_map_config(cls) -> Dict[str, Any]:
        """Get map configuration dictionary"""
        return {
            "center": {"lat": cls.DEFAULT_MAP_CENTER[0], "lon": cls.DEFAULT_MAP_CENTER[1]},
            "zoom": cls.DEFAULT_MAP_ZOOM,
            "style": cls.MAP_STYLE
        }
    
    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        """Get chart configuration dictionary"""
        return {
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": ["pan2d", "lasso2d", "select2d"],
            "toImageButtonOptions": {
                "format": "png",
                "filename": "argo_chart",
                "height": 600,
                "width": 800,
                "scale": 2
            }
        }

# Create global config instance
dashboard_config = DashboardConfig()