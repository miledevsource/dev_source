from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from config import Config  # 전역 설정 파일 임포트
from routes.config_api import config_bp  # 분리한 라우터 가져오기
from routes.extractor_api import extractor_bp  # 🚀 추가!
from routes.env_api import env_bp
from routes.provider_api import provider_bp
import os
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# ==========================================
# 🚀 [추가] 오류 및 시스템 로그 파일 기록 설정
# ==========================================
# 1. 실행 위치에 'log' 폴더가 없으면 자동 생성
log_dir = os.path.join(os.getcwd(), 'log')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 2. 로그 파일 설정 (error.log에 저장, 최대 5MB, 백업 5개 유지, 한글 깨짐 방지 utf-8)
log_file = os.path.join(log_dir, 'error.log')
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')

# 3. 로그 출력 포맷 지정 (시간 | 로그레벨 | 발생모듈 | 에러메시지)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO) # INFO, WARNING, ERROR 등 모두 기록

# 4. Flask 앱 로거와 Werkzeug(HTTP 통신) 로거에 핸들러 부착
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
logging.getLogger('werkzeug').addHandler(file_handler)
# ==========================================

app.json.ensure_ascii = False

# 세션을 사용하기 위해 반드시 시크릿 키가 필요합니다. 
# (실제 운영 환경에서는 복잡한 문자열이나 환경변수를 사용하세요)
app.secret_key = 'eicu_super_secret_key'

app.register_blueprint(config_bp)
app.register_blueprint(extractor_bp)  # 🚀 추가! 이제 /api/extract/... 주소가 활성화됩니다.
app.register_blueprint(env_bp)  # 🚀 추가!
app.register_blueprint(provider_bp)

# =======================================
# 1. 로그인/로그아웃 라우팅
# =======================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    # 이미 로그인된 상태라면 바로 대시보드로 이동
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        user_id = request.form.get('id')
        user_pw = request.form.get('pw')

        # [임시 계정 검증] 실무에서는 DB 조회(SELECT)를 통해 비밀번호(해시)를 비교해야 합니다.
        if user_id == 'admin' and user_pw == 'admin123':
            session['logged_in'] = True  # 세션에 로그인 상태 저장
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
        else:
            error = "아이디 또는 비밀번호가 일치하지 않습니다."
            
    # GET 요청이거나 로그인 실패 시 login.html 렌더링
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    # 세션 정보 초기화
    session.clear()
    return redirect(url_for('login'))

# =======================================
# 2. 메인 대시보드 및 메뉴 라우팅
# =======================================
# 기본 주소('/') 접속 시 로그인이 안 되어 있으면 로그인 페이지로 튕겨냅니다.
@app.route('/')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user_id=session.get('user_id'))

@app.route('/xml-config')
def xml_config():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    api_base_url = f"http://10.1.0.135:{Config.PORT}/api/config"

    return render_template('XmlConfigSetting.html', api_base_url=api_base_url)

# dll 추출 화면
@app.route('/ddl-extract')
def ddl_extract():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('ddl.html')

# env.config 설정 화면 
@app.route('/env-config')
def env_config():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('env.html')

#  REST API 설정 화면 
@app.route('/Provider-Api')
def Provider_Api():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('ProviderApi.html')

#  환경설정 화면 
@app.route('/info-setting')
def info_Setting():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('infoSetting.html')


if __name__ == '__main__':
    # print("==============CONFIG API 서버 작동중=============")

    # # 1. 서버 시작 전 DB 연결 테스트
    # print(f"[*] DB 서버({DATABASE_URL.split('@')[-1].split('/')[0]}) 연결을 시도합니다...")
    # try:
    #     # 연결 시도
    #     test_conn = psycopg2.connect(DATABASE_URL)
    #     # 성공 시 즉시 닫기
    #     test_conn.close()
    #     print("[+] ✅ DB 연결 성공! 정상적으로 통신이 가능합니다.")
    # except Exception as e:
    #     print("[-] ❌ DB 연결 실패! DB 서버가 켜져 있는지, IP/포트/계정 정보가 맞는지 확인하세요.")
    #     print(f"    상세 오류: {e}")
        

    # print("======================================================")
    
    # 2. Flask 웹 서버 실행
    print("[*] 웹 서버를 시작합니다. (포트: 8888)")

    app.run(debug=True, port=8888, host='0.0.0.0') # 외부 접속을 위해 host='0.0.0.0' 추가