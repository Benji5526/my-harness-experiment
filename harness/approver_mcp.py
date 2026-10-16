"""모의 승인자: Claude Code의 --permission-prompt-tool 로 연결되는 최소 MCP(stdio) 서버.

권한 프롬프트가 뜰 때마다 호출되어 (시각, 도구, 입력)을 JSONL로 기록하고 무조건 허용한다.
이 로그의 줄 수가 '승인 요청 횟수'이다. 승인에 걸리는 사람의 대기 시간은 여기서 흉내 내지 않는다(0초).
"""
import json
import os
import sys
import time

LOG = os.environ["APPROVER_LOG"]

TOOL = {
    "name": "approve",
    "description": "Log the permission request and allow it.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string"},
            "input": {"type": "object"},
            "tool_use_id": {"type": "string"},
        },
        "required": ["tool_name", "input"],
    },
}


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": msg["params"].get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "approver", "version": "1.0"}}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [TOOL]}})
    elif method == "tools/call":
        args = msg["params"].get("arguments", {})
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), "tool": args.get("tool_name"),
                                "input": args.get("input")}, ensure_ascii=False) + "\n")
        decision = {"behavior": "allow", "updatedInput": args.get("input", {})}
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "content": [{"type": "text", "text": json.dumps(decision)}]}})
    elif mid is not None:
        send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "unknown method"}})
