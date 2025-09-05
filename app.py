import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import random

# Page configuration
st.set_page_config(
    page_title="FloatChat - ARGO Data Explorer",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .chat-container {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .metric-container {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

def query_backend(user_query, region="Pacific", date_range=None, data_type="All"):
    """
    Placeholder function that simulates calling the backend.
    Returns dummy data based on the query parameters.
    
    Args:
        user_query (str): Natural language query from user
        region (str): Selected ocean region
        date_range (tuple): Start and end dates
        data_type (str): Type of data requested (CTD, BGC, All)
    
    Returns:
        dict: Response containing text, data, and metadata
    """
    # Simulate processing time
    time.sleep(2)
    
    # Generate dummy response based on query content
    response_text = f"Based on your query '{user_query}' for the {region} region"
    
    if date_range:
        response_text += f" from {date_range[0]} to {date_range[1]}"
    
    response_text += f", here's what I found using {data_type} data:\n\n"
    
    # Generate dummy insights
    insights = [
        f"Found {random.randint(50, 200)} ARGO floats in the specified region",
        f"Average temperature: {random.uniform(15, 25):.1f}°C",
        f"Salinity range: {random.uniform(34, 36):.2f} - {random.uniform(36, 38):.2f} PSU",
        f"Data quality: {random.choice(['Excellent', 'Good', 'Fair'])} ({random.randint(85, 99)}% valid measurements)"
    ]
    
    response_text += "\n".join([f"• {insight}" for insight in insights])
    
    # Generate dummy float locations
    n_floats = random.randint(20, 50)
    
    # Region-specific coordinate ranges
    region_coords = {
        "Pacific": {"lat_range": (-60, 60), "lon_range": (120, -80)},
        "Atlantic": {"lat_range": (-60, 60), "lon_range": (-80, 20)},
        "Indian Ocean": {"lat_range": (-60, 30), "lon_range": (20, 120)}
    }
    
    coords = region_coords.get(region, region_coords["Pacific"])
    
    float_data = pd.DataFrame({
        'float_id': [f"ARGO_{i:04d}" for i in range(n_floats)],
        'latitude': np.random.uniform(coords["lat_range"][0], coords["lat_range"][1], n_floats),
        'longitude': np.random.uniform(coords["lon_range"][0], coords["lon_range"][1], n_floats),
        'temperature': np.random.uniform(10, 30, n_floats),
        'salinity': np.random.uniform(34, 38, n_floats),
        'depth': np.random.uniform(0, 2000, n_floats)
    })
    
    # Generate dummy profile data
    depths = np.arange(0, 2000, 50)
    profile_data = pd.DataFrame({
        'depth': depths,
        'temperature': 25 * np.exp(-depths/1000) + np.random.normal(0, 0.5, len(depths)),
        'salinity': 35 + 2 * np.exp(-depths/500) + np.random.normal(0, 0.1, len(depths))
    })
    
    return {
        'text': response_text,
        'float_locations': float_data,
        'profile_data': profile_data,
        'metadata': {
            'query_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'region': region,
            'data_type': data_type,
            'n_floats': n_floats
        }
    }

def create_float_map(float_data, region):
    """Create an interactive map showing ARGO float locations."""
    fig = px.scatter_mapbox(
        float_data,
        lat="latitude",
        lon="longitude",
        color="temperature",
        size="depth",
        hover_data=["float_id", "salinity"],
        color_continuous_scale="Viridis",
        size_max=15,
        zoom=2,
        title=f"ARGO Float Locations - {region}"
    )
    
    fig.update_layout(
        mapbox_style="open-street-map",
        height=500,
        margin={"r":0,"t":30,"l":0,"b":0}
    )
    
    return fig

def create_profile_plots(profile_data):
    """Create temperature and salinity profile plots."""
    fig = go.Figure()
    
    # Temperature profile
    fig.add_trace(go.Scatter(
        x=profile_data['temperature'],
        y=-profile_data['depth'],  # Negative for oceanographic convention
        mode='lines+markers',
        name='Temperature (°C)',
        line=dict(color='red', width=2),
        yaxis='y'
    ))
    
    # Salinity profile on secondary y-axis
    fig.add_trace(go.Scatter(
        x=profile_data['salinity'],
        y=-profile_data['depth'],
        mode='lines+markers',
        name='Salinity (PSU)',
        line=dict(color='blue', width=2),
        xaxis='x2',
        yaxis='y'
    ))
    
    fig.update_layout(
        title="Temperature and Salinity Profiles",
        xaxis=dict(title="Temperature (°C)", side="bottom"),
        xaxis2=dict(title="Salinity (PSU)", overlaying="x", side="top"),
        yaxis=dict(title="Depth (m)"),
        height=500,
        showlegend=True
    )
    
    return fig

def main():
    """Main application function."""
    
    # Header
    st.markdown('<h1 class="main-header">🌊 FloatChat</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">AI-Powered ARGO Ocean Data Explorer</p>', unsafe_allow_html=True)
    
    # Initialize session state for chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "last_response" not in st.session_state:
        st.session_state.last_response = None
    
    # Sidebar controls
    with st.sidebar:
        st.header("🔧 Data Filters")
        
        # Region selection
        region = st.selectbox(
            "Select Ocean Region",
            ["Pacific", "Atlantic", "Indian Ocean"],
            help="Choose the ocean region for data exploration"
        )
        
        # Date range picker
        st.subheader("📅 Time Period")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now() - timedelta(days=365),
                max_value=datetime.now()
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now(),
                max_value=datetime.now()
            )
        
        date_range = (start_date, end_date)
        
        # Data type toggle
        data_type = st.radio(
            "Data Type",
            ["All", "CTD", "BGC"],
            help="CTD: Conductivity, Temperature, Depth | BGC: Biogeochemical"
        )
        
        # Display current settings
        st.markdown("---")
        st.subheader("📊 Current Settings")
        st.info(f"""
        **Region:** {region}  
        **Period:** {start_date} to {end_date}  
        **Data Type:** {data_type}
        """)
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("💬 Chat with ARGO Data")
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask me about ARGO ocean data... (e.g., 'Show me salinity profiles near the equator in March 2023')"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Display assistant response with loading
            with st.chat_message("assistant"):
                with st.spinner("🔍 Analyzing ARGO data..."):
                    response = query_backend(prompt, region, date_range, data_type)
                    st.session_state.last_response = response
                
                st.markdown(response['text'])
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response['text']})
    
    with col2:
        st.subheader("📈 Quick Stats")
        if st.session_state.last_response:
            metadata = st.session_state.last_response['metadata']
            
            # Display metrics
            st.metric("Active Floats", metadata['n_floats'])
            st.metric("Region", metadata['region'])
            st.metric("Data Type", metadata['data_type'])
            st.metric("Last Updated", metadata['query_time'])
        else:
            st.info("💡 Ask a question to see data statistics!")
    
    # Visualization area
    if st.session_state.last_response:
        st.markdown("---")
        st.subheader("🗺️ Data Visualizations")
        
        # Create two columns for visualizations
        viz_col1, viz_col2 = st.columns(2)
        
        with viz_col1:
            # Float locations map
            st.plotly_chart(
                create_float_map(
                    st.session_state.last_response['float_locations'], 
                    region
                ),
                use_container_width=True
            )
        
        with viz_col2:
            # Profile plots
            st.plotly_chart(
                create_profile_plots(st.session_state.last_response['profile_data']),
                use_container_width=True
            )
        
        # Data table (expandable)
        with st.expander("📋 View Raw Float Data"):
            st.dataframe(
                st.session_state.last_response['float_locations'],
                use_container_width=True
            )
    
    # Footer
    st.markdown("---")
    st.markdown(
        '<p style="text-align: center; color: #888;">FloatChat v1.0 | Powered by ARGO Global Ocean Observing System</p>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
