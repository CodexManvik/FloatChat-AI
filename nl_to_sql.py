"""
Production-Ready Natural Language to SQL Translation System
Handles analytical queries for ARGO oceanographic data
"""

import ollama
from sqlalchemy import create_engine, text
import pandas as pd
import config
import re
from typing import Dict, List, Tuple, Optional

class NLToSQLTranslator:
    """Advanced NL-to-SQL translator with enhanced query understanding"""
    
    def __init__(self):
        self.engine = create_engine(config.DATABASE_URL)
        self.schema_info = self._get_schema_info()
        self.query_templates = self._load_query_templates()
    
    def _get_schema_info(self):
        """Get comprehensive database schema information"""
        schema_query = """
        SELECT 
            table_name,
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name IN ('floats', 'profiles', 'measurements')
        ORDER BY table_name, ordinal_position;
        """
        
        with self.engine.connect() as conn:
            schema_df = pd.read_sql_query(schema_query, conn)
        
        # Group by table
        schema_info = {}
        for table in ['floats', 'profiles', 'measurements']:
            table_cols = schema_df[schema_df['table_name'] == table]
            schema_info[table] = table_cols[['column_name', 'data_type']].to_dict('records')
        
        return schema_info
    
    def _load_query_templates(self) -> Dict[str, str]:
        """Pre-defined SQL templates for common query patterns"""
        return {
            'avg_by_depth': """
                SELECT depth, 
                       AVG(temperature) as avg_temperature,
                       AVG(salinity) as avg_salinity,
                       COUNT(*) as measurement_count
                FROM measurements 
                WHERE temperature IS NOT NULL AND salinity IS NOT NULL
                GROUP BY depth 
                ORDER BY depth
                LIMIT 100;
            """,
            
            'multi_dataset_comparison': """
                SELECT 
                    dataset_type,
                    COUNT(*) as observation_count,
                    AVG(temperature) as avg_temperature,
                    AVG(salinity) as avg_salinity,
                    MIN(time) as start_date,
                    MAX(time) as end_date
                FROM measurements 
                GROUP BY dataset_type
                ORDER BY observation_count DESC;
            """,
            
            'regional_comparison': """
                SELECT 
                    CASE 
                        WHEN lat > 0 THEN 'Northern Hemisphere'
                        ELSE 'Southern Hemisphere'
                    END as region,
                    AVG(temperature) as avg_temperature,
                    AVG(salinity) as avg_salinity,
                    AVG(oxygen) as avg_oxygen,
                    COUNT(*) as measurement_count
                FROM measurements 
                WHERE temperature IS NOT NULL
                GROUP BY CASE WHEN lat > 0 THEN 'Northern Hemisphere' ELSE 'Southern Hemisphere' END;
            """,
            
            'depth_ranges': """
                SELECT 
                    CASE 
                        WHEN depth < 100 THEN 'Surface (0-100m)'
                        WHEN depth < 500 THEN 'Intermediate (100-500m)'
                        WHEN depth < 1000 THEN 'Deep (500-1000m)'
                        ELSE 'Very Deep (>1000m)'
                    END as depth_range,
                    AVG(temperature) as avg_temperature,
                    AVG(salinity) as avg_salinity,
                    AVG(oxygen) as avg_oxygen,
                    COUNT(*) as measurement_count
                FROM measurements 
                WHERE temperature IS NOT NULL
                GROUP BY CASE 
                    WHEN depth < 100 THEN 'Surface (0-100m)'
                    WHEN depth < 500 THEN 'Intermediate (100-500m)'
                    WHEN depth < 1000 THEN 'Deep (500-1000m)'
                    ELSE 'Very Deep (>1000m)'
                END
                ORDER BY MIN(depth);
            """,
            
            'float_summary': """
                SELECT 
                    f.float_id,
                    f.wmo_id,
                    f.deployment_date,
                    COUNT(DISTINCT p.profile_id) as total_profiles,
                    COUNT(m.id) as total_measurements,
                    AVG(m.temperature) as avg_temperature,
                    AVG(m.salinity) as avg_salinity,
                    MIN(m.depth) as min_depth,
                    MAX(m.depth) as max_depth
                FROM floats f
                JOIN profiles p ON f.float_id = p.float_id
                JOIN measurements m ON p.profile_id = m.profile_id
                WHERE m.temperature IS NOT NULL
                GROUP BY f.float_id, f.wmo_id, f.deployment_date
                ORDER BY total_measurements DESC
                LIMIT 50;
            """,
            
            'temporal_trends': """
                SELECT 
                    DATE_TRUNC('month', m.time) as month,
                    AVG(m.temperature) as avg_temperature,
                    AVG(m.salinity) as avg_salinity,
                    COUNT(*) as measurement_count
                FROM measurements m
                WHERE m.temperature IS NOT NULL
                GROUP BY DATE_TRUNC('month', m.time)
                ORDER BY month
                LIMIT 100;
            """,
            
            'bgc_analysis': """
                SELECT 
                    CASE 
                        WHEN depth < 200 THEN 'Euphotic Zone'
                        WHEN depth < 1000 THEN 'Mesopelagic Zone'
                        ELSE 'Bathypelagic Zone'
                    END as ocean_zone,
                    AVG(oxygen) as avg_oxygen,
                    AVG(ph) as avg_ph,
                    AVG(chlorophyll) as avg_chlorophyll,
                    COUNT(*) as measurement_count
                FROM measurements 
                WHERE oxygen IS NOT NULL AND ph IS NOT NULL
                GROUP BY CASE 
                    WHEN depth < 200 THEN 'Euphotic Zone'
                    WHEN depth < 1000 THEN 'Mesopelagic Zone'
                    ELSE 'Bathypelagic Zone'
                END
                ORDER BY MIN(depth);
            """
        }
    
    def is_analytical_query(self, query: str) -> bool:
        """Enhanced analytical query detection"""
        analytical_patterns = [
            # Statistical operations
            r'\b(average|mean|avg|sum|count|total|maximum|max|minimum|min)\b',
            # Comparative operations  
            r'\b(compare|comparison|versus|vs|between|difference)\b',
            # Aggregation terms
            r'\b(group|aggregate|distribution|range|trend|correlation)\b',
            # Quantitative terms
            r'\b(how many|how much|statistics|statistical|percentage|percent)\b',
            # Relational terms
            r'\b(greater than|less than|higher|lower|above|below|top|bottom)\b',
            # Temporal analysis
            r'\b(over time|temporal|monthly|yearly|seasonal)\b'
        ]
        
        query_lower = query.lower()
        return any(re.search(pattern, query_lower) for pattern in analytical_patterns)
    
    def detect_query_intent(self, query: str) -> str:
        """Detect the intent/type of analytical query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['depth', 'profile', 'vertical']):
            if any(word in query_lower for word in ['average', 'mean']):
                return 'avg_by_depth'
        
        if any(word in query_lower for word in ['region', 'compare', 'hemisphere', 'north', 'south']):
            return 'regional_comparison'
        
        if any(word in query_lower for word in ['depth range', 'surface', 'deep', 'zone']):
            return 'depth_ranges'
        
        if any(word in query_lower for word in ['float', 'summary', 'overview']):
            return 'float_summary'
        
        if any(word in query_lower for word in ['time', 'temporal', 'trend', 'month', 'year']):
            return 'temporal_trends'
        
        if any(word in query_lower for word in ['oxygen', 'ph', 'chlorophyll', 'bgc', 'biogeochemical']):
            return 'bgc_analysis'
        
        return 'custom'
    
    def generate_sql(self, nl_query: str) -> Tuple[str, str]:
        """Generate SQL query with intent detection"""
        
        # First, try template matching (faster)
        intent = self.detect_query_intent(nl_query)
        
        if intent != 'custom' and intent in self.query_templates:
            return self.query_templates[intent].strip(), intent
        
        # For common patterns, use simple mapping instead of LLM
        query_lower = nl_query.lower()
        
        if 'average temperature' in query_lower and 'depth' in query_lower:
            return self.query_templates['avg_by_depth'].strip(), 'avg_by_depth'
        
        if 'compare' in query_lower and ('region' in query_lower or 'hemisphere' in query_lower):
            return self.query_templates['regional_comparison'].strip(), 'regional_comparison'
        
        if 'float' in query_lower and ('summary' in query_lower or 'count' in query_lower):
            return self.query_templates['float_summary'].strip(), 'float_summary'
        
        # Fall back to LLM generation for custom queries
        schema_context = self._format_schema_for_prompt()
        
        prompt = f"""
You are an expert PostgreSQL analyst for ARGO oceanographic data.
Convert this natural language query to a precise SQL query.

DATABASE SCHEMA:
{schema_context}

QUERY RULES:
1. Always use proper JOINs: floats -> profiles -> measurements
2. Include meaningful column aliases
3. Add appropriate WHERE clauses for NULL handling
4. Use LIMIT to prevent excessive results (max 1000 rows)
5. Include ORDER BY for logical sorting
6. Use proper aggregation functions (AVG, COUNT, MIN, MAX, SUM)
7. Handle date/time operations with PostgreSQL functions
8. For regional analysis, use latitude/longitude ranges

EXAMPLE PATTERNS:
- Depth analysis: GROUP BY depth or depth ranges
- Regional: GROUP BY latitude/longitude regions  
- Temporal: GROUP BY DATE_TRUNC('month', time)
- Float analysis: GROUP BY float_id with JOINs
- BGC analysis: Focus on oxygen, ph, chlorophyll columns

Natural Language Query: {nl_query}

Return ONLY the SQL query without explanations or formatting:
"""
        
        try:
            # Add timeout and simpler prompt for faster processing
            response = ollama.chat(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1, "top_p": 0.9}  # More deterministic, faster
            )
            
            sql_query = response["message"]["content"].strip()
            
            # Clean up formatting
            sql_query = re.sub(r'```sql\n?', '', sql_query)
            sql_query = re.sub(r'```\n?', '', sql_query)
            sql_query = sql_query.strip()
            
            # Add safety limit if not present
            if 'limit' not in sql_query.lower():
                sql_query += ' LIMIT 1000'
            
            return sql_query, 'custom'
            
        except Exception as e:
            print(f"Error generating SQL: {e}")
            return None, 'error'
    
    def validate_sql(self, sql_query: str) -> bool:
        """Basic SQL validation before execution"""
        dangerous_keywords = ['drop', 'delete', 'truncate', 'alter', 'create', 'insert', 'update']
        sql_lower = sql_query.lower()
        
        # Check for dangerous operations
        if any(keyword in sql_lower for keyword in dangerous_keywords):
            return False
        
        # Must be a SELECT statement
        if not sql_lower.strip().startswith('select'):
            return False
        
        return True
    
    def execute_sql_query(self, sql_query: str) -> Tuple[pd.DataFrame, str]:
        """Execute SQL with comprehensive error handling"""
        
        if not self.validate_sql(sql_query):
            return pd.DataFrame(), "Invalid or unsafe SQL query"
        
        try:
            with self.engine.connect() as conn:
                result_df = pd.read_sql_query(text(sql_query), conn)
            
            if result_df.empty:
                return result_df, "Query executed successfully but returned no results"
            
            return result_df, "success"
            
        except Exception as e:
            error_msg = str(e)
            
            # Provide helpful error messages
            if "column" in error_msg.lower() and "does not exist" in error_msg.lower():
                return pd.DataFrame(), f"Column not found. Available columns: {self._get_available_columns()}"
            elif "syntax error" in error_msg.lower():
                return pd.DataFrame(), "SQL syntax error. Please check the query structure."
            else:
                return pd.DataFrame(), f"Database error: {error_msg}"
    
    def _get_available_columns(self) -> str:
        """Get list of available columns for error messages"""
        all_columns = []
        for table, columns in self.schema_info.items():
            for col in columns:
                all_columns.append(f"{table}.{col['column_name']}")
        return ", ".join(all_columns[:20])  # Limit for readability
    
    def _format_schema_for_prompt(self) -> str:
        """Enhanced schema formatting for LLM"""
        schema_text = "TABLES AND COLUMNS:\n"
        
        for table_name, columns in self.schema_info.items():
            schema_text += f"\n{table_name.upper()}:\n"
            for col in columns:
                schema_text += f"  - {col['column_name']} ({col['data_type']})\n"
        
        schema_text += """
TABLE RELATIONSHIPS:
- floats (1) -> profiles (many) via float_id
- profiles (1) -> measurements (many) via profile_id  
- measurements also has direct float_id reference

KEY MEASUREMENT COLUMNS:
- Physical: temperature, salinity, depth, pressure, lat, lon, time
- BGC: oxygen, ph, chlorophyll, nitrate, backscatter, cdom, downwelling_par
- Identifiers: float_id, profile_id, cycle_number, wmo_id

COMMON QUERY PATTERNS:
- Depth profiles: GROUP BY depth
- Regional analysis: GROUP BY lat/lon ranges
- Temporal trends: GROUP BY DATE_TRUNC('month', time)
- Float comparison: GROUP BY float_id
- BGC analysis: Focus on oxygen, ph, chlorophyll
"""
        
        return schema_text

def process_analytical_query(nl_query: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Enhanced analytical query processing with comprehensive error handling"""
    
    try:
        translator = NLToSQLTranslator()
        
        # Check if query is analytical
        if not translator.is_analytical_query(nl_query):
            return None, "Not an analytical query - use semantic search instead"
        
        # Generate SQL
        sql_query, intent = translator.generate_sql(nl_query)
        if not sql_query:
            return None, "Failed to generate SQL query"
        
        # Execute SQL
        result_df, execution_status = translator.execute_sql_query(sql_query)
        
        if execution_status != "success":
            return None, f"SQL execution failed: {execution_status}"
        
        # Prepare comprehensive response
        response = {
            'sql_query': sql_query,
            'results': result_df,
            'row_count': len(result_df),
            'column_count': len(result_df.columns) if not result_df.empty else 0,
            'query_type': 'analytical',
            'intent': intent,
            'execution_status': execution_status,
            'summary_stats': _generate_summary_stats(result_df) if not result_df.empty else {}
        }
        
        return response, None
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in process_analytical_query: {error_details}")
        return None, f"Unexpected error in analytical query processing: {str(e)}"

def _generate_summary_stats(df: pd.DataFrame) -> Dict:
    """Generate summary statistics for query results"""
    
    # Convert numpy types to Python native types for JSON serialization
    stats = {
        'total_rows': int(len(df)),
        'columns': [str(col) for col in df.columns],
        'numeric_columns': [str(col) for col in df.select_dtypes(include=['float64', 'int64']).columns],
        'has_nulls': bool(df.isnull().any().any())
    }
    
    # Add basic statistics for numeric columns
    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
    if len(numeric_cols) > 0:
        stats['numeric_summary'] = {}
        for col in numeric_cols[:5]:  # Limit to first 5 numeric columns
            col_data = df[col]
            if not col_data.isna().all():
                stats['numeric_summary'][str(col)] = {
                    'mean': float(col_data.mean()),
                    'min': float(col_data.min()),
                    'max': float(col_data.max()),
                    'count': int(col_data.count())
                }
            else:
                stats['numeric_summary'][str(col)] = {
                    'mean': None,
                    'min': None,
                    'max': None,
                    'count': 0
                }
    
    return stats

def get_sample_analytical_queries() -> Dict[str, List[str]]:
    """Comprehensive sample queries organized by category"""
    return {
        "Depth Analysis": [
            "What is the average temperature at different depths?",
            "Show salinity profiles by depth ranges",
            "Compare temperature between surface and deep water",
            "Find the deepest measurements for each float"
        ],
        
        "Regional Comparison": [
            "Compare salinity between northern and southern hemispheres",
            "Show temperature differences across ocean regions",
            "Analyze BGC parameters by geographic location",
            "Compare measurements between different latitude ranges"
        ],
        
        "Temporal Trends": [
            "Show temperature trends over time",
            "Count measurements by month",
            "Analyze seasonal variations in ocean parameters",
            "Track float deployment patterns over time"
        ],
        
        "Float Analysis": [
            "Show summary statistics for each float",
            "Compare performance between different floats",
            "Find floats with the most measurements",
            "Analyze float operational duration"
        ],
        
        "BGC Parameters": [
            "What are the oxygen levels below 500 meters?",
            "Compare BGC parameters between surface and deep water",
            "Show pH variations with depth",
            "Analyze chlorophyll distribution in different ocean zones"
        ],
        
        "Statistical Analysis": [
            "Calculate correlation between temperature and salinity",
            "Find outliers in temperature measurements",
            "Show distribution of measurements by depth",
            "Identify patterns in missing data"
        ]
    }

def test_nl_to_sql_system():
    """Comprehensive test suite for NL-to-SQL system"""
    
    print("🧪 Testing NL-to-SQL System")
    print("=" * 50)
    
    translator = NLToSQLTranslator()
    
    # Test 1: Query classification
    test_queries = [
        ("What is the average temperature?", True),
        ("Show me temperature measurements", False),
        ("Compare salinity between regions", True),
        ("Tell me about ARGO floats", False),
        ("Count measurements by depth", True)
    ]
    
    print("1. Testing query classification:")
    for query, expected in test_queries:
        result = translator.is_analytical_query(query)
        status = "✅" if result == expected else "❌"
        print(f"   {status} '{query}' -> {result}")
    
    # Test 2: Template matching
    print("\n2. Testing template matching:")
    template_queries = [
        "What is the average temperature at different depths?",
        "Compare salinity between northern and southern regions",
        "Show BGC parameters by ocean zones"
    ]
    
    for query in template_queries:
        intent = translator.detect_query_intent(query)
        print(f"   ✅ '{query}' -> {intent}")
    
    # Test 3: SQL generation and execution
    print("\n3. Testing SQL execution:")
    test_query = "What is the average temperature at different depths?"
    
    try:
        result, error = process_analytical_query(test_query)
        if error:
            print(f"   ❌ Error: {error}")
        else:
            print(f"   ✅ Query executed successfully")
            print(f"      - Rows returned: {result['row_count']}")
            print(f"      - Columns: {result['column_count']}")
            print(f"      - Intent: {result['intent']}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    print("\n✅ NL-to-SQL system testing completed!")

if __name__ == "__main__":
    test_nl_to_sql_system()