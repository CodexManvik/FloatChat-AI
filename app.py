import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import random
import pydeck as pdk

# Page configuration
st.set_page_config(
    page_title="FloatChat - ARGO Data Explorer",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Global dark theme with oceanic accents */
    .main {
        background: linear-gradient(135deg, #0f1419 0%, #1a2332 50%, #0f1419 100%);
        color: #e8f4fd;
    }
    
    /* Hero section styling */
    .hero-container {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #3b82f6 100%);
        padding: 4rem 2rem;
        border-radius: 20px;
        margin: 2rem 0;
        text-align: center;
        color: white;
        box-shadow: 0 20px 40px rgba(59, 130, 246, 0.3);
        border: 1px solid rgba(59, 130, 246, 0.2);
    }
    
    .hero-title {
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 1rem;
        text-shadow: 2px 2px 8px rgba(0,0,0,0.5);
        background: linear-gradient(45deg, #60a5fa, #34d399);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .hero-subtitle {
        font-size: 1.5rem;
        font-weight: 300;
        margin-bottom: 2rem;
        opacity: 0.9;
        color: #bfdbfe;
    }
    
    /* Updated description styling for better centering and spacing */
    .hero-description {
        font-size: 1.2rem;
        line-height: 1.8;
        max-width: 1000px;
        margin: 0 auto 3rem auto;
        opacity: 0.9;
        color: #dbeafe;
        text-align: center;
        padding: 0 1rem;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 120px;
    }
    
    /* Enhanced launch button with larger size and bright yellow hover effect */
    .launch-button {
        background: #000000;
        color: white;
        padding: 1.5rem 4rem;
        border: none;
        border-radius: 50px;
        font-size: 1.4rem;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.3s ease;
        text-decoration: none;
        display: inline-block;
        margin: 2rem auto;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
        text-transform: uppercase;
        letter-spacing: 1px;
        border: 2px solid transparent;
    }
    
    .launch-button:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 35px rgba(255, 235, 59, 0.6);
        background: #ffeb3b;
        color: #000000;
        border: 2px solid #fdd835;
    }
    
    /* Added button container for proper centering */
    .button-container {
        display: flex;
        justify-content: center;
        align-items: center;
        margin: 2rem 0;
    }

    /* Back button styling */
    .back-button {
        background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
        color: white;
        padding: 0.8rem 1.5rem;
        border: none;
        border-radius: 25px;
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        margin-bottom: 1rem;
    }
    
    .back-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(107, 114, 128, 0.4);
    }
    
    /* Chat styling */
    .chat-message {
        padding: 1.2rem;
        margin: 0.8rem 0;
        border-radius: 18px;
        max-width: 85%;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    .user-message {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        margin-left: auto;
        text-align: right;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    
    .assistant-message {
        background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
        border: 1px solid #4b5563;
        color: #f3f4f6;
    }
    
    /* Stats card styling */
    .stats-card {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        margin: 1rem 0;
        border: 1px solid #374151;
        color: #f3f4f6;
    }
    
    /* Search bar styling */
    .search-container {
        background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
        padding: 1rem;
        border-radius: 15px;
        margin: 1rem 0;
        border: 1px solid #4b5563;
    }
    
    /* Info cards styling */
    .info-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 15px;
        padding: 2rem;
        margin: 1rem 0;
        border: 1px solid #334155;
        color: #e2e8f0;
        box-shadow: 0 8px 25px rgba(0,0,0,0.2);
    }
    
    /* Footer */
    .footer {
        text-align: center;
        color: #9ca3af;
        font-size: 0.9rem;
        margin-top: 3rem;
        padding: 2rem;
        border-top: 1px solid #374151;
        background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
        border-radius: 15px;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
    }
    
    /* Override Streamlit's default styling */
    .stSelectbox > div > div {
        background-color: #374151;
        color: #f3f4f6;
    }
    
    .stDateInput > div > div {
        background-color: #374151;
        color: #f3f4f6;
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

def create_animated_ocean_map():
    """Create an animated global ocean map with moving ARGO floats using reliable map provider"""
    # Generate sample float data with animation
    n_floats = 100
    
    # Create base float positions with better global distribution
    float_data = []
    for i in range(n_floats):
        # Better distribution across ocean basins
        if i < 40:  # Pacific
            base_lat = np.random.uniform(-50, 50)
            base_lon = np.random.uniform(120, -80)
        elif i < 70:  # Atlantic
            base_lat = np.random.uniform(-50, 60)
            base_lon = np.random.uniform(-80, 20)
        else:  # Indian Ocean
            base_lat = np.random.uniform(-50, 30)
            base_lon = np.random.uniform(20, 120)
        
        status = np.random.choice(['Active', 'Inactive'], p=[0.85, 0.15])
        
        float_data.append({
            'latitude': base_lat,
            'longitude': base_lon,
            'status': status,
            'float_id': f'ARGO_{i:04d}',
            'temperature': np.random.uniform(5, 30),
            'salinity': np.random.uniform(34, 38),
            'depth': np.random.uniform(0, 2000),
            'last_contact': np.random.randint(1, 30)
        })
    
    df = pd.DataFrame(float_data)
    
    # Use Plotly for more reliable map rendering
    fig = px.scatter_mapbox(
        df,
        lat="latitude",
        lon="longitude",
        color="status",
        size="temperature",
        hover_data=["float_id", "temperature", "salinity", "depth", "last_contact"],
        color_discrete_map={"Active": "#10b981", "Inactive": "#ef4444"},
        size_max=15,
        zoom=1.2,
        title="🌍 Global ARGO Float Network - Real-time Status",
        mapbox_style="open-street-map"
    )
    
    fig.update_layout(
        height=600,
        margin={"r":0,"t":50,"l":0,"b":0},
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white')
    )
    
    return fig

def show_homepage():
    """Display the enhanced homepage with modern hero section"""
    st.markdown("""
    <div class="hero-container">
        <h1 class="hero-title">🌊 FloatChat</h1>
        <p class="hero-subtitle">AI-Powered ARGO Ocean Data Explorer</p>
        <div class="hero-description">
            FloatChat is your AI-powered gateway to the world's oceans. It empowers scientists, students, and marine enthusiasts to explore, visualize, and analyze ARGO float data in real time. With natural language querying, you can ask questions like 'Show me temperature patterns in the Pacific over the last month' or 'Find salinity trends at 1000m depth,' and instantly see insightful visualizations. From tracking ocean currents to discovering climate change indicators, FloatChat puts the pulse of the ocean at your fingertips — anywhere, anytime.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("🚀 Launch Chatbot", key="main_launch_btn", help="Start exploring ARGO data with AI assistance", 
                    use_container_width=True):
            st.session_state.current_page = "chatbot"
            st.rerun()
    
    st.markdown("---")
    
    st.subheader("🌍 Global ARGO Float Network")
    st.markdown("*Interactive visualization of ARGO floats across the world's oceans*")
    
    # Create and display the fixed map
    fig = create_animated_ocean_map()
    st.plotly_chart(fig, use_container_width=True)

def create_float_map(float_data, region):
    """Create an interactive map showing ARGO float locations with enhanced styling."""
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
        title=f"🗺️ ARGO Float Locations - {region}",
        mapbox_style="open-street-map"
    )
    
    fig.update_layout(
        height=500,
        margin={"r":0,"t":50,"l":0,"b":0},
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(31,41,55,0.8)',
        font=dict(color='white')
    )
    
    return fig

def create_profile_plots(profile_data):
    """Create temperature and salinity profile plots with enhanced styling."""
    fig = go.Figure()
    
    # Temperature profile
    fig.add_trace(go.Scatter(
        x=profile_data['temperature'],
        y=-profile_data['depth'],  # Negative for oceanographic convention
        mode='lines+markers',
        name='Temperature (°C)',
        line=dict(color='#ef4444', width=3),
        marker=dict(size=6),
        yaxis='y'
    ))
    
    # Salinity profile on secondary y-axis
    fig.add_trace(go.Scatter(
        x=profile_data['salinity'],
        y=-profile_data['depth'],
        mode='lines+markers',
        name='Salinity (PSU)',
        line=dict(color='#3b82f6', width=3),
        marker=dict(size=6),
        xaxis='x2',
        yaxis='y'
    ))
    
    fig.update_layout(
        title="📈 Temperature and Salinity Profiles",
        xaxis=dict(title="Temperature (°C)", side="bottom", color='white'),
        xaxis2=dict(title="Salinity (PSU)", overlaying="x", side="top", color='white'),
        yaxis=dict(title="Depth (m)", color='white'),
        height=500,
        showlegend=True,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(31,41,55,0.8)',
        font=dict(color='white')
    )
    
    return fig

def show_chatbot():
    """Display the enhanced chatbot page with back button"""
    if st.button("⬅ Back to Homepage", key="back_btn", help="Return to homepage"):
        st.session_state.current_page = "homepage"
        st.rerun()
    
    st.markdown('<h1 style="text-align: center; color: #60a5fa; font-size: 2.5rem; margin-bottom: 2rem;">💬 FloatChat Assistant</h1>', unsafe_allow_html=True)
    
    # Initialize session state for chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "last_response" not in st.session_state:
        st.session_state.last_response = None
    
    # Sidebar controls with enhanced styling
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
        st.subheader("💬 Chat Interface")
        
        # Chat container with custom styling
        chat_container = st.container()
        
        with chat_container:
            # Display chat messages with improved styling
            for i, message in enumerate(st.session_state.messages):
                if message["role"] == "user":
                    st.markdown(f"""
                    <div class="chat-message user-message">
                        <strong>You:</strong> {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="chat-message assistant-message">
                        <strong>🤖 FloatChat:</strong> {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
        
        # Chat input
        if prompt := st.chat_input("Ask me about ARGO ocean data... (e.g., 'Show me salinity profiles near the equator in March 2023')"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display assistant response with loading
            with st.spinner("🔍 Analyzing ARGO data..."):
                response = query_backend(prompt, region, date_range, data_type)
                st.session_state.last_response = response
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response['text']})
            st.rerun()
    
    with col2:
        st.subheader("📈 Query Statistics")
        if st.session_state.last_response:
            metadata = st.session_state.last_response['metadata']
            
            # Enhanced stats display
            st.markdown(f"""
            <div class="stats-card">
                <h4>📊 Last Query Results</h4>
                <p><strong>Active Floats:</strong> {metadata['n_floats']}</p>
                <p><strong>Region:</strong> {metadata['region']}</p>
                <p><strong>Data Type:</strong> {metadata['data_type']}</p>
                <p><strong>Timestamp:</strong> {metadata['query_time']}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("💡 Ask a question to see data statistics!")
    
    if st.session_state.last_response:
        st.markdown("---")
        st.subheader("📊 Data Visualizations")
        
        # Create tabs for different views
        tab1, tab2 = st.tabs(["🗺️ Map View", "📈 Profile Plots"])
        
        with tab1:
            st.plotly_chart(
                create_float_map(
                    st.session_state.last_response['float_locations'], 
                    region
                ),
                use_container_width=True
            )
        
        with tab2:
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

def main():
    """Main application function with simplified navigation."""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "homepage"
    
    # Display selected page based on session state
    if st.session_state.current_page == "homepage":
        show_homepage()
    else:
        show_chatbot()
    
    st.markdown("""
    <div class="footer">
        <p><strong>FloatChat v2.0</strong> | Powered by ARGO Global Ocean Observing System</p>
        <p>🌊 Exploring the world's oceans through AI-powered data analysis</p>
        <p><a href="https://argo.ucsd.edu/" target="_blank" style="color: #60a5fa;">Learn more about ARGO</a> | 
        <a href="#" style="color: #60a5fa;">Documentation</a> | 
        <a href="#" style="color: #60a5fa;">Support</a></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
