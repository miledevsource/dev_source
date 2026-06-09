from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from functools import wraps
from datetime import datetime
import psycopg2
import json
from flask_cors import CORS  # <--- 1. CORS 라이브러리 추가
import oracledb
import os

app = Flask(__name__)
CORS(app)  # <--- 2. 모든 도메인에서 오는 요청을 허용 (CORS 적용)

# ==========================================
# [필수 추가] 세션을 사용하기 위한 암호화 키 (아무 문자열이나 길게 설정)
# ==========================================
app.secret_key = "vital-secure-secret-key-12345!"

DATABASE_URL = "postgresql://postgres:!Q%40W%23E$R@192.168.228.128:5432/icu"

# 폴더 매핑
FOLDER_MAPPING = {
    'FUNCTION': 'Functions',
    'PROCEDURE': 'Procedures',
    'PACKAGE': 'Packages',
    'PACKAGE BODY': 'Packages',
    'VIEW': 'Views'
}

# ==========================================
# [핵심 추가] 로그인 여부를 검사하는 수문장 (데코레이터)
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 세션에 'logged_in' 값이 없으면 로그인 페이지로 강제 이동!
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# [추가] 메인 메뉴 라우트
# ==========================================
@app.route('/main_menu')
@login_required  # <--- 로그인 안 하면 못 들어오게 막음
def main_menu():
    # templates 폴더의 main_menu.html을 띄워줌
    return render_template('main_menu.html')

# ==========================================
# [수정] 로그인 / 로그아웃 라우트
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user_id = request.form.get('id')
        user_pw = request.form.get('pw')
        
        # [변경] ID: admin / PW: admin123 일 때만 통과
        if user_id == 'admin' and user_pw == 'admin123':
            session['logged_in'] = True     
            session['user_id'] = user_id    
            
            # [변경] 로그인 성공 시 'main_menu' 라우트로 강제 이동
            return redirect(url_for('main_menu')) 
        else:
            error = "아이디 또는 비밀번호가 일치하지 않습니다."
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear() # 세션 파기 (로그아웃)
    return redirect(url_for('login'))

# ==========================================
# 3. API 라우트 정의
# ==========================================
@app.route('/')
def home():
    user = session.get('user_id', 'Unknown')
    return f"""
        <h1>Config.xml API 작동중... (접속자: {user})</h1>
        <br>
        <a href='/setting'>👉 설정 화면(XmlConfigSetting.html)으로 이동</a>
        <br><br>
        <a href='/logout'>🚪 로그아웃</a>
    """

# ==========================================
# HTML 웹 페이지 연결 라우트
# ==========================================
@app.route('/setting')
@login_required  # <--- [적용] 설정 화면도 로그인 안 하면 못 들어감
def xml_config_setting():
    # 프로젝트 폴더 내의 templates/XmlConfigSetting.html 파일을 브라우저에 띄워줍니다.
    return render_template('XmlConfigSetting.html')

# ==========================================
# 1. 에이전트 동기화 API (에이전트 -> 서버) - 버전 비교 제거
# ==========================================
@app.route('/api/config/sync/<hospital_code>', methods=['GET'])
def sync_config(hospital_code):
    # DB에 바로 연결하여 무조건 최신 데이터를 조회합니다.
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT config_version, config_xml FROM icu.agent_config_master WHERE hospital_code = %s", (hospital_code,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"detail": "Config not found"}), 404
            
        db_version, config_xml = row
        
        # 클라이언트의 버전 확인 없이 즉시 최신 XML 원문을 반환합니다.
        return jsonify({
            "version": db_version,
            "xml_data": config_xml
        })
    finally:
        cursor.close()
        conn.close()

# ==========================================
# 2. 관리자 설정 배포 API (WPF 관리자 툴 -> 서버)
# ==========================================
@app.route('/api/config/admin/<hospital_code>', methods=['POST'])
def update_config(hospital_code):
    # 관리자 프로그램이 보낸 JSON 받기 {"xml_data": "<Config>..."}
    data = request.get_json()
    new_xml = data.get('xml_data')
    
    if not new_xml:
        return jsonify({"detail": "xml_data is required"}), 400

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # PostgreSQL의 강력한 UPSERT(Insert or Update) 기능 사용
        # 데이터가 없으면 Insert, 있으면 Update 하고 버전을 1 증가시킴
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
        
        return jsonify({"message": "Successfully updated", "new_version": new_version})
    except Exception as e:
        conn.rollback()
        return jsonify({"detail": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    print("==============CONFIG API 서버 작동중=============")

    # 1. 서버 시작 전 DB 연결 테스트
    print(f"[*] DB 서버({DATABASE_URL.split('@')[-1].split('/')[0]}) 연결을 시도합니다...")
    try:
        # 연결 시도
        test_conn = psycopg2.connect(DATABASE_URL)
        # 성공 시 즉시 닫기
        test_conn.close()
        print("[+] ✅ DB 연결 성공! 정상적으로 통신이 가능합니다.")
    except Exception as e:
        print("[-] ❌ DB 연결 실패! DB 서버가 켜져 있는지, IP/포트/계정 정보가 맞는지 확인하세요.")
        print(f"    상세 오류: {e}")
        
    print("======================================================")
    
    # 2. Flask 웹 서버 실행
    print("[*] 웹 서버를 시작합니다. (포트: 8888)")

    app.run(debug=True, port=8888, host='0.0.0.0') # 외부 접속을 위해 host='0.0.0.0' 추가