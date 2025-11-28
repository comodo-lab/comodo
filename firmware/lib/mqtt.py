import socket
import struct
import binascii
import ssl


class MQTTException(Exception):
    pass


class MQTTClient:
    def __init__(
        self,
        client_id,
        server,
        port=0,
        user=None,
        password=None,
        keepalive=0,
        ssl_enabled=False,
    ):
        if port == 0:
            port = 8883 if ssl_enabled else 1883
        self.client_id = client_id
        self.sock = None
        self.server = server
        self.port = port
        self.ssl_enabled = ssl_enabled
        self.pid = 0
        self.cb = None
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0
        self.lw_retain = False

    def _send_str(self, s: bytes):
        self.sock.sendall(struct.pack("!H", len(s)))
        self.sock.sendall(s)

    def _recv_len(self):
        n = 0
        sh = 0
        while True:
            b = self.sock.recv(1)[0]
            n |= (b & 0x7F) << sh
            if not b & 0x80:
                return n
            sh += 7

    def set_callback(self, f):
        self.cb = f

    def set_last_will(self, topic, msg, retain=False, qos=0):
        assert 0 <= qos <= 2
        assert topic
        self.lw_topic = topic
        self.lw_msg = msg
        self.lw_qos = qos
        self.lw_retain = retain

    def connect(self, clean_session=True):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = socket.getaddrinfo(self.server, self.port, 0, socket.SOCK_STREAM)[0][-1]
        self.sock.connect(addr)
        if self.ssl_enabled:
            context = ssl.create_default_context()
            self.sock = context.wrap_socket(self.sock, server_hostname=self.server)

        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        sz = 10 + 2 + len(self.client_id)
        msg[6] = clean_session << 1
        if self.user:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
        if self.keepalive:
            assert self.keepalive < 65536
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF
        if self.lw_topic:
            sz += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            msg[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
            msg[6] |= self.lw_retain << 5

        i = 1
        while sz > 0x7F:
            premsg[i] = (sz & 0x7F) | 0x80
            sz >>= 7
            i += 1
        premsg[i] = sz

        self.sock.sendall(premsg[: i + 2])
        self.sock.sendall(msg)
        self._send_str(
            self.client_id.encode()
            if isinstance(self.client_id, str)
            else self.client_id
        )
        if self.lw_topic:
            self._send_str(self.lw_topic.encode())
            self._send_str(self.lw_msg.encode())
        if self.user:
            self._send_str(self.user.encode())
            self._send_str(self.pswd.encode())

        resp = self.sock.recv(4)
        assert resp[0] == 0x20 and resp[1] == 0x02
        if resp[3] != 0:
            raise MQTTException(resp[3])
        return resp[2] & 1

    def disconnect(self):
        self.sock.sendall(b"\xe0\0")
        self.sock.close()

    def ping(self):
        self.sock.sendall(b"\xc0\0")

    def publish(self, topic, msg, retain=False, qos=0):
        if isinstance(topic, str):
            topic = topic.encode()
        if isinstance(msg, str):
            msg = msg.encode()

        pkt = bytearray(b"\x30\0\0\0")
        pkt[0] |= qos << 1 | retain
        sz = 2 + len(topic) + len(msg)
        if qos > 0:
            sz += 2
        assert sz < 2097152
        i = 1
        while sz > 0x7F:
            pkt[i] = (sz & 0x7F) | 0x80
            sz >>= 7
            i += 1
        pkt[i] = sz
        self.sock.sendall(pkt[: i + 1])
        self._send_str(topic)
        if qos > 0:
            self.pid += 1
            pid = self.pid
            struct.pack_into("!H", pkt, 0, pid)
            self.sock.sendall(pkt[:2])
        self.sock.sendall(msg)
        if qos == 1:
            while True:
                op = self.wait_msg()
                if op == 0x40:
                    sz = self.sock.recv(1)
                    assert sz == b"\x02"
                    rcv_pid = self.sock.recv(2)
                    rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]
                    if pid == rcv_pid:
                        return
        elif qos == 2:
            raise NotImplementedError("QoS 2 not supported")

    def subscribe(self, topic, qos=0):
        assert self.cb is not None, "Subscribe callback is not set"
        if isinstance(topic, str):
            topic = topic.encode()

        pkt = bytearray(b"\x82\0\0\0")
        self.pid += 1
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, self.pid)
        self.sock.sendall(pkt)
        self._send_str(topic)
        self.sock.sendall(qos.to_bytes(1, "little"))
        while True:
            op = self.wait_msg()
            if op == 0x90:
                resp = self.sock.recv(4)
                assert resp[1] == pkt[2] and resp[2] == pkt[3]
                if resp[3] == 0x80:
                    raise MQTTException(resp[3])
                return

    def wait_msg(self):
        res = self.sock.recv(1)
        self.sock.setblocking(True)
        if not res:
            raise OSError("Socket closed")
        if res == b"\xd0":  # PINGRESP
            sz = self.sock.recv(1)[0]
            assert sz == 0
            return None
        op = res[0]
        if op & 0xF0 != 0x30:
            return op
        sz = self._recv_len()
        topic_len_bytes = self.sock.recv(2)
        topic_len = (topic_len_bytes[0] << 8) | topic_len_bytes[1]
        topic = self.sock.recv(topic_len)
        sz -= topic_len + 2
        pid = None
        if op & 6:
            pid_bytes = self.sock.recv(2)
            pid = pid_bytes[0] << 8 | pid_bytes[1]
            sz -= 2
        msg = self.sock.recv(sz)
        if self.cb:
            self.cb(topic, msg)
        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self.sock.sendall(pkt)
        elif op & 6 == 4:
            raise NotImplementedError("QoS 2 not supported")
        return op

    def check_msg(self):
        self.sock.setblocking(False)
        try:
            return self.wait_msg()
        except BlockingIOError:
            return None
