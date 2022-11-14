import logging

from api_request import ApiRequest
from config import config

"""
All communication is done via the two functions update() and set(). The software can be customized via these two 
functions. The update function must read the values from the hardware. The set function is triggered by
the application with the three parameters (stop , phase, amp). The set function must send these to the wallbox.

In this implementation, communication does not take place directly with the wallbox because the separate application 
(meterhub) already provides the entire status of the wallbox. This means that the wallbox is not unnecessarily burdened 
by further queries. The control commands are also sent to the wallbox via (meterhub). This avoids simultaneous queries
and commands.
"""

class Adapt:
    def __init__(self):
        self.log = logging.getLogger("adapt")
        self.meterhub = ApiRequest(config['meterhub_address'], timeout=0.5, lifetime=10, log_name='meterhub')

    def update(self, app, post=None):
        """
        Query the wallbox and the necessary electricity meters
        """
        d = self.meterhub.read(post)
        self.log.debug("read: {}".format(d))

        app.state = self.meterhub.get('car_state')
        app.amp = self.meterhub.get('car_amp')
        app.wb_phase = self.meterhub.get('car_phase')  # phase from wallbox 1/3
        app.power = self.meterhub.get('car_p')
        app.charge_energy = self.meterhub.get('car_e_cycle')
        app.stop = self.meterhub.get('car_stop')
        # calculation of the available excess
        p = -self.meterhub.get('grid_p', 0) + self.meterhub.get('car_p', 0)
        if self.meterhub.get('bat_p', 0) < 0:  # Einspeisen
            p = p + self.meterhub.get('bat_p', 0)  # minus
        app.excess_p = p

    def set(self, stop=None, phase=None, amp=None):
        """
        Sending commands to the wallbox

        amp = 1..16  1..16 ampere
        stop=bool    True=force wallbox to stop, False=release wallbox  (frc=0,1     0=force release, 1=force stop)
        phase=1,3    desired phase operation        (psm=1,2     1=1-Phase 2=3-Phase)

        Wallbox:
        api/set?amp=6&frc=0&psm=1
        """
        cmd = []
        if amp is not None and 6 <= amp <= 16:
            cmd.append('amp={}'.format(amp))

        if stop is True:
            cmd.append('frc=1')
        elif stop is False:
            cmd.append('frc=0')

        if phase is not None and phase == 1:
            cmd.append('psm=1')
        elif phase is not None and phase == 3:
            cmd.append('psm=2')

        if cmd:
            cmd = '/command/goe?' + "&".join(cmd)

            if self.meterhub.read(url_extension=cmd):
                self.log.debug("set wallbox command: '{}'".format(cmd))
            else:
                self.log.error("set wallbox command: '{}' failed".format(cmd))


if __name__ == "__main__":
    import time

    class App:
        def __init__(self):
            self.state = None
            self.amp = None
            self.phase = None
            self.power = None
            self.charge_energy = None
            self.stop = None
            self.excess_p = None

    app = App()
    io = Adapt()
    while True:
        io.update(app)
        print(app.__dict__)
        time.sleep(2)
