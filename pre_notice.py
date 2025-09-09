from datetime import datetime
from solapi import SolapiMessageService
from common import *

API_URL = "https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService/getPublicPrcureThngInfoServcPPSSrch"

def format_pre_message(item):
    """사전공고 메시지 포맷"""
    return (
        f"[사전 공고 알림]\n"
        f"■ 사업명: {item.get('prdctClsfcNoNm')}\n"
        f"■ 등록번호: {item.get('bfSpecRgstNo')}\n"
        f"■ 수요기관: {item.get('rlDminsttNm')}\n"
        f"■ 배정예산금액: {int(item.get('asignBdgtAmt', 0)):,}원\n"
        f"■ 접수일시: {item.get('rcptDt')}\n"
        f"■ 의견등록마감일시: {item.get('opninRgstClseDt')}\n"
    )

def format_pre_log(item):
    """사전공고 로그 포맷"""
    return (
        f"사전 공고 | "
        f"사업명='{item.get('prdctClsfcNoNm')}', "
        f"등록번호={item.get('bfSpecRgstNo')}, "
        f"수요기관='{item.get('rlDminsttNm')}', "
        f"배정예산금액='{item.get('asignBdgtAmt')}', "
        f"접수일시={item.get('rcptDt')}"
        f"의견등록마감일시={item.get('opninRgstClseDt')}"
    )

def main():
    """사전공고 알림 서비스 실행"""

    # 환경변수 로딩
    env_vars = load_environment()

    # CoolSMS API 설정
    message_service = SolapiMessageService(
        api_key=env_vars['coolsms_api_key'],
        api_secret=env_vars['coolsms_api_secret']
    )

    # 데이터 로딩
    sent_data = load_sent_data()
    users = load_users()

    # 배치 시간 구간 계산
    now = datetime.now()
    # now = datetime.strptime("202508111900", "%Y%m%d%H%M") # 테스트용 시간 지정
    print(f"현재 시각: {now}")
    inqry_bgn_dt, inqry_end_dt = get_batch_time_ranges(now)
    print(f"[배치 요청 시간 범위] {inqry_bgn_dt} ~ {inqry_end_dt}")

    total_notifications = 0

    # 사용자별 키워드 기반 API 요청
    for user in users:
        name = user['name']
        phone = user['phone']
        search_conditions = user.get('search_conditions', [])

        pre_conditions = [c for c in search_conditions if c.get('type') == 'pre']

        if not pre_conditions:
            print(f"[{name}] 사전공고 검색 조건이 없습니다.")
            continue

        if name not in sent_data:
            sent_data[name] = {"bid_notices": [], "pre_notices": [], "award_notices": []}

        user_sent = sent_data[name].get('pre_notices', [])

        # 각 조건에 대해 API 요청 실행
        for condition in pre_conditions:
            keyword = condition.get('keyword')
            notice_org = condition.get('notice_org')
            demand_org = condition.get('demand_org')

            if not (keyword or notice_org or demand_org):
                print(f"[{name}] 검색 조건이 없어 건너뜀")
                continue

            # API 요청 파라미터 구성
            params = {
                "ServiceKey": env_vars['service_key'],
                "pageNo": 1,
                "numOfRows": 100,
                "inqryDiv": 1,
                "inqryBgnDt": inqry_bgn_dt,
                "inqryEndDt": inqry_end_dt,
                "type": "json"
            }

            # 검색 조건 파라미터 추가
            if keyword:
                params["prdctClsfcNoNm"] = keyword
            if notice_org:
                params["ntceInsttNm"] = notice_org
            if demand_org:
                params["dminsttNm"] = demand_org

            # 검색 조건 설명 생성
            search_desc = build_search_description(keyword, notice_org, demand_org)

            # API 요청 및 응답 처리
            items = make_api_request(API_URL, params, name, search_desc)

            if items is None or not items:
                print("-" * 40)
                continue

            # 결과가 5개 초과인 경우 제한 메시지 전송
            if check_result_limit_and_notify(items, message_service, env_vars['coolsms_sender'], phone, search_desc):
                print("-" * 40)
                continue

            # 알림 처리
            new_notices = 0
            for i, item in enumerate(items, start=1):
                bid_no = item.get("bfSpecRgstNo")

                # 중복 알림 방지
                if bid_no in user_sent:
                    continue

                # 메시지 내용 구성 및 발송
                msg_text = format_pre_message(item)
                print(format_pre_log(item))

                if send_message(message_service, env_vars['coolsms_sender'], phone, msg_text):
                    user_sent.append(bid_no)
                    new_notices += 1

            # 결과 출력
            if new_notices == 0:
                print("모든 결과는 이미 알림 발송됨.")

            total_notifications += new_notices
            print("-" * 40)

        # 사용자별 발송 이력 업데이트
        sent_data[name]['pre_notices'] = user_sent

    # 전체 발송 이력 저장
    save_sent_data(sent_data)
    print(f"* 총 {total_notifications} 건의 새로운 사전공고 알림 발송\n")

if __name__ == "__main__":
    main()