"""Implementation of SIP (Session Initiation Protocol)."""
import asyncio
from dataclasses import dataclass
import logging
import re

from homeassistant.core import HomeAssistant

SIP_PORT = 5060

_LOGGER = logging.getLogger(__name__)
_CRLF = "\r\n"
_SDP_USERNAME = "homeassistant"
_SDP_ID = "".join(str(ord(c)) for c in "hass")  # 10497115115
_OPUS_PAYLOAD = "123"

# <sip:IP:PORT>;tag=...
_SIP_IP = re.compile(r"^<sip:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):\d+>(;.+)?$")


@dataclass
class CallInfo:
    caller_ip: str
    caller_sip_port: int
    caller_rtp_port: int
    server_ip: str
    headers: dict[str, str]


class SIPDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr):
        try:
            message = data.decode()
            method, headers, body = self._parse_sip(message)

            if method and (method.lower() != "invite"):
                # Not an INVITE message
                return

            caller_ip, caller_sip_port = addr
            _LOGGER.debug(
                "Incoming call from ip=%s, port=%s", caller_ip, caller_sip_port
            )

            # Extract caller's RTP port
            caller_rtp_port: int | None = None
            body_lines = body.splitlines()
            for line in body_lines:
                line = line.strip()
                if line:
                    key, value = line.split("=", maxsplit=1)
                    if key == "m":
                        parts = value.split()
                        if parts[0] == "audio":
                            caller_rtp_port = int(parts[1])

            assert caller_rtp_port is not None, "No caller RTP port"

            # Extract our visible IP afrom SIP header.
            # This must be the IP we use for RTP.
            server_ip_match = _SIP_IP.match(headers["to"])
            assert server_ip_match is not None
            server_ip = server_ip_match.group(1)

            _LOGGER.debug("Server ip=%s", server_ip)

            # _LOGGER.debug("Received %s", method)
            # _LOGGER.debug(headers)
            # _LOGGER.debug(body)

            self.on_call(
                CallInfo(
                    caller_ip=caller_ip,
                    caller_sip_port=caller_sip_port,
                    caller_rtp_port=caller_rtp_port,
                    server_ip=server_ip,
                    headers=headers,
                )
            )
        except Exception:
            _LOGGER.exception("datagram_received")

    def on_call(self, call_info: CallInfo):
        # self.answer(call_info.headers, call_info.addr, 5004)
        pass

    def answer(
        self,
        headers: dict[str, str],
        caller_ip: str,
        caller_sip_port: int,
        server_ip: str,
        server_rtp_port: int,
    ):
        """Send OK message to caller with our IP and RTP port."""
        assert self.transport is not None

        # SDP = Session Description Protocol
        # https://en.wikipedia.org/wiki/Session_Description_Protocol
        body_lines = [
            "v=0",
            f"o={_SDP_USERNAME} {_SDP_ID} 1 IN IP4 {server_ip}",
            f"s={_SDP_USERNAME} 1.0",
            f"c=IN IP4 {server_ip}",
            "t=0 0",
            f"m=audio {server_rtp_port} RTP/AVP {_OPUS_PAYLOAD}",
            f"a=rtpmap:{_OPUS_PAYLOAD} opus/48000/2",
            "a=ptime:20",
            "a=maxptime:150",
            "a=sendrecv",
            _CRLF,
        ]
        body = _CRLF.join(body_lines)

        response_headers = {
            "Via": headers["via"],
            "From": headers["from"],
            "To": headers["to"],
            "Call-ID": headers["call-id"],
            "Content-Type": "application/sdp",
            "Content-Length": len(body),
            "CSeq": headers["cseq"],
            "Contact": headers["contact"],
            "User-Agent": f"{_SDP_USERNAME} 1.0",
            "Allow": "INVITE, ACK, BYE, CANCEL, OPTIONS",
        }
        response_lines = ["SIP/2.0 200 OK"]

        for key, value in response_headers.items():
            response_lines.append(f"{key}: {value}")

        response_lines.append(_CRLF)
        response_str = _CRLF.join(response_lines) + body
        response_bytes = response_str.encode()

        self.transport.sendto(response_bytes, (caller_ip, caller_sip_port))
        _LOGGER.debug(
            "Sent OK to ip=%s, port=%s with rtp_port=%s",
            caller_ip,
            caller_sip_port,
            server_rtp_port,
        )

    def _parse_sip(self, message: str) -> tuple[str | None, dict[str, str], str]:
        """Parse SIP message and return method, headers, and body."""
        lines = message.splitlines()

        method: str | None = None
        headers: dict[str, str] = {}
        offset: int = 0

        for i, line in enumerate(lines):
            if line:
                offset += len(line) + len(_CRLF)

            if i == 0:
                method = line.split()[0]
            elif not line:
                break
            else:
                key, value = line.split(":", maxsplit=1)
                headers[key.lower()] = value.strip()

        body = message[offset:]

        return method, headers, body
