from __future__ import annotations
from dataclasses import dataclass
from ldap3 import Server, Connection, ALL


@dataclass
class LdapConfig:
    server_uri: str
    user_dn_template: str
    use_ssl: bool = False
    connect_timeout: int = 5


def ldap_authenticate(username: str, password: str, cfg: LdapConfig) -> bool:
    if not username or not password:
        return False

    user_dn = cfg.user_dn_template.format(username=username)

    try:
        server = Server(cfg.server_uri, get_info=ALL, use_ssl=cfg.use_ssl, connect_timeout=cfg.connect_timeout)
        conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        conn.unbind()
        return True
    except Exception:
        return False