from flask import flash
from app import app, db, logger
from app.models import Miner, MinerModel
from app.views.antminer_json import (get_summary,
                                     get_pools,
                                     get_stats,
                                     )
import re
from datetime import timedelta, datetime
from multiprocessing import Process

def update_unit_and_value(value, unit):
    while value > 1024:
        value = value / 1024.0
        if unit == 'MH/s':
            unit = 'GH/s'
        elif unit == 'GH/s':
            unit = 'TH/s'
        elif unit == 'TH/s':
            unit = 'PH/s'
        elif unit == 'PH/s':
            unit = 'EH/s'
        else:
            assert False, "Unsupported unit: {}".format(unit)
    return (value, unit)




def getAndUpdate(miner):

    active_miners = []
    errors = False

    rec_ip={}
    rec_worker={}
    rec_model_id={}
    rec_remarks={}
    rec_chipsOs={}
    rec_chipsXs={}
    rec_chipsl={}
    rec_tem={}
    rec_fan={}
    rec_hash={}
    rec_hwerorr={}
    rec_uptime={}
    rec_online={}
    total_hash_rate_per_model = {"L3+": {"value": 0, "unit": "MH/s" },
                                "S7": {"value": 0, "unit": "GH/s" },
                                "S9": {"value": 0, "unit": "GH/s" },
                                "D3": {"value": 0, "unit": "MH/s" },
                                "T9": {"value": 0, "unit": "TH/s" },
                                "A3": {"value": 0, "unit": "GH/s" },
                                "L3": {"value": 0, "unit": "MH/s" },}

    if Miner.query.filter_by(ip=miner.ip).first() is not None:
        miner_stats = get_stats(miner.ip)
#            print(miner_stats)
        rec_last = str(datetime.now().strftime('%H:%M:%S %d/%m/%Y'))
        if miner_stats['STATUS'][0]['STATUS'] == 'error':
            errors = True
            rec_ip = miner.ip
            rec_worker = '0'
            rec_model_id = miner.model_id
            rec_remarks = miner.remarks
            rec_chipsOs = '0'
            rec_chipsXs = '0'
            rec_chipsl = '0'
            rec_tem = '0'
            rec_fan = '0'
            rec_hash = '0'
            rec_hwerorr = '0'
            rec_uptime = '0'
            rec_online = '0'
        else:
            rec_ip=miner.ip
            rec_online = '1'

            miner_pools = get_pools(miner.ip)

            try: rec_worker = miner_pools['POOLS'][0]['User']
            except: rec_worker = '0'
			
			
            rec_model_id = miner.model_id

            rec_remarks = miner.remarks


            asic_chains = [miner_stats['STATS'][1][chain] for chain in miner_stats['STATS'][1].keys() if
                            "chain_acs" in chain]
            O = [str(o).count('o') for o in asic_chains]
            rec_chipsOs = sum(O)
            X = [str(x).count('x') for x in asic_chains]
            rec_chipsXs = sum(X)
            _dash_chips = [str(x).count('-') for x in asic_chains]
            rec_chipsl = sum(_dash_chips)

            rec_tem = [int(miner_stats['STATS'][1][temp]) for temp in
                    sorted(miner_stats['STATS'][1].keys(), key=lambda x: str(x)) if
                    re.search(miner.model.temp_keys + '[0-9]', temp) if miner_stats['STATS'][1][temp] != 0]

            rec_fan = [miner_stats['STATS'][1][fan] for fan in
                        sorted(miner_stats['STATS'][1].keys(), key=lambda x: str(x)) if
                        re.search("fan" + '[0-9]', fan) if miner_stats['STATS'][1][fan] != 0]


            ghs5s = float(str(miner_stats['STATS'][1]['GHS 5s']))
            value, unit = update_unit_and_value(ghs5s, total_hash_rate_per_model[miner.model.model]['unit'])
            rec_hash = "{:3.2f} {}".format(value, unit)

            rec_hwerorr = miner_stats['STATS'][1]['Device Hardware%']

            rec_uptime = timedelta(seconds=miner_stats['STATS'][1]['Elapsed'])


        try:
#                if Miner.query.filter_by(ip=miner.ip).first() is None:
#                    record = Temp(ip=rec_ip, \
#                                  worker=str(rec_worker), \
#                                  model_id= rec_model_id, \
#                                  remarks=str(rec_remarks), \
#                                  chipsOs=str(rec_chipsOs), \
#                                  chipsXs=str(rec_chipsXs), \
#                                  chipsl=str(rec_chipsl), \
#                                  tem=str(rec_tem), \
#                                  fan=str(rec_fan), \
#                                  hash=str(rec_hash), \
#                                  hwerorr=str(rec_hwerorr), \
#                                  uptime=str(rec_uptime), \
#                                  online=str(rec_online), \
#                                  last=str(rec_last))
#                    db.session.add(record)
#                    db.session.commit()

#                else:
            record = Miner.query.filter_by(ip=rec_ip).first()
            record.worker = str(rec_worker)
            record.model_id = rec_model_id
            record.remarks = str(rec_remarks)
            record.chipsOs = str(rec_chipsOs)
            record.chipsXs = str(rec_chipsXs)
            record.chipsl = str(rec_chipsl)
            record.tem = str(rec_tem)
            record.fan = str(rec_fan)
            record.hash = str(rec_hash)
            record.hwerorr = str(rec_hwerorr)
            record.uptime = str(rec_uptime)
            record.online = str(rec_online)
            record.last = str(rec_last)
            db.session.commit()
            error_message = "IP Address {} updated".format(rec_ip)
#                    flash(error_message, "alert-success")
            logger.info(error_message)
        except:
            db.session.rollback()
            error_message = "[ERROR] Some shit happen!"
            logger.info(error_message)
#                flash(error_message, "alert-danger")

    
    
    
    
def updateRecords():
    """Add two numbers server side, ridiculous but well..."""
    miners = Miner.query.all()
    i = 0

    for miner in miners:
        a = getAndUpdate(miner)
        p = Process(target=a, args=(i,))
        p.start()
        i = i + 1
    
    

