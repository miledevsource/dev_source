# 경로: project_root/services/db_connect.py
import psycopg2
from config import Config

def get_db_connection():
    """Config에서 DB 주소를 가져와 PostgreSQL에 연결합니다."""
    # Config.POSTGRES_URL은 .env에 설정된 주소라고 가정합니다.
    return psycopg2.connect(Config.POSTGRES_URL) 

def get_config_from_db(hospital_code):
    """(GET) 병원 코드로 최신 설정 조회"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT config_version, config_xml FROM icu.agent_config_master WHERE hospital_code = %s", (hospital_code,))
        row = cursor.fetchone()
        
        if not row:
            return False, {"detail": "Config not found"}, 404
            
        db_version, config_xml = row
        return True, {"version": db_version, "xml_data": config_xml}, 200
        
    except Exception as e:
        return False, {"detail": str(e)}, 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def save_config_to_db(hospital_code, new_xml):
    """(POST) PostgreSQL UPSERT를 이용한 설정 저장"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        upsert_query = """
            INSERT INTO icu.agent_config_master (hospital_code, config_xml, config_version, updated_at)
            VALUES (%s, %s, 1, CURRENT_TIMESTAMP)
            ON CONFLICT (hospital_code) 
            DO UPDATE SET 
                config_xml = EXCLUDED.config_xml,
                config_version = agent_config_master.config_version + 1,
                updated_at = CURRENT_TIMESTAMP
            RETURNING config_version;
        """
        cursor.execute(upsert_query, (hospital_code, new_xml))
        new_version = cursor.fetchone()[0]
        conn.commit()
        
        return True, {"message": "Successfully updated", "new_version": new_version}, 200
        
    except Exception as e:
        if conn: conn.rollback()
        return False, {"detail": str(e)}, 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()