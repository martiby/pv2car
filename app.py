import logging
import os
import time
from datetime import datetime

from adapt import Adapt
from config import config
from filter import Filter
from timer import IntervalTimer, Timer
from web import AppWeb

"""
    Application modes:  stop, grid, pv
    Go-e states :       idle, charge, wait, complete, error
    
    stop by wallbox     charge -> complete
    remove plug         complete --> idle 
    low pv stop         charge --> complete 
"""

class App:
    def __init__(self):
        self.log = logging.getLogger('app')
        self.version = "1.3.2"
        self.log.info('start pv2car {}'.format(self.version))
        self.web = AppWeb(self)
        self.io = Adapt()  # Wallbox IO

        self.sample_timer = IntervalTimer(2)  # timer for data acquisition
        self.car_cmd_block_timer = Timer(duration=3)  # block command to prevent to many commands
        self.filter_excess_short = Filter(cut=1, avg=2)  # discard low/high and average over two
        self.filter_excess_long = Filter(cut=2, avg=26)  # filter over 1min

        # timer for pv start/stop
        self.pv_timer = Timer(duration=config['pv_start_time'])
        self.pv_block_timer = Timer(duration=config['pv_block_time'])
        self.pv_timer.set_expired()

        # timer for 3 phase start/stop
        self.phase_timer = Timer(duration=config['pv_start_time'])
        self.phase_block_timer = Timer(duration=config['pv_block_time'])
        self.phase_timer.set_expired()

        # variables
        self.pvmin = "100%"  # UI setting, see config.py with pvmin_steps
        self.auto_phase = False  # UI setting, enable 3phase operation
        self.control_reserve = 250  # UI setting for  reserve/distance for control loop

        self.excess_p = 0
        self.excess_p_short = 0  # actual excess power, minimal filtered over 3 samples
        self.excess_p_long = 0  # actual excess power, filtered over 1min

        self.mode = 'pv'
        self.prev_mode = ''
        self.state = None
        self.prev_state = None

        self.pv_ready = False  # ready for charging
        self.phase_ready = False  # ready for 3 phase operation

        self.stop = None   # wallbox is in force stop
        self.amp = None  # amp level
        self.wb_phase = None  # phase setting from wallbox 1/3)
        self.phase = None  # phase 1,2,3 (from Wallobox with aditional 2phase detection)
        self.power = None  # measured power
        self.charge_energy = None # actual charged energy
        self.plug = None  # car plug state
        self.info = ''  # human readable information string
        self.pv_start_p = None #
        self.pv_stop_p = None
        # car commands, holding pending setting to wallbox
        self.amp_cmd = None
        self.stop_cmd = None
        self.phase_cmd = None

        self.data = {}  # Dictionary with data

    def user_cmd_handler(self, user_cmd):
        """
        Processing of user commands (UI buttons) depending on the active fsm state

        :param user_cmd: 'stop', 'grid', 'pv'
        :return:
        """
        if user_cmd == 'stop':
            self.mode = 'stop'
            if not self.stop:
                self.stop_cmd = True
                self.log.info("user cmd: stop, stopping wallbox")
            else:
                self.log.info("user cmd: stop, wallbox already stopped")
        elif user_cmd == 'grid':
            self.mode = 'grid'
            if self.stop:
                self.stop_cmd = False
                self.log.info("user cmd: grid, releasing wallbox")
            else:
                self.log.info("user cmd: grid, wallbox already released")
        elif user_cmd == 'pv':
            if self.mode in ('stop', 'grid'):
                self.mode = "pv"
                if self.state == "charge":
                    self.log.info("user cmd: pv, already charging")
                else:
                    self.log.info("user cmd: pv")
            else:
                if self.pv_ready and self.stop is True and \
                        self.stop_cmd is None and \
                        self.phase_cmd is None and \
                        self.state == 'complete':
                    self.stop_cmd = False
                    self.log.info(
                        "user cmd: already in pv mode, release and direct start without waiting".format(user_cmd))
                else:
                    self.log.info("user cmd: already in pv mode, direct start without waiting".format(user_cmd))

            # The user input overrides the otherwise usual waiting time
            self.pv_timer.set_expired()  # override waiting time
            self.phase_timer.set_expired()  # override waiting time
            self.pv_block_timer.stop()  # disable block time
            self.phase_block_timer.stop()  # disable block time

    def fsm_stop(self):
        """
        STATE: Wallbox STOP
        """
        if self.mode != self.prev_mode:
            if self.stop is True:
                self.log.info("{} state entered, wallbox already stopped".format(self.quick_info()))
            else:
                self.log.info("{} state entered".format(self.quick_info()))
        if self.stop_cmd is True and self.stop is True:  # successful, stopped
            self.log.info("{} wallbox stopped".format(self.quick_info()))
        if self.state is not None and self.state != self.prev_state:
            self.log.info("{} car state changed".format(self.quick_info()))
            if self.state == "idle" and self.stop is False:  # Bugfix 14.07.2022
                self.log.info("{} restop after unplug".format(self.quick_info()))
                self.stop_cmd = True
        if self.stop_cmd is None and self.stop is False:  # state change to grid (by wallbox app)
            self.log.info("{} external wallbox release".format(self.quick_info()))
            self.mode = 'grid'

    def fsm_grid(self):
        """
        STATE: Wallbox RELEASE, grid charge
        """
        if self.mode != self.prev_mode:
            if self.stop is False:
                self.log.info("{} state entered, wallbox already released".format(self.quick_info()))
            else:
                self.log.info("{} state entered".format(self.quick_info()))
        if self.stop_cmd is False and self.stop is False:  # successful, released
            self.log.info("{} wallbox released".format(self.quick_info()))
        if self.state is not None and self.state != self.prev_state:
            self.log.info("{} car state changed".format(self.quick_info()))
        elif self.stop_cmd is None and self.stop is True:  # state change to stop (by wallbox app)
            self.log.info("{} external wallbox stop detected".format(self.quick_info()))
            self.mode = 'stop'

    def fsm_pv(self):
        """
        STATE: PV controlled wallbox
        """
        if self.mode != self.prev_mode and self.stop_cmd is None:  # entry without cmd
            self.log.info("{} state entered, pv_ready={} excess={}W start={}W ".format(self.quick_info(), self.pv_ready, self.excess_p_long,
                                                                                     self.pv_start_p))
        # phase switch
        if self.auto_phase and self.phase_cmd is None and self.phase_ready and self.phase == 1 and self.state in (
                'wait', 'charge'):
            self.log.info("{} start 3 phase operation".format(self.quick_info()))
            self.phase_cmd = 3
            self.amp_cmd = 6

        if (not self.phase_ready or not self.auto_phase) and self.phase == 3 and self.phase_cmd is None:
            self.log.info("{} start 1 phase operation".format(self.quick_info()))
            self.phase_cmd = 1
            self.amp_cmd = 6

        # state change
        if self.state is not None and self.state != self.prev_state:
            self.log.info("{} car state change".format(self.quick_info()))

        # stop charge (stop wallbox),   no stop while state change
        elif not self.pv_ready and self.stop is False and self.stop_cmd is not True:
            self.stop_cmd = True
            self.amp_cmd = 6
            self.log.info("{} low pv, stopping wallbox, excess={} pv_stop_p={} ".format(self.quick_info(), self.excess_p_long,
                                                                                       self.pv_stop_p))
            # release muss auch bei 'complete' gesendet werden, sonst ist die Wallbox blockiert wenn das Auto z.B.
            # durch Änderung des Ladelimits nachträglich starten will. 'complete' geht nicht weg.
            # Nach low stop geht die Box in complete, deshalb release auch wenn complete.

        elif self.pv_ready and self.stop is True and \
                self.stop_cmd is not False \
                and self.state in ('wait', 'complete', 'error') and \
                self.phase_cmd is None:
            self.stop_cmd = False
            self.amp_cmd = 6
            self.log.info("{} releasing wallbox, start with excess={}W pv_start_p={}W ".format(self.quick_info(), self.excess_p_long,
                                                                                              self.pv_start_p))
        if self.state == "charge":
            self.pv_amp_ctrl()  # active amp control

    def pv_amp_ctrl(self):
        """
        Continuous adjustment of the current during charging
        """
        if self.amp and self.phase:
            phase = self.phase  # 1 or 3 phase by wallbox setting, 2 if car only uses 2 phases
            excess_p_short = self.excess_p_short - self.control_reserve
            excess_p_long = self.excess_p_long - self.control_reserve
            excess_amp_short = int(excess_p_short / (phase * 230))
            excess_amp_long = int(excess_p_long / (phase * 230))
            excess_amp_min = min(excess_amp_short, excess_amp_long)
            if excess_amp_short < self.amp:  # amp step down
                amp = excess_amp_short
            elif excess_amp_min > self.amp:  # amp step up
                amp = excess_amp_min
            else:
                amp = self.amp
            amp = min(max(amp, 6), 16)  # limit 6..16
            if self.amp_cmd is None and self.amp != amp:  # no pending set
                self.log.debug("amp change {} --> {}".format(self.amp, amp))
                self.amp_cmd = amp

    def quick_info(self):
        """
        Shortcut for logging
        :return: compact status string
        """
        stop_info = {True: 'stop', False: 'release'}.get(self.stop, None)
        return "[{}, {}, {}, {}x{}A]".format(self.mode, self.state, stop_info, self.phase, self.amp)

    def update_in(self):
        """
        Check available excess / conditions and set flags: pv_ready, phase_ready
        """
        try:
            p_set = self.amp * 230 * self.wb_phase
            if self.wb_phase > 1 and p_set * 0.5 < self.power < p_set * 5 / 6:
                self.phase = 2
            else:
                self.phase = self.wb_phase
        except:
            self.phase = self.wb_phase

        # update start and stop power

        if self.pvmin.endswith('%'):
            self.pv_start_p = self.pv_stop_p = round(int(self.pvmin[0:-1]) / 100 * 6 * 230)
        elif self.pvmin.endswith('A'):
            self.pv_start_p = int(self.pvmin[0:-1]) * 230
            self.pv_stop_p = round((6 * 230 + self.pv_start_p) / 2)
        else:
            self.pv_start_p = self.pv_stop_p = 6 * 230  # default

        self.excess_p_short = self.filter_excess_short(self.excess_p)
        self.excess_p_long = self.filter_excess_long(self.excess_p)

        # === PV ===

        if not self.pv_ready and not self.pv_block_timer.is_running():  # stop --> ready ?
            if self.excess_p_long > self.pv_start_p:
                self.pv_timer.start(duration=config['pv_start_time'], restart=False)
                if self.pv_timer.is_expired():
                    self.pv_ready = True
                    self.pv_timer.stop()
                    self.pv_block_timer.stop()
                    self.log.info("{} pv_ready=true".format(self.quick_info()))
            else:
                self.pv_timer.stop(duration=config['pv_start_time'])

        elif self.pv_ready:  # ready --> stop ?
            if self.excess_p_long < self.pv_stop_p:
                self.pv_timer.start(duration=config['pv_end_time'], restart=False)
                if self.pv_timer.is_expired():
                    self.pv_ready = False
                    self.pv_timer.stop()
                    self.pv_block_timer.start(duration=config['pv_block_time'])  # prevent to early pv restart
                    self.log.info("{} pv_ready=false".format(self.quick_info()))
            else:
                self.pv_timer.stop(duration=config['pv_end_time'])

        # === Phase ===

        if self.pv_ready:
            if not self.phase_ready and not self.phase_block_timer.is_running() and not self.pv_timer.is_running():
                if self.excess_p_long > config['phase_start_power']:
                    self.phase_timer.start(duration=config['phase_start_time'], restart=False)
                    if self.phase_timer.is_expired():
                        self.phase_ready = True
                        self.phase_timer.stop()
                        self.phase_block_timer.stop()
                        self.log.info("{} phase_ready=true".format(self.quick_info()))
                else:
                    self.phase_timer.stop(duration=config['phase_start_time'])
            else:
                if self.excess_p_long < config['phase_end_power']:
                    self.phase_timer.start(duration=config['phase_end_time'], restart=False)
                    if self.phase_timer.is_expired():
                        self.phase_ready = False
                        self.phase_timer.stop()
                        self.phase_block_timer.start(duration=config['phase_block_time'])  # start block
                        self.log.info("{} phase_ready=false".format(self.quick_info()))
                else:
                    self.phase_timer.stop(duration=config['phase_end_time'])
        elif self.pv_ready:
            self.phase_ready = False
            self.phase_timer.stop()
            self.log.info("{} phase_ready=false".format(self.quick_info()))

    def update_out(self):
        """
        Write current status and main information dataset (self.data)
        """
        # build info string
        try:
            mode = {'pv': 'PV', 'grid': 'Netz', 'stop': 'Aus'}.get(self.mode, None)
            state = {'wait': 'Warten', 'charge': 'Ladevorgang aktiv', 'complete': 'Laden beendet'}.get(self.state, None)

            if self.state == 'idle' and self.stop is False:
                state = 'Ladebereit'
            elif (self.state == 'idle' or self.state == 'wait') and self.stop is True:
                state = 'Laden gesperrt'

            if state and mode:
                self.info = mode + ' - ' + state
        except:
            self.info = "[{},{}, stop={}]".format(self.mode, self.state, self.stop)

        if self.state and self.state != 'idle':
            self.plug = True
        else:
            self.plug = False

        self.data["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data["meterhub"] = self.io.meterhub.data
        self.data["debug"] = {
            "excess_p": self.excess_p,
            "excess_p_short": self.excess_p_short,
            "excess_p_long": self.excess_p_long,
            "pv_start_p": self.pv_start_p,
            "pv_stop_p": self.pv_stop_p,
            "pv_timer": self.pv_timer.get_info(),
            "pv_block_timer": self.pv_block_timer.get_info(),
            "phase_ready": self.phase_ready,
            "phase_timer": self.phase_timer.get_info(),
            "phase_block_timer": self.phase_block_timer.get_info()
        }
        self.data['mode'] = self.mode
        self.data["state"] = self.state
        self.data["stop"] = self.stop
        self.data['pv_ready'] = self.pv_ready
        self.data["amp"] = self.amp
        self.data["phase"] = self.phase
        self.data["plug"] = self.plug
        self.data["info"] = self.info
        self.data["power"] = self.power
        self.data["charge_energy"] = self.charge_energy
        self.data["pvmin"] = self.pvmin
        self.data["auto_phase"] = self.auto_phase
        self.data["control_reserve"] = self.control_reserve

    def wallbox_command_handler(self):
        """
        Transfer of commands to the wallbox. Evaluation and logging for successful state changes.
        """
        # successful wallbox state changes

        if self.stop is not None and self.stop_cmd == self.stop:
            if self.stop is True:
                self.log.debug("{} stop command successful".format(self.quick_info()))
            else:
                self.log.debug("{} release command successful".format(self.quick_info()))
            self.stop_cmd = None
        if self.phase is not None and self.phase_cmd == self.phase:
            self.log.debug("{} phase command successful".format(self.quick_info()))
            self.phase_cmd = None
        if self.amp is not None and self.amp_cmd == self.amp:
            self.log.debug("{} amp command successful".format(self.quick_info()))
            self.amp_cmd = None
        # check if wallbox is online and no pending command before sending a command
        if not self.car_cmd_block_timer.is_running() and self.amp is not None and \
                (self.stop_cmd is not None or self.phase_cmd is not None or self.amp_cmd is not None):
            self.log.info("set wallbox command stop={} phase={} amp={}".format(self.stop_cmd, self.phase_cmd,
                                                                               self.amp_cmd))
            self.io.set(stop=self.stop_cmd, phase=self.phase_cmd, amp=self.amp_cmd)
            self.car_cmd_block_timer.start()

    def call_fsm(self):
        """
        Run application code depending on active mode
        """
        self.update_in()  # check excess/conditions and set flags: pv_ready, phase_ready
        if self.mode == 'stop':
            self.fsm_stop()
        elif self.mode == 'grid':
            self.fsm_grid()
        elif self.mode == 'pv':
            self.fsm_pv()
        self.prev_mode = self.mode
        self.prev_state = self.state
        self.wallbox_command_handler()
        self.update_out()

    def main(self):
        """
        Application mainloop
        """
        while True:
            if self.sample_timer():  # typical 2sec
                self.io.update(self, post={'car_pv_ready': self.pv_ready, 'car_plug': self.plug, 'car_info': self.info})
                self.call_fsm()
            time.sleep(0.1)
