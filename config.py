# config.py
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    """기본 설정 (전역 변수처럼 사용)"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True') == 'True'
    PORT = int(os.environ.get('PORT', 8888))

    # Oracle DB 설정
    DB_USER = os.environ.get('ORACLE_USER')
    DB_PASSWORD = os.environ.get('ORACLE_PASSWORD')
    DB_DSN = os.environ.get('ORACLE_DSN')

    # PostgreSQL 설정
    POSTGRES_URL = os.environ.get('POSTGRES_URL')