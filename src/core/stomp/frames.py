"""
STOMP协议帧定义和解析

STOMP帧格式:
COMMAND
header1:value1
header2:value2

body^@

其中 ^@ 是NULL字符(\\x00)
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
import json


class StompCommand(str, Enum):
    """STOMP命令"""
    # 客户端命令
    CONNECT = "CONNECT"
    STOMP = "STOMP"  # STOMP 1.2 别名
    SEND = "SEND"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    ACK = "ACK"
    NACK = "NACK"
    BEGIN = "BEGIN"
    COMMIT = "COMMIT"
    ABORT = "ABORT"
    DISCONNECT = "DISCONNECT"
    
    # 服务端命令
    CONNECTED = "CONNECTED"
    MESSAGE = "MESSAGE"
    RECEIPT = "RECEIPT"
    ERROR = "ERROR"


@dataclass
class StompFrame:
    """STOMP帧"""
    command: StompCommand
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    
    def to_bytes(self) -> bytes:
        """序列化为STOMP帧格式"""
        lines = [self.command.value]
        
        for key, value in self.headers.items():
            # STOMP头编码：转义特殊字符
            escaped_key = self._encode_header(key)
            escaped_value = self._encode_header(str(value))
            lines.append(f"{escaped_key}:{escaped_value}")
        
        lines.append("")  # 空行分隔headers和body
        
        frame = "\n".join(lines)
        if self.body:
            frame += self.body
        frame += "\x00"  # NULL终止符
        
        return frame.encode("utf-8")
    
    def to_json(self) -> str:
        """序列化为JSON格式（用于简化传输）"""
        return json.dumps({
            "command": self.command.value,
            "headers": self.headers,
            "body": self.body,
        })
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "StompFrame":
        """从STOMP帧格式解析"""
        text = data.decode("utf-8").rstrip("\x00")
        return cls.from_text(text)
    
    @classmethod
    def from_text(cls, text: str) -> "StompFrame":
        """从文本解析STOMP帧"""
        text = text.rstrip("\x00")
        lines = text.split("\n")
        
        if not lines:
            raise ValueError("Empty STOMP frame")
        
        # 解析命令
        command_str = lines[0].strip().upper()
        try:
            command = StompCommand(command_str)
        except ValueError:
            raise ValueError(f"Unknown STOMP command: {command_str}")
        
        # 解析headers
        headers = {}
        body_start = 1
        for i, line in enumerate(lines[1:], 1):
            if line == "":
                body_start = i + 1
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[cls._decode_header(key)] = cls._decode_header(value)
        
        # 解析body
        body = "\n".join(lines[body_start:]) if body_start < len(lines) else ""
        
        return cls(command=command, headers=headers, body=body)
    
    @classmethod
    def from_json(cls, data: str) -> "StompFrame":
        """从JSON解析"""
        obj = json.loads(data)
        command = StompCommand(obj.get("command", "").upper())
        headers = obj.get("headers", {})
        body = obj.get("body", "")
        return cls(command=command, headers=headers, body=body)
    
    @staticmethod
    def _encode_header(value: str) -> str:
        """编码header值（转义特殊字符）"""
        return value.replace("\\", "\\\\").replace("\n", "\\n").replace(":", "\\c").replace("\r", "\\r")
    
    @staticmethod
    def _decode_header(value: str) -> str:
        """解码header值"""
        return value.replace("\\r", "\r").replace("\\n", "\n").replace("\\c", ":").replace("\\\\", "\\")


# 便捷工厂函数
def connected_frame(version: str = "1.2", heart_beat: str = "10000,10000", server: str = "frontai-stomp/1.0") -> StompFrame:
    """创建CONNECTED帧"""
    return StompFrame(
        command=StompCommand.CONNECTED,
        headers={
            "version": version,
            "heart-beat": heart_beat,
            "server": server,
        }
    )


def message_frame(destination: str, message_id: str, subscription: str, body: str, content_type: str = "application/json") -> StompFrame:
    """创建MESSAGE帧"""
    return StompFrame(
        command=StompCommand.MESSAGE,
        headers={
            "destination": destination,
            "message-id": message_id,
            "subscription": subscription,
            "content-type": content_type,
            "content-length": str(len(body.encode("utf-8"))),
        },
        body=body,
    )


def receipt_frame(receipt_id: str) -> StompFrame:
    """创建RECEIPT帧"""
    return StompFrame(
        command=StompCommand.RECEIPT,
        headers={"receipt-id": receipt_id},
    )


def error_frame(message: str, details: str = "") -> StompFrame:
    """创建ERROR帧"""
    return StompFrame(
        command=StompCommand.ERROR,
        headers={
            "message": message,
            "content-type": "text/plain",
        },
        body=details,
    )
