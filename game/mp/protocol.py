"""Length-prefixed JSON frames (big-endian uint32 length)."""
import json
import struct

_MAX_FRAME = 4 * 1024 * 1024


def write_message(sock, obj: dict) -> None:
    raw = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    if len(raw) > _MAX_FRAME:
        raise ValueError('frame too large')
    sock.sendall(struct.pack('>I', len(raw)) + raw)


def parse_frames_from_buffer(buf: bytearray) -> list:
    """Pop complete frames from buf; leave partial frame in buf."""
    out = []
    while True:
        if len(buf) < 4:
            break
        (n,) = struct.unpack('>I', buf[:4])
        if n > _MAX_FRAME:
            raise ValueError('invalid frame length')
        if len(buf) < 4 + n:
            break
        payload = bytes(buf[4:4 + n])
        del buf[:4 + n]
        try:
            out.append(json.loads(payload.decode('utf-8')))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError('invalid json frame') from None
    return out


def read_messages(sock, buf: bytearray) -> list:
    """Recv one chunk, append to buf, return newly completed messages."""
    chunk = sock.recv(65536)
    if not chunk:
        raise ConnectionError('peer closed connection')
    buf.extend(chunk)
    return parse_frames_from_buffer(buf)
