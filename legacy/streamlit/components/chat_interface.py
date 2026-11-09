"""
Chat Interface Component
Provides conversational AI interaction with ARGO data through RAG pipeline
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Optional, Any, Tuple
import logging
from datetime import datetime
import json
import re
from dashboard_config import dashboard_config
from components.api_client import APIClient, APIException
from components.data_transformer import DataTransformer
from components.map_visualization import InteractiveMap
from components.profile_visualizer import ProfileVisualizer

logger = logging.getLogger(__name__)

class ChatInterface:
    """Conversational AI interface for ARGO data exploration"""
    
    def __init__(self, api_client: Optional[APIClient] = None):
        self.api_client = api_client or st.session_state.get('api_client')
        self.config = dashboard_config
        self.transformer = DataTransformer()
        self.map_viz = InteractiveMap()
        self.profile_viz = ProfileVisualizer()
        
        # Initialize chat history in session state
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        # Sample queries for user guidance
        self.sample_queries = self._get_sample_queries()
    
    def render_chat_container(self) -> None: 
        """Render the main chat interface"""
        
        st.subheader("💬 Ask Questions About ARGO Data")
        
        # Chat input area
        col1, col2 = st.columns([4, 1])
        
        with col1:
            user_query = st.text_input(
                "Enter your question:",
                placeholder="e.g., Show me salinity profiles near the equator in March 2023",
                help="Ask questions about ARGO float data, locations, profiles, or oceanographic conditions"
            )
        
        with col2:
            send_button = st.button("Send", type="primary", use_container_width=True)
        
        # Process query
        if send_button and user_query.strip():
            self._process_user_query(user_query.strip())
            st.rerun()
        
        # Quick action buttons
        st.markdown("**Quick Actions:**")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🗺️ Show Float Locations", use_container_width=True):
                self._process_user_query("Show me all ARGO float locations")
        
        with col2:
            if st.button("🌡️ Temperature Profiles", use_container_width=True):
                self._process_user_query("Show me temperature profiles for recent data")
        
        with col3:
            if st.button("🧂 Salinity Analysis", use_container_width=True):
                self._process_user_query("Analyze salinity patterns in the Indian Ocean")
        
        with col4:
            if st.button("📊 Data Summary", use_container_width=True):
                self._process_user_query("Give me a summary of available ARGO data")
        
        st.markdown("---")
        
        # Sample queries section
        self._render_sample_queries()
        
        st.markdown("---")
        
        # Chat history
        self._render_chat_history()
    
    def _process_user_query(self, query: str) -> None:
        """Process user query through RAG pipeline and generate response"""
        
        if not query:
            return
        
        # Add user message to history
        user_message = {
            'type': 'user',
            'content': query,
            'timestamp': datetime.now()
        }
        st.session_state.chat_history.append(user_message)
        
        # Show processing indicator
        with st.spinner("🤖 Processing your query..."):
            try:
                if self.api_client:
                    # Send query to RAG pipeline
                    response = self.api_client.query_rag_pipeline(query)
                    
                    if response:
                        # Process the response
                        ai_message = self._create_ai_response(query, response)
                        st.session_state.chat_history.append(ai_message)
                        
                        # Generate visualizations if applicable
                        self._generate_visualizations_from_response(response, query)
                    else:
                        # Handle empty response
                        error_message = {
                            'type': 'ai',
                            'content': "I couldn't process your query. Please try rephrasing your question.",
                            'timestamp': datetime.now(),
                            'error': True
                        }
                        st.session_state.chat_history.append(error_message)
                
                else:
                    # No API client available
                    fallback_message = {
                        'type': 'ai',
                        'content': "I'm currently unable to connect to the ARGO data system. Please check the system status and try again.",
                        'timestamp': datetime.now(),
                        'error': True
                    }
                    st.session_state.chat_history.append(fallback_message)
            
            except APIException as e:
                error_message = {
                    'type': 'ai',
                    'content': f"I encountered an error processing your query: {str(e)}",
                    'timestamp': datetime.now(),
                    'error': True
                }
                st.session_state.chat_history.append(error_message)
            
            except Exception as e:
                logger.error(f"Unexpected error in chat processing: {e}")
                error_message = {
                    'type': 'ai',
                    'content': "I encountered an unexpected error. Please try a different question.",
                    'timestamp': datetime.now(),
                    'error': True
                }
                st.session_state.chat_history.append(error_message)
    
    def _create_ai_response(self, query: str, response) -> Dict[str, Any]:
        """Create AI response message from RAG pipeline response"""
        
        # Extract metadata for visualization hints
        metadata = self.transformer.extract_metadata_for_chat(response.__dict__)
        
        # Enhance the response with interactive elements
        enhanced_content = self._enhance_response_content(response.answer, metadata)
        
        ai_message = {
            'type': 'ai',
            'content': enhanced_content,
            'timestamp': datetime.now(),
            'metadata': metadata,
            'raw_response': response,
            'query_type': metadata.get('query_type', 'unknown')
        }
        
        return ai_message
    
    def _enhance_response_content(self, answer: str, metadata: Dict[str, Any]) -> str:
        """Enhance AI response with interactive elements and formatting"""
        
        enhanced = answer
        
        # Add data context if available
        if metadata.get('data_count', 0) > 0:
            enhanced += f"\n\n📊 **Data Context**: Found {metadata['data_count']} relevant measurements"
            
            if metadata.get('float_ids'):
                float_count = len(metadata['float_ids'])
                enhanced += f" from {float_count} ARGO float{{'s' if float_count > 1 else ''}}"
        
        # Add query type information
        query_type = metadata.get('query_type', 'unknown')
        if query_type == 'analytical':
            enhanced += "\n\n🔬 **Analysis Type**: Statistical/Analytical Query"
        elif query_type == 'semantic':
            enhanced += "\n\n🔍 **Search Type**: Semantic/Descriptive Query"
        
        # Add visualization hints
        if metadata.get('postgres_ids'):
            enhanced += "\n\n💡 **Tip**: I can create visualizations from this data. Check the charts below!"
        
        return enhanced
    
    def _generate_visualizations_from_response(self, response, query: str) -> None:
        """Generate appropriate visualizations based on query response"""
        
        try:
            metadata = self.transformer.extract_metadata_for_chat(response.__dict__)
            
            # Check if we have data to visualize
            postgres_ids = metadata.get('postgres_ids', [])
            sql_results = getattr(response, 'sql_results', None)
            
            if sql_results:
                # Handle SQL results visualization
                self._create_sql_visualizations(sql_results, query)
            
            elif postgres_ids and len(postgres_ids) > 0:
                # Handle profile data visualization
                self._create_profile_visualizations(postgres_ids[:50], query)  # Limit for performance
            
            else:
                # No specific data to visualize, but maybe show general info
                self._create_general_visualizations(query)
        
        except Exception as e:
            logger.error(f"Error generating visualizations: {e}")
            st.error("Could not generate visualizations for this query.")
    
    def _create_sql_visualizations(self, sql_results: List[Dict], query: str) -> None:
        """Create visualizations from SQL query results"""
        
        if not sql_results:
            return
        
        # Convert to DataFrame
        df = self.transformer.sql_results_to_dataframe(sql_results)
        
        if df.empty:
            return
        
        st.subheader("📈 Query Results Visualization")
        
        # Determine appropriate visualization based on columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        if len(numeric_cols) >= 2:
            # Create scatter plot or line chart
            col1, col2 = st.columns(2)
            
            with col1:
                # First chart - could be depth vs temperature
                if 'depth' in df.columns and 'avg_temperature' in df.columns:
                    fig = px.scatter(
                        df, 
                        x='avg_temperature', 
                        y='depth',
                        title='Temperature vs Depth',
                        labels={'avg_temperature': 'Temperature (°C)', 'depth': 'Depth (m)'}
                    )
                    fig.update_yaxis(autorange="reversed")  # Oceanographic convention
                    st.plotly_chart(fig, use_container_width=True)
                
                elif len(numeric_cols) >= 2:
                    fig = px.scatter(
                        df,
                        x=numeric_cols[0],
                        y=numeric_cols[1],
                        title=f'{numeric_cols[1]} vs {numeric_cols[0]}'
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Second chart - could be salinity or other parameter
                if 'depth' in df.columns and 'avg_salinity' in df.columns:
                    fig = px.scatter(
                        df,
                        x='avg_salinity',
                        y='depth', 
                        title='Salinity vs Depth',
                        labels={'avg_salinity': 'Salinity (PSU)', 'depth': 'Depth (m)'}
                    )
                    fig.update_yaxis(autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)
                
                elif len(numeric_cols) >= 3:
                    fig = px.bar(
                        df.head(10),
                        x=df.columns[0],
                        y=numeric_cols[2],
                        title=f'{numeric_cols[2]} Distribution'
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        # Show data table
        with st.expander("📋 View Raw Data"):
            st.dataframe(df, use_container_width=True)
    
    def _create_profile_visualizations(self, postgres_ids: List[int], query: str) -> None:
        """Create profile visualizations from measurement IDs"""
        
        try:
            if not self.api_client:
                st.warning("⚠️ No API connection available for live data visualization.")
                return
            
            st.subheader("🌊 Profile Visualizations")
            
            with st.spinner("Loading profile data..."):
                # Get profile data from live API
                try:
                    profiles_data = self.api_client.get_profiles_by_ids(postgres_ids[:20])  # Limit for performance
                    
                    if not profiles_data:
                        st.info("No profile data found for the specified measurements.")
                        return
                    
                    # Convert to DataFrame
                    df = self.transformer.profiles_to_dataframe(profiles_data)
                    
                    if df.empty:
                        st.info("No valid profile data could be processed.")
                        return
                    
                    # Show data summary first
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Measurements", len(df))
                    with col2:
                        st.metric("Floats", df['float_id'].nunique() if 'float_id' in df.columns else 0)
                    with col3:
                        if 'depth' in df.columns:
                            st.metric("Max Depth", f"{df['depth'].max():.0f}m")
                    
                    # Determine visualization type based on query content
                    query_lower = query.lower()
                    
                    if 'location' in query_lower or 'where' in query_lower or 'map' in query_lower:
                        self._create_location_visualization(df)
                    elif 'profile' in query_lower or 'temperature' in query_lower or 'salinity' in query_lower:
                        self._create_profile_plots(df)
                    else:
                        # Default: show both location and profile
                        self._create_location_visualization(df)
                        self._create_profile_plots(df)
                
                except APIException as e:
                    st.error(f"API Error: {str(e)}")
                    st.info("💡 Try a different query or check the system status.")
                
                except Exception as e:
                    logger.error(f"Error fetching profile data: {e}")
                    st.error("Could not fetch profile data from the API.")
        
        except Exception as e:
            logger.error(f"Error creating profile visualizations: {e}")
            st.error("Could not create profile visualizations.")
    
    def _create_location_visualization(self, df: pd.DataFrame) -> None:
        """Create location-based visualizations"""
        try:
            st.write("**Float Locations**")
            
            # Extract location data
            if 'latitude' in df.columns and 'longitude' in df.columns:
                locations_df = df[['latitude', 'longitude', 'float_id']].drop_duplicates()
                
                if not locations_df.empty:
                    # Create simple scatter plot on map
                    fig = px.scatter_mapbox(
                        locations_df,
                        lat='latitude',
                        lon='longitude',
                        hover_name='float_id',
                        zoom=3,
                        height=400,
                        title="ARGO Float Locations"
                    )
                    fig.update_layout(mapbox_style="open-street-map")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No location data available for visualization.")
            else:
                st.info("Location data (latitude/longitude) not available in the dataset.")
        
        except Exception as e:
            logger.error(f"Error creating location visualization: {e}")
            st.error("Could not create location visualization.")
    
    def _create_profile_plots(self, df: pd.DataFrame) -> None:
        """Create profile plots from data"""
        try:
            st.write("**Oceanographic Profiles**")
            
            # Check for required columns
            required_cols = ['depth']
            available_params = []
            
            if 'temperature' in df.columns:
                available_params.append('temperature')
            if 'salinity' in df.columns:
                available_params.append('salinity')
            if 'pressure' in df.columns:
                available_params.append('pressure')
            
            if not available_params or 'depth' not in df.columns:
                st.info("Insufficient data for profile visualization. Need depth and at least one parameter (temperature/salinity).")
                return
            
            # Get unique floats (limit to first 3 for performance)
            if 'float_id' in df.columns:
                unique_floats = df['float_id'].unique()[:3]
                
                for i, float_id in enumerate(unique_floats):
                    float_data = df[df['float_id'] == float_id].copy()
                    
                    if len(float_data) > 0:
                        st.write(f"**Float {float_id}**")
                        
                        # Create profile plots
                        cols = st.columns(len(available_params))
                        
                        for j, param in enumerate(available_params):
                            with cols[j]:
                                # Create individual parameter profile
                                fig = px.scatter(
                                    float_data,
                                    x=param,
                                    y='depth',
                                    title=f'{param.title()} Profile',
                                    labels={
                                        param: f'{param.title()} ({"°C" if param == "temperature" else "PSU" if param == "salinity" else "dbar"})',
                                        'depth': 'Depth (m)'
                                    }
                                )
                                fig.update_yaxes(autorange="reversed")  # Oceanographic convention
                                fig.update_layout(height=400)
                                st.plotly_chart(fig, use_container_width=True)
            else:
                # No float_id, create aggregate profile
                st.write("**Aggregate Profile**")
                
                cols = st.columns(len(available_params))
                
                for j, param in enumerate(available_params):
                    with cols[j]:
                        fig = px.scatter(
                            df,
                            x=param,
                            y='depth',
                            title=f'{param.title()} Profile',
                            labels={
                                param: f'{param.title()} ({"°C" if param == "temperature" else "PSU" if param == "salinity" else "dbar"})',
                                'depth': 'Depth (m)'
                            }
                        )
                        fig.update_yaxes(autorange="reversed")
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
        
        except Exception as e:
            logger.error(f"Error creating profile plots: {e}")
            st.error("Could not create profile plots.")
    
    def _create_general_visualizations(self, query: str) -> None:
        """Create general visualizations when no specific data is available"""
        
        query_lower = query.lower()
        
        # Show relevant general information based on query
        if 'summary' in query_lower or 'overview' in query_lower:
            st.subheader("📊 ARGO System Overview")
            
            if self.api_client:
                try:
                    # Get live system statistics
                    with st.spinner("Loading system statistics..."):
                        stats = self.api_client.get_system_statistics()
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Active Floats", stats.get('active_floats', 'N/A'))
                        with col2:
                            st.metric("Total Profiles", stats.get('total_profiles', 'N/A'))
                        with col3:
                            st.metric("Measurements", f"{stats.get('total_measurements', 0):,}")
                        with col4:
                            st.metric("Data Quality", f"{stats.get('data_quality', 0):.1f}%")
                        
                        # Show recent activity if available
                        if stats.get('recent_activity'):
                            st.subheader("📈 Recent Activity")
                            activity_df = pd.DataFrame(stats['recent_activity'])
                            
                            if not activity_df.empty:
                                fig = px.line(
                                    activity_df,
                                    x='date',
                                    y='count',
                                    title='Recent Measurement Activity'
                                )
                                st.plotly_chart(fig, use_container_width=True)
                
                except Exception as e:
                    logger.error(f"Error fetching system statistics: {e}")
                    # Fallback to placeholder data
                    self._show_placeholder_overview()
            else:
                self._show_placeholder_overview()
        
        elif 'location' in query_lower or 'where' in query_lower:
            st.info("💡 For specific location queries, try asking about particular regions like 'Arabian Sea' or 'Bay of Bengal'")
            
            # Show available regions if API is connected
            if self.api_client:
                try:
                    regions = self.api_client.get_available_regions()
                    if regions:
                        st.write("**Available Regions:**")
                        for region in regions[:10]:  # Show first 10
                            st.write(f"• {region}")
                except Exception as e:
                    logger.error(f"Error fetching regions: {e}")
    
    def _show_placeholder_overview(self) -> None:
        """Show placeholder overview when live data is not available"""
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Active Floats", "Loading...", "")
        with col2:
            st.metric("Total Profiles", "Loading...", "")
        with col3:
            st.metric("Measurements", "Loading...", "")
        with col4:
            st.metric("Data Quality", "Loading...", "")
        
        st.info("⚠️ Live data connection not available. Connect to the ARGO API to see real-time statistics.")
    
    def _render_sample_queries(self) -> None:
        """Render sample queries for user guidance"""
        
        with st.expander("💡 Example Questions You Can Ask"):
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🗺️ Location & Geographic Queries:**")
                for query in self.sample_queries['location']:
                    if st.button(f"📍 {query}", key=f"sample_loc_{hash(query)}", use_container_width=True):
                        self._process_user_query(query)
                
                st.markdown("**🌡️ Temperature & Salinity:**")
                for query in self.sample_queries['temperature_salinity']:
                    if st.button(f"🌊 {query}", key=f"sample_ts_{hash(query)}", use_container_width=True):
                        self._process_user_query(query)
            
            with col2:
                st.markdown("**🧪 BGC & Water Quality:**")
                for query in self.sample_queries['bgc']:
                    if st.button(f"🔬 {query}", key=f"sample_bgc_{hash(query)}", use_container_width=True):
                        self._process_user_query(query)
                
                st.markdown("**📊 Data Analysis:**")
                for query in self.sample_queries['analysis']:
                    if st.button(f"📈 {query}", key=f"sample_analysis_{hash(query)}", use_container_width=True):
                        self._process_user_query(query)
    
    def _render_chat_history(self) -> None:
        """Render chat history with messages"""
        
        st.subheader("💬 Conversation History")
        
        if not st.session_state.chat_history:
            st.info("Start a conversation by asking a question about ARGO data!")
            return
        
        # Show recent messages (last 10)
        recent_messages = st.session_state.chat_history[-10:]
        
        for i, message in enumerate(reversed(recent_messages)):
            self._render_chat_message(message, len(recent_messages) - i - 1)
        
        # Clear history button
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🗑️ Clear History", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
        
        with col2:
            if st.button("📥 Export Chat", use_container_width=True):
                self._export_chat_history()
    
    def _render_chat_message(self, message: Dict[str, Any], index: int) -> None:
        """Render individual chat message"""
        
        timestamp = message['timestamp'].strftime("%H:%M:%S")
        
        if message['type'] == 'user':
            # User message
            st.markdown(f"""
            <div style="background: #e3f2fd; padding: 10px; border-radius: 10px; margin: 5px 0; border-left: 4px solid #1976d2;">
                <strong>👤 You</strong> <small>({timestamp})</small><br>
                {message['content']}
            </div>
            """, unsafe_allow_html=True)
        
        else:
            # AI message
            bg_color = "#ffebee" if message.get('error') else "#f3e5f5"
            border_color = "#d32f2f" if message.get('error') else "#7b1fa2"
            icon = "❌" if message.get('error') else "🤖"
            
            st.markdown(f"""
            <div style="background: {bg_color}; padding: 10px; border-radius: 10px; margin: 5px 0; border-left: 4px solid {border_color};">
                <strong>{icon} ARGO Assistant</strong> <small>({timestamp})</small><br>
                {message['content']}
            </div>
            """, unsafe_allow_html=True)
            
            # Show metadata if available
            if message.get('metadata') and not message.get('error'):
                metadata = message['metadata']
                
                if metadata.get('data_count', 0) > 0:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.caption(f"📊 Data Points: {metadata['data_count']}")
                    
                    with col2:
                        if metadata.get('float_ids'):
                            st.caption(f"🎯 Floats: {len(metadata['float_ids'])}")
                    
                    with col3:
                        st.caption(f"🔍 Type: {metadata.get('query_type', 'Unknown')}")
    
    def _export_chat_history(self) -> None:
        """Export chat history as downloadable file"""
        
        if not st.session_state.chat_history:
            st.warning("No chat history to export.")
            return
        
        # Create export data
        export_data = []
        for message in st.session_state.chat_history:
            export_data.append({
                'timestamp': message['timestamp'].isoformat(),
                'type': message['type'],
                'content': message['content'],
                'query_type': message.get('query_type', 'N/A')
            })
        
        # Convert to JSON
        export_json = json.dumps(export_data, indent=2)
        
        # Create download
        st.download_button(
            label="📥 Download Chat History",
            data=export_json,
            file_name=f"argo_chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    def _get_sample_queries(self) -> Dict[str, List[str]]:
        """Get sample queries organized by category"""
        
        return {
            'location': [
                "Show me ARGO floats in the Arabian Sea",
                "What floats are near the equator?",
                "Find measurements in the Bay of Bengal",
                "Where are the active floats located?"
            ],
            'temperature_salinity': [
                "Show me temperature profiles near the equator in March 2023",
                "Compare salinity patterns in different regions",
                "What's the average temperature at 500m depth?",
                "Find the warmest surface waters"
            ],
            'bgc': [
                "Compare BGC parameters in the Arabian Sea for the last 6 months",
                "Show me oxygen levels in deep water",
                "Find areas with high chlorophyll concentration",
                "What are the pH levels near the surface?"
            ],
            'analysis': [
                "Give me a summary of available ARGO data",
                "Compare data quality between different floats",
                "Show trends in ocean temperature over time",
                "What's the data coverage in the Indian Ocean?"
            ]
        }
    
    def get_chat_statistics(self) -> Dict[str, Any]:
        """Get statistics about chat usage"""
        
        if not st.session_state.chat_history:
            return {}
        
        total_messages = len(st.session_state.chat_history)
        user_messages = len([m for m in st.session_state.chat_history if m['type'] == 'user'])
        ai_messages = len([m for m in st.session_state.chat_history if m['type'] == 'ai'])
        error_messages = len([m for m in st.session_state.chat_history if m.get('error')])
        
        return {
            'total_messages': total_messages,
            'user_messages': user_messages,
            'ai_messages': ai_messages,
            'error_messages': error_messages,
            'success_rate': (ai_messages - error_messages) / max(ai_messages, 1) * 100
        }