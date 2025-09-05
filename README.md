# FloatChat - ARGO Ocean Data Explorer

An AI-powered conversational interface for exploring ARGO ocean data using Streamlit.

## Features

- 🌊 Interactive chatbot for natural language queries about ocean data
- 🗺️ Geospatial visualization of ARGO float locations
- 📊 Interactive temperature and salinity profile plots
- 🔧 Sidebar controls for region, date range, and data type filtering
- 💬 Clean chat interface with message history
- 📈 Real-time data statistics and metrics

## Installation

1. Install dependencies:
\`\`\`bash
pip install -r requirements.txt
\`\`\`

2. Run the application:
\`\`\`bash
streamlit run app.py
\`\`\`

## Usage

1. **Select Filters**: Use the sidebar to choose ocean region, date range, and data type
2. **Ask Questions**: Type natural language queries like:
   - "Show me salinity profiles near the equator in March 2023"
   - "What's the temperature distribution in the Pacific?"
   - "Find floats with high salinity readings"
3. **Explore Data**: View interactive maps and plots generated from your queries
4. **Analyze Results**: Check the quick stats panel for data summaries

## Architecture

The app is designed to be modular and production-ready:

- `query_backend()`: Placeholder function for backend integration
- `create_float_map()`: Generates interactive geospatial visualizations
- `create_profile_plots()`: Creates temperature/salinity depth profiles
- Clean separation of UI components and data processing

## Future Enhancements

- Connect to real ARGO database (SQL + Chroma vector store)
- Integrate Qwen LLM for advanced query processing
- Add more visualization types (time series, 3D plots)
- Implement user authentication and query history
- Add data export functionality

## Data Sources

This demo uses simulated ARGO float data. In production, it will connect to:
- ARGO Global Data Assembly Centre (GDAC)
- Real-time quality controlled oceanographic measurements
- Historical and near real-time data streams
