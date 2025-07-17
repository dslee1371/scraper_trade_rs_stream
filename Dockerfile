FROM python:3.9-slim

# 시스템 패키지 업데이트 및 필수 설치
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉터리 설정
WORKDIR /app

# 필요 파일 복사
COPY . /app

# 파이썬 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 스트림릿 기본 포트 오픈
EXPOSE 8501

# 웹앱 실행
CMD ["streamlit", "run", "scraper_trade_rs_stream.py", "--server.port=8501", "--server.address=0.0.0.0"]
