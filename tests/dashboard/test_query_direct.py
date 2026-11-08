"""
Direct test of the query processing to isolate the issue
"""

from nl_to_sql import process_analytical_query

def test_direct():
    print("Testing analytical query processing directly...")
    
    query = "What is the average temperature at different depths?"
    
    try:
        result, error = process_analytical_query(query)
        
        if error:
            print(f"Error: {error}")
        else:
            print("Success!")
            print(f"SQL Query: {result['sql_query'][:100]}...")
            print(f"Row count: {result['row_count']}")
            print(f"Intent: {result['intent']}")
            print(f"Execution status: {result['execution_status']}")
            
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct()