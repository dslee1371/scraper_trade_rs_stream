FROM python:3.9-slim

# 시스템 패키지 업데이트 및 필수 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉터리 설정
WORKDIR /app

# 필요 파일 복사
COPY requirements.txt /app/
COPY . /app/

# 파이썬 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 데이터 디렉토리 생성
RUN mkdir -p /app/data

# 스트림릿 기본 포트 + Prometheus 메트릭 포트 오픈
EXPOSE 8501 8000

# 헬스체크 추가 (Streamlit과 Prometheus 메트릭 서버 모두 확인)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health && \
        curl --fail http://localhost:8000/metrics

# 웹앱 실행
CMD ["streamlit", "run", "scraper_trade_rs_stream.py", "--server.port=8501", "--server.address=0.0.0.0"]
