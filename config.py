config = {
    'meterhub_address': 'http://192.168.0.10:8008',  # URL to meterhub if use in adapt.py
    # 'meterhub_address': 'http://localhost:8008',  # use for local meterhub simulation

    'password': ['1234', 'sjk89-2Pa'],  # Password for web access

    'http_port': 8090,  # HTTP port of the webserver
    'www_path': "www",  # path for static webserver files
    'log_path': "log",  # log path

    'pv_start_time': 10 * 60,  # [s] time above the start condition for loading start
    'pv_end_time': 5 * 60,  # [s] time below minimum charge for end of charge
    'pv_block_time': 10 * 60,  # [s] pause time before restarting charging

    'phase_start_power': 4800,  # [W] power for 3 phase operation
    'phase_end_power': 4200,  # [W] power for 1 phase operation

    'phase_start_time': 10 * 60,  # [s] time above start condition for 3 phase operation
    'phase_end_time': 10 * 60,  # [s] time below shutdown condition for 3 phase operation
    'phase_block_time': 10 * 60,  # [s] waiting time for 3 phase operation restart

    'pvmin_levels': ['25%', '50%', '75%', '100%', '7A', '9A', '12A'],  # ui setting for pvmin selection
    'control_reserve_levels': [0, 250, 500, 1000]  # ui setting for control_reserve selection
}
