# app.py (최종 - 실제 API 키 및 구조 반영)

import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
import random 
import json # JSON 응답 처리 명확화를 위해 추가

# -----------------------------------------------------
# 1. 페이지 설정 및 제목
# -----------------------------------------------------
st.set_page_config(
    page_title="🅿️ 주차장 실시간 정보 - 공공 데이터 연동",
    layout="wide"
)

st.title("🅿️ 스마트 주차 안내 시스템: 공공 주차장 실시간 확인!")
st.markdown("""
이 앱은 한국교통안전공단 주차장 실시간 정보 API와 연동된 구조로 작동합니다.
---
""")

# -----------------------------------------------------
# 2. API 엔드포인트 및 키 설정 (제공받은 실제 정보 반영)
# -----------------------------------------------------

# 📌 1. API 엔드포인트: 명세서 기반으로 정확히 구성
# Host + Base Path + Endpoint
API_ENDPOINT = "https://api.odcloud.kr/api/15150101/v1/uddi:1ddc788e-fdd8-4255-9e6d-a8f260dc20db" 

# 📌 2. 실제 발급받은 인증키 적용
SERVICE_KEY = "6d3fcec1cb59910225aa7de9c79def31b2102379f73dc40baa7130a7fac4c1e3" 

# -----------------------------------------------------
# 시뮬레이션 데이터 함수 (API 호출 실패 시 대비)
# -----------------------------------------------------
def simulate_api_data():
    base_lat = 37.5665; base_lon = 126.9780; num_spots = 100 
    df = pd.DataFrame({
        'lat': np.random.randn(num_spots) * 0.005 + base_lat,
        'lon': np.random.randn(num_spots) * 0.007 + base_lon,
        'prk_name': [f'공영주차장-{i+1:02d}' for i in range(num_spots)],
        '총잔여주차구획수': np.random.randint(0, 500, size=num_spots),
        '총주차구획수': np.random.randint(500, 1000, size=num_spots)
    })
    return df
# -----------------------------------------------------


def fetch_parking_data_from_api():
    """실제 공공데이터 API를 호출하여 주차장 데이터를 가져옵니다."""
    
    # 🌟 API 요청에 필요한 파라미터 정의 (명세서의 Query Parameter 반영)
    params = {
        'serviceKey': SERVICE_KEY,
        'page': '1',
        'perPage': '100',          # 한 번에 가져올 데이터 수 (최대 100개)
        'returnType': 'JSON'       # JSON 형식 요청
    }
    
    try:
        # 1. 실제 API에 GET 요청 (timeout 설정으로 안정성 확보)
        response = requests.get(API_ENDPOINT, params=params, timeout=10)
        response.raise_for_status() # HTTP 오류(4xx, 5xx) 발생 시 예외 발생
        
        # 2. JSON 데이터 파싱
        json_data = response.json()
        
        # 3. 데이터가 담긴 'data' 배열 추출 (명세서의 구조 반영)
        data_list = json_data.get('data', [])

        if not data_list:
             st.warning("API에서 유효한 데이터를 가져오지 못했습니다. 시뮬레이션 데이터를 사용합니다.")
             return simulate_api_data()
             
        parking_df = pd.DataFrame(data_list)
        
        # 4. 데이터프레임 컬럼 정리 및 타입 변환
        # 잔여석 및 총구획수를 정수형으로 변환
        for col in ['총잔여주차구획수', '총주차구획수']:
             # API 명세서에 따르면 이 필드는 정수형이므로, 변환을 시도합니다.
            parking_df[col] = pd.to_numeric(parking_df.get(col, 0), errors='coerce').fillna(0).astype(int)
        
        # ⚠️ 공공 API 응답에는 위도(lat)와 경도(lon) 필드가 직접 포함되어 있지 않을 수 있습니다. 
        # (별도의 API를 통해 주소로 좌표를 변환해야 할 수 있음)
        # 현재는 지도 시각화를 위해 'lat'과 'lon' 컬럼이 이미 있다고 가정하거나 시뮬레이션 데이터에 의존합니다.
        
        # 주차 혼잡 상태를 문자열로 매핑하여 보여줄 수 있음
        status_map = {0: '여유', 1: '보통', 2: '혼잡', 3: '만차'}
        parking_df['주차혼잡상태_텍스트'] = parking_df['주차혼잡상태'].map(status_map)

        return parking_df
        
    except requests.exceptions.RequestException as e:
        st.error(f"API 호출 실패 (네트워크/서버 오류): {e}")
        return simulate_api_data() 
    
    except Exception as e:
        st.error(f"데이터 처리 오류: {e}")
        return simulate_api_data()

# -----------------------------------------------------
# 3. 실시간 업데이트 컨테이너 설정 및 루프 시작
# -----------------------------------------------------

realtime_container = st.empty()

# 5초마다 업데이트
while True:
    with realtime_container.container():
        
        # 1. 데이터 가져오기 (실제 API 호출)
        parking_df = fetch_parking_data_from_api()
        
        if parking_df is not None and not parking_df.empty:
            
            # 2. 현황 계산 (명세서의 필드명 사용)
            total_parking_lots = len(parking_df)
            total_available_spots = parking_df['총잔여주차구획수'].sum()
            total_max_spots = parking_df['총주차구획수'].sum()
            
            # 3. Streamlit 컴포넌트 업데이트
            st.subheader(f"✅ 데이터 갱신 시간: {time.strftime('%H:%M:%S')}")
            
            # 현황 메트릭 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="조회된 주차장 수", value=f"{total_parking_lots}개")
            with col2:
                st.metric(label="총 주차 구획 수", value=f"{total_max_spots}개") 
            with col3:
                st.metric(
                    label="✅ 실시간 빈자리 수 (합산)", 
                    value=f"{total_available_spots}개",
                    delta_color="normal",
                    delta=f"혼잡도: {parking_df['주차혼잡상태_텍스트'].mode().iloc[0] if '주차혼잡상태_텍스트' in parking_df.columns else '알 수 없음'}"
                )

            # 텍스트 알림
            st.header(f"🚗 고객님! 현재 조회된 주차장의 총 잔여석은 **{total_available_spots}**개 입니다! 🥳")

            # 4. 지도 시각화 업데이트 (위도/경도 데이터의 존재 여부에 따라 시각화)
            st.subheader("📍 주차장 위치 시각화")
            
            # ⚠️ 위도/경도 컬럼명이 실제 API에 있는지 확인 후 시각화
            # 현재는 필드가 없다고 가정하고 시뮬레이션 데이터의 lat/lon을 사용하여 지도 표시
            
            if 'lat' in parking_df.columns and 'lon' in parking_df.columns and not parking_df.dropna(subset=['lat', 'lon']).empty:
                st.map(parking_df.dropna(subset=['lat', 'lon']), latitude='lat', longitude='lon', size=15)
            else:
                 st.warning("지도 시각화에 필요한 위도/경도 데이터가 현재 API 응답에 없습니다. (주소 변환 API 필요)")

            # 5. 사용자 위치 기반 안내 (다음 단계 구현 예정)
            st.subheader("🔍 가까운 빈자리 안내 (다음 단계 기능)")
            st.markdown("사용자의 위치를 분석해 가장 가까운 주차장을 찾아 안내하는 로직이 추가될 예정입니다.")
            
        else:
            st.error("주차장 데이터를 불러오는 데 실패했습니다. 잠시 후 다시 시도해 주세요.")

    # 6. 다음 업데이트까지 잠시 대기
    time.sleep(5)
