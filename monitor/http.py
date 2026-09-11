"""Cliente HTTP común: reintentos, límite de ritmo por host y lectura de robots.txt."""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

from .config import DELAY_POR_HOST, REINTENTOS, TIMEOUT, USER_AGENT

log = logging.getLogger("monitor.http")
_ultimo: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


class Cliente:
    def __init__(self, user_agent: str = USER_AGENT, delay: float = DELAY_POR_HOST,
                 comprobar_robots: bool = False):
        self.delay = delay
        self.comprobar_robots = comprobar_robots
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,ca;q=0.8",
        })

    # -- cortesía ------------------------------------------------------------
    def _espera(self, host: str) -> None:
        falta = self.delay - (time.time() - _ultimo.get(host, 0))
        if falta > 0:
            time.sleep(falta)
        _ultimo[host] = time.time()

    def permitido(self, url: str) -> bool:
        if not self.comprobar_robots:
            return True
        host = urlparse(url).netloc
        if host not in _robots:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"https://{host}/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None
            _robots[host] = rp
        rp = _robots[host]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    # -- peticiones ----------------------------------------------------------
    def get(self, url: str, **kw) -> requests.Response | None:
        return self._peticion("GET", url, **kw)

    def post(self, url: str, **kw) -> requests.Response | None:
        return self._peticion("POST", url, **kw)

    def _peticion(self, metodo: str, url: str, **kw):
        if not self.permitido(url):
            log.warning("robots.txt impide %s", url)
            return None
        host = urlparse(url).netloc
        kw.setdefault("timeout", TIMEOUT)
        for intento in range(1, REINTENTOS + 1):
            self._espera(host)
            try:
                r = self.s.request(metodo, url, **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    log.warning("%s %s -> %s (intento %s)", metodo, url, r.status_code, intento)
                    time.sleep(2 ** intento)
                    continue
                return r
            except requests.RequestException as e:
                log.warning("%s %s -> %s (intento %s)", metodo, url, e.__class__.__name__, intento)
                time.sleep(2 ** intento)
        return None
