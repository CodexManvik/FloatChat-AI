"""
Government-style theme and styling utilities
Professional styling suitable for government presentations
"""

import streamlit as st
from typing import Dict, Any

class GovernmentTheme:
    """Government-approved styling and theme configuration"""
    
    # Color palette
    COLORS = {
        "primary": "#1f4e79",      # Government blue
        "secondary": "#2e8b57",    # Forest green
        "accent": "#ff6b35",       # Orange accent
        "success": "#28a745",      # Success green
        "warning": "#ffc107",      # Warning yellow
        "danger": "#dc3545",       # Error red
        "info": "#17a2b8",         # Info blue
        "light": "#f8f9fa",        # Light gray
        "dark": "#343a40",         # Dark gray
        "white": "#ffffff",        # White
        "text": "#262730"          # Text color
    }
    
    # Typography
    FONTS = {
        "primary": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "monospace": "'Fira Code', 'Courier New', monospace"
    }
    
    @classmethod
    def get_css(cls) -> str:
        """Get complete CSS for government styling"""
        return f"""
        <style>
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        /* Root variables */
        :root {{
            --primary-color: {cls.COLORS['primary']};
            --secondary-color: {cls.COLORS['secondary']};
            --accent-color: {cls.COLORS['accent']};
            --success-color: {cls.COLORS['success']};
            --warning-color: {cls.COLORS['warning']};
            --danger-color: {cls.COLORS['danger']};
            --info-color: {cls.COLORS['info']};
            --light-color: {cls.COLORS['light']};
            --dark-color: {cls.COLORS['dark']};
            --text-color: {cls.COLORS['text']};
            --font-family: {cls.FONTS['primary']};
        }}
        
        /* Hide Streamlit branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        .stDeployButton {{visibility: hidden;}}
        
        /* Main container styling */
        .main .block-container {{
            padding-top: 1rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }}
        
        /* Typography */
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
            font-family: var(--font-family);
            color: var(--primary-color);
            font-weight: 600;
        }}
        
        .stMarkdown p, .stMarkdown li {{
            font-family: var(--font-family);
            color: var(--text-color);
            line-height: 1.6;
        }}
        
        /* Header styling */
        .main-header {{
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            color: white;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        
        .header-title {{
            font-size: 2.5rem;
            font-weight: 700;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            font-family: var(--font-family);
        }}
        
        .header-subtitle {{
            font-size: 1.2rem;
            margin: 0.5rem 0 0 0;
            opacity: 0.95;
            font-weight: 400;
        }}
        
        /* Status indicators */
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }}
        
        .status-online {{ background-color: var(--success-color); }}
        .status-offline {{ background-color: var(--danger-color); }}
        .status-warning {{ background-color: var(--warning-color); }}
        
        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
            100% {{ opacity: 1; }}
        }}
        
        /* Card styling */
        .metric-card {{
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            border-left: 4px solid var(--primary-color);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        
        .metric-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }}
        
        /* Button styling */
        .stButton > button {{
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 500;
            font-family: var(--font-family);
            padding: 0.75rem 1.5rem;
            transition: all 0.3s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            background: linear-gradient(135deg, #1a4269 0%, #267a4d 100%);
        }}
        
        .stButton > button:active {{
            transform: translateY(0);
        }}
        
        /* Sidebar styling */
        .css-1d391kg {{
            background: var(--light-color);
            border-right: 2px solid #e9ecef;
        }}
        
        .css-1d391kg .stSelectbox > div > div {{
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 6px;
        }}
        
        /* Metric styling */
        .stMetric {{
            background: white;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid var(--primary-color);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .stMetric > div {{
            font-family: var(--font-family);
        }}
        
        /* Alert styling */
        .stSuccess {{
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-left: 4px solid var(--success-color);
            border-radius: 6px;
        }}
        
        .stError {{
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            border-left: 4px solid var(--danger-color);
            border-radius: 6px;
        }}
        
        .stWarning {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-left: 4px solid var(--warning-color);
            border-radius: 6px;
        }}
        
        .stInfo {{
            background: #d1ecf1;
            border: 1px solid #bee5eb;
            border-left: 4px solid var(--info-color);
            border-radius: 6px;
        }}
        
        /* Input styling */
        .stTextInput > div > div > input {{
            border: 1px solid #dee2e6;
            border-radius: 6px;
            font-family: var(--font-family);
        }}
        
        .stTextInput > div > div > input:focus {{
            border-color: var(--primary-color);
            box-shadow: 0 0 0 2px rgba(31, 78, 121, 0.25);
        }}
        
        /* Selectbox styling */
        .stSelectbox > div > div {{
            border: 1px solid #dee2e6;
            border-radius: 6px;
        }}
        
        /* Slider styling */
        .stSlider > div > div > div > div {{
            background: var(--primary-color);
        }}
        
        /* Checkbox styling */
        .stCheckbox > label > div {{
            background: white;
            border: 2px solid #dee2e6;
        }}
        
        .stCheckbox > label > div[data-checked="true"] {{
            background: var(--primary-color);
            border-color: var(--primary-color);
        }}
        
        /* Tab styling */
        .stTabs > div > div > div > div {{
            background: var(--light-color);
            border: 1px solid #dee2e6;
            border-radius: 8px 8px 0 0;
            color: var(--text-color);
        }}
        
        .stTabs > div > div > div > div[data-selected="true"] {{
            background: var(--primary-color);
            color: white;
        }}
        
        /* Footer styling */
        .dashboard-footer {{
            background: var(--light-color);
            padding: 2rem;
            border-top: 2px solid #dee2e6;
            margin-top: 3rem;
            border-radius: 8px;
        }}
        
        /* Responsive design */
        @media (max-width: 768px) {{
            .main .block-container {{
                padding-left: 1rem;
                padding-right: 1rem;
            }}
            
            .header-title {{
                font-size: 2rem;
            }}
            
            .header-subtitle {{
                font-size: 1rem;
            }}
        }}
        
        /* Loading animation */
        .loading-spinner {{
            border: 3px solid var(--light-color);
            border-top: 3px solid var(--primary-color);
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: var(--light-color);
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: var(--primary-color);
            border-radius: 4px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: #1a4269;
        }}
        </style>
        """
    
    @classmethod
    def apply_theme(cls) -> None:
        """Apply the government theme to Streamlit"""
        st.markdown(cls.get_css(), unsafe_allow_html=True)
    
    @classmethod
    def create_status_badge(cls, status: str, text: str) -> str:
        """Create a status badge with appropriate styling"""
        status_class = f"status-{status}"
        return f'<span class="status-indicator {status_class}"></span><strong>{text}</strong>'
    
    @classmethod
    def create_metric_card(cls, title: str, value: str, delta: str = None, help_text: str = None) -> str:
        """Create a styled metric card"""
        delta_html = f'<div class="metric-delta">{delta}</div>' if delta else ''
        help_html = f'<div class="metric-help">{help_text}</div>' if help_text else ''
        
        return f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
            {delta_html}
            {help_html}
        </div>
        """