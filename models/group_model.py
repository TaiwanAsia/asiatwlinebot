from .shared_db_model import db

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