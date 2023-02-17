from .shared_db_model import db
from datetime import datetime, timedelta, timezone

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