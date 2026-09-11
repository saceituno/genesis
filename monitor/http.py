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
_bloqueados: set[str] = set()   # hosts que han respondido 403 al agente propio


class Cliente:
    # Si un WAF rechaza al agente propio (403), se reintenta con cabeceras de
    # navegador antes de darse por vencido.
    CABECERAS_NAVEGADOR = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "image/avif,image/webp,*/*;q=0.8"),
        "Accept-Language": "es-ES,es;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }

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
                extra = dict(kw)
                if intento > 1 and host in _bloqueados:
                    cabeceras = dict(self.CABECERAS_NAVEGADOR)
                    cabeceras.update(extra.pop("headers", None) or {})
                    extra["headers"] = cabeceras
                r = self.s.request(metodo, url, **extra)
                if r.status_code == 403:
                    _bloqueados.add(host)
                if r.status_code in (403, 429, 500, 502, 503, 504):
                    log.warning("%s %s -> %s (intento %s)", metodo, url, r.status_code, intento)
                    time.sleep(2 ** intento)
                    continue
                return r
            except requests.RequestException as e:
                log.warning("%s %s -> %s (intento %s)", metodo, url, e.__class__.__name__, intento)
                time.sleep(2 ** intento)
        return None
