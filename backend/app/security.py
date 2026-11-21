import ipaddress

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def is_local_host(host: str | None) -> bool:
    """Return True when a request originates from the local machine."""
    if not host:
        return False
    if host in LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
