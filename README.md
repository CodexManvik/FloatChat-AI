make a python env, i made it in 3.13.5

in pwsh- python -r requirements.txt

nitu and shashwat- work on chroma or other db and let me know about the changes
                  all changes to be pushed in the updates branch

archit and nemat- .csv file are to be stored in app/core/data/raw, check the directory out
                  run this command on pwsh- python -m app.ingest.ingest && uvicorn app.core.main:app --reload
                  after running, in browser, go to this page- http://127.0.0.1:8000/docs
                  make the implementation better and work on /api/ask
                  galti se bhi ingestion matt start kar dena, your pc wont be able to handle the load in time
                  all changes to be pushed in the updates branch

khushi- make the frontend and push it in the main branch


ask me if stuck 
