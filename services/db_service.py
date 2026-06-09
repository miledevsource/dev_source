# 경로: project_root/services/db_service.py
import oracledb
import os
import zipfile
import time
import shutil
import requests

FOLDER_MAPPING = {
    'TABLE': 'Tables',
    'FUNCTION': 'Functions', 
    'PROCEDURE': 'Procedures',
    'PACKAGE': 'Packages', 
    'PACKAGE BODY': 'Packages', 
    'VIEW': 'Views'
}

def push_to_github(config, files_dict, commit_message="Update DDLs"):
    token = config.get('token')
    repo = config.get('repo')
    branch = config.get('branch', 'main')
    target_path = config.get('path', '').strip('/')
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    base_url = f"https://api.github.com/repos/{repo}"

    try:
        # 1. 브랜치 조회 (🌟 GET 요청은 'ref' 단수형 사용)
        get_ref_url = f"{base_url}/git/ref/heads/{branch}"
        res = requests.get(get_ref_url, headers=headers)
        if res.status_code != 200: return False, f"브랜치 조회 실패: {res.text}"
        last_commit_sha = res.json()['object']['sha']

        # 2. Tree 정보 가져오기
        res = requests.get(f"{base_url}/git/commits/{last_commit_sha}", headers=headers)
        base_tree_sha = res.json()['tree']['sha']

        # 3. 새 Tree 만들기 (업로드할 파일들)
        tree_data = []
        for filepath, content in files_dict.items():
            full_path = f"{target_path}/{filepath}".strip('/') if target_path else filepath
            tree_data.append({
                "path": full_path,
                "mode": "100644",
                "type": "blob",
                "content": content
            })

        res = requests.post(f"{base_url}/git/trees", json={"base_tree": base_tree_sha, "tree": tree_data}, headers=headers)
        if res.status_code != 201: return False, f"Tree 생성 실패: {res.text}"
        new_tree_sha = res.json()['sha']

        # 4. 새 Commit 만들기
        commit_payload = {"message": commit_message, "tree": new_tree_sha, "parents": [last_commit_sha]}
        res = requests.post(f"{base_url}/git/commits", json=commit_payload, headers=headers)
        if res.status_code != 201: return False, f"Commit 생성 실패: {res.text}"
        new_commit_sha = res.json()['sha']

        # 5. 브랜치 업데이트 (🌟 PATCH 요청은 'refs' 복수형 사용!)
        update_ref_url = f"{base_url}/git/refs/heads/{branch}"
        res = requests.patch(update_ref_url, json={"sha": new_commit_sha}, headers=headers)
        if res.status_code != 200: return False, f"Ref 업데이트 실패: {res.text}"

        return True, "성공"
    except Exception as e:
        return False, str(e)


# 🚀 1. DB에서 DDL을 추출하는 함수 (기존)
def extract_oracle_ddl(user, password, dsn, target_schema, output_dir, object_types, save_mode='server'):
    logs = []
    zip_filename = None
    
    def log_message(msg): logs.append(msg)

    target_schema = target_schema.upper()
    actual_types = []
    for t in object_types:
        actual_types.append(t.upper())
        if t.upper() == 'PACKAGE':
            actual_types.append('PACKAGE BODY')

    base_dir = os.getcwd()
    temp_downloads_dir = os.path.join(base_dir, 'temp_downloads')
    
    if save_mode == 'local':
        os.makedirs(temp_downloads_dir, exist_ok=True)
        output_dir = os.path.join(temp_downloads_dir, f"temp_{target_schema}_{int(time.time())}")

    try:
        log_message("▶ Oracle DB에 연결 중...")
        connection = oracledb.connect(user=user, password=password, dsn=dsn)
        cursor = connection.cursor()
        log_message("▶ 연결 성공!\n")

        cursor.execute("BEGIN DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SQLTERMINATOR', true); DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PRETTY', true); DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SEGMENT_ATTRIBUTES', false); END;")

        bind_names = [f":obj{i}" for i in range(len(actual_types))]
        in_clause = ", ".join(bind_names)
        sql_get_objects = f"SELECT OBJECT_NAME, OBJECT_TYPE FROM ALL_OBJECTS WHERE OWNER = :owner AND OBJECT_TYPE IN ({in_clause}) ORDER BY OBJECT_TYPE, OBJECT_NAME"
        
        bind_vars = {"owner": target_schema}
        for i, t in enumerate(actual_types):
            bind_vars[f"obj{i}"] = t

        cursor.execute(sql_get_objects, **bind_vars)
        objects = cursor.fetchall()

        if not objects:
            log_message(f"[{target_schema}] 계정에 추출할 객체가 없습니다.")
            return True, "\n".join(logs), None

        log_message(f"총 {len(objects)}개의 객체를 추출합니다...\n")

        for obj_name, obj_type in objects:
            sub_folder_name = FOLDER_MAPPING.get(obj_type, obj_type)
            meta_type = obj_type.replace(' ', '_')
            obj_name_clean = obj_name.strip()
            ddl_text = ""

            try:
                cursor.execute(f"SELECT DBMS_METADATA.GET_DDL('{meta_type}', '{obj_name_clean}', '{target_schema}') FROM DUAL")
                ddl_clob = cursor.fetchone()[0]
                ddl_text = ddl_clob.read().rstrip(' \t\n\r').rstrip('/') if ddl_clob else ""
            except oracledb.DatabaseError:
                pass

            if ddl_text:
                filename = f"{obj_name_clean}_BODY.sql" if obj_type == 'PACKAGE BODY' else f"{obj_name_clean}.sql"
                target_folder = os.path.join(output_dir, sub_folder_name)
                os.makedirs(target_folder, exist_ok=True)
                with open(os.path.join(target_folder, filename), 'w', encoding='utf-8') as f:
                    f.write(ddl_text)
                log_message(f" ✅ [추출 완료] {sub_folder_name} / {filename}")

        if save_mode == 'local':
            log_message("\n▶ 파일 압축 진행 중...")
            zip_filename = f"DDL_EXPORT_{target_schema}_{int(time.time())}.zip"
            with zipfile.ZipFile(os.path.join(temp_downloads_dir, zip_filename), 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), output_dir))
            shutil.rmtree(output_dir, ignore_errors=True)
            log_message("▶ 다운로드를 준비합니다.")
        else:
            log_message(f"\n▶ 서버 폴더({output_dir})에 저장이 완료되었습니다!")

        return True, "\n".join(logs), zip_filename

    except Exception as e:
        log_message(f"\n[오류 발생] {e}")
        return False, "\n".join(logs), None
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()


# 🚀 2. DB 연결 없이 "서버 폴더 파일"만 읽어서 GitHub에 올리는 전용 함수 (신규)
def sync_local_to_github(output_dir, target_schema, github_config):
    logs = []
    def log_message(msg): logs.append(msg)

    if not os.path.exists(output_dir):
        return False, f"❌ [{output_dir}] 폴더를 찾을 수 없습니다.\n먼저 DDL 추출 작업을 통해 파일을 서버에 저장해주세요."

    log_message(f"▶ [{output_dir}] 폴더의 파일을 스캔하여 GitHub 동기화를 시작합니다...")
    github_files = {}
    
    # 폴더 내의 모든 .sql 파일을 읽어옴
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('.sql'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, output_dir)
                gh_path = rel_path.replace('\\', '/') # 윈도우 경로를 리눅스식(GitHub)으로 변경
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    github_files[gh_path] = f.read()

    if not github_files:
        return False, f"❌ [{output_dir}] 폴더 안에 업로드할 .sql 파일이 없습니다."

    schema_name = target_schema if target_schema else "Database"
    commit_msg = f"Auto-Sync DDLs for {schema_name} ({len(github_files)} files)"
    
    # GitHub Push 실행
    gh_success, gh_msg = push_to_github(github_config, github_files, commit_msg)
    
    if gh_success:
        log_message(f"🐙 GitHub에 성공적으로 커밋되었습니다! (파일 {len(github_files)}개)")
        return True, "\n".join(logs)
    else:
        log_message(f"❌ GitHub 동기화 실패: {gh_msg}")
        return False, "\n".join(logs)