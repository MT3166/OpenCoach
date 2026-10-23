"""用已安装的 Chrome 和标准库在独立视口验收页面，不修改日常浏览器。"""
import argparse
import base64
import getpass
import http.cookiejar
import json
from pathlib import Path
import re
import secrets
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from smoke_h5 import Browser

class CDP:
    def __init__(self, url):
        parsed = urllib.parse.urlsplit(url)
        self.socket = socket.create_connection((parsed.hostname, parsed.port), timeout=15)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        handshake = (f'GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\n'
            f'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n')
        self.socket.sendall(handshake.encode())
        header = bytearray()
        while not header.endswith(b'\r\n\r\n'):
            header.extend(self.read(1))
        if b' 101 ' not in header:
            raise RuntimeError('Chrome 调试连接未建立')
        self.sequence = 0

    def read(self, size):
        data = bytearray()
        while len(data) < size:
            chunk = self.socket.recv(size - len(data))
            if not chunk:
                raise EOFError('Chrome connection closed')
            data.extend(chunk)
        return bytes(data)

    def send(self, data, opcode=1):
        length = len(data)
        size = bytes([0x80 | length]) if length < 126 else (
            b'\xfe' + struct.pack('!H', length) if length < 65536 else b'\xff' + struct.pack('!Q', length))
        mask = secrets.token_bytes(4)
        self.socket.sendall(bytes([0x80 | opcode]) + size + mask +
                            bytes(value ^ mask[index % 4] for index, value in enumerate(data)))

    def receive(self):
        message = bytearray()
        while True:
            first, second = self.read(2)
            length = second & 127
            if length == 126:
                length = struct.unpack('!H', self.read(2))[0]
            elif length == 127:
                length = struct.unpack('!Q', self.read(8))[0]
            if length > 20_000_000:
                raise RuntimeError('Unexpected Chrome message size')
            mask = self.read(4) if second & 128 else None
            payload = self.read(length)
            if mask:
                payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
            if first & 15 == 8:
                raise EOFError('Chrome connection closed')
            if first & 15 == 9:
                self.send(payload, opcode=10)
                continue
            message.extend(payload)
            if first & 128:
                return json.loads(message)

    def call(self, method, params=None):
        self.sequence += 1
        self.send(json.dumps({'id': self.sequence, 'method': method, 'params': params or {}}).encode())
        while True:
            response = self.receive()
            if response.get('id') == self.sequence:
                if 'error' in response:
                    raise RuntimeError(response['error'])
                return response.get('result', {})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--width', type=int, default=390)
    parser.add_argument('--height', type=int, default=844)
    parser.add_argument('--script',help='可选的浏览器验收脚本，不记录密码')
    parser.add_argument('--origin-ip',help='指定测试服务器，域名及TLS验证保持正常')
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.url)
    origin = f'{parsed.scheme}://{parsed.netloc}'
    client = Browser(origin,args.origin_ip)
    password = getpass.getpass('Demo account password (not saved): ')
    state = client.login(args.username,password)
    del password
    if not state['user']:
        raise RuntimeError('演示账号登录失败')
    cookies=client.jar
    browser = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    artifacts = Path(__file__).resolve().parent.parent / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    with socket.socket() as allocator:
        allocator.bind(('127.0.0.1', 0))
        port = allocator.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='browser-', dir=artifacts, ignore_cleanup_errors=True) as profile:
        assert Path(profile).resolve().is_relative_to(artifacts.resolve())
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        arguments=[str(browser), '--headless=new', '--disable-gpu',
            '--no-first-run', '--no-default-browser-check', '--disable-background-mode',
            '--disable-background-networking', f'--user-data-dir={profile}',
            '--remote-debugging-address=127.0.0.1', f'--remote-debugging-port={port}', 'about:blank']
        if args.origin_ip:
            arguments.extend(['--no-proxy-server','--host-resolver-rules=MAP '+str(parsed.hostname)+' '+args.origin_ip])
        process = subprocess.Popen(arguments,
            startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cdp = None
        try:
            targets = None
            for _ in range(60):
                try:
                    targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=2))
                    if targets:
                        break
                except (OSError, ValueError):
                    time.sleep(.2)
            if not targets:
                raise RuntimeError('Chrome did not start')
            cdp = CDP(next(item['webSocketDebuggerUrl'] for item in targets if item['type'] == 'page'))
            cdp.call('Page.enable')
            cdp.call('Network.enable')
            cdp.call('Emulation.setDeviceMetricsOverride', {'width': args.width, 'height': args.height,
                'deviceScaleFactor': 1, 'mobile': args.width < 600})
            for cookie in cookies:
                cdp.call('Network.setCookie', {'name': cookie.name, 'value': cookie.value,
                    'url': origin, 'path': cookie.path or '/', 'secure': cookie.secure,
                    'httpOnly':any(key.lower()=='httponly' for key in cookie._rest)})
            cdp.call('Page.navigate', {'url': args.url})
            for _ in range(80):
                state = cdp.call('Runtime.evaluate', {'expression': 'document.readyState === "complete" && !!document.querySelector("h1") && !document.querySelector(".loading")', 'returnByValue': True})
                if state.get('result', {}).get('value'):
                    break
                time.sleep(.1)
            if args.script:
                executed=cdp.call('Runtime.evaluate',{'expression':Path(args.script).read_text(encoding='utf-8'),'awaitPromise':True,'returnByValue':True})
                if 'exceptionDetails' in executed:
                    raise RuntimeError(executed['exceptionDetails'])
                print('browser_flow='+json.dumps(executed.get('result',{}).get('value'),ensure_ascii=False),flush=True)
            time.sleep(.6)
            result = cdp.call('Runtime.evaluate', {'expression':
                'JSON.stringify({url:location.href,width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,heading:document.querySelector("h1")?.textContent})',
                'returnByValue': True})
            state = json.loads(result['result']['value'])
            if state['overflow'] or '/login/' in state['url']:
                raise RuntimeError(state)
            screenshot = cdp.call('Page.captureScreenshot', {'format': 'png', 'fromSurface': True,
                'clip': {'x': 0, 'y': 0, 'width': args.width, 'height': args.height, 'scale': 1}})
            Path(args.output).write_bytes(base64.b64decode(screenshot['data']))
            print(json.dumps(state, ensure_ascii=False))
            print('screenshot=' + str(Path(args.output).resolve()))
        finally:
            if cdp:
                try:
                    cdp.call('Browser.close')
                except (OSError, EOFError):
                    pass
                cdp.socket.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

if __name__ == '__main__':
    main()
