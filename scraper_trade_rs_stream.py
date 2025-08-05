import time
import streamlit as st
import requests
import json
import csv
import pandas as pd
import base64
from datetime import datetime
import plotly.express as px
import io

# Prometheus client imports
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from flask import Flask, Response
from threading import Thread

# ─── Prometheus 메트릭 정의 ─────────────────────────────────────────────
PAGE_VIEWS = Counter(
    'streamlit_page_views_total',
    'Total number of times the Streamlit app was loaded'
)
FETCH_CALLS = Counter(
    'naver_fetch_calls_total',
    'Total number of calls to fetch_real_estate_data'
)
FETCH_LATENCY = Histogram(
    'naver_fetch_latency_seconds',
    'Latency of each fetch_real_estate_data call in seconds',
    buckets=[0.5, 1, 2, 5, 10]
)

# ─── Flask 서버로 /metrics 엔드포인트 실행 ─────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

def run_metrics_server():
    flask_app.run(host="0.0.0.0", port=8001)

Thread(target=run_metrics_server, daemon=True).start()

# ─── Streamlit 페이지 로드 시 메트릭 증가 ─────────────────────────────────
PAGE_VIEWS.inc()

# ─── 데이터 스크래핑 함수 (메트릭 포함) ────────────────────────────────────
def fetch_real_estate_data(complex_no, page=1, max_pages=10):
    FETCH_CALLS.inc()
    start_time = time.time()

    all_articles = []
    status_placeholder = st.empty()
    progress_bar = st.progress(0.0)

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

    current_page = page
    while current_page <= max_pages:
        status_placeholder.text(f"페이지 {current_page}/{max_pages} 데이터 가져오는 중...")
        progress_bar.progress(current_page / max_pages)

        url = (
            f'https://new.land.naver.com/api/articles/complex/{complex_no}'
            f'?realEstateType=APT%3APRE%3AABYG%3AJGC%3AOPST&tradeType=&'
            f'tag=%3A%3A%3A%3A%3A%3A%3A%3A&rentPriceMin=0&rentPriceMax=900000000'
            f'&priceMin=0&priceMax=900000000&areaMin=0&areaMax=900000000'
            f'&oldBuildYears&recentlyBuildYears&minHouseHoldCount&maxHouseHoldCount'
            f'&showArticle=false&sameAddressGroup=false&minMaintenanceCost'
            f'&maxMaintenanceCost&priceType=RETAIL&directions='
            f'&page={current_page}&complexNo={complex_no}&buildingNos='
            f'&areaNos=&type=list&order=rank'
        )

        try:
            resp = requests.get(url, cookies=cookies, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            articles = data.get('articleList', [])
            if not articles:
                status_placeholder.text("더 이상 매물이 없습니다.")
                break

            all_articles.extend(articles)
            if not data.get('isMoreData', False):
                status_placeholder.text("더 이상 데이터가 없습니다.")
                break

            time.sleep(1)
            current_page += 1

        except requests.exceptions.RequestException as e:
            status_placeholder.error(f"페이지 {current_page} 데이터 가져오기 실패: {e}")
            break
        except json.JSONDecodeError as e:
            status_placeholder.error(f"페이지 {current_page} JSON 디코딩 실패: {e}")
            break

    progress_bar.progress(1.0)
    status_placeholder.text(f"총 {len(all_articles)}개 매물 정보를 가져왔습니다.")

    FETCH_LATENCY.observe(time.time() - start_time)
    return all_articles

# ─── 가격 문자열 정제 함수 ─────────────────────────────────────────────────
def clean_price(price_str):
    if not price_str:
        return ""
    price_str = price_str.replace("억", "").strip()
    parts = price_str.split()
    if len(parts) == 2:
        try:
            billions = float(parts[0])
            thousands = float(parts[1].replace(",", "")) / 10000
            return f"{billions + thousands:.2f}"
        except Exception:
            return price_str
    try:
        return f"{float(price_str):.2f}"
    except ValueError:
        return price_str

# ─── 데이터 처리 함수 ────────────────────────────────────────────────────
def process_data(articles):
    if not articles:
        return pd.DataFrame()
    processed = []
    for art in articles:
        row = {
            '매물번호': art.get('articleNo', ''),
            '매물명': art.get('articleName', ''),
            '건물명': art.get('buildingName', ''),
            '거래유형': art.get('tradeTypeName', ''),
            '가격': art.get('dealOrWarrantPrc', ''),
            '가격(억)': clean_price(art.get('dealOrWarrantPrc', '')),
            '면적명': art.get('areaName', ''),
            '공급면적(㎡)': art.get('area1', ''),
            '전용면적(㎡)': art.get('area2', ''),
            '층정보': art.get('floorInfo', ''),
            '방향': art.get('direction', ''),
            '태그': ', '.join(art.get('tagList', [])) if isinstance(art.get('tagList'), list) else art.get('tagList', ''),
            '특징': art.get('articleFeatureDesc', ''),
            '부동산': art.get('realtorName', ''),
            '확인일자': art.get('articleConfirmYmd', ''),
            '위도': art.get('latitude', ''),
            '경도': art.get('longitude', '')
        }
        processed.append(row)
    df = pd.DataFrame(processed)
    df['가격(억)'] = pd.to_numeric(df['가격(억)'], errors='coerce')
    return df

# ─── CSV 다운로드 링크 생성 ───────────────────────────────────────────────
def create_download_link(df, filename="data.csv"):
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">CSV 파일 다운로드</a>'
    return href

# ─── Streamlit 메인 함수 ────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="네이버 부동산 데이터 스크래퍼",
        page_icon="🏢",
        layout="wide"
    )
    st.title("네이버 부동산 데이터 스크래퍼")
    st.markdown("네이버 부동산에서 매물 정보를 수집하고 CSV 파일로 저장합니다.")

    st.sidebar.header("검색 설정")
    complex_no = st.sidebar.text_input(
        "단지 번호 입력",
        value="131345",
        help="예: https://new.land.naver.com/complexes/131345 에서 131345"
    )
    max_pages = st.sidebar.slider(
        "최대 페이지 수",
        min_value=1,
        max_value=20,
        value=5
    )

    if st.sidebar.button("데이터 가져오기"):
        if not complex_no.isdigit():
            st.error("단지 번호는 숫자여야 합니다.")
            return
        with st.spinner("데이터 가져오는 중..."):
            articles = fetch_real_estate_data(int(complex_no), max_pages=max_pages)
        if not articles:
            st.warning("데이터를 가져오지 못했습니다.")
            return
        df = process_data(articles)
        st.session_state.df = df
        st.success(f"총 {len(df)}개 매물 정보를 가져왔습니다!")

    if 'df' in st.session_state and not st.session_state.df.empty:
        df = st.session_state.df
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"naver_real_estate_{complex_no}_{timestamp}.csv"

        tab1, tab2, tab3 = st.tabs(["데이터", "분석", "시각화"])

        with tab1:
            st.markdown(create_download_link(df, filename), unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True)

        with tab2:
            st.subheader("데이터 분석")
            if '가격(억)' in df:
                c1, c2, c3 = st.columns(3)
                c1.metric("평균 가격(억)", f"{df['가격(억)'].mean():.2f}")
                c2.metric("최고 가격(억)", f"{df['가격(억)'].max():.2f}")
                c3.metric("최저 가격(억)", f"{df['가격(억)'].min():.2f}")

            st.subheader("거래 유형별 평균 가격")
            if '거래유형' in df and '가격(억)' in df:
                trade_avg = df.groupby('거래유형')['가격(억)'].agg(['mean','count']).reset_index()
                trade_avg.columns = ['거래유형','평균 가격(억)','매물 수']
                st.dataframe(trade_avg, use_container_width=True)

            st.subheader("면적별 평균 가격")
            if '전용면적(㎡)' in df and '가격(억)' in df:
                df['면적구간'] = pd.cut(df['전용면적(㎡)'], bins=[0,30,60,85,120,200],
                                      labels=['~30㎡','30~60㎡','60~85㎡','85~120㎡','120㎡~'])
                area_avg = df.groupby('면적구간')['가격(억)'].agg(['mean','count']).reset_index()
                area_avg.columns = ['면적구간','평균 가격(억)','매물 수']
                st.dataframe(area_avg, use_container_width=True)

        with tab3:
            st.subheader("데이터 시각화")
            if '가격(억)' in df:
                st.subheader("가격 분포")
                fig1 = px.histogram(df, x='가격(억)', nbins=20, title="가격 분포")
                st.plotly_chart(fig1, use_container_width=True)

                if '층정보' in df:
                    df['층'] = df['층정보'].str.extract(r'(\d+)/').astype(float)
                    floor_df = df.dropna(subset=['층'])
                    if not floor_df.empty:
                        st.subheader("층별 가격")
                        fig2 = px.scatter(
                            floor_df, x='층', y='가격(억)',
                            color='거래유형', title="층별 가격",
                            labels={'층':'층','가격(억)':'가격(억)'}
                        )
                        st.plotly_chart(fig2, use_container_width=True)

                if '전용면적(㎡)' in df:
                    st.subheader("면적별 가격")
                    fig3 = px.scatter(
                        df, x='전용면적(㎡)', y='가격(억)',
                        color='거래유형', title="면적별 가격",
                        labels={'전용면적(㎡)':'전용면적(㎡)','가격(억)':'가격(억)'}
                    )
                    st.plotly_chart(fig3, use_container_width=True)

                if '위도' in df and '경도' in df:
                    st.subheader("지도 보기")
                    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
                    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
                    map_df = df.dropna(subset=['위도','경도'])
                    if not map_df.empty:
                        fig4 = px.scatter_mapbox(
                            map_df, lat='위도', lon='경도',
                            color='가격(억)', size='전용면적(㎡)',
                            hover_name='매물명',
                            hover_data=['가격','거래유형','층정보','전용면적(㎡)'],
                            zoom=15, mapbox_style="carto-positron"
                        )
                        st.plotly_chart(fig4, use_container_width=True)

if __name__ == "__main__":
    main()
