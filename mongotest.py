import shutil
from typing import List, Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from pydantic import BaseModel
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import os
import fitz
import boto3
import uuid

load_dotenv()

app = FastAPI()


AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")


if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME, AWS_REGION]):
    raise ValueError("One or more environment variables are not set. Please check your .env file.")


s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)


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
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI


aiclient = OpenAI()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://regularform.vercel.app",
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

client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)


db = client["lol1"]
collection = db["lol1"]


@app.post("/uploadfile/")
async def upload_file(file: UploadFile = File(...), text: Optional[str] = Form(None), ):
    try:
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_contents = await file.read()
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=unique_filename, Body=file_contents)
        if(text != None):
            document = {
                "pdf_name": unique_filename,
                "user_text": text
            }
        else:
            document = {
                "pdf_name": unique_filename,
            } 

        collection.insert_one(document)
        return {
            "pdf_name": unique_filename,
        }

    except (NoCredentialsError, PartialCredentialsError):
        raise HTTPException(status_code=500, detail="AWS credentials not configured properly")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


class VectorData(BaseModel):
    pdf_name: str
    text_content: str
    vector: List[float]


@app.get("/vector")
def get_vector_by_name(name: str):
    vector_data = collection.find_one({"pdf_name": name})
    if not vector_data:
        raise HTTPException(status_code=404, detail="Vector not found")
    
    response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=name)

    file_contents = response['Body'].read()

    pdf_document = fitz.open(stream=file_contents, filetype="pdf")

    pdf_text = ""
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        pdf_text += page.get_text()

    text = "Create quiz"
    
    document_identifier = {'pdf_name': name} 
    field_name = 'user_text'

    result = collection.find_one({**document_identifier, field_name: {"$exists": True}})

    if result:
        text = vector_data['user_text']

    completion = aiclient.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"Give me a name of this document with quotes without your comments based on text of this document: {pdf_text}"
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
                "content": f"Write me one json without any comment from you for google forms api updating google form quiz without adding name and title by adding ONLY MCQ test questions based on this text: {pdf_text}"
            },
            {
                "role": "user",
                "content": f"{text}"
            }
        ]
    )

    return {"filename": vector_data['pdf_name'],
            "pdf_content": pdf_text,
            "form_name": completion.choices[0].message.content,
            "questions": response.choices[0].message.content,
            "google_api_key": os.getenv('GOOGLE_API_KEY')
            }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
