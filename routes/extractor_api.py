# 경로: project_root/routes/extractor_api.py
from flask import Blueprint, request, jsonify, send_file
import os
import traceback  # 🚀 상단에 임포트 추가!
import logging    # 🚀 상단에 임포트 추가!
from services.db_service import extract_oracle_ddl, sync_local_to_github

extractor_bp = Blueprint('extractor_api', __name__, url_prefix='/api/extract')

# 1. DDL 추출 라우터 (DB 조회)
@extractor_bp.route('/ddl', methods=['POST'])
def run_ddl_extraction():
    data = request.get_json()
    
    db_user = data.get('user')
    db_password = data.get('password')
    db_dsn = data.get('dsn')
    target_schema = data.get('target')
    output_dir = data.get('output_dir')
    object_types = data.get('object_types', [])
    save_mode = data.get('save_mode', 'server')
    
    if not all([db_user, db_password, db_dsn, target_schema]):
        return jsonify({"error": "필수 파라미터가 누락되었습니다."}), 400

    # DDL 추출 실행 (GitHub 파라미터 제거됨)
    success, log_result, zip_filename = extract_oracle_ddl(
        db_user, db_password, db_dsn, target_schema, output_dir, object_types, save_mode
    )
    
    if success:
        response_data = {"log": log_result}
        if save_mode == 'local' and zip_filename:
            response_data["download_url"] = f"/api/extract/download/{zip_filename}"
        return jsonify(response_data), 200
    else:
        return jsonify({"log": log_result, "error": "추출 중 오류가 발생했습니다."}), 500

# 🚀 2. GitHub 동기화 전용 라우터 (DB 접속 없음)
@extractor_bp.route('/github_sync', methods=['POST'])
def run_github_sync():
    try:
        data = request.get_json()
        output_dir = data.get('output_dir')
        target_schema = data.get('target', 'OracleDB')
        github_config = data.get('github_config')

        if not output_dir or not github_config:
            return jsonify({"error": "폴더 경로와 GitHub 설정이 필요합니다."}), 400

        # 로컬 폴더 -> GitHub 스캔 및 푸시
        success, log_result = sync_local_to_github(output_dir, target_schema, github_config)

        if success:
            return jsonify({"log": log_result}), 200
        else:
            # 🌟 CMD(터미널) 창에 실패 원인을 아주 크게 출력합니다!
            print("\n" + "="*50)
            print("🚨 [GitHub 동기화 실패 상세 원인] 🚨")
            print(log_result)
            print("="*50 + "\n")
            
            return jsonify({
                "log": log_result, 
                "error": f"GitHub 통신 실패 상세사유:\n{log_result}"
            }), 500

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        # 🌟 파이썬 치명적 에러 발생 시에도 콘솔에 크게 출력합니다.
        print("\n" + "="*50)
        print("🚨 [서버 치명적 오류] 🚨")
        print(error_details)
        print("="*50 + "\n")
        
        return jsonify({
            "log": "서버에서 파이썬 오류가 발생했습니다.", 
            "error": f"상세 원인:\n{error_details}"
        }), 500

# 3. 로컬 다운로드 라우터
@extractor_bp.route('/download/<filename>', methods=['GET'])
def download_zip(filename):
    file_path = os.path.join(os.getcwd(), 'temp_downloads', filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=filename)
    else:
        return "파일을 찾을 수 없습니다.", 404