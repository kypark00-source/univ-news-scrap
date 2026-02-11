import re
import json
import time
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import date, datetime, timedelta

import streamlit as st
import pandas as pd
import requests

# =========================
# 1. 경로 및 설정 관리 (웹 버전 최적화)
# =========================
# 웹 환경에서는 현재 작업 디렉토리를 기준으로 설정 파일을 잡습니다.
SETTINGS_PATH = Path("news_settings.json")

DEFAULT_SETTINGS = {
    "schools": ["고려대", "동국대", "연세대", "성균관대", "가천대", "건국대", "경기대"],
    "keywords": ["장학금", "발전기금", "기부", "후원", "기금", "모금"]
}

def load_settings():
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except:
            pass
    return DEFAULT_SETTINGS

def save_settings(data):
    # 웹 서버 환경에서도 파일 쓰기가 가능하도록 설정
    try:
        SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except:
        st.error("설정 파일 저장 중 오류가 발생했습니다. (권한 문제일 수 있습니다)")

# 세션 상태에 설정 로드
if 'config' not in st.session_state:
    st.session_state.config = load_settings()

# =========================
# 2. 뉴스 검색 엔진
# =========================
def fetch_news(keyword, start_date, end_date):
    encoded_kw = requests.utils.quote(keyword)
    rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=ko&gl=KR&ceid=KR:ko"
    results = []
    try:
        resp = requests.get(rss_url, timeout=10)
        root = ET.fromstring(resp.text)
        for item in root.findall('.//item'):
            title = item.find('title').text
            link = item.find('link').text
            pub_date_raw = item.find('pubDate').text[:16]
            try:
                pub_date = pd.to_datetime(pub_date_raw).date()
            except:
                continue

            if start_date <= pub_date <= end_date:
                results.append({"date": pub_date, "title": title, "link": link})
    except:
        pass
    return results

# =========================
# 3. UI 구성 (Streamlit)
# =========================
st.set_page_config(page_title="대학 뉴스 스크랩 매니저", layout="wide")
st.title("📰 대학 뉴스 통합 검색 및 관리 시스템")

# --- 사이드바 영역 ---
with st.sidebar:
    st.header("⚙️ 검색 및 필터 설정")

    # 키워드 편집
    kw_input = st.text_area("🔍 검색 키워드 (쉼표 구분)",
                            value=", ".join(st.session_state.config["keywords"]),
                            help="구글 뉴스에서 검색할 단어들을 입력하세요.")

    # 학교 편집
    sch_input = st.text_area("🏫 필터링 학교명 (쉼표 구분)",
                             value=", ".join(st.session_state.config["schools"]),
                             help="수집된 기사 중 이 이름이 포함된 것만 골라냅니다.")

    if st.button("✅ 설정 저장하기", use_container_width=True):
        st.session_state.config["keywords"] = [x.strip() for x in kw_input.split(",") if x.strip()]
        st.session_state.config["schools"] = [x.strip() for x in sch_input.split(",") if x.strip()]
        save_settings(st.session_state.config)
        st.success("설정이 저장되었습니다!")

    st.divider()

    # 기간 설정
    st.subheader("🗓️ 기간 선택")
    st_d = st.date_input("시작일", value=date.today() - timedelta(days=14))
    en_d = st.date_input("종료일", value=date.today())

# --- 시스템 종료 안내 ---
st.sidebar.markdown("<br>" * 5, unsafe_allow_html=True)
st.sidebar.divider()

if st.sidebar.button("❌ 프로그램 종료 안내", help="웹 버전은 브라우저 탭을 닫으면 종료됩니다.", use_container_width=True):
    st.balloons()
    st.error("웹 버전은 서버를 직접 끌 수 없습니다. 브라우저 탭을 직접 닫아주세요!")
    st.info("이 주소를 즐겨찾기 해두시면 언제든 다시 접속하실 수 있습니다.")

# =========================
# 4. 메인 실행 영역
# =========================
if st.button("🚀 뉴스 수집 및 필터링 시작", type="primary", use_container_width=True):
    schools = st.session_state.config["schools"]
    includes = st.session_state.config["keywords"]

    all_raw = []
    status = st.empty()

    for kw in includes:
        status.info(f"현재 '{kw}' 관련 기사들을 수집하고 있습니다...")
        all_raw.extend(fetch_news(kw, st_d, en_d))

    if all_raw:
        df_all = pd.DataFrame(all_raw).drop_duplicates(subset=["link"])

        final_list = []
        for _, row in df_all.iterrows():
            matched_school = next((s for s in schools if s in row['title']), None)
            if matched_school:
                row_dict = row.to_dict()
                row_dict['school'] = matched_school
                final_list.append(row_dict)

        if final_list:
            df = pd.DataFrame(final_list).sort_values(by="date", ascending=False)
            status.success(f"검색 완료! 총 {len(df)}건의 대학 관련 뉴스를 찾았습니다.")

            for i, r in df.iterrows():
                with st.container():
                    col_info, col_btn = st.columns([8, 2])
                    with col_info:
                        st.markdown(f"#### {r['title']}")
                        st.caption(f"📅 날짜: {r['date']} | 🏫 학교: {r['school']}")
                    with col_btn:
                        st.link_button("기사 보기 🔗", r['link'], use_container_width=True)
                st.divider()

            csv_data = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button("⬇️ 검색 결과 CSV로 저장", csv_data, f"news_report_{date.today()}.csv")
        else:
            status.warning("기사는 찾았으나 지정하신 학교명이 포함된 뉴스가 없습니다.")
    else:
        status.error("해당 기간 내에 검색된 기사가 없습니다.")
