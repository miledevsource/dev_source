# 경로: project_root/routes/env_api.py
import os
import psycopg2
import oracledb
from flask import Blueprint, request, jsonify
from dotenv import load_dotenv, set_key
from urllib.parse import urlparse, unquote, quote

env_bp = Blueprint('env_api', __name__, url_prefix='/api/env')
ENV_FILE_PATH = '.env'

@env_bp.route('/load', methods=['GET'])
def load_env_data():
    """1. .env 파일에서 PostgreSQL 및 Oracle 정보를 읽어옵니다."""
    load_dotenv(ENV_FILE_PATH, override=True) 
    
    pg_url = os.environ.get('POSTGRES_URL', '')
    pg_data = {"host": "", "port": "5432", "dbname": "", "user": "", "password": ""}
    
    if pg_url:
        parsed = urlparse(pg_url)
        pg_data = {
            "host": parsed.hostname or '',
            "port": parsed.port or 5432,
            "dbname": parsed.path.lstrip('/') or '',
            "user": unquote(parsed.username) if parsed.username else '',
            "password": unquote(parsed.password) if parsed.password else ''
        }
    
    ora_data = {
        "user": os.environ.get('ORACLE_USER', ''),
        "password": os.environ.get('ORACLE_PASSWORD', ''),
        "dsn": os.environ.get('ORACLE_DSN', '')
    }
    
    return jsonify({"postgres": pg_data, "oracle": ora_data}), 200

@env_bp.route('/test/postgres', methods=['POST'])
def test_pg_connection():
    """2. PostgreSQL 연결 테스트"""
    data = request.get_json()
    try:
        conn = psycopg2.connect(
            host=data.get('host'), port=data.get('port'), dbname=data.get('dbname'),
            user=data.get('user'), password=data.get('password'), connect_timeout=3
        )
        conn.close()
        return jsonify({"message": "PostgreSQL DB 연결에 성공했습니다."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@env_bp.route('/test/oracle', methods=['POST'])
def test_ora_connection():
    """3. Oracle 연결 테스트"""
    data = request.get_json()
    try:
        conn = oracledb.connect(
            user=data.get('user'), password=data.get('password'), dsn=data.get('dsn')
        )
        conn.close()
        return jsonify({"message": "Oracle DB 연결에 성공했습니다."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@env_bp.route('/preview', methods=['POST'])
def preview_env_data():
    """4. 화면에서 입력한 데이터로 .env 파일의 미리보기(가상 조립 텍스트)를 생성합니다."""
    data = request.get_json()
    pg_data = data.get('postgres', {})
    ora_data = data.get('oracle', {})
    
    # 조립될 새로운 값들
    new_pg_url = ""
    if pg_data.get('host'):
        encoded_pw = quote(pg_data.get('password', ''))
        new_pg_url = f"postgresql://{pg_data.get('user')}:{encoded_pw}@{pg_data.get('host')}:{pg_data.get('port')}/{pg_data.get('dbname')}"
        
    new_ora_user = ora_data.get('user', '')
    new_ora_pw = ora_data.get('password', '')
    new_ora_dsn = ora_data.get('dsn', '')

    # 기존 .env 파일 읽기
    env_content = ""
    if os.path.exists(ENV_FILE_PATH):
        with open(ENV_FILE_PATH, 'r', encoding='utf-8') as f:
            env_content = f.read()

    lines = env_content.split('\n')
    updated_lines = []
    found_keys = {'POSTGRES_URL': False, 'ORACLE_USER': False, 'ORACLE_PASSWORD': False, 'ORACLE_DSN': False}

    # 기존 파일의 줄들을 하나씩 스캔하면서 값이 있으면 교체 (주석 유지)
    for line in lines:
        if '=' in line and not line.strip().startswith('#'):
            key = line.split('=')[0].strip()
            if key == 'POSTGRES_URL' and new_pg_url:
                updated_lines.append(f"POSTGRES_URL={new_pg_url}")
                found_keys['POSTGRES_URL'] = True
                continue
            elif key == 'ORACLE_USER' and new_ora_user:
                updated_lines.append(f"ORACLE_USER={new_ora_user}")
                found_keys['ORACLE_USER'] = True
                continue
            elif key == 'ORACLE_PASSWORD' and new_ora_pw:
                updated_lines.append(f"ORACLE_PASSWORD={new_ora_pw}")
                found_keys['ORACLE_PASSWORD'] = True
                continue
            elif key == 'ORACLE_DSN' and new_ora_dsn:
                updated_lines.append(f"ORACLE_DSN={new_ora_dsn}")
                found_keys['ORACLE_DSN'] = True
                continue
        updated_lines.append(line)

    # 기존 파일에 없었던 항목이면 맨 아랫줄에 추가
    if new_pg_url and not found_keys['POSTGRES_URL']: updated_lines.append(f"POSTGRES_URL={new_pg_url}")
    if new_ora_user and not found_keys['ORACLE_USER']: updated_lines.append(f"ORACLE_USER={new_ora_user}")
    if new_ora_pw and not found_keys['ORACLE_PASSWORD']: updated_lines.append(f"ORACLE_PASSWORD={new_ora_pw}")
    if new_ora_dsn and not found_keys['ORACLE_DSN']: updated_lines.append(f"ORACLE_DSN={new_ora_dsn}")

    return jsonify({"preview_text": "\n".join(updated_lines)}), 200

@env_bp.route('/save-raw', methods=['POST'])
def save_raw_env():
    """5. 사용자가 최종 확인/수정한 텍스트를 그대로 .env 파일에 덮어씁니다."""
    data = request.get_json()
    raw_text = data.get('raw_text', '')
    
    try:
        with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(raw_text)
        
        # OS 메모리(환경변수)에도 다시 로드
        load_dotenv(ENV_FILE_PATH, override=True)
        return jsonify({"message": ".env 파일이 성공적으로 업데이트되었습니다."}), 200
    except Exception as e:
        return jsonify({"error": f"저장 실패: {str(e)}"}), 500