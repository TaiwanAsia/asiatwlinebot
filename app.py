from flask import Flask, request, abort
from flask_migrate import Migrate
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc
from sqlalchemy.sql import text
from imgurpython import ImgurClient
import re, json, threading
from datetime import datetime, timedelta, timezone
from common import get_user, get_group, check_chatroom_uploads_folder, get_uploads_file, get_stored_docs_by_chatroom, upload_docs
from models import db, Activities, Activities_routine, Notes, Group, User, Docs


app = Flask(__name__)


# 匯入設定
import config
line_bot_api = LineBotApi(config.line_bot_api)
handler = WebhookHandler(config.handler)
app.config['SQLALCHEMY_DATABASE_URI'] = config.app_config
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    'connect_args': {
        'connect_timeout': 10
    },
    "pool_recycle": 1
     # MySQL (and MariaDB) servers are configured to drop connections that have been idle for 8 hours,
     # which can result in an error like 2013: Lost connection to MySQL server during query.
     # A default pool_recycle value of 2 hours (7200 seconds) is used to recreate connections before that timeout.
}



db.init_app(app)

# Imgur
imgur_client_id     = 'de1eaec338fc230'
imgur_client_secret = 'a4bed7e222664343dd71151eb97f3952e1cf7bd9'
imgur_access_token  = 'f7f66bd26a9447435edddc02146e0aa3d6fc4a5e'
imgur_refresh_token = 'f152d59b47d908344eea63821004b420544712ae'
imgur_album_id      = 'HLxMNTE'
client = ImgurClient(imgur_client_id, imgur_client_secret, imgur_access_token, imgur_refresh_token)
# local_img_file      = f'./uploads/Cd3929322489fb8d23b071b0d53589248/17665313608328.png'
# image  = upload_docs(client, local_img_file, imgur_album_id)
# print(f"圖片網址: {image['link']}")




# [id, userid, date, activity, userreply] 
# 當 userreply=0 則每分鐘繼續提醒; userreply=1 則停止提醒(從清單移除)
global alertList, alerted
alertList = []
alerted   = []
from realtime import periodGuy





# ============開機推播============
# with app.app_context():
#     sql = "SELECT DISTINCT userid FROM activities"
#     Edata = db.session.execute(text(sql)).fetchall()
#     list2 = []
#     for event in Edata:
#         list2.append(event[0])
    # reply = "金秘書跟您說早安！\n試著直接輸入行程名稱或點選下方選單開始使用～"
    # reply = "小秘書升級中～請稍後！"
    # print(reply)
    # line_bot_api.multicast(list2, TextSendMessage(text=reply))
# ============開機推播============




# 監測
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'


# Message event: File處理
@handler.add(MessageEvent, message=FileMessage)
def handler_message(event):
    user = get_user(event.source.user_id)
    if event.source.type == 'group':
        group = get_group(event.source.group_id)
        chatroom    = group
        chatroom_id = group.group_id
    else:
        chatroom    = user
        chatroom_id = user.user_id
        
    if chatroom.file_reply == 'off':
        return
    else:
        # add_log(chatroom, 'upload file', str(event.message))
        content = line_bot_api.get_message_content(event.message.id)
        check_chatroom_uploads_folder(chatroom_id)
        path = './uploads/' + chatroom_id + '/' + event.message.file_name
        if os.path.exists(path):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="此檔名已存在。"))
            raise FileExistsError("此檔名已存在。")
        try:
            with open(path, 'wb') as fd:
                for chunk in content.iter_content():
                    fd.write(chunk)
        except Exception as e:
            print('發生錯誤', e)
        finally:
            print("儲存結束")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="文件已儲存。"))
        return

# Message event: Image處理
@handler.add(MessageEvent, message=ImageMessage)
def handle_message(event):
    user = get_user(event.source.user_id)
    if event.source.type == 'group':
        group = get_group(event.source.group_id)
        chatroom    = group
        chatroom_id = group.group_id
    else:
        chatroom    = user
        chatroom_id = user.user_id
    if chatroom.file_reply == 'off':
        return
    else:
        # add_log(chatroom, 'upload file', str(event.message))
        content = line_bot_api.get_message_content(event.message.id)
        check_chatroom_uploads_folder(chatroom_id)
        path = './uploads/' + chatroom_id + '/' + event.message.id + '.png'

        # save on local
        try:
            with open(path, 'wb') as fd:
                for chunk in content.iter_content():
                    fd.write(chunk)
        except Exception as e:
            print('儲存發生錯誤', e)
        finally:
            print("儲存結束")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="圖片已儲存。"))

        # upload to Imgur
        try:
            upload = upload_docs(client, path, imgur_album_id)
            print(f"圖片網址: {upload['link']}")
            img = Docs(user_id=user.user_id, type='image', local=path, url=upload['link'])
            db.session.add(img)
            db.session.commit()
        except Exception as e:
            print('上傳Imgur發生錯誤', e)
        finally:
            print("上傳Imgur結束")
        
        
        return


# Message event: Text處理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    message_type = event.message.type
    user_id = event.source.user_id
    user = get_user(event.source.user_id)
    reply_token = event.reply_token
    message = event.message.text
    today = datetime.now().strftime("%Y-%m-%d")


    if event.source.type == 'group':
        group = get_group(event.source.group_id)
        chatroom    = group
        chatroom_id = group.group_id
    else:
        chatroom    = user
        chatroom_id = user.user_id
    if message == '設定':
        SettingsMessage = json.load(open('templates/settings.json', 'r', encoding='utf-8'))
        box = SettingsMessage["body"]["contents"]
        if chatroom.text_reply == 'off':
            box[0]['action']['label']       = '開啟文字訊息自動回覆'
            box[0]['action']['data']        = 'text&on&'
            box[0]['action']['displayText'] = '開啟文字訊息自動回覆'
        box[0]['action']['data'] += chatroom_id
        if chatroom.file_reply == 'off':
            box[1]['action']['label']       = '開啟文件訊息自動儲存'
            box[1]['action']['data']        = 'file&on&'
            box[1]['action']['displayText'] = '開啟文件訊息自動儲存'
        box[1]['action']['data'] += chatroom_id
        if chatroom.image_reply == 'off':
            box[2]['action']['label']       = '開啟圖片訊息自動儲存'
            box[2]['action']['data']        = 'image&on&'
            box[2]['action']['displayText'] = '開啟圖片訊息自動儲存'
        box[2]['action']['data'] += chatroom_id
        line_bot_api.reply_message(reply_token, FlexSendMessage('Settings Info', SettingsMessage, quick_reply=QuickReply(
            items=[
                QuickReplyButton(action=MessageAction(label='設定', text='設定'))
            ]
        )))
        return
    elif message in ['文件', '檔案', '備份', '圖片', '照片']:
        SettingsMessage = json.load(open('templates/settings.json', 'r', encoding='utf-8'))
        box = SettingsMessage["body"]["contents"]
        box[0]['action']['label']       = '檢視儲存文件'
        box[0]['action']['data']        = 'file&view&'
        box[0]['action']['displayText'] = '檢視儲存文件'
        box[0]['action']['data'] += chatroom_id
        box[1]['action']['label']       = '檢視儲存圖片'
        box[1]['action']['data']        = 'image&view&'
        box[1]['action']['displayText'] = '檢視儲存圖片'
        box[1]['action']['data'] += chatroom_id
        del box[2]
        line_bot_api.reply_message(reply_token, FlexSendMessage('Settings Info', SettingsMessage, quick_reply=QuickReply(
            items=[
                QuickReplyButton(action=MessageAction(label='設定', text='設定'))
            ]
        )))
        return


    if chatroom.text_reply == 'off':
        return
    
    else:

        possible_message = ['至明天', '三天內', '七天內', '一周內', '一週內', '一個月', '未來所有行程', '今日完成行程']
        # 主菜單
        if re.match("菜單",message) or message == "menu" or message == "Menu" or message == "M":
            buttons_template_message = TemplateSendMessage(
                alt_text='主菜單',
                template=ButtonsTemplate(
                    thumbnail_image_url='https://free.com.tw/blog/wp-content/uploads/2014/08/Placekitten480.jpg',
                    image_aspect_ratio='rectangle',
                    image_size='cover',
                    image_background_color='#FFFFFF',
                    title='Menu',
                    text='選擇動作',
                    default_action=URIAction(
                        label='view detail',
                        uri='http://example.com/page/123'
                    ),
                    actions=[
                        MessageAction(
                            label = "瀏覽行程",
                            text  = "瀏覽行程"
                        ),
                        MessageAction(
                            label = "刪除行程",
                            text  = "刪除行程"
                        ),
                        MessageAction(
                            label = "刪除記事",
                            text  = "刪除記事"
                        ),
                    ]
                )
            )
            line_bot_api.reply_message(reply_token, buttons_template_message)

        # 查詢行程-1
        elif re.match("瀏覽所有行程", message):
            print(f"\n ------------ 瀏覽所有行程 ------------")
            
            buttons_template_message = TemplateSendMessage(
                alt_text='行程瀏覽',
                template=ButtonsTemplate(
                    thumbnail_image_url='https://free.com.tw/blog/wp-content/uploads/2014/08/Placekitten480.jpg',
                    image_aspect_ratio='rectangle',
                    image_size='cover',
                    image_background_color='#FFFFFF',
                    title='瀏覽行程',
                    text='選擇欲瀏覽範圍',
                    default_action=URIAction(
                        label='view detail',
                        uri='http://example.com/page/123'
                    ),
                    actions=[
                        MessageAction(
                            label = "至明天",
                            text  = "至明天"
                        ),
                        MessageAction(
                            label = "七天內",
                            text  = "七天內"
                        ),
                        MessageAction(
                            label = "未來所有行程",
                            text  = "未來所有行程"
                        ),
                        MessageAction(
                            label = "今日完成行程",
                            text  = "今日完成行程"
                        ),
                    ]
                )
            )
            line_bot_api.reply_message(reply_token, buttons_template_message)


        # 查詢行程-2
        elif message in possible_message:
            isPast = False
            if message == "今日完成行程":
                isPast = True
                sql_cmd = f"""SELECT id, time, title FROM activities WHERE
                userid = '{user_id}' AND time BETWEEN '{today}' AND '{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}' AND status = '已確認'
                ORDER BY `time`"""
            else:
                add_days = 9999
                if re.match('至明天',message):
                    add_days = 2
                if message == "三天內":
                    add_days = 4
                if message == "七天內" or message == "一周內" or message == "一週內":
                    add_days = 8

                date2 = (datetime.now() + timedelta(days=add_days)).strftime("%Y-%m-%d") 
                sql_cmd = f"""SELECT id, time, title FROM activities WHERE
                    userid = '{user_id}' AND time BETWEEN '{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}' AND '{date2}' AND status = '已確認'
                    ORDER BY `time`"""

            activities = db.session.execute(text(sql_cmd)).fetchall()

            get_V3_activities(activities, reply_token, isPast)


        # 關閉提醒
        elif re.match(r"OK", message, re.IGNORECASE):
            Eid = int(message[2:])
            
            for idx, val in enumerate(alertList):
                if val[0] == Eid:
                    if val[4] == '已確認':
                        sql = f"UPDATE activities SET status = '已提醒1' WHERE id = '{Eid}'"
                        alertList[idx][4] = "已提醒1"
                        reply = "第一次提醒已關閉。"
                    elif val[4] == '已提醒1':
                        sql = f"UPDATE activities SET status = '已提醒2' WHERE id = '{Eid}'"
                        alertList[idx][4] = "已提醒2"
                        reply = "第二次提醒已關閉。"

            db.session.execute(text(sql))
            print(f"{reply}: {Eid}")
            line_bot_api.reply_message(reply_token, TextSendMessage(text = f"行程{Eid}: {reply}"))


        # 瀏覽所有固定行程
        elif message == "瀏覽所有固定行程":
            print(f"\n ------------ 瀏覽所有固定行程 ------------")

            sql = 'SELECT * FROM `activities_routine` WHERE `status` = "finish" AND `userid` = "{0}"'.format(user_id)
            activities_routine = db.session.execute(text(sql)).fetchall()

            get_V3_routines(activities_routine, reply_token, False)
        
        
        # 瀏覽所有記事
        elif message == "瀏覽所有記事":
            print(f"\n ------------ 瀏覽所有記事 ------------")

            sql = 'SELECT id, title, status FROM `notes` WHERE `status` = "成功" AND `userid` = "{0}"'.format(user_id)
            notes = db.session.execute(text(sql)).fetchall()

            get_V3_notes(notes, reply_token)

        
        # 查看使用教學
        elif message == "使用教學":
            str_1 = """歡迎來到使用教學～～\n目前有三個項目我會幫您 [記錄] 與 [提醒] ，分別是
    1. 單次行程
    2. 固定行程
    3. 記事(備忘錄)"""
            line_bot_api.push_message(user_id, TextSendMessage(text=str_1))

            str_2 = """使用方式->直接輸入關鍵字\n現在試試看輸入關鍵字吧！\nEX:
            家庭聚餐
            固定週會
            Netflix密碼123okok"""
            line_bot_api.push_message(user_id, TextSendMessage(text=str_2))
            str_3 = """想查詢所有資訊的話\n\n輸入"菜單" 或是 "Menu" \n\n就可以選擇想瀏覽的項目囉！！"""
            line_bot_api.push_message(user_id, TextSendMessage(text=str_3))
            

        # Step 0
        else:
            try:
                keyword = str(message).upper()
                newInput = Activities(userid=user_id, time=today, title=keyword, status='日期待確認')
                db.session.add(newInput)
                db.session.commit()
                print(f"\n ------------ Step 0 ------------ id: {newInput.id}")
            except exc.InvalidRequestError:
                db.session.rollback()
            except Exception as e:
                print(e)

            Aid = str(newInput.id)

            # FlexMessage Menu
            # 載入menu
            Menu = json.load(open('templates/menu.json','r',encoding='utf-8'))
            actions = Menu['contents'][0]['body']['contents']

            actions[0]['action']['data'] = f'add_schedule&{Aid}'
            actions[1]['action']['data'] = f'search_schedule&{keyword}&{Aid}'
            actions[2]['action']['data'] = f'add_note&{Aid}'
            actions[3]['action']['data'] = f'search_note&{keyword}&{Aid}'
            actions[4]['action']['data'] = f'add_routine_1&{keyword}&{Aid}'
            actions[5]['action']['data'] = f'search_routine&{keyword}&{Aid}'

            line_bot_api.reply_message(reply_token, FlexSendMessage('Menu', Menu))




@handler.add(PostbackEvent)
def handle_postback(event):
    from sqlalchemy.sql import text
    ts = str(event.postback.data)
    action = ts.split("&")[0]
    user_id = event.source.user_id
    reply_token = event.reply_token

    # 取消新增行程 [After Confirm template]
    if action == "cancel":
        table = str(ts.split("&")[1])
        id = str(ts.split("&")[2])
        sql = f"DELETE FROM `{table}` WHERE (`id` = '{id}')"
        db.session.execute(text(sql))
        db.session.commit()
        text_message = TextSendMessage(text = "成功取消新增。")
        line_bot_api.reply_message(reply_token, text_message)


    # 確認新增 [After Confirm template]
    if action == "confirm":
        table = str(ts.split("&")[1])
        id = str(ts.split("&")[2])

        print(f"\n ------------ 確認新增 [After Confirm template] ------------ {table} : {id}")

        if table == "activities":
            sql = f"UPDATE `{table}` SET status = '已確認' WHERE (`id` = '{id}')"
            db.session.execute(text(sql))
            db.session.commit()

            get_V3_activity(id, reply_token, False)


        if table == "notes":
            sql = f'SELECT `id`, `time`, `title` FROM `activities` WHERE `id` = {id}'
            data = db.session.execute(text(sql)).fetchone()

            # 先刪 Step 0 新增的activity
            sql = f"DELETE FROM `activities` WHERE (`id` = '{id}')"
            db.session.execute(text(sql))
            db.session.commit()

            newInput = Notes(userid=user_id, title=data[2], status='成功')
            db.session.add(newInput)
            db.session.commit()
            Aid = str(newInput.id)

            sql = f'SELECT `id`, `title`, `status` FROM `notes` WHERE `id` = {Aid}'
            data = db.session.execute(text(sql)).fetchone()
            get_V3_note(Aid, reply_token, '新增成功')


        if table == "activities_routine":
            # status 改為 finish完成
            Activities_routine.query.filter(Activities_routine.id == id).update({'status' : 'finish'})
            db.session.commit()

            # 輸出固定行程
            get_V3_routine(id, reply_token)
            

    # 新增行程
    if action == "add_schedule":
        print("\n ------------ 新增行程 ------------")
        id = str(ts.split("&")[1])
        a = event.postback.params
        Edate = a['datetime'][:10]
        Etime = a['datetime'][11:]
        Edatetime = str(Edate) + " " + str(Etime) + ":00"

        sql = f"UPDATE activities SET `time` = '{Edatetime}', `status` = '待確認' WHERE id = {id}"
        db.session.execute(text(sql))
        db.session.commit()

        sql = f"""SELECT id, time, title FROM activities WHERE id = {id}"""
        data = db.session.execute(text(sql)).fetchone()

        if data == None:
            reply = "請重新新增。"
            line_bot_api.reply_message(reply_token,TextSendMessage(text = reply))
        else:
            confirm_template_message = TemplateSendMessage(
                alt_text='Confirm template',
                template=ConfirmTemplate(
                    text=f'{Edatetime}\n{data[2]}',
                    actions=[
                        PostbackAction(
                            label='確認新增',
                            display_text='確認新增',
                            data=f'confirm&activities&{data[0]}'
                        ),
                        PostbackAction(
                            label='取消',
                            display_text='取消新增',
                            data=f'cancel&activities&{data[0]}'
                        ),
                    ]
                )
            )
            line_bot_api.reply_message(reply_token,confirm_template_message)



    # 查詢行程
    if action == "search_schedule":
        keyword = str(ts.split("&")[1])
        id      = ts.split("&")[2]
        print("\n ------------ 查詢行程 ------------")
        
        # 先刪 Step 0 新增的activity
        sql = f"DELETE FROM `activities` WHERE (`id` = '{id}')"
        db.session.execute(text(sql))
        db.session.commit()

        # LIKE查詢
        date2 = (datetime.now() + timedelta(days=9999)).strftime("%Y-%m-%d") 
        sql = 'SELECT `id`, `time`, `title` FROM `activities` WHERE `status` = "已確認" AND `userid` = "{0}" AND `title` LIKE "{1}" AND `time` BETWEEN "{2}" AND "{3}" ORDER BY `time`'.format(user_id, "%%"+keyword.upper()+"%%", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), date2)
        activities = db.session.execute(text(sql)).fetchall()

        if len(activities) > 0:
            get_V3_activities(activities, reply_token, False)
        else:
            text = "查無此行程。"
            line_bot_api.reply_message(reply_token, TextSendMessage(text = text))



    # 行程內容
    if action == "activity":
        id = str(ts.split("&")[1])
        print(f"\n ------------ 行程內容 id:{id} ------------")
        
        get_V3_activity(id, reply_token, False)



    # 行程更改時間
    if action == "change_datetime":
        id = str(ts.split("&")[1])
        print(f"\n ------------ 行程更改時間 id:{id} ------------")
        a = event.postback.params
        Edate = a['datetime'][:10]
        Etime = a['datetime'][11:]
        Edatetime = str(Edate) + " " + str(Etime) + ":00"

        actv = Activities.query.filter(Activities.id == id).first()
        actv.time = Edatetime

        db.session.commit()

        get_V3_activity(id, reply_token, True)



    # 行程刪除
    if action == "delete_schedule":
        id    = str(ts.split("&")[1])
        stage = str(ts.split("&")[2])

        print(f"\n ------------ 行程刪除 id:{id} ------------ stage:{stage}")
        
        sql = f'SELECT `id`, `time`, `title` FROM `activities` WHERE `id` = {id}'
        data = db.session.execute(text(sql)).fetchone()

        if stage == "1":
            confirm_template_message = TemplateSendMessage(
                    alt_text='Confirm template',
                    template=ConfirmTemplate(
                        text=f'{data[2]}\n{data[1]}',
                        actions=[
                            PostbackAction(
                                label='確認刪除',
                                display_text='確認刪除',
                                data=f'delete_schedule&{data[0]}&{2}'
                            ),
                            PostbackAction(
                                label='取消',
                                display_text='取消刪除',
                                data=f'activity&{data[0]}'
                            ),
                        ]
                    )
                )
            line_bot_api.reply_message(reply_token,confirm_template_message)

        if stage == "2":
            sql = f"DELETE FROM `activities` WHERE (`id` = '{id}')"
            db.session.execute(text(sql))
            db.session.commit()

            line_bot_api.reply_message(reply_token, TextSendMessage(text="行程刪除成功"))

        

    # 瀏覽行程
    if action == "browse_schedule":
        print(f"\n ------------ 瀏覽行程 ------------")

        # 先刪 Step 0 新增的activity
        id = ts.split("&")[1]
        sql = f"DELETE FROM `activities` WHERE (`id` = '{id}')"
        db.session.execute(text(sql))
        db.session.commit()
        
        buttons_template_message = TemplateSendMessage(
            alt_text='行程瀏覽',
            template=ButtonsTemplate(
                thumbnail_image_url='https://free.com.tw/blog/wp-content/uploads/2014/08/Placekitten480.jpg',
                image_aspect_ratio='rectangle',
                image_size='cover',
                image_background_color='#FFFFFF',
                title='瀏覽行程',
                text='選擇欲瀏覽範圍',
                default_action=URIAction(
                    label='view detail',
                    uri='http://example.com/page/123'
                ),
                actions=[
                    MessageAction(
                        label = "至明天",
                        text  = "至明天"
                    ),
                    MessageAction(
                        label = "七天內",
                        text  = "七天內"
                    ),
                    MessageAction(
                        label = "未來所有行程",
                        text  = "未來所有行程"
                    ),
                    MessageAction(
                        label = "今日完成行程",
                        text  = "今日完成行程"
                    ),
                ]
            )
        )
        line_bot_api.reply_message(reply_token, buttons_template_message)

    

    # 新增記事
    if action == "add_note":
        id = str(ts.split("&")[1])

        print(f"\n ------------ 新增記事 ------------ id: {id}")

        sql = f'SELECT `id`, `time`, `title` FROM `activities` WHERE `id` = {id}'
        data = db.session.execute(text(sql)).fetchone()
        
        if data == None:
            reply = "請重新新增。"
            line_bot_api.reply_message(reply_token,TextSendMessage(text = reply))
        else:
            confirm_template_message = TemplateSendMessage(
                alt_text='Confirm template',
                template=ConfirmTemplate(
                    text=f'{data[2]}',
                    actions=[
                        PostbackAction(
                            label='確認新增',
                            display_text='確認新增',
                            data=f'confirm&notes&{id}'
                        ),
                        PostbackAction(
                            label='取消',
                            display_text='取消新增',
                            data=f'cancel&activities&{id}'
                        ),
                    ]
                )
            )
            line_bot_api.reply_message(reply_token,confirm_template_message)
 


    # 查詢記事
    if action == "search_note":
        keyword = str(ts.split("&")[1])
        id      = ts.split("&")[2]
        print("\n ------------ 查詢記事 ------------")
        
        # 先刪 Step 0 新增的activity
        sql = f"DELETE FROM `activities` WHERE (`id` = '{id}')"
        db.session.execute(text(sql))
        db.session.commit()

        # LIKE查詢
        sql = 'SELECT `id`, `title`, `status` FROM `notes` WHERE `status` = "成功" AND `userid` = "{0}" AND `title` LIKE "{1}" ORDER BY `created_at`'.format(user_id, "%%"+keyword.upper()+"%%")
        notes = db.session.execute(text(sql)).fetchall()

        get_V3_notes(notes, reply_token)

    
    # 記事內容
    if action == "note":
        id = str(ts.split("&")[1])
        print(f"\n ------------ 記事內容 id:{id} ------------")
        
        get_V3_note(id, reply_token, '詳細內容')



    # 記事刪除
    if action == "delete_note":
        id    = str(ts.split("&")[1])
        stage = str(ts.split("&")[2])

        print(f"\n ------------ 記事刪除 id:{id} ------------ stage:{stage}")
        
        sql = f'SELECT `id`, `title`, `status` FROM `notes` WHERE `id` = {id}'
        data = db.session.execute(text(sql)).fetchone()

        if stage == "1":
            confirm_template_message = TemplateSendMessage(
                    alt_text='Confirm template',
                    template=ConfirmTemplate(
                        text=f'{data[1]}',
                        actions=[
                            PostbackAction(
                                label='確認刪除',
                                display_text='確認刪除',
                                data=f'delete_note&{data[0]}&{2}'
                            ),
                            PostbackAction(
                                label='取消',
                                display_text='取消刪除',
                                data=f'note&{data[0]}'
                            ),
                        ]
                    )
                )
            line_bot_api.reply_message(reply_token,confirm_template_message)

        if stage == "2":
            Notes.query.filter(Notes.id == id).update({'status' : '刪除'})
            db.session.commit()
            line_bot_api.reply_message(reply_token, TextSendMessage(text="記事刪除成功"))



    # 查詢固定行程
    if action == "search_routine":
        keyword = str(ts.split("&")[1])
        id      = ts.split("&")[2]
        print("\n ------------ 查詢固定行程 ------------")

        # 先刪 Step 0 新增的activity
        sql = f"DELETE FROM `activities` WHERE (`id` = '{id}')"
        db.session.execute(text(sql))
        db.session.commit()

        # LIKE查詢
        date2 = (datetime.now() + timedelta(days=9999)).strftime("%Y-%m-%d") 
        sql = 'SELECT * FROM `activities_routine` WHERE `status` = "finish" AND `userid` = "{0}" AND `title` LIKE "{1}" AND `end_date` BETWEEN "{2}" AND "{3}" ORDER BY `created_at`'.format(user_id, "%%"+keyword.upper()+"%%", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), date2)
        activities_routine = db.session.execute(text(sql)).fetchall()

        if len(activities_routine) > 0:
            get_V3_routines(activities_routine, reply_token, False)
        else:
            text = "查無此固定行程。"
            line_bot_api.reply_message(reply_token, TextSendMessage(text = text))


    
    # 檢視固定行程內容
    if action == "routine":
        id = str(ts.split("&")[1])
        print(f"\n ------------ 固定行程內容 id:{id} ------------")
        get_V3_routine(id, reply_token)



    # 刪除固定行程
    if action == "delete_routine":
        print("\n ------------ 刪除固定行程 ------------")

        page = int(ts.split("&")[1])
        id = ts.split("&")[2]
        
        if page == 999:
            print(f"\n ------------ id:{id} ------------")
            sql = f"SELECT * FROM activities_routine WHERE (`id` = '{id}')"
            ARdata = db.session.execute(text(sql)).fetchone()
            sql = f"DELETE FROM `activities_routine` WHERE (`id` = '{id}')"
            db.session.execute(text(sql))
            db.session.commit()
            reply = f"行程: {ARdata[2]} 已刪除。"
            line_bot_api.reply_message(reply_token, TextSendMessage(text = reply))
        
        else:
            limitFrom = int(page) -1
            sql = f"SELECT * FROM `activities_routine` WHERE (`userid` = '{user_id}') LIMIT {limitFrom*3},3"
            AR = db.session.execute(text(sql)).fetchall()

            if AR:
                actionsR = []
                
                for idx, val in enumerate(AR):
                    actionsR.append(
                        PostbackAction(
                            label = f"刪除{val[2]}",
                            display_text = f"刪除固定行程{val[0]}",
                            data = f'delete_routine&999&{val[0]}'
                        )
                    )

                actionsR.append(
                    PostbackAction(
                        label = f"*****下一頁*****",
                        display_text = f"*****下一頁*****",
                        data = f'delete_routine&{page+1}&0'
                    )
                )

                buttons_template_message = TemplateSendMessage(
                    alt_text='固定行程',
                    template=ButtonsTemplate(
                        thumbnail_image_url='https://cdn.teknotut.com/wp-content/uploads/2019/05/menghapus-file-dengan-kondisi-tertentu-di-linux.png',
                        image_aspect_ratio='rectangle',
                        image_size='cover',
                        image_background_color='#FFFFFF',
                        title='Menu',
                        text='要刪除什麼固定行程?',
                        default_action=URIAction(
                            label='view detail',
                            uri='http://example.com/page/123'
                        ),
                        actions = actionsR
                    )
                )
                line_bot_api.reply_message(reply_token, buttons_template_message)
            else:
                reply = "已無其他固定行程。"
                line_bot_api.reply_message(reply_token, TextSendMessage(text = reply))


    # 新增固定行程 Step 1: 選擇頻率
    if action == "add_routine_1":
        print("\n ------------ 新增固定行程  Step 1: 選擇頻率 ------------")

        keyword = str(ts.split("&")[1])
        id      = int(ts.split("&")[2])

        # 先刪 Step 0 新增的activity
        sql = f"DELETE FROM `activities` WHERE (`id` = '{id}')"
        db.session.execute(text(sql))
        db.session.commit()

        # Step 1 選擇頻率
        buttons_template_message = TemplateSendMessage(
            alt_text='新增固定行程',
            template=ButtonsTemplate(
                thumbnail_image_url='https://www.thirtyhandmadedays.com/wp-content/uploads/2020/07/printable-daily-schedule.jpg',
                image_aspect_ratio='rectangle',
                image_size='cover',
                image_background_color='#FFFFFF',
                title='固定行程 Step 1',
                text='選擇頻率',
                default_action=URIAction(
                    label='view detail',
                    uri='http://example.com/page/123'
                ),
                actions=[
                    PostbackAction(
                            label = "每日",
                            display_text = "每日",
                            data = f'add_routine_2&每日&{1}&{keyword}'
                    ),
                    PostbackAction(
                            label = "每週",
                            display_text = "每週",
                            data = f'add_routine_2&每週&{1}&{keyword}'
                    ),
                    PostbackAction(
                            label = "每月",
                            display_text = "每月",
                            data = f'add_routine_2&每月&{1}&{keyword}'
                    ),
                ]
            )
        )
        line_bot_api.reply_message(reply_token, buttons_template_message)

        

    


    # 新增固定行程 Step 2: 選擇 日期、時間、結束日期
    if action == "add_routine_2":
        print("\n ------------ 新增固定行程 ------------")

        frequency = ts.split("&")[1]
        stage     = int(ts.split("&")[2])

        print(frequency + " " + str(stage))

        # 頻率[每日]
        if frequency == "每日":

            sql = "SET time_zone='+8:00'"
            db.session.execute(text(sql))
            db.session.commit()

            # 頻率[每日] - 選擇幾點幾分
            if stage == 1:

                # 先新建資料
                keyword   = ts.split("&")[3]
                newInput = Activities_routine(userid=user_id, title=keyword, frequency=frequency, frequency_2='', time='', status='ready')
                db.session.add(newInput)
                db.session.commit()
                print(f"\n ------------ 新增固定行程 id: {newInput.id} ------------")

                buttons_template_message = TemplateSendMessage(
                    alt_text='固定行程選擇時間',
                    template=ButtonsTemplate(
                        thumbnail_image_url='https://www.ikea.com.tw/dairyfarm/tw/images/360/0836019_PE778493_S4.jpg',
                        image_aspect_ratio='square',
                        image_size='contain',
                        image_background_color='#FFFFFF',
                        title='選擇時間',
                        text='選擇固定行程提醒時間～',
                        default_action=URIAction(
                            label='view detail',
                            uri='http://example.com/page/123'
                        ),
                        actions=[
                            DatetimePickerAction(
                                label='選擇時間',
                                data=f'add_routine_2&{frequency}&{2}&{newInput.id}',
                                mode='time',
                                initial='00:00'
                            )
                        ]
                    )
                )
                line_bot_api.reply_message(reply_token, buttons_template_message)

            # 頻率[每日] - 選擇固定行程的結束日期
            if stage == 2:
                id = ts.split("&")[3]
                data = event.postback.params
                time = data['time']

                # 更新資料 time
                Activities_routine.query.filter(Activities_routine.id == id).update({'time' : time})
                db.session.commit()

                buttons_template_message = TemplateSendMessage(
                    alt_text='固定行程選擇時間',
                    template=ButtonsTemplate(
                        thumbnail_image_url='https://image.shutterstock.com/image-vector/calendar-cartoon-vector-illustration-hand-260nw-357444302.jpg',
                        image_aspect_ratio='rectangle',
                        image_size='cover',
                        image_background_color='#FFFFFF',
                        title='選擇週期的結束時間',
                        text='固定行程持續到哪一天呢～',
                        default_action=URIAction(
                            label='view detail',
                            uri='http://example.com/page/123'
                        ),
                        actions=[
                            DatetimePickerAction(
                                label='選擇結束日期',
                                data=f'add_routine_2&{frequency}&{3}&{id}',
                                mode='date',
                            )
                        ]
                    )
                )
                line_bot_api.reply_message(reply_token, buttons_template_message)

            if stage == 3:
                a = event.postback.params
                date = a['date']
                id = ts.split("&")[3]

                # 更新資料 end_date
                Activities_routine.query.filter(Activities_routine.id == id).update({'end_date' : date})
                db.session.commit()

                sql = f"SELECT id, title, frequency, frequency_2, time, end_date, status FROM `activities_routine` WHERE id = '{id}'"
                routine = db.session.execute(text(sql)).fetchone()

                confirm_template_message = TemplateSendMessage(
                    alt_text='Confirm template',
                    template=ConfirmTemplate(
                        text=f'{routine[1]}\n{routine[2]} {routine[3]} {routine[4]} {routine[5]}',
                        actions=[
                            PostbackAction(
                                label='確認新增',
                                display_text='確認新增',
                                data=f'confirm&activities_routine&{routine[0]}'
                            ),
                            PostbackAction(
                                label='取消',
                                display_text='取消新增',
                                data=f'cancel&activities_routine&{routine[0]}'
                            ),
                        ]
                    )
                )
                line_bot_api.reply_message(reply_token,confirm_template_message)

            

        # 頻率[每週]
        if frequency == "每週":

            # 頻率[每週] - 選擇一~日
            if stage == 1:

                # 先新建資料
                keyword   = ts.split("&")[3]
                newInput = Activities_routine(userid=user_id, title=keyword, frequency=frequency, frequency_2='', time='', status='ready')
                db.session.add(newInput)
                db.session.commit()
                print(f"\n ------------ 新增固定行程 id: {newInput.id} ------------")

                # 準備 FlexMessage
                FlexMessage = json.load(open('templates/routine_option_1.json','r',encoding='utf-8'))
                actions = FlexMessage['contents'][0]['body']['contents']
                for action in actions:
                    action['action']['data'] = action['action']['data'] + f"&{newInput.id}"
                line_bot_api.reply_message(reply_token, FlexSendMessage('Weekday choice',FlexMessage))
            
            # 頻率[每週] - 選擇幾點幾分
            if stage == 2:
                frequency_2 = ts.split("&")[3]
                id          = ts.split("&")[4]

                # 減少db使用，不在此更新 frequency_2 資料，將參數放入data內，在 stage 3 一併更新
                print(f"\n ------------ 更新固定行程 frequency_2: {frequency_2} ------------")

                buttons_template_message = TemplateSendMessage(
                    alt_text='固定行程選擇時間',
                    template=ButtonsTemplate(
                        thumbnail_image_url='https://image.shutterstock.com/image-vector/calendar-cartoon-vector-illustration-hand-260nw-357444302.jpg',
                        image_aspect_ratio='rectangle',
                        image_size='cover',
                        image_background_color='#FFFFFF',
                        title='選擇時間',
                        text='選擇固定行程提醒時間～',
                        default_action=URIAction(
                            label='view detail',
                            uri='http://example.com/page/123'
                        ),
                        actions=[
                            DatetimePickerAction(
                                label='選擇時間',
                                data=f'add_routine_2&{frequency}&{3}&{frequency_2}&{id}',
                                mode='time',
                                initial='00:00'
                            )
                        ]
                    )
                )
                line_bot_api.reply_message(reply_token, buttons_template_message)

            # 頻率[每週] - 選擇固定行程的結束日期
            if stage == 3:
                frequency_2 = ts.split("&")[3]
                id          = ts.split("&")[4]
                a = event.postback.params
                time = a['time']
                print(f"\n ------------ 更新固定行程 time: {time} ------------")

                # 更新資料 frequency_2, time
                Activities_routine.query.filter(Activities_routine.id == id).update({'time' : time, 'frequency_2' : frequency_2})
                db.session.commit()
            
                buttons_template_message = TemplateSendMessage(
                    alt_text='固定行程選擇時間',
                    template=ButtonsTemplate(
                        thumbnail_image_url='https://image.shutterstock.com/image-vector/calendar-cartoon-vector-illustration-hand-260nw-357444302.jpg',
                        image_aspect_ratio='rectangle',
                        image_size='cover',
                        image_background_color='#FFFFFF',
                        title='選擇週期的結束時間',
                        text='固定行程持續到哪一天呢～',
                        default_action=URIAction(
                            label='view detail',
                            uri='http://example.com/page/123'
                        ),
                        actions=[
                            DatetimePickerAction(
                                label='選擇結束日期',
                                data=f'add_routine_2&{frequency}&{4}&{id}',
                                mode='date',
                            )
                        ]
                    )
                )
                line_bot_api.reply_message(reply_token, buttons_template_message)

            if stage == 4:
                id = ts.split("&")[3]
                a = event.postback.params
                date = a['date']
                print(f"\n ------------ 更新固定行程 end_date: {date} ------------")
                
                # 更新資料 end_date
                Activities_routine.query.filter(Activities_routine.id == id).update({'end_date' : date})
                db.session.commit()

                sql = f"SELECT id, title, frequency, frequency_2, time, end_date, status FROM `activities_routine` WHERE id = '{id}'"
                routine = db.session.execute(text(sql)).fetchone()

                confirm_template_message = TemplateSendMessage(
                    alt_text='Confirm template',
                    template=ConfirmTemplate(
                        text=f'{routine[1]}\n{routine[2]} {routine[3]} {routine[4]} {routine[5]}',
                        actions=[
                            PostbackAction(
                                label='確認新增',
                                display_text='確認新增',
                                data=f'confirm&activities_routine&{routine[0]}'
                            ),
                            PostbackAction(
                                label='取消',
                                display_text='取消新增',
                                data=f'cancel&activities_routine&{routine[0]}'
                            ),
                        ]
                    )
                )
                line_bot_api.reply_message(reply_token,confirm_template_message)



        # 頻率[每月]
        if frequency == "每月":

            # 頻率[每週] - 選擇日期
            if stage == 1:

                # 先新建資料
                keyword   = ts.split("&")[3]
                newInput = Activities_routine(userid=user_id, title=keyword, frequency=frequency, frequency_2='', time='', status='ready')
                db.session.add(newInput)
                db.session.commit()
                print(f"\n ------------ 新增固定行程 id: {newInput.id} ------------")

                # 準備 FlexMessage
                FlexMessage = json.load(open('templates/routine_option_2.json','r',encoding='utf-8'))
                contents = FlexMessage['contents']
                for bubble in contents:
                    actions = bubble['body']['contents']
                    for action in actions:
                        action['action']['data'] = action['action']['data'] + f"&{newInput.id}"
                line_bot_api.reply_message(reply_token, FlexSendMessage('Date choice',FlexMessage))
            
            # 頻率[每週] - 選擇幾點幾分
            if stage == 2:
                frequency_2 = ts.split("&")[3]
                id          = ts.split("&")[4]

                # 減少db使用，不在此更新 frequency_2 資料，將參數放入data內，在 stage 3 一併更新
                print(f"\n ------------ 更新固定行程 frequency_2: {frequency_2} ------------")

                buttons_template_message = TemplateSendMessage(
                    alt_text='固定行程選擇時間',
                    template=ButtonsTemplate(
                        thumbnail_image_url='https://image.shutterstock.com/image-vector/calendar-cartoon-vector-illustration-hand-260nw-357444302.jpg',
                        image_aspect_ratio='rectangle',
                        image_size='cover',
                        image_background_color='#FFFFFF',
                        title='選擇時間',
                        text='選擇固定行程提醒時間～',
                        default_action=URIAction(
                            label='view detail',
                            uri='http://example.com/page/123'
                        ),
                        actions=[
                            DatetimePickerAction(
                                label='選擇時間',
                                data=f'add_routine_2&{frequency}&{3}&{frequency_2}&{id}',
                                mode='time',
                                initial='00:00'
                            )
                        ]
                    )
                )
                line_bot_api.reply_message(reply_token, buttons_template_message)

            # 頻率[每月] - 選擇固定行程的結束日期
            if stage == 3:
                frequency_2 = ts.split("&")[3]
                id          = ts.split("&")[4]
                a = event.postback.params
                time = a['time']
                print(f"\n ------------ 更新固定行程 time: {time} ------------")
                
                # 更新資料 frequency_2, time
                Activities_routine.query.filter(Activities_routine.id == id).update({'time' : time, 'frequency_2' : frequency_2})
                db.session.commit()

                buttons_template_message = TemplateSendMessage(
                    alt_text='固定行程選擇時間',
                    template=ButtonsTemplate(
                        thumbnail_image_url='https://image.shutterstock.com/image-vector/calendar-cartoon-vector-illustration-hand-260nw-357444302.jpg',
                        image_aspect_ratio='rectangle',
                        image_size='cover',
                        image_background_color='#FFFFFF',
                        title='選擇週期的結束時間',
                        text='固定行程持續到哪一天呢～',
                        default_action=URIAction(
                            label='view detail',
                            uri='http://example.com/page/123'
                        ),
                        actions=[
                            DatetimePickerAction(
                                label='選擇結束日期',
                                data=f'add_routine_2&{frequency}&{4}&{id}',
                                mode='date',
                            )
                        ]
                    )
                )
                line_bot_api.reply_message(reply_token, buttons_template_message)

            if stage == 4:
                id = ts.split("&")[3]
                a = event.postback.params
                date = a['date']
                print(f"\n ------------ 更新固定行程 end_date: {date} ------------")

                # 更新資料 end_date
                Activities_routine.query.filter(Activities_routine.id == id).update({'end_date' : date})
                db.session.commit()
                
                sql = f"SELECT id, title, frequency, frequency_2, time, end_date, status FROM `activities_routine` WHERE id = '{id}'"
                routine = db.session.execute(text(sql)).fetchone()

                confirm_template_message = TemplateSendMessage(
                    alt_text='Confirm template',
                    template=ConfirmTemplate(
                        text=f'{routine[1]}\n{routine[2]} {routine[3]} {routine[4]} {routine[5]}',
                        actions=[
                            PostbackAction(
                                label='確認新增',
                                display_text='確認新增',
                                data=f'confirm&activities_routine&{routine[0]}'
                            ),
                            PostbackAction(
                                label='取消',
                                display_text='取消新增',
                                data=f'cancel&activities_routine&{routine[0]}'
                            ),
                        ]
                    )
                )
                line_bot_api.reply_message(reply_token,confirm_template_message)

    
    # 固定行程 關閉提醒
    if action == "shutup":
        idx = int(ts.split("&")[1])
        Eid = alertList[idx][0]
        print(f"\n ------------ 關閉固定行程提醒 ID: {Eid} ------------")
        alerted.append(Eid)
        alerted.append(Eid)
        alerted.append(Eid)

    param = ts.split("&")
    if action == 'text':
        on_off = param[1]
        if param[2][0] == 'C':
            group = Group.get_by_group_id(param[2])
            group.turn_on_off_text_reply(on_off)
        else:
            user = User.get_by_user_id(param[2])
            user.turn_on_off_text_reply(on_off)
        reply_message = '文字訊息已關閉自動回覆。' if on_off == 'off' else '文字訊息已開啟自動回覆。'
        line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_message))
    
    elif action == 'file':
        if param[1] == 'view':
            folder    = param[2]
            # subfolder = param[3]
            path      = f'./uploads/{folder}'
            if not os.path.isdir(path):
                reply_message = "您尚未上傳任何文件"
                line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_message))
                return

            files = get_stored_docs_by_chatroom(path)
            
        elif param[1] in ['on', 'off']:
            on_off = param[1]
            if param[2][0] == 'C':
                group = Group.get_by_group_id(param[2])
                group.turn_on_off_file_reply(on_off)
            else:
                user = User.get_by_user_id(param[2])
                user.turn_on_off_file_reply(on_off)
            reply_message = '文件訊息已關閉自動儲存。' if on_off == 'off' else '文件訊息已開啟自動儲存。'
            line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_message))
    
    elif action == 'image':
        if param[1] == 'view':
            folder    = param[2]
            # subfolder = param[3]
            path      = f'./uploads/{folder}'
            if not os.path.isdir(path):
                reply_message = "您尚未上傳任何文件"
                line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_message))
                return
            Template = json.load(open('templates/template.json','r',encoding='utf-8'))
            targets = get_stored_docs_by_chatroom(path)
            template_contents = Template['contents'][0]['body']['contents']
            print(template_contents)
            for target in targets:
                filename, extension = os.path.splitext(target)
                if extension not in ['.png', '.jpg']:
                    continue
                print(f'c: \n{path}/{target}\n')
                file_info = Docs.query.filter(Docs.local == f'{path}/{target}').first()
                if file_info is None:
                    continue
                Template['contents'][0]['body']['contents'].append({
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "image",
                            "url": f"{file_info.url}"
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": f"{filename}",
                                "data": f"sendImage&{file_info.url}"
                            }
                        }
                    ]
                })
                del Template['contents'][0]['body']['contents'][0]
            line_bot_api.reply_message(reply_token, FlexSendMessage('Template',Template))



        elif param[1] in ['on', 'off']:
            on_off = param[1]
            if param[2][0] == 'C':
                group = Group.get_by_group_id(param[2])
                group.turn_on_off_image_reply(on_off)
            else:
                user = User.get_by_user_id(param[2])
                user.turn_on_off_image_reply(on_off)
            reply_message = '圖片訊息已關閉自動回覆。' if on_off == 'off' else '圖片訊息已開啟自動回覆。'
            line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_message))


    elif action == 'sendImage':
        url = param[1]
        image_message = ImageSendMessage(
            original_content_url=url,
            preview_image_url=url
        )
        line_bot_api.reply_message(reply_token, image_message)


    

######### 以下放多次使用的 def #########

# 取得多個固定行程內容[Flex template]
def get_V3_routines(activities_routine, reply_token, isPast):
    if len(activities_routine) > 0:
        contents = []
        for routine in activities_routine:
            contents.append({
                'type': 'button',
                'action': {
                    'type' : 'postback',
                    'label': f'{routine[2]}',
                    'data' : f'routine&{routine[0]}'
                } 
            })
        Template = json.load(open('templates/template.json','r',encoding='utf-8'))
        Template['contents'][0]['body']['contents'] = contents
        line_bot_api.reply_message(reply_token, FlexSendMessage('Template',Template))
    else:
        text = "查無此固定行程。"
        line_bot_api.reply_message(reply_token, TextSendMessage(text = text))


# 取得單一固定行程內容[Button template]
def get_V3_routine(id, reply_token):
    from sqlalchemy.sql import text
    sql = f"SELECT id, title, frequency, frequency_2, time, end_date, status FROM `activities_routine` WHERE id = '{id}'"
    data = db.session.execute(text(sql)).fetchone()

    title       = data[1]
    frequency_2 = data[3]+" " if data[3] is not None else ''
    text        = data[2] + " " + frequency_2 + str(data[4]) + " " + str(data[5])

    buttons_template_message = TemplateSendMessage(
        alt_text = f'固定行程{data[0]}',
        template=ButtonsTemplate(
            thumbnail_image_url='https://www.thirtyhandmadedays.com/wp-content/uploads/2020/07/printable-daily-schedule.jpg',
            image_aspect_ratio='rectangle',
            image_size='cover',
            image_background_color='#FFFFFF',
            title = f'{title}',
            text  = f'{text}',
            default_action=URIAction(
                label='view detail',
                uri='http://example.com/page/123'
            ),
            actions=[
                PostbackAction(
                    label = "刪除固定行程",
                    display_text = "刪除固定行程",
                    data = f'delete_routine&999&{data[0]}'
                )
            ]
        )
    )
    line_bot_api.reply_message(reply_token, buttons_template_message)



# 取得多個記事內容[Flex template]
def get_V3_notes(notes, reply_token):
    if len(notes) > 0:
        contents = []
        for note in notes:
            contents.append({
                'type': 'button',
                'action': {
                    'type' : 'postback',
                    'label': f'{note[1]}',
                    'data' : f'note&{note[0]}'
                } 
            })
        Template = json.load(open('templates/template.json','r',encoding='utf-8'))
        Template['contents'][0]['header']['contents'][0]['text'] = '記事'
        Template['contents'][0]['body']['contents'] = contents
        line_bot_api.reply_message(reply_token, FlexSendMessage('Template',Template))
    else:
        line_bot_api.reply_message(reply_token, TextSendMessage(text = "查無記事。"))


# 取得單一記事內容[Button template]
def get_V3_note(id, reply_token, stage):
    sql = f"SELECT `id`, `title`, `status` FROM `notes` WHERE `id` = {id} AND `status` = '成功'"
    data = db.session.execute(text(sql)).fetchone()

    buttons_template_message = TemplateSendMessage(
        alt_text = f'記事 {data[1]}',
        template=ButtonsTemplate(
            image_aspect_ratio='rectangle',
            image_size='cover',
            image_background_color='#FFFFFF',
            title = f'記事 {stage}',
            text  = f'{data[1]}',
            default_action=URIAction(
                label='view detail',
                uri='http://example.com/page/123'
            ),
            actions=[
                PostbackAction(
                    label = "刪除記事",
                    display_text = "刪除記事",
                    data = f'delete_note&{data[0]}&{1}'
                )
            ]
        )
    )
    line_bot_api.reply_message(reply_token, buttons_template_message)


# 取得多個行程內容[Flex template]
def get_V3_activities(activities, reply_token, isPast):
    if len(activities) > 0:
        contents = []
        for activity in activities:
            contents.append({
                'type': 'button',
                'action': {
                    'type' : 'postback',
                    'label': f'{activity[2]}',
                    'data' : f'activity&{activity[0]}'
                } 
            })
        Template = json.load(open('templates/template.json','r',encoding='utf-8'))
        Template['contents'][0]['body']['contents'] = contents
        line_bot_api.reply_message(reply_token, FlexSendMessage('Template',Template))
    else:
        text = "查無此未來行程。"
        if isPast:
            text = "查無此過去行程。"
        line_bot_api.reply_message(reply_token, TextSendMessage(text = text))


# 取得單一行程內容[Button template]
def get_V3_activity(id, reply_token, ifupdate):
    sql = f'SELECT `id`, `time`, `title` FROM `activities` WHERE `id` = {id}'
    data = db.session.execute(text(sql)).fetchone()

    title = data[2]
    if ifupdate == True:
        title = data[2] + " 更新成功"

    buttons_template_message = TemplateSendMessage(
        alt_text = f'行程{data[0]}',
        template=ButtonsTemplate(
            thumbnail_image_url='https://www.thirtyhandmadedays.com/wp-content/uploads/2020/07/printable-daily-schedule.jpg',
            image_aspect_ratio='rectangle',
            image_size='cover',
            image_background_color='#FFFFFF',
            title = f'{title}',
            text  = f'{data[1]}',
            default_action=URIAction(
                label='view detail',
                uri='http://example.com/page/123'
            ),
            actions=[
                DatetimePickerAction(
                    label='更改時間',
                    data=f'change_datetime&{data[0]}',
                    mode='datetime'
                ),
                PostbackAction(
                    label = "刪除行程",
                    display_text = "刪除行程",
                    data = f'delete_schedule&{data[0]}&{1}'
                )
            ]
        )
    )
    line_bot_api.reply_message(reply_token, buttons_template_message)




threading.Thread(target=periodGuy, args=(alertList, alerted), daemon=True, name='periodGuy').start()


import os
if __name__ == "__main__":
    port = int(os.environ.get('PORT', config.port))
    app.run(host='0.0.0.0', port=port, debug=True)