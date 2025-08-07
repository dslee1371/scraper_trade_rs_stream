import threading
import time
import base64
import requests
import json
import csv
import io
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    Gauge,
    start_http_server,
    generate_latest,
    CONTENT_TYPE_LATEST
)

# ─── Prometheus Metrics 정의 ────────────────────────────────────────────────
# 전역 registry 사용하지 않고 커스텀 registry 사용
registry = CollectorRegistry()

PAGE_FETCH_COUNTER = Counter(
    'naver_scraper_pages_fetched_total',
    '총 네이버 부동산 페이지 요청 횟수',
    registry=registry
)
PAGE_FETCH_DURATION = Histogram(
    'naver_scraper_page_fetch_duration_seconds',
    '페이지 요청 지연 시간(초)',
    buckets=(0.1, 0.5, 1, 2, 5, 10),
    registry=registry
)
ARTICLE_COUNTER = Counter(
    'naver_scraper_articles_processed_total',
    '처리된 매물(article) 총 건수',
    registry=registry
)
LAST_PAGE_ARTICLE_GAUGE = Gauge(
    'naver_scraper_last_page_article_count',
    '마지막 페이지에서 가져온 매물(article) 수',
    registry=registry
)

# 메트릭 서버 시작 상태를 추적하는 전역 변수
metrics_server_started = False
metrics_server_lock = threading.Lock()

def start_metrics_server():
    """Prometheus metrics 서버 시작 (포트 8000)"""
    global metrics_server_started
    
    with metrics_server_lock:
        if not metrics_server_started:
            try:
                start_http_server(8000, registry=registry)
                metrics_server_started = True
                print("✅ Prometheus metrics server started on :8000")
            except Exception as e:
                print(f"❌ Failed to start metrics server: {e}")
        else:
            print("ℹ️ Metrics server already running")

def get_metric_value(metric):
    """메트릭 값을 안전하게 가져오는 함수"""
    try:
        if hasattr(metric, '_value'):
            if hasattr(metric._value, '_value'):
                return metric._value._value
            else:
                return metric._value
        else:
            # Counter나 Gauge의 경우 직접 값을 가져올 수 있는 방법
            samples = list(metric.collect())[0].samples
            if samples:
                return samples[0].value
            return 0
    except Exception as e:
        print(f"메트릭 값 가져오기 실패: {e}")
        return 0

def print_metrics_debug():
    """디버깅을 위한 메트릭 값 출력"""
    try:
        print(f"=== 메트릭 디버깅 정보 ===")
        print(f"PAGE_FETCH_COUNTER: {get_metric_value(PAGE_FETCH_COUNTER)}")
        print(f"ARTICLE_COUNTER: {get_metric_value(ARTICLE_COUNTER)}")
        print(f"LAST_PAGE_ARTICLE_GAUGE: {get_metric_value(LAST_PAGE_ARTICLE_GAUGE)}")
        
        # Prometheus 형식으로 메트릭 출력 (디버깅용)
        metrics_output = generate_latest(registry).decode('utf-8')
        print("=== Prometheus 메트릭 출력 ===")
        for line in metrics_output.split('\n'):
            if 'naver_scraper' in line and not line.startswith('#'):
                print(line)
        print("=" * 50)
    except Exception as e:
        print(f"메트릭 디버깅 출력 실패: {e}")

# 백그라운드에서 metrics 서버 구동 (한 번만)
if not metrics_server_started:
    threading.Thread(target=start_metrics_server, daemon=True).start()

# ─── Streamlit 앱 설정 ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="네이버 부동산 데이터 스크래퍼",
    page_icon="🏢",
    layout="wide"
)

st.title("네이버 부동산 데이터 스크래퍼")
st.markdown("네이버 부동산에서 매물 정보를 수집하고 CSV 파일로 저장합니다.")

# 메트릭 정보 표시 (사이드바에)
with st.sidebar:
    st.header("📊 메트릭 정보")
    
    if st.button("메트릭 새로고침"):
        st.rerun()
    
    try:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("페이지 요청", get_metric_value(PAGE_FETCH_COUNTER))
            st.metric("처리된 매물", get_metric_value(ARTICLE_COUNTER))
        with col2:
            st.metric("마지막 페이지 매물", get_metric_value(LAST_PAGE_ARTICLE_GAUGE))
    except Exception as e:
        st.error(f"메트릭 표시 오류: {e}")

def fetch_real_estate_data(complex_no, page=1, max_pages=10):
    all_articles = []
    status_placeholder = st.empty()
    progress_bar = st.progress(0)

    cookies = {
        'NAC': 't9neDIhO7XOeC',
        'NACT': '1',
        'NNB': 'PABUYQL3IUEGQ',
        'SRT30': '1745372539',
        'SRT5': '1745372539',
        'page_uid': 'jsmaYql3IUEGQ',
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

    current_page = page
    while current_page <= max_pages:
        status_placeholder.text(f"📄 페이지 {current_page}/{max_pages} 데이터 가져오는 중...")
        progress_bar.progress(current_page / max_pages)

        url = (
            f'https://new.land.naver.com/api/articles/complex/{complex_no}'
            f'?realEstateType=APT%3APRE%3AABYG%3AJGC%3AOPST&tradeType=&'
            f'tag=%3A%3A%3A%3A%3A%3A%3A%3A&rentPriceMin=0&rentPriceMax=900000000'
            f'&priceMin=0&priceMax=900000000&areaMin=0&areaMax=900000000'
            f'&oldBuildYears&recentlyBuildYears&minHouseHoldCount&maxHouseHoldCount'
            f'&showArticle=false&sameAddressGroup=false&minMaintenanceCost'
            f'&maxMaintenanceCost&priceType=RETAIL&directions=&page={current_page}'
            f'&complexNo={complex_no}&buildingNos=&areaNos=&type=list&order=rank'
        )

        # HTTP 요청 및 메트릭 측정
        request_start_time = time.time()
        
        try:
            with PAGE_FETCH_DURATION.time():
                response = requests.get(url, cookies=cookies, headers=headers)
                response.raise_for_status()
                
            # 요청이 성공한 경우에만 페이지 카운터 증가
            PAGE_FETCH_COUNTER.inc()
            print(f"✅ 페이지 {current_page} 요청 성공 - 카운터 증가")
            
        except Exception as e:
            status_placeholder.error(f"❌ 페이지 {current_page} 데이터 가져오기 실패: {e}")
            print(f"❌ HTTP 요청 실패: {e}")
            break

        # JSON 파싱
        try:
            data = response.json()
            print(f"📊 페이지 {current_page} JSON 파싱 성공")
        except Exception as e:
            status_placeholder.error(f"❌ 페이지 {current_page} JSON 파싱 실패: {e}")
            print(f"❌ JSON 파싱 실패: {e}")
            continue

        # 매물 데이터 처리
        articles = data.get('articleList', [])
        article_count = len(articles)
        
        print(f"📄 페이지 {current_page}: {article_count}개 매물 발견")
        
        if not articles:
            status_placeholder.text("ℹ️ 더 이상 매물이 없습니다.")
            LAST_PAGE_ARTICLE_GAUGE.set(0)
            break

        # 매물 리스트에 추가
        all_articles.extend(articles)
        
        # 매물 카운터 증가 (이 페이지에서 가져온 매물 수만큼)
        ARTICLE_COUNTER.inc(article_count)
        print(f"📈 매물 카운터 {article_count}개 증가")
        
        # 게이지 업데이트 (마지막 페이지의 매물 수)
        LAST_PAGE_ARTICLE_GAUGE.set(article_count)
        print(f"📊 게이지를 {article_count}로 설정")
        
        # 메트릭 디버깅 출력
        print_metrics_debug()

        status_placeholder.text(f"✅ 페이지 {current_page}에서 {article_count}개 매물 정보를 가져왔습니다.")
        
        # 더 이상 데이터가 없으면 종료
        if not data.get('isMoreData', False):
            status_placeholder.text("✅ 마지막 페이지입니다.")
            break

        time.sleep(1)  # 요청 간 딜레이
        current_page += 1

    progress_bar.progress(1.0)
    total_articles = len(all_articles)
    status_placeholder.text(f"🎉 총 {total_articles}개 매물 정보를 가져왔습니다.")
    
    # 최종 메트릭 디버깅 정보
    print(f"\n{'='*50}")
    print(f"🎯 최종 결과")
    print(f"{'='*50}")
    print(f"실제 수집된 매물 수: {total_articles}")
    print(f"처리한 페이지 수: {current_page - 1}")
    print_metrics_debug()
    
    return all_articles

def clean_price(price_str):
    if not price_str:
        return ""
    price_str = price_str.replace("억", " ").strip()
    parts = price_str.split()
    if len(parts) == 2:
        try:
            billions = float(parts[0])
            thousands = float(parts[1].replace(",", "")) / 10000
            return f"{billions + thousands:.2f}"
        except (ValueError, IndexError):
            return price_str
    try:
        return f"{float(price_str):.2f}"
    except ValueError:
        return price_str

def process_data(articles):
    if not articles:
        return pd.DataFrame()
    processed_data = []
    for article in articles:
        processed_data.append({
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
        })
    df = pd.DataFrame(processed_data)
    df['가격(억)'] = pd.to_numeric(df['가격(억)'], errors='coerce')
    return df

def create_download_link(df, filename="data.csv"):
    csv_data = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv_data.encode('utf-8-sig')).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 CSV 파일 다운로드</a>'

def main():
    # 메트릭 서버가 시작되었는지 확인
    start_metrics_server()
    
    st.sidebar.header("🔧 검색 설정")
    complex_no = st.sidebar.text_input(
        "단지 번호 입력",
        value="131345",
        help="네이버 부동산 URL에서 complexes/ 다음에 오는 숫자입니다."
    )
    max_pages = st.sidebar.slider(
        "최대 페이지 수",
        min_value=1,
        max_value=20,
        value=5,
        help="가져올 최대 페이지 수"
    )

    if st.sidebar.button("🚀 데이터 가져오기", type="primary"):
        try:
            cn = int(complex_no)
        except ValueError:
            st.error("❌ 단지 번호는 숫자여야 합니다.")
            return

        with st.spinner("🔄 데이터 가져오는 중..."):
            articles = fetch_real_estate_data(cn, max_pages=max_pages)
            if not articles:
                st.warning("⚠️ 데이터를 가져오지 못했습니다.")
                return
            df = process_data(articles)
            st.session_state.df = df
            st.session_state.cn = cn
            st.success(f"🎉 총 {len(df)} 개의 매물 정보를 가져왔습니다!")
            
            # 메트릭 정보 자동 새로고침
            st.rerun()

    if 'df' in st.session_state and not st.session_state.df.empty:
        df = st.session_state.df
        cn = st.session_state.cn
        tab1, tab2, tab3 = st.tabs(["📄 데이터", "📊 분석", "📈 시각화"])

        with tab1:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"naver_real_estate_data_{cn}_{timestamp}.csv"
            st.markdown(create_download_link(df, filename), unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True)

        with tab2:
            st.subheader("📊 데이터 분석")
            if '가격(억)' in df.columns:
                c1, c2, c3 = st.columns(3)
                c1.metric("평균 가격(억)", f"{df['가격(억)'].mean():.2f}")
                c2.metric("최고 가격(억)", f"{df['가격(억)'].max():.2f}")
                c3.metric("최저 가격(억)", f"{df['가격(억)'].min():.2f}")

            st.subheader("거래 유형별 평균 가격")
            if '거래유형' in df.columns:
                trade_avg = df.groupby('거래유형')['가격(억)'].agg(['mean','count']).reset_index()
                trade_avg.columns = ['거래유형','평균 가격(억)','매물 수']
                st.dataframe(trade_avg, use_container_width=True)

            st.subheader("면적별 평균 가격")
            if '전용면적(㎡)' in df.columns:
                df['면적구간'] = pd.cut(df['전용면적(㎡)'], bins=[0,30,60,85,120,200],
                                      labels=['~30㎡','30~60㎡','60~85㎡','85~120㎡','120㎡~'])
                area_avg = df.groupby('면적구간')['가격(억)'].agg(['mean','count']).reset_index()
                area_avg.columns=['면적구간','평균 가격(억)','매물 수']
                st.dataframe(area_avg, use_container_width=True)

        with tab3:
            st.subheader("📈 데이터 시각화")
            if '가격(억)' in df.columns:
                st.subheader("가격 분포")
                fig = px.histogram(df, x='가격(억)', nbins=20, title="가격 분포")
                st.plotly_chart(fig, use_container_width=True)

                if '층정보' in df.columns:
                    df['층'] = df['층정보'].str.extract(r'(\d+)/').astype(float, errors='ignore')
                    fl = df.dropna(subset=['층'])
                    if not fl.empty:
                        st.subheader("층별 가격")
                        fig = px.scatter(fl, x='층', y='가격(억)',
                                         color='거래유형' if '거래유형' in fl.columns else None,
                                         title="층별 가격",
                                         labels={'층':'층','가격(억)':'가격(억)'})
                        st.plotly_chart(fig, use_container_width=True)

                if '전용면적(㎡)' in df.columns:
                    st.subheader("면적별 가격")
                    fig = px.scatter(df, x='전용면적(㎡)', y='가격(억)',
                                     color='거래유형' if '거래유형' in df.columns else None,
                                     title="면적별 가격",
                                     labels={'전용면적(㎡)':'전용면적(㎡)','가격(억)':'가격(억)'})
                    st.plotly_chart(fig, use_container_width=True)

                if '위도' in df.columns and '경도' in df.columns:
                    st.subheader("🗺️ 지도 보기")
                    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
                    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
                    mp = df.dropna(subset=['위도','경도'])
                    if not mp.empty:
                        fig = px.scatter_mapbox(mp, lat='위도', lon='경도',
                                               color='가격(억)',
                                               size='전용면적(㎡)' if '전용면적(㎡)' in mp.columns else None,
                                               hover_name='매물명',
                                               hover_data=['가격','거래유형','층정보','전용면적(㎡)'],
                                               zoom=15,
                                               mapbox_style="carto-positron")
                        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
