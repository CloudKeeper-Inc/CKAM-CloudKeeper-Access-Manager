import os
from dotenv import load_dotenv
load_dotenv(dotenv_path='.env.backend')
class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
    AWS_REGION = os.environ.get('AWS_REGION')
    REQUEST_TABLE_NAME = os.environ.get('REQUEST_TABLE_NAME')
    APPROVER_TABLE_NAME = os.environ.get('APPROVER_TABLE_NAME')
    ACCESS_MANAGER_METADATA_TABLE = os.environ.get('ACCESS_MANAGER_METADATA_TABLE')
    # Crucial for local development
    LOCALSTACK_ENDPOINT = os.environ.get('LOCALSTACK_ENDPOINT')