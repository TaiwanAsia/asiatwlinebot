from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone

db = SQLAlchemy()

class Activities(db.Model):

    __tablename__ = 'activities'

    id         = db.Column(db.Integer, primary_key=True)
    userid     = db.Column(db.String(45), nullable=False)
    time       = db.Column(db.DateTime, nullable=True)
    title      = db.Column(db.String(225), nullable=True)
    status     = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"))


    def __repr__(self):
        return '<Activities %r  -  %r  %r  %r  %r>' % (self.id, self.userid, self.time, self.title, self.status)

    def add(self):
        db.session.add(self)
        try:
            db.session.commit()
        except Exception as e:
            # db.session.rollback()
            print(e+'\n')
            # logger.exception(e)

    def get_all_by_userid(userid):
        return Activities.query.filter_by(userid=userid).all()

    def find_by_title(userid, title):
        userid_filter = Activities.userid == userid
        title_filter  = Activities.title.like('%{}%'.format(title))
        query = Activities.query.filter(userid_filter, title_filter)
        return query.all()

    def delete_unchecked_activities():
        print("定時清除未完成行程")
        status_filter = Activities.status.in_('日期待確認','待確認').all()
        activities = Activities.query.filter(status_filter).all()
        print(activities)
        db.session.delete(activities)
        db.session.commit()




class Activities_routine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.String(80), nullable=False)
    title = db.Column(db.Text, nullable=True)
    frequency = db.Column(db.Text, nullable=False)
    frequency_2 = db.Column(db.Text, nullable=True)
    time = db.Column(db.Time, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"))

    def __repr__(self):
        return '<Activities_routine %r>' % self.activity_routine






class Notes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.String(80), nullable=False)
    title = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"))
    
    def __repr__(self):
        return '<Notes %r>' % self.note






class Group(db.Model):
    __tablename__ = 'group'

    id          = db.Column(db.Integer, primary_key=True)
    group_id    = db.Column(db.String(50), nullable=False)
    user_ids    = db.Column(db.String(225), nullable=False, default='')
    text_reply  = db.Column(db.String(10), nullable=False, default='on')
    image_reply = db.Column(db.String(10), nullable=False, default='on')
    file_reply  = db.Column(db.String(10), nullable=False, default='on')
    last_message_time = db.Column(db.DateTime, nullable=True)
    updated_at  = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs) -> None:
        super(Group, self).__init__(**kwargs)

    def __repr__(self):
        return '<user %r  %r %r>' % (self.id, self.group_id, self.user_ids)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def get_by_group_id(group_id):
        return Group.query.filter_by(group_id=group_id).first()

    def turn_on_off_text_reply(self, mode):
        self.text_reply = mode        
        db.session.commit()
    
    def turn_on_off_file_reply(self, mode):
        self.file_reply = mode        
        db.session.commit()
    
    def turn_on_off_image_reply(self, mode):
        self.image_reply = mode        
        db.session.commit()



class User(db.Model):
    __tablename__ = 'user'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.String(50), nullable=False)
    is_member   = db.Column(db.String(10), nullable=False, default='no')
    is_admin    = db.Column(db.String(10), nullable=False, default='no')
    text_reply  = db.Column(db.String(10), nullable=False, default='on')
    image_reply = db.Column(db.String(10), nullable=False, default='on')
    file_reply  = db.Column(db.String(10), nullable=False, default='on')
    join_member_time  = db.Column(db.DateTime, nullable=True)
    last_message_time = db.Column(db.DateTime, nullable=True)
    updated_at  = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs) -> None:
        super(User, self).__init__(**kwargs)

    def __repr__(self):
        return '<user %r  %r %r>' % (self.id, self.user_id, self.last_message_time)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def get_by_user_id(user_id):
        return User.query.filter_by(user_id=user_id).first()

    def turn_on_off_text_reply(self, mode):
        self.text_reply = mode        
        db.session.commit()
    
    def turn_on_off_file_reply(self, mode):
        self.file_reply = mode        
        db.session.commit()
    
    def turn_on_off_image_reply(self, mode):
        self.image_reply = mode        
        db.session.commit()