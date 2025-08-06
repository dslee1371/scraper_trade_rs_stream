# 네이버 부동산 데이터 스크래퍼 with Prometheus 모니터링

네이버 부동산에서 매물 정보를 수집하고 분석하는 Streamlit 애플리케이션에 Prometheus 모니터링을 추가한 프로젝트입니다.

## 🚀 주요 기능

### 데이터 수집
- 네이버 부동산 API를 통한 매물 정보 수집
- 다중 페이지 데이터 자동 수집
- 실시간 진행상황 표시
- CSV 파일 다운로드 기능

### 데이터 분석 및 시각화
- 가격 통계 분석 (평균, 최고, 최저)
- 거래 유형별/면적별 분석
- 층별 가격 분포 시각화
- 지도 기반 매물 위치 표시

### Prometheus 모니터링
- **API 요청 모니터링**: 성공률, 응답시간, 에러율
- **데이터 처리 모니터링**: 처리 시간, 데이터 건수
- **사용자 행동 분석**: 페이지 뷰, 다운로드, 액션 추적
- **실시간 알림**: 에러 발생, 성능 이슈 감지
- **가격 통계 추적**: 단지별 가격 변동 모니터링

## 📊 모니터링 메트릭

### Counters
- `naver_scraper_api_requests_total`: API 요청 횟수
- `naver_scraper_data_fetched_total`: 수집된 데이터 건수
- `naver_scraper_errors_total`: 에러 발생 횟수
- `naver_scraper_user_actions_total`: 사용자 액션 횟수

### Histograms
- `naver_scraper_request_duration_seconds`: API 요청 응답시간
- `naver_scraper_data_processing_duration_seconds`: 데이터 처리 시간

### Gauges
- `naver_scraper_active_users`: 현재 활성 사용자 수
- `naver_scraper_price_mean_billion`: 평균 가격
- `naver_scraper_current_data_size`: 현재 데이터 크기
- `naver_scraper_last_successful_fetch_timestamp`: 마지막 성공적인 수집 시간

## 🛠 설치 및 실행

### 필수 요구사항
- Docker & Docker Compose
- Python 3.9+
- 8501, 8000, 9090, 3000, 9093 포트 사용 가능

### 1. 프로젝트 클론
```bash
git clone <repository-url>
cd naver-real-estate-scraper
```

### 2. 자동 설정 및 실행
```bash
chmod +x setup.sh
./setup.sh
```

### 3. 수동 설정 (선택사항)
```bash
# Python 패키지 설치
pip install -r requirements.txt

# Docker 컨테이너 실행
docker-compose up -d

# Streamlit 앱 실행 (로컬)
streamlit run scraper_trade_rs_stream.py --server.port=8501
```

### 4. 모니터링 테스트
```bash
python test_monitoring.py
```

## 🌐 접속 정보

| 서비스 | URL | 설명 |
|--------|-----|------|
| Streamlit 앱 | http://localhost:8501 | 메인 애플리케이션 |
| Prometheus | http://localhost:9090 | 메트릭 수집 서버 |
| Grafana | http://localhost:3000 | 대시보드 (admin/admin123) |
| AlertManager | http://localhost:9093 | 알림 관리 |
| 메트릭 엔드포인트 | http://localhost:8000/metrics | 원시 메트릭 데이터 |

## 📁 프로젝트 구조

```
.
├── scraper_trade_rs_stream.py    # 메인 애플리케이션 (Prometheus 모니터링 포함)
├── requirements.txt              # Python 의존성
├── Dockerfile                   # 컨테이너 이미지 빌드
├── docker-compose.yml           # 다중 서비스 구성
├── prometheus.yml               # Prometheus 설정
├── alert_rules.yml              # 알림 규칙
├── alertmanager.yml             # 알림 관리자 설정
├── grafana-dashboard.json       # Grafana 대시보드
├── test_monitoring.py           # 모니터링 테스트
├── setup.sh                     # 자동 설정 스크립트
└── grafana/
    ├── provisioning/
    │   ├── datasources/         # 데이터소스 설정
    │   └── dashboards/          # 대시보드 프로비저닝
    └── dashboards/              # 대시보드 파일
```

## 🔧 사용법

### 1. 데이터 수집
1. 브라우저에서 http://localhost:8501 접속
2. 사이드바에서 단지번호 입력 (예: 131345)
3. 최대 페이지 수 설정
4. "데이터 가져오기" 버튼 클릭

### 2. 모니터링 확인
1. **Grafana**: http://localhost:3000 (admin/admin123)
   - 사전 구성된 대시보드로 실시간 모니터링
   - 가격 통계, API 성능, 에러율 등 확인
   
2. **Prometheus**: http://localhost:9090
   - 원시 메트릭 데이터 쿼리
   - 알림 규칙 상태 확인

### 3. 알림 설정
AlertManager를 통해 다음 상황에서 알림 발생:
- API 요청 실패율 증가
- 데이터 처리 시간 초과
- 장시간 데이터 수집 없음
- 서비스 다운

## 📈 Grafana 대시보드

### 주요 패널
1. **API 요청 성공률**: 실시간 성공률 모니터링
2. **현재 활성 사용자**: 동시 사용자 수
3. **응답 시간 분포**: 50th, 95th, 99th percentile
4. **단지별 평균 가격**: 가격 변동 추이
5. **사용자 행동 분석**: 페이지 뷰, 다운로드 등
6. **에러 유형별 분석**: 에러 패턴 파악

### 권장 Grafana 쿼리
```promql
# API 성공률
rate(naver_scraper_api_requests_total{status="success"}[5m]) / 
rate(naver_scraper_api_requests_total[5m]) * 100

# 95th percentile 응답시간
histogram_quantile(0.95, rate(naver_scraper_request_duration_seconds_bucket[5m]))

# 시간당 에러율
rate(naver_scraper_errors_total[1h])
```

## 🚨 알림 규칙

### 주요 알림
- **HighErrorRate**: 에러율 > 10%
- **APIRequestFailure**: API 실패율 > 5%
- **DataProcessingTimeout**: 처리시간 > 10초
- **NoDataFetchedRecently**: 1시간 이상 수집 없음
- **ServiceDown**: 서비스 다운

### 알림 채널 설정
`alertmanager.yml`에서 다음 채널 설정 가능:
- 이메일 알림
- Slack 알림
- 웹훅 알림

## 🔍 문제해결

### 일반적인 문제
1. **포트 충돌**: 기본 포트들이 사용 중인 경우
   ```bash
   # 사용 중인 포트 확인
   netstat -tulpn | grep :8501
   netstat -tulpn | grep :9090
   ```

2. **Docker 권한 문제**:
   ```bash
   sudo usermod -aG docker $USER
   # 로그아웃 후 재로그인
   ```

3. **메트릭이 표시되지 않음**:
   ```bash
   # 서비스 상태 확인
   docker-compose ps
   
   # 로그 확인
   docker-compose logs naver-scraper
   ```

### 로그 확인
```bash
# 전체 서비스 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f naver-scraper
docker-compose logs -f prometheus
docker-compose logs -f grafana
```

### 서비스 재시작
```bash
# 전체 재시작
docker-compose down && docker-compose up -d

# 특정 서비스만 재시작
docker-compose restart naver-scraper
```

## 🔒 보안 고려사항

1. **Grafana 비밀번호**: 기본 비밀번호를 변경하세요
2. **네트워크 접근**: 필요시 방화벽 규칙 설정
3. **API 키**: 민감한 정보는 환경변수로 관리
4. **HTTPS**: 프로덕션 환경에서는 HTTPS 설정 권장

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 📞 지원

문제가 발생하거나 질문이 있으시면 이슈를 생성해주세요.
