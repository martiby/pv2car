#!/usr/bin/env python3

import json
from datetime import datetime
from bottle import request, static_file, route, run, post, get

data = {}

@route('/')
@post('/')
def index():
    data['time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data['timestamp'] = int(datetime.utcnow().timestamp())
    return data

@route('/sim')
@post('/sim')
def push():
    try:
        post = json.loads(request.body.read())
        print("sim data received: {}".format(post))
        for k, v in post.items():
            data[k] = v
        return data
    except:
        return static_file('sim.html', root='')

@route('/command/<target>')
def command(target=None):
    """
    Handle commands: /command/<target>
    Returns: Dictionary with dataset
    """
    print("web_command target={} command={}".format(target, request.query_string))

    return data



run(host='0.0.0.0', server='waitress', port=8008)
