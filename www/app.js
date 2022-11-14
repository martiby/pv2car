var app = app || {};

// Loaded from the server with /app-var by index.html and returned as javascript
// config = { ... };
// version = "1.0.0";

/**
 *  Init application
 */
app.init = function () {
    let self = app;
    console.log("app.init");
    document.getElementById('app-version').textContent = version;

    // Setup PowerFlow view (https://github.com/martiby/PowerFlow)
    const pflow_config = {
        table: [
            {id: 'pv', type: 'pv'},
            {id: 'home', type: 'home', sign: -1},
            {id: 'bat', type: 'bat', sign: -1},
            {id: 'grid', type: 'grid'},
            {id: 'car', type: 'car', sign: -1, wallbox: true}],
        bar: {
            in: [
                {id: 'pv', type: 'pv'},
                {id: 'bat', type: 'bat', sign: -1},
                {id: 'grid', type: 'grid'}],
            out: [
                {id: 'home', type: 'home'},
                {id: 'car', type: 'car'},
                {id: 'bat', type: 'bat'},
                {id: 'grid', type: 'grid', sign: -1}]
        }
    };

    app.pflow = new Pflow('pflow-table', 'pflow-bar', pflow_config);  // Init PowerFlow

    // set dropdown options
    for (let v of config.pvmin_levels) {
        document.getElementById('pvmin-select').innerHTML += `<option value="${v}">${v} PV-Minimum</option>`
    }
    for (let v of config.control_reserve_levels) {
        document.getElementById('control-reserve-select').innerHTML += `<option value="${v}">${v} Watt Regelreserve</option>`
    }

    // setup set_mode_events for buttons
    document.getElementById('stop-button').addEventListener('click', self.set_mode);
    document.getElementById('grid-button').addEventListener('click', self.set_mode);
    document.getElementById('pv-button').addEventListener('click', self.set_mode);

    // add 'change' and 'tap' events to all select inputs to trigger set_config()
    document.querySelectorAll('select').forEach(ele => {
        ele.addEventListener('change', self.set_config);
        ele.addEventListener('tap', self.set_config);
    });

    // event for info logo to toggle debug information
    document.getElementById('info-logo').addEventListener('click', function () {
        let ele = document.getElementById('debug-container');
        if (ele.style.display === "none") {
            ele.style.display = "block";
        } else {
            ele.style.display = "none";
        }
    });

    self.state = null;  // clear application state (updated by poll)
    self.poll_state();  // start polling
}

/**
 *  Mode button click --> command request
 *
 *  Sends one of the three mode button commands: stop, grid or pv
 */
app.set_mode = function () {
    let self = app;
    let mode = this.id.slice(0, -7); // remove  '-button'
    let url = 'api/set?cmd=' + mode;
    self.show_mode_button(null);
    console.log("set mode", url);
    fetch_json(url, app.show_state);
}

/**
 * Settings (Dropdown select)
 *
 * Send new settings to webserver
 */
app.set_config = function () {
    let self = app;
    let url = 'api/set?';
    url += '&pvmin=' + document.getElementById('pvmin-select').value;
    url += '&control-reserve=' + document.getElementById('control-reserve-select').value;
    url += '&auto-phase=' + document.getElementById('auto-phase-select').value;
    console.log("set config", url);
    fetch_json(url, self.show_state);
}

/**
 * Show state on the interface
 *
 * @param state received by api (/api/state)
 */
app.show_state = function (state) {
    let self = app;
    state = state || {};   // empty object to prevent errors
    // console.log("state", state);
    self.state = state;

    // === PFlow ===

    let d = {
        pv: {
            power: state?.meterhub?.pv_p,
            subline: 'Süd: ' + (state?.meterhub?.pv1_p ?? '---') + ' W  Nord: ' + (state?.meterhub?.pv2_p ?? '---') + ' W',
        },
        home: {power: state?.meterhub?.home_p},
        bat: {
            power: state?.meterhub?.bat_p,
            info: (state?.meterhub?.bat_soc) ? state.meterhub.bat_soc + ' %' : '-- %',
            subline: state?.meterhub?.bat_info
        },
        car: {
            power: state?.power,
            disable: !state?.plug,
            info: ((state?.charge_energy ?? 0) > 0) ? (state.charge_energy / 1000).toFixed(1) + ' kWh' : '',
            subline: state?.info,

            wallbox_pvready: state?.pv_ready,
            wallbox_stop: state?.stop,
            wallbox_amp: (state?.phase && state?.amp) ? state?.phase + 'x' + state?.amp + 'A' : 'xxx'

        },
        grid: {
            power: state?.meterhub?.grid_p
        }
    };

    self.pflow.update(d);

    getById = function (id) {
        return document.getElementById(id);
    }

    // === Headline with time ===

    try {
        getById('time').textContent = state.time.slice(11)
    } catch (e) {
        getById('time').textContent = "DISCONNECTED";
    }

    // === Mode buttons ===
    self.show_mode_button(state);

    getById('pvmin-select').value = state?.pvmin ?? '';
    getById('control-reserve-select').value = state?.control_reserve ?? '';
    getById('auto-phase-select').value = state?.auto_phase ?? '';

    // === Table with debug values (default hidden, activated by click at the logo) ===
    getById('debug-mode').textContent = state?.mode ?? '';
    getById('debug-state').textContent = state?.state ?? '';
    getById('debug-stop').textContent = state?.stop ?? '';

    getById('debug-pv-start').textContent = (state?.debug?.pv_start_p ?? '---') + ' W';
    getById('debug-pv-stop').textContent = (state?.debug?.pv_stop_p ?? '---') + ' W';

    getById('debug-excess').textContent = (state?.debug?.excess_p ?? '---') + ' W';
    getById('debug-excess-short').textContent = (state?.debug?.excess_p_short ?? '---') + ' W';
    getById('debug-excess-long').textContent = (state?.debug?.excess_p_long ?? '---') + ' W';

    getById('debug-pv-ready').textContent = state?.pv_ready ?? '';
    getById('debug-pv-timer').textContent = state?.debug?.pv_timer ?? '';
    getById('debug-pv-block-timer').textContent = state?.debug?.pv_block_timer ?? '';

    getById('debug-phase-ready').textContent = state?.debug?.phase_ready ?? '';
    getById('debug-phase-timer').textContent = state?.debug?.phase_timer ?? '';
    getById('debug-phase-block-timer').textContent = state?.debug?.phase_block_timer ?? '';
}

/**
 * Shows the current state at the buttons
 *
 * @param state complete state (API response)
 */
app.show_mode_button = function (state) {
    let self = app;
    let stop = document.getElementById('stop-button');
    let grid = document.getElementById('grid-button');
    let pv = document.getElementById('pv-button');

    stop.classList.toggle('btn-outline-primary', state?.mode !== 'stop');
    stop.classList.toggle('btn-primary', state?.mode === 'stop');

    grid.classList.toggle('btn-outline-primary', state?.mode !== 'grid');
    grid.classList.toggle('btn-primary', state?.mode === 'grid');

    pv.classList.toggle('btn-outline-primary', state?.mode !== 'pv');
    pv.classList.toggle('btn-primary', state?.mode === 'pv');
}

/**
 * Cyclic polling the state (/api/state)
 */
app.poll_state = function () {
    let self = app;
    fetch_json('api/state',
        function (response) {
            self.show_state(response)
        }, function (error) {
            console.log('poll_state_error', error);
            self.show_state(null)
        });
    setTimeout(self.poll_state, 1000);
};

/**
 * Fetch JSON (AJAX Request)
 *
 * @param url requested url
 * @param success callback for success
 * @param error callback for error (optional)
 * @param post dictionary to send as json post (optional)
 */
function fetch_json(url, success, error, post) {
    if (post) {
        post = {
            method: 'POST',
            body: JSON.stringify(post),
            headers: {'Content-Type': 'application/json'}
        }
    }
    fetch(url, post).then(function (response) {
        if (response.ok) {
            return response.json();
        } else {
            return Promise.reject(response);
        }
    }).then(function (data) {
        success(data);
    }).catch(function (err) {
        if (error) error(err);
    });
}

window.onload = function () {
    app.init();
}