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
from app.views.backUpdate import updateRecords, update_unit_and_value
from app import app, db, logger, __version__
from app.models import Miner, MinerModel, Settings
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
    active_miners = []
    inactive_miners = []
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
    total_miner_info = {"L3+": {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0},
                        "S7":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0},
                        "S9":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0},
                        "D3":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0},
                        "T9":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0},
                        "A3":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0},
                        "L3":  {"sum": 0, "ok": 0, "err": 0, "war": 0, "offline": 0},}
    total_hash_rate_per_model = {"L3+": {"value": 0, "unit": "MH/s" },
                                "S7": {"value": 0, "unit": "GH/s" },
                                "S9": {"value": 0, "unit": "GH/s" },
                                "D3": {"value": 0, "unit": "MH/s" },
                                "T9": {"value": 0, "unit": "TH/s" },
                                "A3": {"value": 0, "unit": "GH/s" },
                                "L3": {"value": 0, "unit": "MH/s" },}
                                
    
    errors = False
    miner_errors = {}
    
    for miner in miners:
        errors = False
        miner_stats = Miner.query.filter_by(ip=miner.ip).first()
        total_miner_info[miner.model.model]["sum"] += 1
        if miner_stats.online == '0':
            errors = True
            inactive_miners.append(miner)
            total_miner_info[miner.model.model]["offline"] += 1
        else:
            active_miners.append(miner)
            
            
        chips_list = [int(y) for y in str(miner.model.chips).split(',')]
        total_chips = sum(chips_list)           
        Os = miner.chipsOs
        Xs = miner.chipsXs
        temps = miner.tem  
        if temps[0] == '[':
            temps = temps[1:-1]
            temps = temps.split(',')
        else:
            temps = ['0']
        if int(Xs) > 0:
            error_message = "[WARNING] '{}' chips are defective on miner '{}'.".format(Xs, miner.ip)
            logger.warning(error_message)
#            flash(error_message, "alert-warning")
            errors = True
            miner_errors.update({miner.ip: error_message})
            total_miner_info[miner.model.model]["war"] += 1
        if (int(Os) + int(Xs) < total_chips) and (int(Os) + int(Xs) != 0):        
            error_message = "[ERROR] ASIC chips are missing from miner '{}'. Your Antminer '{}' has '{}/{} chips'." \
                    .format(miner.ip,
                            miner.model.model,
                            Os + Xs,
                            total_chips)
            logger.error(error_message)
#            flash(error_message, "alert-danger")
            errors = True
            miner_errors.update({miner.ip: error_message})
            total_miner_info[miner.model.model]["err"] += 1
        if int(max(temps)) >= 80:
            error_message = "[WARNING] High temperatures on miner '{}'.".format(miner.ip)
            logger.warning(error_message)
#            flash(error_message, "alert-warning")
            total_miner_info[miner.model.model]["war"] += 1
            errors = True
            
        
        if errors == False:
           total_miner_info[miner.model.model]["ok"] += 1
        ghs5s = miner.hash
        ghs5s = ghs5s[0:-4] 
        if ghs5s == '':
            ghs5s = 0
#        value, unit = update_unit_and_value(float(ghs5s), total_hash_rate_per_model[miner.model.model]['unit'])
#        hash_rates.update({miner.ip: "{:3.2f} {}".format(value, unit)})
        total_hash_rate_per_model[miner.model.model]["value"] += float(ghs5s)
        check_rate = (float(ghs5s) / miner_hashrate[miner.model.model]) * 100
        if (check_rate < 80) and (check_rate != 0):
            error_message = "[WARNING] Low Hashrate '{}'.".format(miner.ip)
            logger.warning(error_message)
#            flash(error_message, "alert-warning")
            total_miner_info[miner.model.model]["war"] += 1
            errors = True    
        
        
        
        
    # Flash success/info message
    if not miners:
        error_message = "[INFO] No miners added yet. Please add miners using the above form."
        logger.info(error_message)
#        flash(error_message, "alert-info")
    elif not errors:
        error_message = "[INFO] All miners are operating normal. No errors found."
        logger.info(error_message)
#        flash(error_message, "alert-info")

    # flash("INFO !!! Check chips on your miner", "info")
    # flash("SUCCESS !!! Miner added successfully", "success")
    # flash("WARNING !!! Check temperatures on your miner", "warning")
    # flash("ERROR !!!Check board(s) on your miner", "error")



    total_hash_rate_per_model_temp = {}
    for key in total_hash_rate_per_model:
        value, unit = update_unit_and_value(total_hash_rate_per_model[key]["value"], total_hash_rate_per_model[key]["unit"])
        if value > 0:
            total_hash_rate_per_model_temp[key] = "{:3.2f} {}".format(value, unit)

    return render_template('myminers.html',
                           version=__version__,
                           models=models,
                           inactive_miners=inactive_miners,
                           miner_errors=miner_errors,
                           total_hash_rate_per_model=total_hash_rate_per_model_temp,
                           total_miner_info=total_miner_info,
                           miners=active_miners,
                           )


                       
                           

@app.route('/add', methods=['GET', 'POST'])
def add_views():
    # always "blindly" load the user
    miner = Miner.query.first()
    models = MinerModel.query.all()
    # forms loaded through db relation
    return render_template('add.html', 
                           models=models)

                           
@app.route('/addminers', methods=['GET', 'POST'])
def addminers():
    """Mass add miners..."""
    miners_model_id = request.form['model_id']

    miners_list = request.form['ip_list']
    miners_list = miners_list.split('\n')

    
    
    for miner_ip in miners_list:    
        if isgoodipv4(miner_ip):
            try:
                miner = Miner(ip=miner_ip, model_id=miners_model_id, remarks='', 
                    worker = '0',
                    chipsOs = '0', 
                    chipsXs = '0', 
                    chipsl = '0', 
                    tem = '0', 
                    fan = '0', 
                    hash = '0', 
                    hwerorr = '0', 
                    uptime = '0', 
                    online = '0', 
                    last = '0')
                db.session.add(miner)
                db.session.commit()
                flash("Miner with IP Address {} added successfully".format(miner.ip), "alert-success")
            except IntegrityError as e:
                db.session.rollback()
                flash("IP Address {} already added".format(miner_ip), "alert-danger")
        else:
            flash("IP: {} is not correct".format(miner_ip), "alert-danger")    
    return redirect(url_for('add_views'))

    

    
    
@app.route('/reboot/<ip>')
def reboot_miner(ip):
    
    cmd = 'root@{}'.format(ip)

    print(cmd)
      
    try:
        subprocess.Popen(["ssh",cmd,"/sbin/reboot"])
    except subprocess.CalledProcessError as e:
        print('Command \n> {}\n is fail with error: {}'.format(e.cmd, e.returncode))
    
    
    
    return redirect(url_for('miners'))
    
    
    
    
    
    
    


@app.route('/delete/<ip>')
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






t = ClockThread(1)
t.start()