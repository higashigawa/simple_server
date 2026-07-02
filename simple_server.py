#!/usr/bin/env python3
import socket
import http.server
import socketserver

try:
    import psutil
except ImportError:
    psutil = None

PORT = 8000

# VPN/仮想アダプタとみなすインターフェース名のパターン
VPN_NAME_PATTERNS = (
    "vpn", "tun", "tap", "ppp", "wg", "utun",
    "tailscale", "zerotier", "nordlynx", "wireguard",
    "docker", "veth", "virbr", "vmnet", "vbox",
    "warp", "cloudflare",
)


def is_vpn_like(name: str) -> bool:
    name = name.lower()
    return any(p in name for p in VPN_NAME_PATTERNS)


def get_default_route_ip() -> str:
    """OSのルーティングに従い、外部通信に使われるIPを取得(実パケットは送らない)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_internet_ip() -> str:
    """VPN等を除外し、実際にインターネットへ繋がっているNICのIPを返す"""
    default_ip = get_default_route_ip()

    if psutil is None:
        # psutil がない場合はデフォルトルートの結果をそのまま使う
        return default_ip

    # default_ip がどのNICに属しているか調べる
    if_addrs = psutil.net_if_addrs()
    if_stats = psutil.net_if_stats()

    default_owner = None
    for nic, addrs in if_addrs.items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address == default_ip:
                default_owner = nic
                break

    # デフォルトルートのNICがVPNっぽくなければそのまま採用
    if default_owner and not is_vpn_like(default_owner):
        return default_ip

    # VPN経由だった場合は、VPNでない有効なNICから候補を探す
    candidates = []
    for nic, addrs in if_addrs.items():
        if is_vpn_like(nic):
            continue
        if nic.lower() in ("lo", "loopback"):
            continue
        stats = if_stats.get(nic)
        if not stats or not stats.isup:
            continue
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                candidates.append((nic, addr.address))

    if candidates:
        return candidates[0][1]

    # どうしても見つからなければデフォルトルートの結果を返す
    return default_ip


if __name__ == "__main__":
    ip = get_internet_ip()
    print("=" * 40)
    print(f"共有元IPアドレス: {ip}")
    print(f"アクセスURL     : http://{ip}:{PORT}/")
    print(f"ローカルアクセス: http://localhost:{PORT}/")
    print("=" * 40)
    print("終了するには Ctrl+C を押してください")

    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()


    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
