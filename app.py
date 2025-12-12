# app.py

import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
import random 

# -----------------------------------------------------
# 1. 페이지 설정 및 제목
# -----------------------------------------------------
st.set_page_config(
    page_title="🅿️ 실시간 빈자리 알림 서비스",
    layout="wide"
)

st.title("🅿️ 스마트 주차 안내 시스템: 공공 주차장 실시간 확인!")
st.markdown("""
이 앱은 공공데이터포털의 주차장 실시간 정보 API 연동을 위한 구조로 설계되었습니다.
---
""")

# -----------------------------------------------------
# 2. API 엔드포인트 및 키 설정
# -----------------------------------------------------

# 📌 1. API 엔드포인트: 한국교통안전공단_주차장실시간정보 API 주소
API_ENDPOINT = "http://apis.data.go.kr/B553881/Parking/PrkSttusInfo" 

# 📌 2. 발급받은 실제 인증키를 여기에 넣으세요!
# 현재는 임시로 대체합니다.
SERVICE_KEY = "YOUR_SERVICE_KEY_HERE" 

# --- 시뮬레이션 데이터 생성 함수 (API 호출 실패 시 사용) ---
def simulate_api_data():
    """API 호출 실패 시 임시로 사용할 가상 주차장 데이터 생성."""
    base_lat = 37.5665; base_lon = 126.9780; num_spots = 100 # 100개 주차장 가정
    
    df = pd.DataFrame({
        'lat': np.random.randn(num_spots) * 0.005 + base_lat,
        'lon': np.random.randn(num_spots) * 0.007 + base_lon,
        'prk_name': [f'공영주차장-{i+1:02d}' for i in range(num_spots)],
        'available_spots': np.random.randint(0, 500, size=num_spots) # 잔여석 0~500개 무작위 생성
    })
    return df
# -----------------------------------------------------

def fetch_parking_data_from_api():
    """공공데이터 API를 호출하여 주차 데이터를 가져옵니다. 실패 시 시뮬레이션 데이터를 반환합니다."""
    
    if SERVICE_KEY == "YOUR_SERVICE_KEY_HERE":
        st.warning("⚠️ 실제 API 키가 없어 시뮬레이션 데이터를 사용합니다. `SERVICE_KEY`를 설정해 주세요.")
        return simulate_api_data()
        
    # 🌟 API 요청에 필요한 파라미터 정의
    params = {
        'serviceKey': SERVICE_KEY,
        'pageNo': '1',
        'numOfRows': '100',
        '_type': 'json'
    }
    
    try:
        # 1. 실제 API에 GET 요청
        response = requests.get(API_ENDPOINT, params=params, timeout=10)
        response.raise_for_status() 
        
        # 2. JSON 데이터 파싱
        json_data = response.json()
        
        # 3. 데이터가 담긴 실제 리스트 경로를 찾아 DataFrame으로 변환
        # (API 응답 구조에 따라 이 'items' 경로는 반드시 수정해야 할 수 있습니다!)
        data_list = json_data.get('response', {}).get('body', {}).get('items', {}).get('item', [])

        if not data_list:
             st.warning("API에서 유효한 데이터를 가져오지 못했습니다. 시뮬레이션 데이터를 사용합니다.")
             return simulate_api_data()
             
        parking_df = pd.DataFrame(data_list)
        
        # 4. 데이터프레임 컬럼 정리 (API 필드명에 맞게 변경하는 예시)
        # 📌 실제 API 컬럼명에 따라 'lat', 'lon', 'available_spots'로 컬럼명을 맞춰야 합니다.
        parking_df = parking_df.rename(columns={
            'lat_column_name_from_api': 'lat',      # 실제 API의 위도 컬럼명
            'lon_column_name_from_api': 'lon',      # 실제 API의 경도 컬럼명
            'available_column_name_from_api': 'available_spots' # 실제 API의 잔여석 컬럼명
        })
        
        # 잔여석 컬럼을 정수형으로 변환
        parking_df['available_spots'] = pd.to_numeric(parking_df.get('available_spots', 0), errors='coerce').fillna(0).astype(int)

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
        
        # 1. 데이터 가져오기 (API 호출 시도)
        parking_df = fetch_parking_data_from_api()
        
        if parking_df is not None and not parking_df.empty:
            
            # 2. 현황 계산
            total_parking_lots = len(parking_df)
            total_available_spots = parking_df['available_spots'].sum()
            
            # 3. Streamlit 컴포넌트 업데이트
            st.subheader(f"✅ 데이터 갱신 시간: {time.strftime('%H:%M:%S')}")
            
            # 현황 메트릭 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="조회된 주차장 수", value=f"{total_parking_lots}개")
            with col2:
                st.metric(label="총 주차 구획 수 (추정)", value="API 정보 필요") 
            with col3:
                st.metric(
                    label="✅ 실시간 빈자리 수 (합산)", 
                    value=f"{total_available_spots}개"
                )

            # 텍스트 알림
            st.header(f"🚗 고객님! 현재 조회된 공영 주차장의 총 잔여석은 **{total_available_spots}**개 입니다! 🥳")

            # 4. 지도 시각화 업데이트
            st.subheader("📍 주차장 위치 시각화")
            st.markdown("**(조회된 공영 주차장 위치를 표시합니다)**")

            # 위도/경도 컬럼이 유효한지 확인하고 지도 표시
            map_data = parking_df.dropna(subset=['lat', 'lon'])
            
            if not map_data.empty:
                st.map(map_data, latitude='lat', longitude='lon', size=15)
            else:
                 st.warning("지도 시각화에 필요한 위도/경도 데이터가 유효하지 않습니다.")

            # 5. 사용자 위치 기반 안내 (다음 단계 구현 예정)
            st.subheader("🔍 가까운 빈자리 안내 (다음 단계 기능)")
            st.markdown("사용자의 위치를 분석해 가장 가까운 주차장을 찾아 안내하는 로직이 추가될 예정입니다.")
            
        else:
            st.error("주차장 데이터를 불러오는 데 실패했습니다. 잠시 후 다시 시도해 주세요.")

    # 6. 다음 업데이트까지 잠시 대기
    time.sleep(5)
