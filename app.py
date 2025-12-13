# app.py (최종 - NameError 해결 및 최적화 완료)

import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
import random 
import json 
import math 

# -----------------------------------------------------
# 1. 페이지 설정 및 제목
# -----------------------------------------------------
st.set_page_config(
    page_title="🅿️ 주차장 실시간 정보 - 공공 데이터 연동",
    layout="wide"
)

st.title("🅿️ 스마트 주차 안내 시스템: 공공 주차장 실시간 확인!")
st.markdown("""
이 앱은 한국교통안전공단 주차장 실시간 정보 API와 연동된 구조로 작동하며, **운전자 위치 기반 최단 거리 안내**를 제공합니다.
---
""")

# -----------------------------------------------------
# 2. API 엔드포인트 및 키 설정 (전역 변수 정의)
# -----------------------------------------------------

API_ENDPOINT = "https://api.odcloud.kr/api/15150101/v1/uddi:1ddc788e-fdd8-4255-9e6d-a8f260dc20db" 
SERVICE_KEY = "6d3fcec1cb59910225aa7de9c79def31b2102379f73dc40baa7130a8fac4c1e3" 

# -----------------------------------------------------
# 3. 거리 계산 함수 정의
# -----------------------------------------------------

def calculate_distance(lat1, lon1, lat2, lon2):
    """유클리드 거리를 계산합니다. (근사치, 거리 비교용으로 적합)"""
    return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)


# -----------------------------------------------------
# 4. 시뮬레이션 및 API 데이터 로드 함수 (st.cache_data 적용)
# -----------------------------------------------------
def simulate_api_data():
    base_lat = 37.5665; base_lon = 126.9780; num_spots = 100 
    df = pd.DataFrame({
        'lat': np.random.randn(num_spots) * 0.005 + base_lat,
        'lon': np.random.randn(num_spots) * 0.007 + base_lon,
        '주차장명': [f'공영주차장-{i+1:02d}' for i in range(num_spots)], 
        '총잔여주차구획수': np.random.randint(0, 500, size=num_spots),
        '총주차구획수': np.random.randint(500, 1000, size=num_spots),
        '주차혼잡상태': np.random.randint(0, 4, size=num_spots)
    })
    return df

@st.cache_data(ttl=300) # 300초(5분)마다 API 데이터를 새로 가져옴
def fetch_parking_data_from_api():
    
    # ⭐️ NameError 해결: SERVICE_KEY와 API_ENDPOINT가 전역 변수임을 명시 ⭐️
    global SERVICE_KEY, API_ENDPOINT
    
    params = {
        'serviceKey': SERVICE_KEY, 'page': '1', 'perPage': '100', 'returnType': 'JSON' 
    }
    
    try:
        response = requests.get(API_ENDPOINT, params=params, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        data_list = json_data.get('data', [])

        if not data_list:
             st.warning("API 응답에 데이터가 없습니다. 시뮬레이션 데이터를 사용합니다.")
             return simulate_api_data()
             
        parking_df = pd.DataFrame(data_list)
        
        # 4. 데이터프레임 컬럼 정리 및 타입 변환
        for col in ['총잔여주차구획수', '총주차구획수', '주차혼잡상태']:
            parking_df[col] = pd.to_numeric(parking_df.get(col, 0), errors='coerce').fillna(0).astype(int)
        
        status_map = {0: '여유', 1: '보통', 2: '혼잡', 3: '만차'}
        parking_df['주차혼잡상태_텍스트'] = parking_df['주차혼잡상태'].map(status_map).fillna('알 수 없음')

        # 주차장명 KeyError 방지 로직 (이전과 동일)
        if '주차장명' not in parking_df.columns:
             if 'PRK_NAME' in parking_df.columns:
                 parking_df = parking_df.rename(columns={'PRK_NAME': '주차장명'})
             elif '주차장관리번호' in parking_df.columns:
                 parking_df = parking_df.rename(columns={'주차장관리번호': '주차장명'})
             else:
                 parking_df['주차장명'] = parking_df.index.to_series().apply(lambda x: f'주차장-{x+1:02d}')


        # 지도 시각화 안정성 강화 로직 (이전과 동일)
        coordinate_mapping = {'PRK_LTTD': 'lat', 'PRK_LGTT': 'lon', 'lat': 'lat', 'lon': 'lon'}
        renamed_cols = {api_col: df_col for api_col, df_col in coordinate_mapping.items() if api_col in parking_df.columns}
        parking_df = parking_df.rename(columns=renamed_cols)

        if 'lat' in parking_df.columns and 'lon' in parking_df.columns:
            parking_df['lat'] = pd.to_numeric(parking_df['lat'], errors='coerce')
            parking_df['lon'] = pd.to_numeric(parking_df['lon'], errors='coerce')
        else:
            sim_df = simulate_api_data()
            parking_df['lat'] = sim_df['lat']
            parking_df['lon'] = sim_df['lon']
            
        return parking_df
        
    except requests.exceptions.RequestException as e:
        st.error(f"API 호출 실패 (네트워크/서버 오류): {e}. 시뮬레이션 데이터를 사용합니다.")
        return simulate_api_data() 
    
    except Exception as e:
        st.error(f"데이터 처리 오류: {e}")
        return simulate_api_data()
# -----------------------------------------------------


# -----------------------------------------------------
# 5. 메인 앱 실행 영역 (루프 제거, 캐싱 적용)
# -----------------------------------------------------

# 초기 사용자 위치 설정
default_lat = 37.5665
default_lon = 126.9780

# 사이드바에 사용자 위치 입력 UI 배치
with st.sidebar:
    st.header("나의 위치 설정 🗺️")
    st.markdown("차량의 현재 위도와 경도를 입력하세요.")
    
    user_lat = st.slider(
        '현재 위도 (Latitude)', 
        min_value=33.0, max_value=43.0, value=default_lat, step=0.0001
    )
    user_lon = st.slider(
        '현재 경도 (Longitude)', 
        min_value=124.0, max_value=132.0, value=default_lon, step=0.0001
    )
    
    # 사용자 위치 시각화 (사이드바 지도)
    user_location_df = pd.DataFrame({'lat': [user_lat], 'lon': [user_lon]})
    st.map(user_location_df, zoom=10, size=100)
    st.info(f"선택된 위치: ({user_lat:.4f}, {user_lon:.4f})")
    

# 1. 데이터 가져오기 (캐싱된 함수 호출)
parking_df = fetch_parking_data_from_api()
# 

if parking_df is not None and not parking_df.empty:
    
    # 2. 현황 계산 및 메트릭 표시
    total_parking_lots = len(parking_df)
    total_available_spots = parking_df['총잔여주차구획수'].sum()
    total_max_spots = parking_df['총주차구획수'].sum()
    
    st.subheader(f"✅ 데이터 갱신 시간: {time.strftime('%H:%M:%S')}")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric(label="조회된 주차장 수", value=f"{total_parking_lots}개")
    with col2: st.metric(label="총 주차 구획 수", value=f"{total_max_spots}개") 
    with col3: st.metric(
        label="✅ 실시간 빈자리 수 (합산)", 
        value=f"{total_available_spots}개",
        delta=f"혼잡도: {parking_df['주차혼잡상태_텍스트'].mode().iloc[0]}"
    )
    st.header(f"🚗 고객님! 현재 조회된 주차장의 총 잔여석은 **{total_available_spots}**개 입니다! 🥳")

    # -----------------------------------------------------
    # 6. 최단 거리 안내 로직
    # -----------------------------------------------------
    
    st.subheader("📍 내 위치 기반 최단 거리 안내")
    
    # 1. 빈 주차장만 필터링
    available_spots_df = parking_df[parking_df['총잔여주차구획수'] > 0].copy()

    if available_spots_df.empty:
        st.warning("현재 주변에 잔여석이 있는 주차장이 없습니다. 잠시 후 다시 시도해 주세요.")
    else:
        # 2. 거리 계산 컬럼 추가
        available_spots_df['distance'] = available_spots_df.apply(
            lambda row: calculate_distance(user_lat, user_lon, row['lat'], row['lon']),
            axis=1
        )
        
        # 3. 거리가 가장 가까운 순으로 정렬하고 상위 5개 추출
        nearest_spots = available_spots_df.sort_values(by='distance').head(5)
        
        nearest_spots['거리 (근사치)'] = nearest_spots['distance'].apply(lambda x: f"{x:.6f}")
        
        st.success(f"📌 {nearest_spots.shape[0]}개의 가장 가까운 주차장을 찾았습니다!")
        
        # 4. 결과 테이블 표시
        st.dataframe(
            nearest_spots[[
                '주차장명',
                '총잔여주차구획수', 
                '주차혼잡상태_텍스트', 
                '거리 (근사치)'
            ]].rename(columns={
                '주차장명': '주차장 이름',
                '총잔여주차구획수': '잔여석',
                '주차혼잡상태_텍스트': '혼잡도'
            }),
            use_container_width=True
        )
        
        # 5. 지도에 결과 시각화
        user_map_data = pd.DataFrame({
            'lat': [user_lat], 
            'lon': [user_lon], 
            'size': 500, 
            'color': '#ff0000', 
            'name': '나의 위치'
        })
        
        spots_map_data = nearest_spots[['lat', 'lon']].copy()
        spots_map_data['size'] = 150 
        spots_map_data['color'] = '#00ff00' 
        spots_map_data['name'] = nearest_spots['주차장명']
        
        final_map_data = pd.concat([user_map_data, spots_map_data])
        
        st.map(final_map_data, latitude='lat', longitude='lon', color='color', size='size')


else:
    st.error("주차장 데이터를 불러오는 데 실패했습니다. 잠시 후 다시 시도해 주세요.")
