#!/usr/bin/env python3
#  -*- coding: utf-8 -*-

import random
import string
from bottle import route, run, get, static_file, request, response, redirect, post


class Session:
    def __init__(self, password):
        self.password = password
        self.sessions = []

    def login(self, password):
        if password is None:
            print("login request")
            return False
        elif password in self.password:
            session_id = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(10))
            if session_id not in self.sessions:
                self.sessions.append(session_id)
                self.sessions = self.sessions[-25:]  # limit to the latest 25 logins
            response.set_cookie('session', session_id, max_age=31556952 * 2)
            print("login successful, new session:", session_id)
            return True
        else:
            print("login attempt with invalid password:", password)
            return False

    def is_valid(self, session_id):
        if session_id is None:
            print("no session cookie set")
            return False
        elif session_id in self.sessions:
            print("session is valid:", session_id)
            return True
        else:
            print("invalid session:", session_id)
            return False

session = Session(password=['1234', '9999'])


@route('/')
def index():
    if session.is_valid(request.get_cookie('session')):
        content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="X-UA-Compatible" content="ie=edge">
            <meta name="mobile-web-app-capable" content="yes">
            <meta name="apple-mobile-web-app-capable" content="yes">
            <link rel="manifest" href='data:application/manifest+json,{"name": "Runloop", "scope": "/", "display": "standalone"}' />
            <title>Application</title>
        </head>
        <body style="background-color: #ddddff">
            <h1>Application</h1>
        </body>
        </html>"""
        return content
    else:
        redirect('/login')


@route('/login')
@post('/login')
def login():
    if session.login(request.forms.get("password", default=None)):
        redirect('/')
    else:
        content = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta http-equiv="X-UA-Compatible" content="ie=edge">
                <meta name="mobile-web-app-capable" content="yes">
                <meta name="apple-mobile-web-app-capable" content="yes">
                <link rel="manifest" href='data:application/manifest+json,{"name": "Runloop", "scope": "/", "display": "standalone"}'/>
                <title>Login</title>
            </head>
            <body style="background-color: #ffeeee">
                <h1>Login</h1>
                <form action="/login" method="POST">
                    <input type="password" id="password" name="password" minlength="4"><br><br>
                    <input type="submit">
                </form>
            </body>
            </html>"""
        return content


@route('/debug')
def debug():
    return "{}".format(session.sessions)

@route('/debug/revoke')
def revoke():
    session.sessions = []
    return "{}".format(session.sessions)

run(host='0.0.0.0', server='waitress', port=8000)