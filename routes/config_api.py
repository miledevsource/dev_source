# 경로: project_root/routes/config_api.py
from flask import Blueprint, jsonify, request
from services.db_connect import get_config_from_db, save_config_to_db

# Blueprint 생성 (URL 접두사 /api/config 설정)
config_bp = Blueprint('config_api', __name__, url_prefix='/api/config')

# ==========================================
# 1. 에이전트 동기화 API (에이전트 -> 서버)
# HTML의 loadFromDB() 가 호출하는 곳: GET /api/config/sync/01
# ==========================================
@config_bp.route('/sync/<hospital_code>', methods=['GET'])
def sync_config(hospital_code):
    success, result_data, status_code = get_config_from_db(hospital_code)
    return jsonify(result_data), status_code

# ==========================================
# 2. 관리자 설정 배포 API (WPF 관리자 툴 -> 서버)
# HTML의 sendPostRequest() 가 호출하는 곳: POST /api/config/admin/01
# ==========================================
@config_bp.route('/admin/<hospital_code>', methods=['POST'])
def update_config(hospital_code):
    data = request.get_json()
    new_xml = data.get('xml_data')
    
    if not new_xml:
        return jsonify({"detail": "xml_data is required"}), 400

    success, result_data, status_code = save_config_to_db(hospital_code, new_xml)
    return jsonify(result_data), status_code