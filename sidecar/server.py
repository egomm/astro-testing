"""
Local N-body backend for the Solar System Orbit Viewer.

Spawned as a Tauri sidecar process. Binds to 127.0.0.1 only (never exposed
to the network). Serves real gravitational N-body positions computed with
REBOUND, rather than analytic/Keplerian approximation.

Initial conditions: standard J2000 osculating orbital elements (the same
low-precision JPL element set used in the pure-JS version of this project)
are converted to Cartesian state vectors (position AND velocity) via
standard two-body orbital mechanics. REBOUND then integrates those bodies
forward/backward under mutual gravity (Sun + 8 planets), so unlike the
pure-JS version, planet-planet perturbations are physically simulated, not
just looked up from an analytic curve.

Units: AU, days, solar masses, using the Gaussian gravitational constant
(k = 0.01720209895) so that G*Msun = k^2 gives time directly in days -
the same convention JPL/Horizons uses.
"""

import math
import sys
from datetime import datetime, timezone

import rebound
from flask import Flask, jsonify, request
from flask_cors import CORS

PORT = 51733
J2000_JD = 2451545.0
GAUSS_K = 0.01720209895
G_AU_DAY_MSUN = GAUSS_K * GAUSS_K  # ~2.959122e-4

# a(AU), e, i(deg), L(deg, mean longitude @ J2000), peri(deg, longitude of
# perihelion), node(deg, longitude of ascending node), period(days),
# mass(solar masses)
ELEMENTS = {
    "Mercury": dict(a=0.38709927, e=0.20563593, i=7.00497902, L=252.25032350,
                     peri=77.45779628, node=48.33076593, period=87.9691, mass=1.6601e-7),
    "Venus":   dict(a=0.72333566, e=0.00677672, i=3.39467605, L=181.97909950,
                     peri=131.60246718, node=76.67984255, period=224.701, mass=2.4478383e-6),
    "Earth":   dict(a=1.00000261, e=0.01671123, i=-0.00001531, L=100.46457166,
                     peri=102.93768193, node=0.0, period=365.256, mass=3.003467e-6),
    "Mars":    dict(a=1.52371034, e=0.09339410, i=1.84969142, L=-4.55343205,
                     peri=-23.94362959, node=49.55953891, period=686.980, mass=3.213e-7),
    "Jupiter": dict(a=5.20288700, e=0.04838624, i=1.30439695, L=34.39644051,
                     peri=14.72847983, node=100.47390909, period=4332.589, mass=9.5479e-4),
    "Saturn":  dict(a=9.53667594, e=0.05386179, i=2.48599187, L=49.95424423,
                     peri=92.59887831, node=113.66242448, period=10759.22, mass=2.8588e-4),
    "Uranus":  dict(a=19.18916464, e=0.04725744, i=0.77263783, L=313.23810451,
                     peri=170.95427630, node=74.01692503, period=30685.4, mass=4.36624e-5),
    "Neptune": dict(a=30.06992276, e=0.00859048, i=1.77004347, L=-55.12002969,
                     peri=44.96476227, node=131.78422574, period=60189.0, mass=5.15140e-5),
}
NAMES = list(ELEMENTS.keys())


def solve_kepler(M, e, tol=1e-9, max_iter=50):
    M = M % (2 * math.pi)
    E = M if e < 0.8 else math.pi
    for _ in range(max_iter):
        dE = (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        E -= dE
        if abs(dE) < tol:
            break
    return E


def elements_to_state(el):
    """Convert osculating elements at J2000 into a heliocentric ecliptic
    Cartesian state vector (position in AU, velocity in AU/day)."""
    a, e, i = el["a"], el["e"], math.radians(el["i"])
    peri, node = math.radians(el["peri"]), math.radians(el["node"])
    n = 2 * math.pi / el["period"]  # mean motion, rad/day
    M = math.radians(el["L"] - el["peri"])  # mean anomaly at J2000
    E = solve_kepler(M, e)

    # position + velocity in the perifocal (orbital) plane
    cosE, sinE = math.cos(E), math.sin(E)
    x_pf = a * (cosE - e)
    y_pf = a * math.sqrt(1 - e * e) * sinE
    factor = n * a / (1 - e * cosE)
    vx_pf = -factor * sinE
    vy_pf = factor * math.sqrt(1 - e * e) * cosE

    w = peri - node  # argument of periapsis
    cw, sw = math.cos(w), math.sin(w)
    co, so = math.cos(node), math.sin(node)
    ci, si = math.cos(i), math.sin(i)

    def rotate(px, py):
        x = (cw * co - sw * so * ci) * px + (-sw * co - cw * so * ci) * py
        y = (cw * so + sw * co * ci) * px + (-sw * so + cw * co * ci) * py
        z = (sw * si) * px + (cw * si) * py
        return x, y, z

    x, y, z = rotate(x_pf, y_pf)
    vx, vy, vz = rotate(vx_pf, vy_pf)
    return (x, y, z, vx, vy, vz)


def build_simulation():
    sim = rebound.Simulation()
    sim.units = ('day', 'AU', 'Msun')  # sets G to the AU/day/Msun convention
    sim.add(m=1.0)  # Sun, at origin, at rest (heliocentric IC - good enough
                     # for this visual precision; a barycentric setup would
                     # be a further-accuracy upgrade, not needed here)
    for name in NAMES:
        x, y, z, vx, vy, vz = elements_to_state(ELEMENTS[name])
        sim.add(m=ELEMENTS[name]["mass"], x=x, y=y, z=z, vx=vx, vy=vy, vz=vz, hash=name)
    sim.move_to_com()
    sim.integrator = "whfast"
    sim.dt = 1.0  # 1 day - comfortably small vs. Mercury's ~88-day period
    return sim


def positions_at(jd):
    """Fresh integration from J2000 to the requested Julian Date. Simple
    and stateless (safe for concurrent requests); for a smoother/faster
    scrubbing experience later, this could be swapped for a long-lived
    Simulation object that steps incrementally instead of re-integrating
    from epoch on every call."""
    sim = build_simulation()
    t = jd - J2000_JD
    sim.integrate(t)
    out = {}
    for name in NAMES:
        p = sim.particles[name]
        out[name] = {"x": p.x, "y": p.y, "z": p.z}
    return out


app = Flask(__name__)
CORS(app)  # local-only server; permissive CORS is fine since it never
           # leaves 127.0.0.1 and Tauri's webview origin needs to reach it


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/positions")
def positions():
    jd = request.args.get("jd", type=float)
    if jd is None:
        date_str = request.args.get("date")
        if date_str:
            d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            jd = d.timestamp() / 86400.0 + 2440587.5
        else:
            jd = J2000_JD
    return jsonify(positions_at(jd))


_orbit_paths_cache = None


@app.route("/orbit-paths")
def orbit_paths():
    """Sample each planet's position across one full period, for drawing
    the guide ellipses. Cached after first call (the result never changes).

    IMPORTANT: this does ONE continuous integration and takes snapshots
    along the way, rather than starting a fresh integration-from-epoch for
    every sample point. The earlier version called positions_at() (which
    integrates from J2000 every time) once per sample - for Neptune's
    ~60,000-day period sampled 200 times that was millions of wasted
    integrator steps, and since Flask's dev server is single-threaded that
    blocked every other request (health checks, position polling) for as
    long as it took, which is what looked like a total freeze.
    """
    global _orbit_paths_cache
    if _orbit_paths_cache is not None:
        return jsonify(_orbit_paths_cache)

    samples_per_planet = 150
    # (t_days_since_epoch, planet_name) pairs, sorted ascending so the
    # shared simulation only ever integrates forward - REBOUND integrates
    # incrementally from its current time to the next requested t, so the
    # total work is bounded by the single largest t requested (~Neptune's
    # period), not by (samples x planets).
    requests_ = []
    for name in NAMES:
        period = ELEMENTS[name]["period"]
        for k in range(samples_per_planet + 1):
            requests_.append((period * k / samples_per_planet, name))
    requests_.sort(key=lambda r: r[0])

    sim = build_simulation()
    result = {name: [] for name in NAMES}
    for t, name in requests_:
        sim.integrate(t)
        p = sim.particles[name]
        result[name].append({"x": p.x, "y": p.y, "z": p.z})

    _orbit_paths_cache = result
    return jsonify(result)


if __name__ == "__main__":
    # Flush immediately so the Rust side can see this line right away if it
    # ever wants to confirm the server is up by scanning stdout.
    print(f"orbit-server listening on 127.0.0.1:{PORT}", flush=True)
    # threaded=True so a slow request (e.g. the first /orbit-paths call
    # before it's cached) can't block health checks / position polling
    # from being answered concurrently.
    app.run(host="127.0.0.1", port=PORT, threaded=True)
