"""필수 키 존재 여부만 확인(값·길이 비출력). 사용: python scripts/check_env.py"""
from precedent_summarizer.config import ENV_PATH, secret_status

print(f".env 파일: {'있음' if ENV_PATH.exists() else '없음'}")
ok = True
for name, present in secret_status().items():
    print(f"  {name}: {'설정됨' if present else '없음'}")
    ok &= present
raise SystemExit(0 if ok else 1)
