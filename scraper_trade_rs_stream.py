import streamlit as st
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, start_http_server, CONTENT_TYPE_LATEST
import requests
import json
import csv
import time
import pandas as pd
import base64
from datetime import datetime
import plotly.express as px
import io
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page config
st.set_page_config(
    page_title="네이버 부동산 데이터 스크래퍼",
    page_icon="🏢",
    layout="wide"
)

# Prometheus metrics
registry = CollectorRegistry()

# Counters
api_requests_total = Counter(
    'naver_scraper_api_requests_total',
    'Total number of API requests made',
    ['complex_no', 'status'],
    registry=registry
)

data_fetched_total = Counter(
    'naver_scraper_data_fetched_total',
    'Total number of real estate listings fetched',
    ['complex_no'],
    registry=registry
)

errors_total = Counter(
    'naver_scraper_errors_total',
    'Total number of errors encountered',
    ['error_type', 'complex_no'],
    registry=registry
)

user_actions_total = Counter(
    'naver_scraper_user_actions_total',
    'Total number of user actions',
    ['action_type'],
    registry=registry
)

# Histograms
request_duration_seconds = Histogram(
    'naver_scraper_request_duration_seconds',
    'Time spent on API requests',
    ['complex_no'],
    registry=registry
)

data_processing_duration_seconds = Histogram(
    'naver_scraper_data_processing_duration_seconds',
    'Time spent processing data',
    ['complex_no'],
    registry=registry
)

# Gauges
current_active_users = Gauge(
    'naver_scraper_active_users',
    'Current number of active users',
    registry=registry
)

last_successful_fetch_timestamp = Gauge(
    'naver_scraper_last_successful_fetch_timestamp',
    'Timestamp of last successful data fetch',
    ['complex_no'],
    registry=registry
)

current_data_size = Gauge(
    'naver_scraper_current_data_size',
    'Current size of fetched data',
    ['complex_no'],
    registry=registry
)

# Price statistics gauges
price_statistics = {
    'mean': Gauge('naver_scraper_price_mean_billion', 'Mean price in billions', ['complex_no'], registry=registry),
    'max': Gauge('naver_scraper_price_max_billion', 'Max price in billions', ['complex_no'], registry=registry),
    'min': Gauge('naver_scraper_price_min_billion', 'Min price in billions', ['complex_no'], registry=registry),
    'count': Gauge('naver_scraper_price_count', 'Number of properties with valid prices', ['complex_no'], registry=registry)
}

class PrometheusMetrics:
    def __init__(self):
        self.active_users = 0
        
    def increment_user(self):
        self.active_users += 1
        current_active_users.set(self.active_users)
        
    def decrement_user(self):
        self.active_users = max(0, self.active_users - 1)
        current_active_users.set(self.active_users)

# Global metrics instance
metrics = PrometheusMetrics()

# Start Prometheus server once
if 'prometheus_server_started' not in st.session_state:
    start_http_server(8000, registry=registry)
    st.session_state['prometheus_server_started'] = True
    logger.info("✅ Prometheus HTTP server bound on 0.0.0.0:8000")
else:
    logger.debug("Prometheus HTTP server already running")

def fetch_real_estate_data(complex_no, page=1, max_pages=10):
    """
    Fetch real estate listing data from Naver Land API with Prometheus monitoring
    
    Args:
        complex_no (int): The complex number to fetch data for
        page (int): Starting page number
        max_pages (int): Maximum number of pages to fetch
        
    Returns:
        list: List of real estate listings
    """
    all_articles = []
    complex_str = str(complex_no)
    
    # Track user action
    user_actions_total.labels(action_type='data_fetch').inc()
    metrics.increment_user()
    
    try:
        # Status placeholder for progress updates
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        # Set up the cookies and headers for the request
        cookies = {
            'NAC': 't9neDIhO7XOeC',
            'NACT': '1',
            'NNB': 'PABUYQL3IUEGQ',
            'SRT30': '1745372539',
            'SRT5': '1745372539',
            'page_uid': 'jsmaYlqpsECssZM5/xhssssssCG-013955',
            '_naver_usersession_': '9vysnRea1HFqlM9WDkofSQ==',
            'nhn.realestate.article.rlet_type_cd': 'A01',
            'nhn.realestate.article.trade_type_cd': '""',
            'nhn.realestate.article.ipaddress_city': '4100000000',
            '_fwb': '170rFhWLiFMt8pEQwrRRiAc.1745372608079',
            'landHomeFlashUseYn': 'Y',
            'realestate.beta.lastclick.cortar': '1100000000',
            'REALESTATE': 'Wed%20Apr%2023%202025%2010%3A43%3A32%20GMT%2B0900%20(Korean%20Standard%20Time)',
            'BUC': '5OChbI3YrWOGTT-aRWFAZ1HSNSvpNqoT0h7q2BedePg=',
        }

        headers = {
            'accept': '*/*',
            'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IlJFQUxFU1RBVEUiLCJpYXQiOjE3NDUzNzI2MTIsImV4cCI6MTc0NTM4MzQxMn0.cAlD7MplsiOZY-Il_aocktdRiDsS77e-zN_VThjwzAo',
            'priority': 'u=1, i',
            'referer': f'https://new.land.naver.com/complexes/{complex_no}?ms=37.6099682,127.1045329,17&a=APT:PRE:ABYG:JGC:OPST&e=RETAIL',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        }
        
        # Fetch data from multiple pages
        current_page = page
        while current_page <= max_pages:
            status_placeholder.text(f"페이지 {current_page}/{max_pages} 데이터 가져오는 중...")
            progress_bar.progress(current_page / max_pages)
            
            url = f'https://new.land.naver.com/api/articles/complex/{complex_no}?realEstateType=APT%3APRE%3AABYG%3AJGC%3AOPST&tradeType=&tag=%3A%3A%3A%3A%3A%3A%3A%3A&rentPriceMin=0&rentPriceMax=900000000&priceMin=0&priceMax=900000000&areaMin=0&areaMax=900000000&oldBuildYears&recentlyBuildYears&minHouseHoldCount&maxHouseHoldCount&showArticle=false&sameAddressGroup=false&minMaintenanceCost&maxMaintenanceCost&priceType=RETAIL&directions=&page={current_page}&complexNo={complex_no}&buildingNos=&areaNos=&type=list&order=rank'
            
            # Measure request duration
            with request_duration_seconds.labels(complex_no=complex_str).time():
                try:
                    response = requests.get(url, cookies=cookies, headers=headers)
                    response.raise_for_status()  # Raise exception for HTTP errors
                    
                    # Track successful API request
                    api_requests_total.labels(complex_no=complex_str, status='success').inc()
                    
                    data = response.json()
                    
                    # Check if we have reached the end of the data
                    if 'articleList' not in data or not data['articleList']:
                        status_placeholder.text(f"페이지 {current_page}에서 더 이상 매물이 없습니다.")
                        break
                        
                    articles = data['articleList']
                    all_articles.extend(articles)
                    
                    # Track data fetched
                    data_fetched_total.labels(complex_no=complex_str).inc(len(articles))
                    
                    status_placeholder.text(f"페이지 {current_page}에서 {len(articles)}개 매물 정보를 가져왔습니다.")
                    
                    # Check if more data is available
                    if not data.get('isMoreData', False):
                        status_placeholder.text("더 이상 데이터가 없습니다.")
                        break
                        
                    # Sleep to avoid hitting rate limits
                    time.sleep(1)
                    current_page += 1
                    
                except requests.exceptions.RequestException as e:
                    # Track failed API request
                    api_requests_total.labels(complex_no=complex_str, status='error').inc()
                    errors_total.labels(error_type='api_request', complex_no=complex_str).inc()
                    status_placeholder.error(f"페이지 {current_page} 데이터 가져오기 실패: {e}")
                    logger.error(f"API request failed for complex {complex_no}, page {current_page}: {e}")
                    break
                except json.JSONDecodeError as e:
                    # Track JSON decode error
                    errors_total.labels(error_type='json_decode', complex_no=complex_str).inc()
                    status_placeholder.error(f"페이지 {current_page} JSON 디코딩 실패: {e}")
                    logger.error(f"JSON decode failed for complex {complex_no}, page {current_page}: {e}")
                    break
        
        progress_bar.progress(1.0)
        status_placeholder.text(f"총 {len(all_articles)}개 매물 정보를 가져왔습니다.")
        
        if all_articles:
            # Update successful fetch timestamp
            last_successful_fetch_timestamp.labels(complex_no=complex_str).set(time.time())
            # Update current data size
            current_data_size.labels(complex_no=complex_str).set(len(all_articles))
            
        return all_articles
        
    except Exception as e:
        errors_total.labels(error_type='general', complex_no=complex_str).inc()
        logger.error(f"General error in fetch_real_estate_data: {e}")
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
        return []
    finally:
        metrics.decrement_user()

def clean_price(price_str):
    """
    Clean and standardize Korean real estate price strings
    Examples:
    - "5억" -> "5.00" (5억 원, or 500 million won)
    - "5억 2,000" -> "5.20" (5억 2천만 원, or 520 million won)
    """
    if not price_str:
        return ""
    
    # Replace Korean currency symbols/words and standardize
    price_str = price_str.replace("억", "").strip()
    
    # Handle price formats like "5억 2,000"
    parts = price_str.split()
    if len(parts) == 2:
        try:
            billions = float(parts[0])
            # In Korean real estate, the second part is already in units of 10,000 won (만 원)
            # So for "5억 2,000", the 2,000 means 2,000만 원 (20 million won)
            thousands = float(parts[1].replace(",", "")) / 10000
            return f"{billions + thousands:.2f}"
        except (ValueError, IndexError):
            return price_str
    
    try:
        return f"{float(price_str):.2f}"
    except ValueError:
        return price_str

def process_data(articles, complex_no):
    """Process the raw articles into a pandas DataFrame with monitoring"""
    if not articles:
        return pd.DataFrame()
    
    complex_str = str(complex_no)
    
    # Measure data processing duration
    with data_processing_duration_seconds.labels(complex_no=complex_str).time():
        try:
            # Create a list to store processed data
            processed_data = []
            
            for article in articles:
                # Extract relevant fields
                row = {
                    '매물번호': article.get('articleNo', ''),
                    '매물명': article.get('articleName', ''),
                    '건물명': article.get('buildingName', ''),
                    '거래유형': article.get('tradeTypeName', ''),
                    '가격': article.get('dealOrWarrantPrc', ''),
                    '가격(억)': clean_price(article.get('dealOrWarrantPrc', '')),
                    '면적명': article.get('areaName', ''),
                    '공급면적(㎡)': article.get('area1', ''),
                    '전용면적(㎡)': article.get('area2', ''),
                    '층정보': article.get('floorInfo', ''),
                    '방향': article.get('direction', ''),
                    '태그': ', '.join(article.get('tagList', [])) if isinstance(article.get('tagList'), list) else article.get('tagList', ''),
                    '특징': article.get('articleFeatureDesc', ''),
                    '부동산': article.get('realtorName', ''),
                    '확인일자': article.get('articleConfirmYmd', ''),
                    '위도': article.get('latitude', ''),
                    '경도': article.get('longitude', '')
                }
                processed_data.append(row)
            
            # Convert to DataFrame
            df = pd.DataFrame(processed_data)
            
            # Convert price to numeric for analysis
            df['가격(억)'] = pd.to_numeric(df['가격(억)'], errors='coerce')
            
            # Update price statistics metrics
            price_data = df['가격(억)'].dropna()
            if not price_data.empty:
                price_statistics['mean'].labels(complex_no=complex_str).set(price_data.mean())
                price_statistics['max'].labels(complex_no=complex_str).set(price_data.max())
                price_statistics['min'].labels(complex_no=complex_str).set(price_data.min())
                price_statistics['count'].labels(complex_no=complex_str).set(len(price_data))
            
            return df
            
        except Exception as e:
            errors_total.labels(error_type='data_processing', complex_no=complex_str).inc()
            logger.error(f"Data processing error for complex {complex_no}: {e}")
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
            return pd.DataFrame()

def create_download_link(df, filename="data.csv"):
    """Generate a download link for the dataframe"""
    try:
        user_actions_total.labels(action_type='download').inc()
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">CSV 파일 다운로드</a>'
        return href
    except Exception as e:
        errors_total.labels(error_type='download', complex_no='unknown').inc()
        logger.error(f"Download link creation error: {e}")
        return "다운로드 링크 생성 실패"

def main():
    # Track page view
    user_actions_total.labels(action_type='page_view').inc()
    
    # Title and description
    st.title("네이버 부동산 데이터 스크래퍼")
    st.markdown("네이버 부동산에서 매물 정보를 수집하고 CSV 파일로 저장합니다.")
    
    # Prometheus metrics info
    with st.expander("📊 모니터링 정보"):
        st.markdown("""
        **Prometheus 메트릭 서버**: http://localhost:8000/metrics
        
        **수집되는 메트릭:**
        - API 요청 수 및 성공/실패율
        - 데이터 처리 시간
        - 에러 발생 빈도
        - 현재 활성 사용자 수
        - 가격 통계 (평균, 최고, 최저)
        - 마지막 성공적인 데이터 수집 시간
        """)
    
    # Sidebar inputs
    st.sidebar.header("검색 설정")
    
    # Complex number input
    complex_no = st.sidebar.text_input(
        "단지 번호 입력",
        value="131345",
        help="네이버 부동산 URL에서 complexes/ 다음에 오는 숫자입니다. 예: https://new.land.naver.com/complexes/131345"
    )
    
    # Max pages input
    max_pages = st.sidebar.slider(
        "최대 페이지 수",
        min_value=1,
        max_value=20,
        value=5,
        help="가져올 최대 페이지 수"
    )
    
    # Fetch data button
    if st.sidebar.button("데이터 가져오기"):
        if not complex_no:
            st.error("단지 번호를 입력해주세요.")
            return
            
        try:
            complex_no = int(complex_no)
        except ValueError:
            st.error("단지 번호는 숫자여야 합니다.")
            errors_total.labels(error_type='input_validation', complex_no='invalid').inc()
            return
            
        # Fetch data
        with st.spinner("데이터 가져오는 중..."):
            articles = fetch_real_estate_data(complex_no, max_pages=max_pages)
            
            if not articles:
                st.warning("데이터를 가져오지 못했습니다.")
                return
                
            # Process data
            df = process_data(articles, complex_no)
            
            # Store in session state
            st.session_state.df = df
            st.session_state.complex_no = complex_no
            
            # Success message
            st.success(f"총 {len(df)} 개의 매물 정보를 가져왔습니다!")
    
    # Display data if available
    if 'df' in st.session_state and not st.session_state.df.empty:
        df = st.session_state.df
        complex_no = st.session_state.complex_no
        
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["데이터", "분석", "시각화", "모니터링"])
        
        with tab1:
            user_actions_total.labels(action_type='view_data').inc()
            
            # Download button
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"naver_real_estate_data_{complex_no}_{timestamp}.csv"
            st.markdown(create_download_link(df, filename), unsafe_allow_html=True)
            
            # Display dataframe
            st.dataframe(df, use_container_width=True)
        
        with tab2:
            user_actions_total.labels(action_type='view_analysis').inc()
            
            st.subheader("데이터 분석")
            
            # Basic statistics
            if '가격(억)' in df.columns:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("평균 가격(억)", f"{df['가격(억)'].mean():.2f}")
                
                with col2:
                    st.metric("최고 가격(억)", f"{df['가격(억)'].max():.2f}")
                
                with col3:
                    st.metric("최저 가격(억)", f"{df['가격(억)'].min():.2f}")
            
            # Group by analysis
            st.subheader("거래 유형별 평균 가격")
            if '거래유형' in df.columns and '가격(억)' in df.columns:
                trade_type_avg = df.groupby('거래유형')['가격(억)'].agg(['mean', 'count']).reset_index()
                trade_type_avg.columns = ['거래유형', '평균 가격(억)', '매물 수']
                st.dataframe(trade_type_avg, use_container_width=True)
            
            st.subheader("면적별 평균 가격")
            if '전용면적(㎡)' in df.columns and '가격(억)' in df.columns:
                # Create bins for area
                df['면적구간'] = pd.cut(
                    df['전용면적(㎡)'], 
                    bins=[0, 30, 60, 85, 120, 200],
                    labels=['~30㎡', '30~60㎡', '60~85㎡', '85~120㎡', '120㎡~']
                )
                
                area_avg = df.groupby('면적구간')['가격(억)'].agg(['mean', 'count']).reset_index()
                area_avg.columns = ['면적구간', '평균 가격(억)', '매물 수']
                st.dataframe(area_avg, use_container_width=True)
        
        with tab3:
            user_actions_total.labels(action_type='view_visualization').inc()
            
            st.subheader("데이터 시각화")
            
            if '가격(억)' in df.columns:
                # Price distribution
                st.subheader("가격 분포")
                fig = px.histogram(df, x='가격(억)', nbins=20, title="가격 분포")
                st.plotly_chart(fig, use_container_width=True)
                
                # Price by floor
                if '층정보' in df.columns:
                    # Extract floor number
                    df['층'] = df['층정보'].str.extract(r'(\d+)/')
                    df['층'] = pd.to_numeric(df['층'], errors='coerce')
                    
                    # Filter out rows with missing floor
                    floor_df = df.dropna(subset=['층'])
                    
                    if not floor_df.empty:
                        st.subheader("층별 가격")
                        fig = px.scatter(
                            floor_df, 
                            x='층', 
                            y='가격(억)',
                            color='거래유형' if '거래유형' in floor_df.columns else None,
                            title="층별 가격",
                            labels={'층': '층', '가격(억)': '가격(억)'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                # Price by area
                if '전용면적(㎡)' in df.columns:
                    st.subheader("면적별 가격")
                    fig = px.scatter(
                        df, 
                        x='전용면적(㎡)', 
                        y='가격(억)',
                        color='거래유형' if '거래유형' in df.columns else None,
                        title="면적별 가격",
                        labels={'전용면적(㎡)': '전용면적(㎡)', '가격(억)': '가격(억)'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Map view
                if '위도' in df.columns and '경도' in df.columns:
                    st.subheader("지도 보기")
                    
                    # Convert lat/lon to numeric
                    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
                    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
                    
                    # Filter out rows with missing coordinates
                    map_df = df.dropna(subset=['위도', '경도'])
                    
                    if not map_df.empty:
                        fig = px.scatter_mapbox(
                            map_df,
                            lat='위도',
                            lon='경도',
                            color='가격(억)',
                            size='전용면적(㎡)' if '전용면적(㎡)' in map_df.columns else None,
                            hover_name='매물명',
                            hover_data=['가격', '거래유형', '층정보', '전용면적(㎡)'],
                            color_continuous_scale=px.colors.sequential.Plasma,
                            zoom=15,
                            mapbox_style="carto-positron"
                        )
                        st.plotly_chart(fig, use_container_width=True)
        
        with tab4:
            user_actions_total.labels(action_type='view_monitoring').inc()
            
            st.subheader("📊 실시간 모니터링")
            
            # Metrics endpoint info
            st.info("Prometheus 메트릭은 http://localhost:8000/metrics 에서 확인할 수 있습니다.")
            
            # Display current metrics (simulated view)
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("현재 세션 통계")
                if 'df' in st.session_state:
                    st.metric("데이터 건수", len(st.session_state.df))
                    st.metric("단지 번호", st.session_state.complex_no)
                    
                    # Price statistics
                    if '가격(억)' in st.session_state.df.columns:
                        price_data = st.session_state.df['가격(억)'].dropna()
                        if not price_data.empty:
                            st.metric("평균 가격(억)", f"{price_data.mean():.2f}")
                            st.metric("최고 가격(억)", f"{price_data.max():.2f}")
                            st.metric("최저 가격(억)", f"{price_data.min():.2f}")
            
            with col2:
                st.subheader("시스템 정보")
                st.metric("Prometheus 서버", "포트 8000에서 실행 중")
                st.metric("현재 시간", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                
                # Show sample metrics
                st.subheader("수집되는 메트릭 예시")
                st.code("""
# API 요청 횟수
naver_scraper_api_requests_total{complex_no="131345",status="success"} 15

# 데이터 처리 시간
naver_scraper_data_processing_duration_seconds{complex_no="131345"} 0.245

# 에러 발생 횟수
naver_scraper_errors_total{error_type="api_request",complex_no="131345"} 0

# 현재 활성 사용자 수
naver_scraper_active_users 2

# 가격 통계
naver_scraper_price_mean_billion{complex_no="131345"} 8.45
naver_scraper_price_max_billion{complex_no="131345"} 15.20
naver_scraper_price_min_billion{complex_no="131345"} 3.80

# 마지막 성공적인 데이터 수집 시간
naver_scraper_last_successful_fetch_timestamp{complex_no="131345"} 1735123456
                """)
                
            # Grafana dashboard suggestion
            st.subheader("🎯 Grafana 대시보드 설정")
            st.markdown("""
            **추천 Grafana 쿼리:**
            
            1. **API 성공률**:
            ```
            rate(naver_scraper_api_requests_total{status="success"}[5m]) / 
            rate(naver_scraper_api_requests_total[5m]) * 100
            ```
            
            2. **평균 응답 시간**:
            ```
            histogram_quantile(0.95, rate(naver_scraper_request_duration_seconds_bucket[5m]))
            ```
            
            3. **시간당 에러율**:
            ```
            rate(naver_scraper_errors_total[1h])
            ```
            
            4. **활성 사용자 수**:
            ```
            naver_scraper_active_users
            ```
            """)
            
            # Alerting rules suggestion
            st.subheader("🚨 추천 알림 규칙")
            st.markdown("""
            **Prometheus AlertManager 규칙:**
            
            ```yaml
            groups:
            - name: naver_scraper_alerts
              rules:
              - alert: HighErrorRate
                expr: rate(naver_scraper_errors_total[5m]) > 0.1
                for: 2m
                labels:
                  severity: warning
                annotations:
                  summary: "네이버 스크래퍼 에러율 증가"
                  description: "에러율이 {{ $value }}% 입니다"
                  
              - alert: APIRequestFailure
                expr: rate(naver_scraper_api_requests_total{status="error"}[5m]) > 0.05
                for: 1m
                labels:
                  severity: critical
                annotations:
                  summary: "API 요청 실패율 증가"
                  
              - alert: DataProcessingTimeout
                expr: histogram_quantile(0.95, rate(naver_scraper_data_processing_duration_seconds_bucket[5m])) > 10
                for: 3m
                labels:
                  severity: warning
                annotations:
                  summary: "데이터 처리 시간 초과"
            ```
            """)

if __name__ == "__main__":
    main()
