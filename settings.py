import os

SQLACHEMY_DATABASE_URI = os.environ.get('SQLACHEMY_DATABASE_URL')
SECRET_KEY = os.environ.get('SECRET_KEY')
SQLACHEMY_TRACK_MODIFICATIONS = False