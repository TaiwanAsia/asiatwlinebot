from linebot.models import *
from datetime import datetime, timedelta, timezone
from models import db, Activities, Activities_routine
from app import app, line_bot_api
from sqlalchemy.sql import text
from sqlalchemy import delete, select
import time


def periodGuy(alertList, alerted):
    while True:
        dt1 = datetime.utcnow().replace(tzinfo=timezone.utc)
        now = dt1.astimezone(timezone(timedelta(hours=8))) # 轉換時區 -> 東八區
        nowdatetime = now.strftime("%Y-%m-%d %H:%M:%S")
        nowtime = now.strftime("%H:%M:%S")
        print('\n'+str(now))
        tmrdate = (now + timedelta(days=2)).strftime("%Y-%m-%d")

        if now.minute%5 == 0:
            clean_useless_actv() # 清除未新增完成的行程

        # 每日08:30推播當日行程
        if now.hour == 8 and now.minute == 30:
            user_acti = {}
            with app.app_context():
                # 刪除未完成的新增行程
                sql = f"DELETE FROM `activities` WHERE `status` IN ('日期待確認','待確認')"
                db.session.execute(sql)
                sql = f"DELETE FROM `activities_routine` WHERE `status` = 'ready'"
                db.session.execute(sql)

                # 抓取當日一次行程
                sql = f"SELECT * FROM activities WHERE time >= '{nowdatetime}' AND time < '{tmrdate} 00:00:00' AND status = '已確認'"
                Edata = db.session.execute(text(sql)).fetchall()

                # 抓取當日固定行程
                weekday = now.isoweekday()
                day     = now.day
                sql = f"SELECT * FROM activities_routine WHERE time >= '{nowtime}' AND `status` = 'finish' AND ((frequency = '每日') OR (frequency = '每週' AND frequency_2 = '{weekday}') OR (frequency = '每月' AND frequency_2 = '{day}')) AND time_format(`time`, '%%H:%%i') > '08:30:00'"
                AR = db.session.execute(text(sql)).fetchall()

            for event in Edata:
                if event[1] not in user_acti:
                    user_acti[event[1]] = ""
                user_acti[event[1]] += f"\n{event[2]}\n{event[3]}"

            for ARdata in AR:
                if ARdata[1] not in user_acti:
                    user_acti[ARdata[1]] = ""
                user_acti[ARdata[1]] += f"\n\n{ARdata[5]}\n{ARdata[2]}"

            print("\n每日推播")
            for ua in user_acti:
                line_bot_api.push_message(ua, TextSendMessage(text="金秘書跟您說早安！\n\n***今日事項***"+user_acti[ua]))

        Edata     = []
        AR        = []

        # 每10分鐘重置一次 alertList
        if now.minute%10 == 0:
            print("\n每10分刷新提醒List")
            alertList = []
            alerted = []
        
        with app.app_context():
            # 抓取當日一次行程
            sql = f"SELECT * FROM activities WHERE time >= '{nowdatetime}' AND time < '{tmrdate} 00:00:00' AND status IN ('已確認','已提醒1')"
            Edata = db.session.execute(text(sql)).fetchall()

            # 抓取當日固定行程
            weekday = now.isoweekday()
            day     = now.day
            sql = f"SELECT * FROM activities_routine WHERE time_to_sec(TIMEDIFF(`time`,'{nowtime}'))/60 > 0 AND time_to_sec(TIMEDIFF(`time`,'{nowtime}'))/60 <= 3 AND `status` = 'finish' AND ((frequency = '每日') OR (frequency = '每週' AND frequency_2 = '{weekday}') OR (frequency = '每月' AND frequency_2 = '{day}'))"
            AR = db.session.execute(text(sql)).fetchall()
            
            
        for event in Edata:
            if [event[0], event[1], event[2], event[3], event[4], '單次'] not in alertList:
                alertList.append([event[0], event[1], event[2], event[3], event[4], '單次'])

        for ARdata in AR:
            if [ARdata[0], ARdata[1], ARdata[2], ARdata[3], ARdata[4], ARdata[5], ARdata[6], ARdata[7], '固定'] not in alertList:
                alertList.append([ARdata[0], ARdata[1], ARdata[2], ARdata[3], ARdata[4], '固定', ARdata[5], ARdata[6], ARdata[7]])
        
        for idx, event in enumerate(alertList):

            # 60分鐘前開始第一次提醒，10分鐘前開始第二提醒
            if event[5] == '單次':

                Eid        = event[0]
                Euserid    = event[1]
                Edatetime  = event[2]
                Etitle     = event[3]
                Euserreply = event[4]

                now_naive = now.replace(tzinfo=None)

                lastMinute = ((Edatetime - now_naive).total_seconds())/60

                if (lastMinute <= 60 and lastMinute >= 50 and Euserreply == "已確認") or (lastMinute < 10 and lastMinute >= 0 and (Euserreply == "已確認" or Euserreply == "已提醒1")):
                    print("\n行程ID: " + str(Eid) + " Bingo!")

                    buttons_template_message = TemplateSendMessage(
                        alt_text='關閉提醒按鈕樣版',
                        template=ButtonsTemplate(
                            thumbnail_image_url='https://img95.699pic.com/xsj/0y/bg/5p.jpg!/fw/700/watermark/url/L3hzai93YXRlcl9kZXRhaWwyLnBuZw/align/southeast',
                            image_aspect_ratio='rectangle',
                            image_size='cover',
                            image_background_color='#FFFFFF',
                            title= f"{Edatetime}",
                            text= f"{Etitle}",
                            default_action=URIAction(
                                label='view detail',
                                uri='http://example.com/page/123'
                            ),
                            actions=[
                                MessageAction(
                                    label = "關閉提醒",
                                    text  = f"OK{Eid}"
                                )
                            ]
                        )
                    )
                    line_bot_api.push_message(Euserid, buttons_template_message)

            # 固定行程在db選取時，已選取三分鐘內行程
            if event[5] == '固定':
                Eid         = event[0]
                Euserid     = event[1]
                Etitle      = event[2]
                Efrequency  = event[3]
                Efrequency2 = event[4]
                Etime       = event[6]
                Eenddate    = event[7]
                Estatus     = event[8]
                Etype       = event[5]

                print("Alerted\n", alerted)
                if Estatus == "finish" and (alerted.count(Eid) <= 3):

                    print(f"\n ------------ 固定行程提醒 ID: {Eid} ------------")

                    buttons_template_message = TemplateSendMessage(
                        alt_text='關閉提醒按鈕樣版',
                        template=ButtonsTemplate(
                            thumbnail_image_url='https://metrifit.com/wp-content/uploads/2020/01/shutterstock_1306931836-e1579713194166.jpg',
                            image_aspect_ratio='rectangle',
                            image_size='cover',
                            image_background_color='#FFFFFF',
                            title= f"{Etitle}",
                            text= f"{Efrequency + Efrequency2} {Etime}",
                            default_action=URIAction(
                                label='view detail',
                                uri='http://example.com/page/123'
                            ),
                            actions=[
                                PostbackAction(
                                    label = "我知道了",
                                    display_text = "我知道了",
                                    data = f'shutup&{idx}'
                                ),
                            ]
                        )
                    )
                    line_bot_api.push_message(Euserid, buttons_template_message)

                    alerted.append(Eid)

        print("\n今日提醒事項: ")
        print(alertList)

        time.sleep(57)


def clean_useless_actv():
    with app.app_context():
        # targets = db.session.execute(db.select(Activities).filter_by(status='日期待確認')).fetchall()

        # Activities
        stmt = delete(Activities).where(Activities.status.in_(["日期待確認", "待確認"]))
        db.session.execute(stmt)
        db.session.commit()

        # Activities_routine
        stmt = delete(Activities_routine).where(Activities_routine.status.in_(["ready"]))
        db.session.execute(stmt)
        db.session.commit()
        