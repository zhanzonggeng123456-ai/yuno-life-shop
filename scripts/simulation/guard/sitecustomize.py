"""Restrict this test process tree's Python socket connections to loopback."""

import ipaddress
import socket


def local_only(operation):
    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0]
            if host != "localhost":
                try:
                    local = ipaddress.ip_address(host).is_loopback
                except ValueError:
                    local = False
                if not local:
                    raise OSError("YUNO simulation blocks external network connections")
        return operation(sock, address)

    return connect


socket.socket.connect = local_only(socket.socket.connect)
socket.socket.connect_ex = local_only(socket.socket.connect_ex)
