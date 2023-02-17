import os
from models.user_model import User
from models.group_model import Group
# from models.log_model import Log
from datetime import datetime, timezone, timedelta

def check_chatroom_uploads_folder(chatroom):
    if not os.path.isdir('../uploads/'+chatroom):
        os.makedirs('./uploads/' + chatroom + '/', exist_ok=True)

def get_uploads_file(chatroom):
    check_chatroom_uploads_folder(chatroom)
    target_path = './uploads/' + chatroom
    files = os.listdir(target_path)
    for f in files:
        fullpath = os.path.join(target_path, f)
        if os.path.isfile(fullpath):
            print("檔案", f)
        elif os.path.isdir(fullpath):
            print("目錄", f)

def get_user(user_id):
    user = User.get_by_user_id(user_id)
    if user is None:
        user = add_user(user_id)
    return user

def add_user(user_id):
    user = User(user_id=user_id, last_message_time=datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"))
    user.save()
    return user

def get_group(group_id):
    group = Group.get_by_group_id(group_id)
    if group is None:
        group = add_group(group_id)
    return group

def add_group(group_id):
    group = Group(group_id=group_id, last_message_time=datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"))
    group.save()
    return group

# def add_log(chatroom, message_type, message_content):
#     chatroom_id = ''
#     if type(chatroom).__name__ == 'Group':
#         chatroom_id = chatroom.group_id
#     elif type(chatroom).__name__ == 'User':
#         chatroom_id = chatroom.user_id
#     log_user = Log(chatroom=chatroom_id, message_type=message_type, message_content=message_content, created_at=datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"))
#     log_user.save()