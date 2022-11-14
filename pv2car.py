#!/usr/bin/env python3

"""
Start script from pv2car.
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from app import App
from config import config

os.makedirs(config['log_path'], exist_ok=True)  # create paths if necessary

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[TimedRotatingFileHandler(os.path.join(config['log_path'], 'log.txt'), when='midnight'),
                              logging.StreamHandler()])

logging.getLogger('waitress.queue').setLevel(logging.ERROR)  # hide waitress info log

# logging.getLogger('adapt').setLevel(logging.DEBUG)
# logging.getLogger('meterhub').setLevel(logging.DEBUG)
# logging.getLogger('web').setLevel(logging.DEBUG)


app = App()
app.main()
