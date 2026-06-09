# 경로: project_root/services/provider_service.py
import psycopg2
import oracledb
import json
import os
from config import Config

def get_pg_conn():
    return psycopg2.connect(Config.POSTGRES_URL)

def get_ora_conn():
    return oracledb.connect(
        user=os.environ.get('ORACLE_USER'),
        password=os.environ.get('ORACLE_PASSWORD'),
        dsn=os.environ.get('ORACLE_DSN')
    )

# 1. API 목록 조회
def get_api_list():
    conn = None
    try:
        conn = get_pg_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT api_id, api_name, target_db, exec_type FROM icu.api_provider_master ORDER BY created_at DESC")
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return True, result
    except Exception as e:
        return False, str(e)
    finally:
        if conn: conn.close()

# 2. 특정 API 상세 조회
def get_api_detail(api_id):
    conn = None
    try:
        conn = get_pg_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT api_id, api_name, target_db, exec_type, exec_text, req_params FROM icu.api_provider_master WHERE api_id = %s", (api_id,))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return True, dict(zip(columns, row))
        return False, "API 정보를 찾을 수 없습니다."
    except Exception as e:
        return False, str(e)
    finally:
        if conn: conn.close()

# 3. API 저장 (UPSERT)
def save_api_config(api_id, api_name, target_db, exec_type, exec_text, req_params):
    conn = None
    try:
        conn = get_pg_conn()
        cursor = conn.cursor()
        query = """
            INSERT INTO icu.api_provider_master (api_id, api_name, target_db, exec_type, exec_text, req_params)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (api_id) DO UPDATE SET
                api_name = EXCLUDED.api_name,
                target_db = EXCLUDED.target_db,
                exec_type = EXCLUDED.exec_type,
                exec_text = EXCLUDED.exec_text,
                req_params = EXCLUDED.req_params;
        """
        cursor.execute(query, (api_id, api_name, target_db, exec_type, exec_text, json.dumps(req_params)))
        conn.commit()
        return True, "API가 성공적으로 등록/수정 되었습니다."
    except Exception as e:
        if conn: conn.rollback()
        return False, f"저장 실패: {str(e)}"
    finally:
        if conn: conn.close()

# 4. API 삭제
def delete_api_config(api_id):
    conn = None
    try:
        conn = get_pg_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM icu.api_provider_master WHERE api_id = %s", (api_id,))
        conn.commit()
        return True, "API가 성공적으로 삭제되었습니다."
    except Exception as e:
        if conn: conn.rollback()
        return False, f"삭제 실패: {str(e)}"
    finally:
        if conn: conn.close()

# 5. 동적 API 실행 (기존 코드 유지)
def execute_dynamic_api(api_id, client_params):
    pg_conn = None
    try:
        pg_conn = get_pg_conn()
        cursor = pg_conn.cursor()
        
        cursor.execute("SELECT target_db, exec_type, exec_text, req_params FROM icu.api_provider_master WHERE api_id = %s", (api_id,))
        row = cursor.fetchone()
        
        if not row: return False, "등록되지 않은 API ID 입니다.", 404
        target_db, exec_type, exec_text, req_params = row
        
        result_data = []
        # if target_db == 'ORACLE':
        #     ora_conn = get_ora_conn()
        #     ora_cursor = ora_conn.cursor()
        #     if exec_type == 'QUERY':
        #         ora_cursor.execute(exec_text, **client_params)
        #         columns = [col[0] for col in ora_cursor.description]
        #         result_data = [dict(zip(columns, row)) for row in ora_cursor.fetchall()]
        #     ora_conn.close()
        
        if target_db == 'ORACLE':
            ora_conn = get_ora_conn()
            ora_cursor = ora_conn.cursor()
            
            try:
                # 🚀 1. 일반 쿼리 (SELECT) 인 경우
                if exec_type == 'QUERY':
                    ora_cursor.execute(exec_text, client_params)
                    if ora_cursor.description: 
                        columns = [col[0] for col in ora_cursor.description]
                        result_data = [dict(zip(columns, row)) for row in ora_cursor.fetchall()]
                        
                # 🚀 2. 프로시저 / 패키지 (PL/SQL) 인 경우
                else:
                    ora_cursor.execute(exec_text, client_params)
                    implicit_results = ora_cursor.getimplicitresults()
                    
                    if implicit_results:
                        result_cursor = implicit_results[0]
                        columns = [col[0] for col in result_cursor.description]
                        result_data = [dict(zip(columns, row)) for row in result_cursor.fetchall()]
            finally:
                ora_conn.close()

            
        elif target_db == 'POSTGRES':
            pg_target_conn = get_pg_conn()
            pg_target_cursor = pg_target_conn.cursor()
            if exec_type == 'QUERY':
                pg_target_cursor.execute(exec_text, client_params)
                columns = [desc[0] for desc in pg_target_cursor.description]
                result_data = [dict(zip(columns, row)) for row in pg_target_cursor.fetchall()]
            pg_target_conn.close()

        return True, result_data, 200

    except Exception as e:
        return False, f"API 실행 중 오류 발생: {str(e)}", 500
    finally:
        if pg_conn: pg_conn.close()