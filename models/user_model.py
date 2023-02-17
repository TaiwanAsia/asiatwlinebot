from .shared_db_model import db

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