import shutil
from typing import List, Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from PyPDF2 import PdfReader
import os

app = FastAPI()
path = ''

def get_pdf_text(pdf_path):
    path = pdf_path
    text = ""
    with open(f"uploads/{pdf_path}", 'rb') as file:
        reader = PdfReader(file)
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text += page.extract_text()
    return text


from pymongo import MongoClient
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

load_dotenv()

aiclient = OpenAI()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Cross-Origin-Opener-Policy"],
)



from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
uri = os.getenv('MONGO_URI')
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client["lol1"]
collection = db["lol1"]


os.makedirs('uploads/', exist_ok=True)


@app.post("/uploadfile/")
async def upload_file(file: UploadFile = File(...), text: Optional[str] = Form(None), ):
    file_location = f"uploads/{file.filename}"
    text += " "
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    document = {
        "pdf_name": file.filename,
        "user_text": text
    }

    collection.insert_one(document)
    return {
        "pdf_name": file.filename,
        "user_text": text
    }


class VectorData(BaseModel):
    pdf_name: str
    text_content: str
    vector: List[float]


class NameRequest(BaseModel):
    name: str


@app.get("/vector")
def get_vector_by_name(name: str):
    vector_data = collection.find_one({"pdf_name": name})
    if not vector_data:
        raise HTTPException(status_code=404, detail="Vector not found")
    
    pdf_content = get_pdf_text(vector_data['pdf_name'])
    text = vector_data['user_text']
    if os.path.exists(f"uploads/{vector_data['pdf_name']}"):
        os.remove(f"uploads/{vector_data['pdf_name']}")
        print(f"File uploads/{vector_data['pdf_name']} deleted successfully")
    else:
        print(f"File uploads/{vector_data['pdf_name']} does not exist")

    completion = aiclient.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"Give me a name of this document with quotes without your comments based on text of this document: {pdf_content}"
            },
        ]
    )

    examples = ['"requests": [{ "createItem": { "item": { "title": "Homework video", "description": "Quizzes in Google Forms", "videoItem": { "video": {"youtubeUri": "https://www.youtube.com/watch?v=Lt5HqPvM-eI" } }}, "location": { "index": 0 } }]',
        '"requests": [{ "createItem": { "item": { "title": "MCQ 1: Backend", "questionItem": { "question": { "required": true, "choiceQuestion": { "type": "RADIO", "options": [ { "value": "Express.js with a backend/ai week boilerplate" }, { "value": "Django with a Django template" }, { "value": "Flask with a Flask template" } ], "shuffle": false } } } }, "location": { "index": 0 } } },{ "createItem": { "item": { "title": "MCQ 2: Frontend Setup", "questionItem": { "question": { "required": true, "choiceQuestion": { "type": "RADIO", "options": [ { "value": "React/Next.js" }, { "value": "Vue.js/Nuxt.js" }, { "value": "Angular" } ], "shuffle": false } } } }, "location": { "index": 1 } } },{ "createItem": { "item": { "title": "MCQ 3: Database", "questionItem": { "question": { "required": true, "choiceQuestion": { "type": "RADIO", "options": [ { "value": "MongoDB with Mongoose ORM" }, { "value": "PostgreSQL with Prisma ORM" }, { "value": "MySQL with Sequelize ORM" } ], "shuffle": false } } } }, "location": { "index": 2 } } }]}',
        '{"requests":[{"createItem":{"item":{"title":"What type of numbers are {1, 2, 3, 4, 5, …}?","questionItem":{"question":{"required":true,"choiceQuestion":{"type":"RADIO","options":[{"value":"Natural Numbers"},{"value":"Whole Numbers"},{"value":"Integers"}],"shuffle":false}}}},"location":{"index":0}}},{"createItem":{"item":{"title":"What type of numbers are {..., -3, -2, -1, 0, 1, 2, ...}?","questionItem":{"question":{"required":true,"choiceQuestion":{"type":"RADIO","options":[{"value":"Whole Numbers"},{"value":"Integers"},{"value":"Natural Numbers"}],"shuffle":false}}}},"location":{"index":1}}},{"createItem":{"item":{"title":"Which numbers can be written in the form a/b, where a and b are integers and b ≠ 0?","questionItem":{"question":{"required":true,"choiceQuestion":{"type":"RADIO","options":[{"value":"Rational Numbers"},{"value":"Irrational Numbers"},{"value":"Real Numbers"}],"shuffle":false}}}},"location":{"index":2}}},{"createItem":{"item":{"title":"Which numbers include all numbers that can be represented on the number line?","questionItem":{"question":{"required":true,"choiceQuestion":{"type":"RADIO","options":[{"value":"Natural Numbers"},{"value":"Integers"},{"value":"Real Numbers"}],"shuffle":false}}}},"location":{"index":3}}},{"createItem":{"item":{"title":"Which type of numbers has only itself and 1 as factors?","questionItem":{"question":{"required":true,"choiceQuestion":{"type":"RADIO","options":[{"value":"Composite Numbers"},{"value":"Prime Numbers"},{"value":"Real Numbers"}],"shuffle":false}}}},"location":{"index":4}}},{"createItem":{"item":{"title":"What is the LCM of 5 and 6?","questionItem":{"question":{"required":true,"choiceQuestion":{"type":"RADIO","options":[{"value":"30"},{"value":"1"},{"value":"5"}],"shuffle":false}}}},"location":{"index":5}}}]}',
        '{"requests":[{"createItem":{"item":{"title":"lol","questionItem":{"question":{"required":false,"grading":{"pointValue":0,"correctAnswers":{"answers":[{"value":"1"}]},"choiceQuestion":{"type":"CHECKBOX","options":[{"value":"1"},{"value":"2"},{"value":"3"}]}}}},"location":{"index":0}}}]}' ]

    response = aiclient.chat.completions.create(
        model="gpt-4o",
        response_format={ "type": "json_object" },
        messages=[
            {
                "role": "system",
                "content": f'You are creater of google forms api jsons. As examples you can use {examples}',
            },
            {
                "role": "user",
                "content": f"Write me one json without any comment from you for google forms api updating google form quiz without adding name and title by adding ONLY MCQ test questions based on this text: {pdf_content}"
            },
            {
                "role": "user",
                "content": f"{text}"
            }
        ]
    )

    return {"filename": vector_data['pdf_name'],
            "pdf_content": pdf_content,
            "form_name": completion.choices[0].message.content,
            "questions": response.choices[0].message.content,
            "google_api_key": os.getenv('GOOGLE_API_KEY')
            }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
