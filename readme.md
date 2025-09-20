# **🌊 FloatChat: AI-Powered ARGO Ocean Data Explorer**

**FloatChat is a conversational AI application that democratizes access to complex ARGO oceanographic data, allowing users to ask natural language questions and receive insightful, visualized answers in real-time.**

## **📖 Project Overview**

Oceanographic data, particularly from the ARGO float program, is a vast and invaluable resource for climate science, yet it remains largely inaccessible to non-specialists due to its complex NetCDF format and the specialized tools required to parse it.  
FloatChat bridges this gap. It leverages a modern AI stack to create an intuitive interface where the complexities of data wrangling are abstracted away. Users can simply ask questions in plain English—like *"What were the sea surface temperatures near the equator in early 2010?"*—and the system retrieves the relevant data, generates a concise answer, and presents interactive visualizations.  
This project demonstrates a complete, end-to-end implementation of a **Retrieval-Augmented Generation (RAG)** pipeline, built entirely with open-source tools designed for local execution, making advanced data science accessible without the need for expensive cloud infrastructure.

## **✨ Key Features**

* **Conversational AI Chatbot**: Interact with ocean data through a natural language interface powered by a locally-run Large Language Model (LLM).  
* **Retrieval-Augmented Generation (RAG)**: The core of the application, using a vector database (ChromaDB) to find relevant data snippets and an LLM to generate context-aware answers.  
* **Dual-Database Architecture**: Utilizes PostgreSQL for structured, relational data storage and ChromaDB for efficient semantic search and retrieval.  
* **Interactive Visualizations**: Dynamically generates maps of float locations and profile plots for temperature and salinity using Plotly.  
* **Local-First Design**: The entire stack, from the LLM (via Ollama) to the databases, is designed to run on a local machine, making it accessible and cost-effective.  
* **RESTful API Backend**: A robust FastAPI backend serves the AI logic and data, cleanly separating it from the user interface.

## **🚀 Live Demo**

\[PASTE A SCREENSHOT OR GIF OF YOUR STREAMLIT APP IN ACTION HERE\]

## **🏛️ System Architecture**

The application is built on a modern RAG architecture that separates data processing, storage, retrieval, and presentation into distinct, communicating components.  
\[PASTE YOUR GENERATED DIAGRAM IMAGE HERE\]

### **DiagramGPT Prompt**

To generate a high-quality diagram for this project, you can use the following prompt with a tool like DiagramGPT or Mermaid Chart:  
"Create a detailed System Architecture Diagram for a RAG (Retrieval-Augmented Generation) application named 'FloatChat' using the Mermaid.js graph TD syntax.  
**Goal:** The diagram should clearly illustrate the flow of data from the user's query to the final visualized answer.  
**Components to Include:**

1. **User**: The person interacting with the system.  
2. **Streamlit Frontend**: The web interface. Label it with the Python logo.  
3. **FastAPI Backend**: The central API server. Label it with the FastAPI logo.  
4. **Ollama Server**: The service running the local LLMs. It should contain two sub-components:  
   * **Embedding Model (nomic-embed-text)**  
   * **LLM (phi3:mini)**  
5. **ChromaDB**: The vector database.  
6. **PostgreSQL**: The relational database. Label it with the PostgreSQL logo.

**Flows to Illustrate:**

1. **RAG Query Flow**:  
   * User submits a text query to the Streamlit Frontend.  
   * Streamlit sends a POST request to the /query endpoint on the FastAPI Backend.  
   * The backend sends the query text to the Ollama Server's Embedding Model to get a vector.  
   * The backend uses this vector to search ChromaDB, which returns relevant document metadata (including postgres\_ids).  
   * The backend constructs a prompt with the user's query and the retrieved documents and sends it to the Ollama Server's LLM.  
   * The LLM generates a text answer.  
   * The backend returns the text answer and the metadata to the Streamlit Frontend.  
2. **Data Fetching Flow for Plots**:  
   * Based on the postgres\_ids from the first response, the Streamlit Frontend sends a POST request to the /get\_profiles endpoint on the FastAPI Backend.  
   * The backend queries the PostgreSQL database using the provided IDs.  
   * PostgreSQL returns the full measurement data (depth, temp, salinity).  
   * The backend returns this data to the Streamlit Frontend.  
   * The Streamlit Frontend uses this data to render the plots.

**Styling Instructions:**

* Use a left-to-right flow.  
* Use different shapes for different component types (e.g., rectangles for services, cylinders for databases).  
* Use clear arrow labels to describe the data being passed (e.g., 'User Query', 'API Request', 'Vector Search', 'SQL Query')."

## **🛠️ Technology Stack**

| Category | Technology | Purpose |
| :---- | :---- | :---- |
| **Frontend** | **Streamlit** | Building the interactive web application and user interface. |
|  | **Plotly** | Creating dynamic, interactive maps and scientific plots. |
| **Backend** | **FastAPI** | Serving the AI/RAG logic and data via a high-performance RESTful API. |
|  | **Uvicorn** | Acting as the ASGI server for the FastAPI application. |
| **Databases** | **PostgreSQL** | Storing the structured, relational ARGO measurement data for fast lookups. |
|  | **ChromaDB** | Storing text embeddings (vectors) for efficient semantic search. |
| **AI / ML** | **Ollama** | Serving local LLMs and embedding models efficiently. |
|  | **Microsoft Phi-3 Mini (phi3:mini)** | The Large Language Model used for generating answers from context. |
|  | **Nomic Embed Text (nomic-embed-text)** | The embedding model used to convert text into vector representations. |
| **Data Tools** | **Xarray**, **Pandas** | Parsing the source .nc files and transforming the data for ingestion. |
|  | **SQLAlchemy** | Interfacing between the Python application and the PostgreSQL database. |

## **🔬 Honest Assessment & Project Status**

This project successfully implements a proof-of-concept for a conversational data exploration tool. The core RAG pipeline is functional and demonstrates the power of combining semantic search with structured data retrieval.  
**Current Limitations:**

1. **Gridded Data vs. Profile Data:** The current data source is a gridded product, meaning each entry in the database is a single point at a specific depth. As a result, the "Profile Plots" currently only show a single data point, as there is no full vertical profile to retrieve for a single ID. This was a key learning from the development process.  
2. **Static Dataset:** The ingestion pipeline is run manually as a script. The system does not yet automatically process new or updated ARGO data.  
3. **Basic Retrieval:** The current retrieval method fetches the top k most similar documents. It does not yet perform more complex aggregations or trend analysis, which would require a Natural-Language-to-SQL implementation.

## **🔭 Future Vision**

This project has a strong foundation with several exciting avenues for future development:

1. **Implement NL-to-SQL:** The most impactful next step would be to empower the LLM to generate and execute SQL queries against the PostgreSQL database. This would allow users to ask complex analytical questions like *"Compare the average salinity in the Atlantic and Pacific oceans in 2012"* and get calculated answers.  
2. **Ingest True Profile Data:** Refactor the ingestion pipeline to process the original ARGO float files, which contain full vertical profiles. This would enable the Profile Plots to show complete, meaningful graphs of temperature and salinity vs. depth.  
3. **Automated Data Ingestion:** Develop an automated pipeline (e.g., using Airflow or a cron job) to periodically download the latest ARGO data and keep the databases up-to-date.  
4. **Enhanced UI:** Allow users to click on a float in the map view to dynamically load its corresponding profile plot, creating a more interconnected and exploratory user experience.

## **⚙️ Setup and Installation**

To run this project locally, please follow these steps:  
**Prerequisites:**

* Python 3.9+  
* PostgreSQL server installed and running.  
* [Ollama](https://ollama.ai/) installed and running.

**1\. Clone the Repository:**  
git clone \[https://github.com/your-username/float-chat.git\](https://github.com/your-username/float-chat.git)  
cd float-chat

**2\. Install Dependencies:**  
pip install \-r requirements.txt

*(Note: You will need to create a requirements.txt file from your environment)*  
3\. Set up Ollama:  
Pull the necessary LLM and embedding models.  
ollama pull phi3:mini  
ollama pull nomic-embed-text

**4\. Set up PostgreSQL:**

* Create a new database named argo.  
* Run the data\_postgresql.py script to create the measurements table and populate it with initial data from your .nc file.  
  python data\_postgresql.py

* *Ensure you update the password in the script if yours is different.*

5\. Create and Populate the Vector Database:  
Run the data\_chroma.py script to generate embeddings and populate ChromaDB. This may take some time.  
python data\_chroma.py

6\. Run the Backend API:  
Start the FastAPI server in a terminal.  
uvicorn main:app \--reload

The API will be available at http://127.0.0.1:8000.  
7\. Run the Frontend Application:  
Open a second terminal and start the Streamlit app.  
streamlit run app.py

The application will be available at http://localhost:8501.

## **📂 File Structure**

* main.py: The FastAPI application containing all API endpoints.  
* app.py: The Streamlit frontend application for the user interface.  
* data\_postgresql.py: Script for one-time ingestion of .nc data into PostgreSQL.  
* data\_chroma.py: Script to fetch data from PostgreSQL and populate the ChromaDB vector store.  
* requirements.txt: A list of all necessary Python packages.  
* chroma\_db/: Directory where the local ChromaDB is persisted.

## **🙏 Acknowledgements**

This project is powered by the invaluable data provided by the **Argo Global Data Assembly Centers**. Argo is an international program that measures the temperature, salinity, and other properties of the ocean's upper 2000 meters.