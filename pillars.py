from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_bootstrap import Bootstrap
from flask_socketio import SocketIO
from flask_apscheduler import APScheduler
import yaml, json, os, time, logging, subprocess
from datetime import datetime
from logging.handlers import RotatingFileHandler
from zipfile import ZipFile
from pprint import pprint

# Needed for SocketIO to actually work...
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config['secret'] = 's;ldi3r#$R@lkjedf$'

bootstrap = Bootstrap(app)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
socketio = SocketIO(app)

if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/event.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Startup...')

def current_time():
    current_time = str(datetime.now().time())
    no_sec = current_time.split('.')
    time = no_sec.pop(0)
    return time

def get_nebulas():
    nebulas = []
    for root, dirs, files in os.walk(r'certs/ca'):
        for file in files:
            if file.endswith('.crt'):
                split = file.split(".")
                file = split.pop(0)
                nebulas.append(f'{file}')
    print(nebulas)
    return nebulas

@app.route('/pillars', methods=['GET', 'POST'])
def pillars():
    nebulas = get_nebulas()
    return render_template('pillars.html', title='Pillars', nebulas=nebulas)

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
# @login_required
def index():
    return redirect(url_for('pillars'))

@socketio.on('connect')
def connect():
    print('Client connected!')

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected')

@socketio.on('nebula_refresh')
def nebula_refresh(data):
    nebulas = get_nebulas()
    socketio.emit('nebula_refresh', nebulas)

@socketio.on('nebula_create')
def socket_event(data):
    name = str(data["data"]["name"])
    command = f'.\cert.exe ca -name "{name}" -out-crt "certs\ca\{name}.crt" -out-key "certs\ca\{name}.key"'
    output = subprocess.run(command, capture_output=True)

    if output.returncode != 0:
        data['error'] = str(output.stderr)
        socketio.emit('return', data)
        return

    # Read the certificates created - WIP
    #with open(f'certs\ca\{name}.crt') as crt_f:
         #data["crt"] = crt_f.read()

    #with open(f'certs\ca\{name}.key') as key_f:
         #data["key"] = key_f.read()
    
    socketio.emit('return', data)

@socketio.on('nebula_join')
def nebula_join(data):
    print(f'Flask received: {data}')
    nebula = str(data["data"]["nebula"])
    device_name = str(data["data"]["device_name"])
    device_ip = str(data["data"]["device_ip"])
    device_group = str(data["data"].get("device_group", ''))
    lh_location = str(data["data"].get("lh_location", ''))
    lh_port = str(data["data"].get("lh_port", ''))
    lh_ip = str(data["data"].get("lh_ip", ''))

    if lh_location and lh_port:
        lh = lh_location + ':' + lh_port

    device_ip_no_cidr = device_ip.split('/')
    device_ip_no_cidr = device_ip_no_cidr.pop(0)
    pprint(device_ip_no_cidr)

    # Create certificates for the endpoint
    command = f'.\cert.exe sign -name "{device_name}" -ip "{device_ip}" -ca-crt "certs\ca\{nebula}.crt" -ca-key "certs\ca\{nebula}.key" -out-crt "certs\{device_name}.crt" -out-key "certs\{device_name}.key"'
    output = subprocess.run(command, capture_output=True)

    # If an error is returned, stop and return the error.
    if output.returncode != 0:
        data['error'] = str(output.stderr)
        print(output)
        socketio.emit('return', data)
        return

    # Read the certificates created - WIP
    #with open(f'certs\{device_name}.crt') as crt_f:
         #data["crt"] = crt_f.read()
         

    #with open(f'certs\{device_name}.key') as key_f:
         #data["key"] = key_f.read()
         

    # Create config file for endpoint
    config = 'config.yml'
    
    with open(config, 'r') as outfile:
        d = yaml.load(outfile, Loader=yaml.SafeLoader)
    
    # Lighthouse logic
    if lh_ip == device_ip_no_cidr:
        d['lighthouse']['am_lighthouse'] = True
        del d['lighthouse']['hosts']
        d['listen']['host'] = f'0.0.0.0'
        d['listen']['port'] = lh_port
    else:
        d['lighthouse']['am_lighthouse'] = False
        d['lighthouse']['hosts'][0] = f'{lh_ip}'
        d['listen']['host'] = '0.0.0.0'
        d['listen']['port'] = 0

    # Required:
    d['pki']['ca'] = f'{nebula}.crt'
    d['pki']['cert'] = f'{device_name}.crt'
    d['pki']['key'] = f'{device_name}.key'

    newlist = []

    if lh_ip:
        newlist.append(lh)
        d['static_host_map'] = dict()
        d['static_host_map'][f'{lh_ip}'] = ''
        d['static_host_map'][f'{lh_ip}'] = newlist
    else:
        del d['static_host_map']
    
    # Save the new endpoint config file
    with open(f'configs\{nebula}_{device_name}.yml', 'w') as outfile:
        yaml.dump(d, outfile, default_style='' , default_flow_style=False)
    

    with ZipFile(f'static\zips\{nebula}_{device_name}.zip', 'w') as myzip:
        myzip.write(f'certs\ca\{nebula}.crt', f'{nebula}.crt')
        myzip.write(f'certs\{device_name}.crt', f'{device_name}.crt')
        myzip.write(f'certs\{device_name}.key', f'{device_name}.key')
        myzip.write(f'configs\{nebula}_{device_name}.yml', f'{nebula}_{device_name}.yml')
    
    data['zip_location'] = f'static\zips\{nebula}_{device_name}.zip'
    socketio.emit('return', data)

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=80, debug=True)
