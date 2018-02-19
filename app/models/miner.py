from app import db


class Miner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(15), unique=True, nullable=False)
    worker = db.Column(db.String(100), nullable=True)
    model_id = db.Column(db.Integer, db.ForeignKey('miner_model.id'), nullable=False)
    model = db.relationship("MinerModel", backref="miners")
    remarks = db.Column(db.String(255), nullable=True)
    chipsOs = db.Column(db.String(255), nullable=True)
    chipsXs = db.Column(db.String(255), nullable=True)
    chipsl = db.Column(db.String(255), nullable=True)
    tem = db.Column(db.String(255), nullable=True)
    fan = db.Column(db.String(255), nullable=True)
    hash = db.Column(db.String(255), nullable=True)
    hwerorr = db.Column(db.String(255), nullable=True)
    uptime = db.Column(db.String(255), nullable=True)
    online = db.Column(db.String(255), nullable=True)
    last = db.Column(db.String(255), nullable=True)
	
    def __repr__(self):
        return "Temp(ip='{}', \
                     worker='{}', \
                     model='{}', \
                     remarks='{}', \
                     chipsOs='{}', \
                     chipsXs='{}', \
                     chipsl='{}', \
                     tem='{}', \
                     fan='{}', \
                     hash='{}', \
                     hwerorr='{}', \
                     uptime='{}', \
                     online='{}', \
                     last='{}')".format(self.ip, \
                                               self.worker, \
                                               self.model, \
                                               self.remarks, \
                                               self.chipsOs, \
                                               self.chipsXs, \
                                               self.chipsl, \
                                               self.tem, \
                                               self.fan, \
                                               self.hash, \
                                               self.hwerorr, \
                                               self.uptime, \
                                               self.online, \
                                               self.last)