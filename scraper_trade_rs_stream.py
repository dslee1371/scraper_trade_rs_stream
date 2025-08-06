import streamlit as st
import requests
import json
import csv
import time
import pandas as pd
import base64
from datetime import datetime
import plotly.express as px
import io

# Set page config
st.set_page_config(
    page_title="네이버 부동산 데이터 스크래퍼",
    page_icon="🏢",
    layout="wide"
)

# Title and description
st.title("네이버 부동산 데이터 스크래퍼")
st.markdown("네이버 부동산에서 매물 정보를 수집하고 CSV 파일로 저장합니다.")

def fetch_real_estate_data(complex_no, page=1, max_pages=10):
    """
    Fetch real estate listing data from Naver Land API
    
    Args:
        complex_no (int): The complex number to fetch data for
        page (int): Starting page number
        max_pages (int): Maximum number of pages to fetch
        
    Returns:
        list: List of real estate listings
    """
    all_articles = []
    
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
        
        try:
            response = requests.get(url, cookies=cookies, headers=headers)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            data = response.json()
            
            # Check if we have reached the end of the data
            if 'articleList' not in data or not data['articleList']:
                status_placeholder.text(f"페이지 {current_page}에서 더 이상 매물이 없습니다.")
                break
                
            articles = data['articleList']
            all_articles.extend(articles)
            
            status_placeholder.text(f"페이지 {current_page}에서 {len(articles)}개 매물 정보를 가져왔습니다.")
            
            # Check if more data is available
            if not data.get('isMoreData', False):
                status_placeholder.text("더 이상 데이터가 없습니다.")
                break
                
            # Sleep to avoid hitting rate limits
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
    
    return all_articles

def clean_price(price_str):
    """
    Clean and standardize Korean real estate price strings
    Examples:
    - "5억" -> "5.00" (5억 원, or 500 million won)
    - "5억 2,000" -> "5.20" (5억 2천만 원, or 520 million won)
    """
    if not price_str:
        return ""
    
    # Replace the Korean "억" unit with a space so both "5억 2,000" and
    # "5억2,000" formats are handled consistently
    price_str = price_str.replace("억", " ").strip()
    
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

def process_data(articles):
    """Process the raw articles into a pandas DataFrame"""
    if not articles:
        return pd.DataFrame()
    
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
    
    return df

def create_download_link(df, filename="data.csv"):
    """Generate a download link for the dataframe"""
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">CSV 파일 다운로드</a>'
    return href

def main():
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
            return
            
        # Fetch data
        with st.spinner("데이터 가져오는 중..."):
            articles = fetch_real_estate_data(complex_no, max_pages=max_pages)
            
            if not articles:
                st.warning("데이터를 가져오지 못했습니다.")
                return
                
            # Process data
            df = process_data(articles)
            
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
        tab1, tab2, tab3 = st.tabs(["데이터", "분석", "시각화"])
        
        with tab1:
            # Download button
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"naver_real_estate_data_{complex_no}_{timestamp}.csv"
            st.markdown(create_download_link(df, filename), unsafe_allow_html=True)
            
            # Display dataframe
            st.dataframe(df, use_container_width=True)
        
        with tab2:
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

if __name__ == "__main__":
    main()