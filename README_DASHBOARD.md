# ARGO Float Dashboard - Streamlit Frontend

> **Status: experimental / work in progress.** This dashboard still uses mock data in places. The main, working demo is `app.py`; see `readme.md`.

A government-grade Streamlit dashboard for visualizing ARGO oceanographic data with interactive maps, profile analysis, and natural language querying capabilities.

## 🚀 Quick Start

### Prerequisites

1. **Python Environment**: Ensure you're in your virtual environment (`sih`)
2. **Backend Running**: The FastAPI backend should be running on `http://localhost:8000`
3. **Dependencies**: Install Streamlit and required packages

### Installation

```bash
# Activate your virtual environment
# (Assuming you're already in the sih environment)

# Install Streamlit dashboard dependencies
pip install streamlit plotly pandas requests

# Or install from requirements file
pip install -r requirements_dashboard.txt
```

### Running the Dashboard

```bash
# Start the Streamlit dashboard
streamlit run streamlit_app.py

# Or specify a custom port
streamlit run streamlit_app.py --server.port 8501
```

The dashboard will be available at: `http://localhost:8501`

## 📋 Current Implementation Status

### ✅ Completed Features (Tasks 1-3)

- **Project Structure**: Complete file organization with components, styles, and utilities
- **API Client**: Robust backend integration with error handling and retry logic
- **Layout Manager**: Government-style responsive layout with professional styling
- **Navigation System**: Tabbed interface with sidebar filters and controls
- **Government Theme**: Professional styling suitable for official presentations
- **Configuration Management**: Centralized config for all dashboard settings

### 🚧 In Progress Features

- **Interactive Map** (Task 4): ARGO float locations and trajectories
- **Profile Visualizations** (Task 5): Temperature-salinity-depth plots
- **Chat Interface** (Task 6): Natural language query system
- **Data Filtering** (Task 7): Advanced filtering and search capabilities
- **Export System** (Task 8): Data and visualization export functionality

## 🏗️ Architecture Overview

```
streamlit_app.py              # Main application entry point
├── components/               # Reusable dashboard components
│   ├── api_client.py        # FastAPI backend integration
│   ├── layout_manager.py    # Main layout and navigation
│   ├── data_transformer.py  # Data processing utilities
│   └── [future components]  # Map, chat, profile visualizers
├── styles/                  # Styling and themes
│   └── government_theme.py  # Government-approved styling
├── utils/                   # Utility functions
│   └── dashboard_utils.py   # Common helper functions
├── tests/                   # Test suite
│   └── test_api_client.py   # API client tests
└── .streamlit/              # Streamlit configuration
    └── config.toml          # App configuration
```

## 🎨 Government Styling Features

- **Professional Color Scheme**: Government blue (#1f4e79) and forest green (#2e8b57)
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Accessibility**: High contrast ratios and keyboard navigation support
- **Clean Typography**: Inter font family for professional appearance
- **Status Indicators**: Real-time system health monitoring
- **Interactive Elements**: Hover effects and smooth transitions

## 🔧 Configuration

### Dashboard Configuration (`dashboard_config.py`)

```python
# API Settings
API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 30

# Map Settings
DEFAULT_MAP_CENTER = (0.0, 80.0)  # Indian Ocean
DEFAULT_MAP_ZOOM = 3

# Performance Settings
CACHE_TTL = 3600  # 1 hour
MAX_EXPORT_SIZE = 100000
```

### Streamlit Configuration (`.streamlit/config.toml`)

```toml
[server]
port = 8501
enableCORS = false

[theme]
primaryColor = "#1f4e79"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
```

## 🧪 Testing

### Run Layout Tests

```bash
# Test layout components
python test_layout.py

# Test API client
python -m pytest tests/test_api_client.py -v

# Test complete setup
python test_dashboard_setup.py
```

### Manual Testing

1. **Backend Connection**: Check system status in sidebar
2. **Navigation**: Test all tab sections
3. **Responsive Design**: Resize browser window
4. **Error Handling**: Disconnect backend and test error states

## 📊 Current Dashboard Sections

### 1. Overview Tab
- System metrics and key performance indicators
- Recent activity charts (placeholder)
- Global coverage summary
- Data quality indicators

### 2. Interactive Map Tab
- Placeholder for ARGO float location map
- Will show float markers, trajectories, and geographic filtering

### 3. Profile Analysis Tab
- Placeholder for temperature-salinity-depth profiles
- Will support multi-profile comparisons and BGC parameters

### 4. Chat Interface Tab
- Placeholder for natural language query system
- Will integrate with RAG pipeline for conversational data exploration

### 5. Data Export Tab
- Placeholder for export functionality
- Will support multiple formats (PNG, PDF, CSV, NetCDF, ASCII)

## 🔍 Troubleshooting

### Common Issues

1. **"Module not found" errors**
   ```bash
   # Ensure you're in the correct virtual environment
   pip install streamlit plotly pandas requests
   ```

2. **Backend connection failed**
   ```bash
   # Check if FastAPI backend is running
   curl http://localhost:8000/health
   
   # Start backend if needed
   uvicorn main:app --reload
   ```

3. **Port already in use**
   ```bash
   # Use a different port
   streamlit run streamlit_app.py --server.port 8502
   ```

4. **Styling not loading**
   - Clear browser cache
   - Check browser console for CSS errors
   - Ensure government_theme.py is properly imported

### Debug Mode

```bash
# Run with debug logging
streamlit run streamlit_app.py --logger.level debug
```

## 🚀 Next Steps

The dashboard foundation is complete! Next tasks will add:

1. **Interactive Mapping** (Task 4): Plotly/Folium integration for float visualization
2. **Profile Charts** (Task 5): Scientific plotting for oceanographic data
3. **AI Chat Interface** (Task 6): Natural language query integration
4. **Advanced Filtering** (Task 7): Real-time data filtering and search
5. **Export System** (Task 8): Professional report generation

## 📞 Support

- **Configuration Issues**: Check `dashboard_config.py` and `.streamlit/config.toml`
- **API Problems**: Verify FastAPI backend is running and accessible
- **Styling Issues**: Check browser console and government theme CSS
- **Performance**: Monitor system resources and adjust `CACHE_TTL` settings

## 🏛️ Government Compliance

This dashboard is designed for government use with:
- Professional styling suitable for official presentations
- Secure API communication with error handling
- Accessibility compliance (WCAG guidelines)
- Responsive design for various devices
- Clean, distraction-free interface
- Proper data attribution and metadata display