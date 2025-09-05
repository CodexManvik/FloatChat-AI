# web_app.py - Web interface for ARGO RAG system
from flask import Flask, render_template, request, jsonify
import os
import sys

# Add the current directory to Python path to import your modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag_query import ArgoRAG

app = Flask(__name__)

# Initialize RAG system
print("🚀 Initializing ARGO RAG System...")
rag_system = ArgoRAG()
print("✅ Web app ready!")

@app.route('/')
def home():
    """Main page with query interface"""
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def query():
    """Handle RAG queries via AJAX"""
    try:
        data = request.get_json()
        question = data.get('question', '')
        
        if not question.strip():
            return jsonify({'error': 'Please enter a question'}), 400
        
        print(f"🔍 Web query: {question}")
        
        # Get vector search results
        results = rag_system.semantic_search(question, n_results=3)
        
        # Generate answer
        answer = rag_system.generate_answer(question, [], results['metadatas'][0])
        
        # Format relevant profiles
        profiles = []
        for i, metadata in enumerate(results['metadatas'][0]):
            profiles.append({
                'id': metadata['float_id'],
                'latitude': f"{metadata['latitude']:.1f}°N",
                'longitude': f"{metadata['longitude']:.1f}°E", 
                'temperature': f"{metadata['surface_temp']:.1f}°C",
                'salinity': f"{metadata['surface_sal']:.1f}",
                'date': metadata['datetime']
            })
        
        return jsonify({
            'answer': answer,
            'profiles': profiles,
            'question': question
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/sample-queries')
def sample_queries():
    """Return sample questions for the UI"""
    samples = [
        "What is the temperature in tropical waters?",
        "Show me salinity data from the Indian Ocean",
        "Where are the warmest ocean temperatures?", 
        "Find data with high salinity values",
        "What are recent temperature measurements?"
    ]
    return jsonify(samples)

if __name__ == '__main__':
    print("\n🌊 ARGO RAG Web Interface Starting...")
    print("🔗 Access at: http://localhost:5000")
    print("=" * 40)
    app.run(debug=True, host='0.0.0.0', port=5000)
