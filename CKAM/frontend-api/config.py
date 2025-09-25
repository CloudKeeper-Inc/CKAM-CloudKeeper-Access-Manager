import os
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env.frontend')

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
    API_BASE_URL = os.environ.get('API_BASE_URL')