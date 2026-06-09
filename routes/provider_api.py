# 경로: project_root/routes/provider_api.py
import json
from flask import Blueprint, request, jsonify, Response
from services.provider_service import save_api_config, execute_dynamic_api, get_api_list, get_api_detail, delete_api_config

provider_bp = Blueprint('provider_api', __name__)

# [관리자 전용] 목록 조회
@provider_bp.route('/api/provider/list', methods=['GET'])
def fetch_api_list():
    success, result = get_api_list()
    # 🟢 명확하게 성공(200)과 실패(500)를 분리합니다.
    if success:
        return jsonify({"data": result}), 200
    else:
        return jsonify({"error": result}), 500

# [관리자 전용] 상세 조회
@provider_bp.route('/api/provider/detail/<api_id>', methods=['GET'])
def fetch_api_detail(api_id):
    success, result = get_api_detail(api_id)
    # 🟢 명확하게 성공(200)과 실패(500)를 분리합니다.
    if success:
        return jsonify({"data": result}), 200
    else:
        return jsonify({"error": result}), 500

# [관리자 전용] 저장 (Upsert)
@provider_bp.route('/api/provider/save', methods=['POST'])
def save_provider_api():
    data = request.get_json(force=True, silent=True) or {}
    success, msg = save_api_config(
        data.get('api_id'), data.get('api_name'), data.get('target_db'), 
        data.get('exec_type'), data.get('exec_text'), data.get('req_params')
    )
    return jsonify({"message": msg}), (200 if success else 500)

# [관리자 전용] 삭제
@provider_bp.route('/api/provider/delete/<api_id>', methods=['DELETE'])
def delete_provider_api(api_id):
    success, msg = delete_api_config(api_id)
    return jsonify({"message": msg}), (200 if success else 500)

# [외부 연동용]
@provider_bp.route('/api/v1/external/<api_id>', methods=['GET', 'POST'])
def call_external_api(api_id):
    if request.method == 'GET':
        client_params = request.args.to_dict() 
    else:
        client_params = request.get_json(force=True, silent=True) or {}
    
    success, result, status_code = execute_dynamic_api(api_id, client_params)
    
    response_data = {
        "status": "SUCCESS" if success else "ERROR",
        "api_id": api_id,
        "data" if success else "message": result
    }
    
    json_str = json.dumps(response_data, ensure_ascii=False)
    return Response(json_str, content_type='application/json; charset=utf-8'), status_code