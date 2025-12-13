# app.py (최종 - 버그 방지 로직 및 실제 API 정보 반영)

import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
import random 
import json 

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
API_ENDPOINT = "https://api.odcloud.kr/api/15150101/v1/uddi:1ddc788e-fdd8-4255-9e6d-a8f260dc20db" 

# 📌 2. 실제 발급받은 인증키 적용
SERVICE_KEY = "6d3fcec1cb59910225aa7de9c79def31b2102379f73dc40baa7130a8fac4c1e3" 

# -----------------------------------------------------
# 시뮬레이션 데이터 함수 (API 호출 실패 시 대비)
# -----------------------------------------------------
def simulate_api_data():
    """API 호출 실패 시 임시로 사용할 가상 주차장 데이터 생성."""
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
    
    # 🌟 API 요청에 필요한 파라미터 정의 (400 오류 해결을 위해 명세서와 1:1 일치 확인)
    params = {
        'serviceKey': SERVICE_KEY,
        'page': '1',
        'perPage': '100',
        'returnType': 'JSON' 
    }
    
    try:
        # 1. 실제 API에 GET 요청
        response = requests.get(API_ENDPOINT, params=params, timeout=10)
        response.raise_for_status() # 400 Bad Request 발생 시 여기서 예외 처리
        
        # 2. JSON 데이터 파싱
        json_data = response.json()
        
        # 3. 데이터가 담긴 'data' 배열 추출 (명세서의 구조 반영)
        data_list = json_data.get('data', [])

        if not data_list:
             st.warning("API 응답에 데이터가 없습니다. 시뮬레이션 데이터를 사용합니다.")
             return simulate_api_data()
             
        parking_df = pd.DataFrame(data_list)
        
        # 4. 데이터프레임 컬럼 정리 및 타입 변환 (명세서 필드명 사용)
        
        # 잔여석 및 총구획수 변환
        for col in ['총잔여주차구획수', '총주차구획수', '주차혼잡상태']:
            parking_df[col] = pd.to_numeric(parking_df.get(col, 0), errors='coerce').fillna(0).astype(int)
        
        # 주차 혼잡 상태 텍스트 매핑
        status_map = {0: '여유', 1: '보통', 2: '혼잡', 3: '만차'}
        parking_df['주차혼잡상태_텍스트'] = parking_df['주차혼잡상태'].map(status_map).fillna('알 수 없음')

        # ⭐️⭐️⭐️ [지도 시각화 안정성 강화 로직] ⭐️⭐️⭐️
        # API에 위도/경도 필드가 직접 없는 경우를 대비해, 잠재적인 필드명을 'lat'/'lon'으로 변환 시도
        
        # 1) 일반적인 공공 API 좌표 필드명으로 변환 시도
        coordinate_mapping = {
            'PRK_LTTD': 'lat',      # 주차장 위도 (예시)
            'PRK_LGTT': 'lon',      # 주차장 경도 (예시)
            'lat': 'lat',           # 이미 lat/lon인 경우
            'lon': 'lon'
        }
        
        # 컬럼 이름 변경 및 숫자형 변환 시도
        renamed_cols = {}
        for api_col, df_col in coordinate_mapping.items():
            if api_col in parking_df.columns:
                renamed_cols[api_col] = df_col
                
        parking_df = parking_df.rename(columns=renamed_cols)

        # 2) 위도/경도 필드가 있으면 숫자형으로 변환
        if 'lat' in parking_df.columns and 'lon' in parking_df.columns:
            parking_df['lat'] = pd.to_numeric(parking_df['lat'], errors='coerce')
            parking_df['lon'] = pd.to_numeric(parking_df['lon'], errors='coerce')
        else:
             # 3) 위도/경도 컬럼이 전혀 없으면 시뮬레이션 데이터를 사용하여 채움
            st.warning("위도/경도 정보가 없어 지도 시각화에 제약이 있습니다. 임시 좌표를 사용합니다.")
            sim_df = simulate_api_data()
            parking_df['lat'] = sim_df['lat']
            parking_df['lon'] = sim_df['lon']
            
        return parking_df
        
    except requests.exceptions.RequestException as e:
        # 400 Bad Request를 포함한 모든 요청 오류 처리
        st.error(f"API 호출 실패 (네트워크/서버 오류): {e}. API 키, 엔드포인트, 파라미터 구성을 다시 확인하십시오.")
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
        
        # 1. 데이터 가져오기 (실제 API 호출 시도)
        parking_df = fetch_parking_data_from_api()
        
        if parking_df is not None and not parking_df.empty:
            
            # 2. 현황 계산
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
                    # 최빈값(mode)을 사용하여 대표 혼잡도 표시
                    delta=f"혼잡도: {parking_df['주차혼잡상태_텍스트'].mode().iloc[0]}"
                )

            # 텍스트 알림
            st.header(f"🚗 고객님! 현재 조회된 주차장의 총 잔여석은 **{total_available_spots}**개 입니다! 🥳")

            # 4. 지도 시각화 업데이트 
            st.subheader("📍 주차장 위치 시각화")
            
            # lat/lon이 유효한 행만 추출
            map_data = parking_df.dropna(subset=['lat', 'lon'])
            
            if not map_data.empty:
                st.map(map_data, latitude='lat', longitude='lon', size=15)
            else:
                 st.warning("지도 시각화에 필요한 유효한 위도/경도 데이터가 없어 지도를 표시할 수 없습니다.")

            # 5. 사용자 위치 기반 안내 (다음 단계 구현 예정)
            st.subheader("🔍 가까운 빈자리 안내 (다음 단계 기능)")
            st.markdown("사용자의 위치를 분석해 가장 가까운 주차장을 찾아 안내하는 로직이 추가될 예정입니다.")
            
        else:
            st.error("주차장 데이터를 불러오는 데 실패했습니다. 잠시 후 다시 시도해 주세요.")

    # 6. 다음 업데이트까지 잠시 대기
    time.sleep(5)
