from github import Github, InputGitTreeElement

def upload_files_to_github(token, repo_name, branch, files_dict):
    """추출된 파일 딕셔너리를 GitHub에 Batch Commit 합니다."""
    logs = []
    try:
        logs.append("▶ GitHub 업로드를 시작합니다...")
        g = Github(token)
        repo = g.get_repo(repo_name)
        
        # ... (기존 Git Tree 커밋 로직 동일하게 배치) ...
        
        logs.append(f"✅ GitHub '{repo_name}' 저장소에 성공적으로 커밋되었습니다!")
        return True, logs
    except Exception as e:
        logs.append(f"❌ GitHub 업로드 오류: {str(e)}")
        return False, logs