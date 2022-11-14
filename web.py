import json
import os
import threading
import logging

from bottle import Bottle
from bottle import request, response, redirect
from bottle import static_file
from config import config
from session import Session


class AppWeb:
    """
    Webserverintegration for PV2Car application
    """

    def __init__(self, app, log='web'):
        self.app = app  # reference to application
        self.log = logging.getLogger(log)
        self.web = Bottle()  # webserver
        self.session = Session(password=config['password'])
        # setup routes
        self.web.route('/', callback=self.web_static)  # hosting static files
        self.web.route('/<filepath:path>', callback=self.web_static)  # hosting static files
        self.web.route('/login', callback=self.web_login, method=('GET', 'POST'))  # application state in json format
        self.web.route('/api/state', callback=lambda: self.app.data)  # application state in json format
        self.web.route('/api/set', callback=self.web_api_set)  # change settings
        self.web.route('/version', callback=lambda: {'version': self.app.version})
        self.web.route('/app-var', callback=self.web_app_var)
        self.web.route('/log', callback=self.web_log)  # access to logfile
        # start webserver thread
        threading.Thread(target=self.web.run, daemon=True,
                         kwargs=dict(host='0.0.0.0', port=config['http_port'], server='waitress')).start()

    def web_static(self, filepath='index.html'):
        """
        Webserver interface for static files        /<filepath:path>
        """
        session_id = request.get_cookie('session')
        remote_addr = request.environ.get('REMOTE_ADDR')

        if self.session.is_valid(session_id):  # static files only after login (session)
            self.log.debug("request to: {} from: {} with valid session_id: {}".format(filepath, remote_addr, session_id))
            return static_file(filepath, root=config['www_path'])
        else:
            if session_id:
                self.log.error("request to: {} from: {} with unknown session_id: {}, redirect to /login".format(filepath, remote_addr, session_id))
            else:
                self.log.error("request to: {} from: {} without session_id, redirect to /login".format(filepath, remote_addr))
            redirect('/login')

    def web_login(self):
        """
        Login view
        :return:
        """
        password = request.forms.get("password", default=None)
        remote_addr = request.environ.get('REMOTE_ADDR')
        if password is None:
            self.log.error("login form request from {}".format(remote_addr))
        elif self.session.login(password):
            self.log.info("login from {} successful, redirect to /".format(remote_addr))
            redirect('/')
            return
        else:
            self.log.error("login attempt from {} with invalid password: {}".format(remote_addr, password))
        return static_file('login.html', root=config['www_path'])

    def web_app_var(self):
        cfg = {k: config[k] for k in ['pvmin_levels', 'control_reserve_levels']}
        return 'config={};version="{}"'.format(json.dumps(cfg), self.app.version)  # access to config and version in json format

    def web_log(self):
        """
        Webserver interface to access the logfile   /log
        """
        response.content_type = 'text/plain'
        return open(os.path.join(config['log_path'], 'log.txt'), 'r').read()

    def web_api_set(self):
        """
        Webserver interface to change settings      /api/set
        """
        session_id = request.get_cookie('session')
        if not self.session.is_valid(session_id):
            return 'login required'

        try:
            self.app.control_reserve = min(max(int(request.query.get('control-reserve', None)), 0), 1000)
        except:
            pass

        pvmin = request.query.get('pvmin', None)
        if pvmin is not None:
            self.app.pvmin = pvmin

        if request.query.get('auto-phase', None) == 'false':
            self.app.auto_phase = False
        if request.query.get('auto-phase', None) == 'true':
            self.app.auto_phase = True

        user_cmd = request.query.get('cmd', None)

        self.app.user_cmd_handler(user_cmd)
        self.app.call_fsm()
        self.app.log.debug("api command: user_cmd={} pvmin={} control_reserve={} auto_phase={}".format(user_cmd,
                                                                                                       self.app.pvmin,
                                                                                                       self.app.control_reserve,
                                                                                                       self.app.auto_phase))
        return self.app.data