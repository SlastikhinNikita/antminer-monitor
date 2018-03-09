from flask import (jsonify,
                   render_template,
                   request,
                   redirect,
                   url_for,
                   flash,
                   )
from flask.views import MethodView
from app.views.antminer_json import (get_summary,
                                     get_pools,
                                     get_stats,
                                     )
from sqlalchemy.exc import IntegrityError
from app.pycgminer import CgminerAPI
from app.views.backUpdate import updateRecords, updateHistory, update_unit_and_value
from app import app, db, logger, __version__
from app.models import Miner, History, MinerModel, Settings
import re
from datetime import timedelta,datetime

import threading
import ast
import time
import subprocess




class ClockThread(threading.Thread):
    def __init__(self,interval):
        threading.Thread.__init__(self)
        self.daemon = True
        self.interval = interval
    def run(self):
        while True:
            try:
                updateRecords()
            finally:
                time.sleep(self.interval)

class ClockThread2(threading.Thread):
    def __init__(self,interval):
        threading.Thread.__init__(self)
        self.daemon = True
        self.interval = interval
    def run(self):
        while True:
                updateHistory()
                time.sleep(self.interval)

# Update from one unit to the next if the value is greater than 1024.
# e.g. update_unit_and_value(1024, "GH/s") => (1, "TH/s")


def isgoodipv4(s):
    pieces = s.split('.')
    if len(pieces) != 4: return False
    try: return all(0<=int(p)<256 for p in pieces)
    except ValueError: return False





@app.route('/')
def miners():
    # Init variables
    miners = Miner.query.all()
    models = MinerModel.query.all()
    workers = {}
    miner_chips = {}
    temperatures = {}
    fans = {}
#    hash_rates = {}
    hw_error_rates = {}
    uptimes = {}
    miner_hashrate = {"L3+": 504,
                       "S7": 4.5,
                       "S9": 13.5,
                       "D3": 17,
                       "T9": 12.5,
                       "A3": 815,
                       "L3": 250,}
    total_miner_info = {"L3+": {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0,"value": 0, "unit": "MH/s"},
                        "All":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0,"value": 0, "unit": "", "evg" : 0},
                        "S7":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0,"value": 0, "unit": "GH/s"},
                        "S9":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0,"value": 0, "unit": "GH/s"},
                        "D3":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0,"value": 0, "unit": "MH/s"},
                        "T9":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0,"value": 0, "unit": "TH/s"},
                        "A3":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0,"value": 0, "unit": "GH/s"},
                        "L3":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0,"value": 0, "unit": "MH/s"},}
    total_hash_rate_per_model = {"L3+": {"value": 0, "unit": "MH/s" },
                                "S7": {"value": 0, "unit": "GH/s" },
                                "S9": {"value": 0, "unit": "GH/s" },
                                "D3": {"value": 0, "unit": "MH/s" },
                                "T9": {"value": 0, "unit": "TH/s" },
                                "A3": {"value": 0, "unit": "GH/s" },
                                "L3": {"value": 0, "unit": "MH/s" },}


    errors = False
    miner_errors = {}
    miner_wars = {}
    miner_offline = {}

    for miner in miners:
        errors = False
        miner_stats = Miner.query.filter_by(ip=miner.ip).first()
        total_miner_info[miner.model.model]["sum"] += 1
        if miner_stats.online == '0':
            errors = True
            total_miner_info[miner.model.model]["offline"] += 1
            error_message = "Offline"
            miner_offline.update({miner.ip: error_message})

        chips_list = [int(y) for y in str(miner.model.chips).split(',')]
        total_chips = sum(chips_list)
        Os = miner.chipsOs
        Xs = miner.chipsXs
        temps = miner.tem
        
        ghs5s = miner.hash
        ghs5s = ghs5s[0:-4]
        if ghs5s == '':
            ghs5s = 0
        total_miner_info[miner.model.model]["value"] += float(ghs5s)        
        check_rate = (float(ghs5s) / miner_hashrate[miner.model.model]) * 100

        if temps[0] == '[':
            temps = temps[1:-1]
            temps = temps.split(',')
        else:
            temps = ['0']
        if temps[0] == '':
           temps = ['0']

        if (int(Xs) > 0) or ((int(Os) + int(Xs) < total_chips) and (int(Os) + int(Xs) != 0)):
            error_message = "Error"                        # "[ERROR] '{}' chips are defective on miner.".format(Xs)
            errors = True
            miner_errors.update({miner.ip: error_message})
            total_miner_info[miner.model.model]["err"] += 1

        elif int(max(temps)) >= 80:
            error_message = "Warning High temperature"                        # [WARNING] High temperatures on miner.
            total_miner_info[miner.model.model]["war"] += 1
            errors = True

#        elif (check_rate < 80) and (check_rate != 0):
#            error_message = "Warning Low Hashrate."            #  "[WARNING] Low Hashrate."
#            total_miner_info[miner.model.model]["war"] += 1
#            errors = True    
#            miner_wars.update({miner.ip: error_message})

#        elif (check_rate > 120) and (check_rate != 0):
#            error_message = "Warning Hashrate Error."            #  "[WARNING] Low Hashrate."
#            total_miner_info[miner.model.model]["war"] += 1
#            errors = True    
#            miner_wars.update({miner.ip: error_message})




        if errors == False:
           total_miner_info[miner.model.model]["ok"] += 1


    # Flash success/info message
    if not miners:
        error_message = "[INFO] No miners added yet. Please add miners using the above form."
#        logger.info(error_message)
#        flash(error_message, "alert-info")
    elif not errors:
        error_message = "[INFO] All miners are operating normal. No errors found."
#        logger.info(error_message)
#        flash(error_message, "alert-info")

    # flash("INFO !!! Check chips on your miner", "info")
    # flash("SUCCESS !!! Miner added successfully", "success")
    # flash("WARNING !!! Check temperatures on your miner", "warning")
    # flash("ERROR !!!Check board(s) on your miner", "error")


    total_miner_info['All']["offline"] = sum(x['offline'] for x in total_miner_info.values())
    total_miner_info['All']["err"] = sum(x['err'] for x in total_miner_info.values())
    total_miner_info['All']["sum"] = sum(x['sum'] for x in total_miner_info.values())
    total_miner_info['All']["war"] = sum(x['war'] for x in total_miner_info.values())
    total_miner_info['All']["ok"] = sum(x['ok'] for x in total_miner_info.values())
    total_miner_info['All']["value"] = sum(x['value'] for x in total_miner_info.values())

    total_hash_rate_per_model_temp = {}
    for key in total_hash_rate_per_model:
        value, unit = update_unit_and_value(total_hash_rate_per_model[key]["value"], total_hash_rate_per_model[key]["unit"])
        if value > 0:
            total_hash_rate_per_model_temp[key] = "{:3.2f} {}".format(value, unit)

    return render_template('myminers.html',
                           version=__version__,
                           models=models,
                           miner_errors=miner_errors,
                           miner_offline=miner_offline,
                           miner_wars=miner_wars,
                           total_hash_rate_per_model=total_hash_rate_per_model_temp,
                           total_miner_info=total_miner_info,
                           miners=miners,
                           )





@app.route('/add', methods=['GET', 'POST'])
def add_views():

    miner = Miner.query.first()
    models = MinerModel.query.all()
    return render_template('add.html',
                           models=models)


@app.route('/addminers', methods=['GET', 'POST'])
def addminers():
    """Mass add miners..."""
    miners_model_id = request.form['model_id']

    miners_list = request.form['ip_list']
    miners_list = miners_list.split('\r\n')



    for miner_ip in miners_list:
        if isgoodipv4(miner_ip):
            try:
                miner = Miner(ip=miner_ip, model_id=miners_model_id, remarks='',
                    worker = '',
                    chipsOs = '0',
                    chipsXs = '0',
                    chipsl = '0',
                    tem = '0',
                    fan = '',
                    hash = '',
                    hwerorr = '',
                    uptime = '',
                    online = '0',
                    last = '')
                db.session.add(miner)
                db.session.commit()
                flash("Miner with IP Address {} added successfully".format(miner.ip), "alert-success")
            except IntegrityError as e:
                db.session.rollback()
                flash("IP Address {} already added".format(miner_ip), "alert-danger")
        else:
            flash("IP: {} is not correct".format(miner_ip), "alert-danger")
    return redirect(url_for('add_views'))





@app.route('/reboot/<ip>', methods=['POST'])
def reboot_miner(ip):
    print("run reboot {}".format(ip))
    try:
        subprocess.Popen(["./reboot_mine",ip])
    except subprocess.CalledProcessError as e:
        print('Command \n> {}\n is fail with error: {}'.format(e.cmd, e.returncode))



    return redirect(url_for('miners'))



#@app.route('/_get_data/', methods=['POST'])
#def _get_data():
#    myList = ['Element1', 'Element2', 'Element3']

#    return jsonify({'data': render_template('response.html', myList=myList)})






@app.route('/delete/<ip>', methods=['POST'])
def delete_miner(ip):
    try:
        miner = Miner.query.filter_by(ip=str(ip)).first()
        db.session.delete(miner)
        db.session.commit()
        error_message = "[INFO] Deleted {} successfully.".format(ip)
        logger.info(error_message)
#        flash(error_message, "alert-success")
    except IntegrityError as e:
        db.session.rollback()
#        flash("IP Address {} Erorr".format(ip), "alert-danger")
    return redirect(url_for('miners'))


@app.route('/history/<ip>')
def history_miner(ip):

    miner_history = History.query.filter_by(ip=str(ip))

    return render_template('history.html',
                           miner_history=miner_history,ip=ip)


						   
						   


t = ClockThread(10)
t.start()
						   
t = ClockThread2(10)
t.start()

