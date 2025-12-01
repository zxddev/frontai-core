#!/usr/bin/env python3
"""
语音指挥Agent端到端测试

模拟 VoiceChatManager 流程，验证：
1. 语义路由分类准确性
2. Agent 返回的 AIResponse 格式
3. WebSocket 消息格式（模拟记录）

日志输出到: logs/voice_commander_test.log
"""
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 配置日志
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "voice_commander_test.log"

# 清空旧日志
with open(LOG_FILE, "w") as f:
    f.write(f"=== Voice Commander E2E Test ===\n")
    f.write(f"Started at: {datetime.now().isoformat()}\n")
    f.write("=" * 50 + "\n\n")

# 配置 logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("e2e_test")


@dataclass
class MockWebSocket:
    """模拟 WebSocket，记录所有发送的消息"""
    messages: List[Dict] = field(default_factory=list)
    
    async def send_json(self, data: Dict) -> None:
        self.messages.append(data)
    
    def get_messages_by_type(self, msg_type: str) -> List[Dict]:
        return [m for m in self.messages if m.get("type") == msg_type]
    
    def clear(self):
        self.messages = []


@dataclass
class MockSession:
    """模拟语音会话"""
    session_id: str = field(default_factory=lambda: str(uuid4()))
    websocket: MockWebSocket = field(default_factory=MockWebSocket)
    config: Dict = field(default_factory=lambda: {"enable_tts": False})
    chat_history: List[Dict] = field(default_factory=list)


# 测试用例
TEST_CASES = [
    # task_status 路由测试
    {"query": "任务进度怎么样", "expected_route": "task_status"},
    {"query": "现在有多少任务", "expected_route": "task_status"},
    {"query": "任务完成情况如何", "expected_route": "task_status"},
    {"query": "正在执行什么任务", "expected_route": "task_status"},
    {"query": "有哪些任务完成了", "expected_route": "task_status"},
    {"query": "搜救任务有多少", "expected_route": "task_status"},
    {"query": "待办任务还有几个", "expected_route": "task_status"},
    {"query": "任务执行到哪了", "expected_route": "task_status"},
    {"query": "今天完成了多少任务", "expected_route": "task_status"},
    {"query": "还有多少任务没完成", "expected_route": "task_status"},
    {"query": "任务总览", "expected_route": "task_status"},
    {"query": "汇报任务情况", "expected_route": "task_status"},
    {"query": "侦察任务完成了吗", "expected_route": "task_status"},
    {"query": "紧急任务有几个", "expected_route": "task_status"},
    {"query": "任务列表", "expected_route": "task_status"},
    
    # resource_status 路由测试
    {"query": "消防队在干什么", "expected_route": "resource_status"},
    {"query": "有多少队伍可用", "expected_route": "resource_status"},
    {"query": "哪些队伍空闲", "expected_route": "resource_status"},
    {"query": "一号车队状态", "expected_route": "resource_status"},
    {"query": "医疗队在哪里", "expected_route": "spatial_query"},  # 位置查询
    {"query": "救援队现在忙吗", "expected_route": "resource_status"},
    {"query": "队伍资源情况", "expected_route": "resource_status"},
    {"query": "还有多少人员待命", "expected_route": "resource_status"},
    {"query": "消防车可以调动吗", "expected_route": "resource_status"},
    {"query": "有没有空闲的救援队", "expected_route": "resource_status"},
    {"query": "队伍部署情况", "expected_route": "resource_status"},
    {"query": "资源统计", "expected_route": "resource_status"},
    {"query": "二号队在执行什么任务", "expected_route": "resource_status"},
    {"query": "可调度的队伍有哪些", "expected_route": "resource_status"},
    {"query": "队伍状态汇总", "expected_route": "resource_status"},
    
    # spatial_query 路由测试
    {"query": "指挥部在哪里", "expected_route": "spatial_query"},
    {"query": "离我最近的医疗点", "expected_route": "spatial_query"},
    {"query": "A区域现在什么情况", "expected_route": "spatial_query"},
    {"query": "受灾点位置", "expected_route": "spatial_query"},
    {"query": "最近的消防站在哪", "expected_route": "spatial_query"},
    {"query": "从指挥部到受灾点多远", "expected_route": "spatial_query"},
    {"query": "附近有什么资源", "expected_route": "spatial_query"},
    {"query": "B区状态怎么样", "expected_route": "spatial_query"},
    {"query": "安置点在什么位置", "expected_route": "spatial_query"},
    {"query": "哪里需要支援", "expected_route": "spatial_query"},
    
    # chitchat 路由测试（降级到基础LLM）
    {"query": "你好", "expected_route": "chitchat"},
    {"query": "今天天气怎么样", "expected_route": "chitchat"},
    {"query": "给我讲个笑话", "expected_route": "chitchat"},
]


def log_to_file(content: str):
    """写入日志文件"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(content + "\n")


def log_separator():
    log_to_file("\n" + "=" * 60 + "\n")


async def test_semantic_routing(query: str) -> tuple:
    """测试语义路由分类"""
    from src.agents.voice_commander.semantic_router import get_semantic_router
    
    router = get_semantic_router()
    route_name, confidence, is_fallback = await router.classify(query)
    
    return route_name, confidence, is_fallback


async def reset_router() -> None:
    """重置语义路由器以加载最新样本"""
    from src.agents.voice_commander.semantic_router import reset_semantic_router
    await reset_semantic_router()


async def test_agent_dispatch(session: MockSession, route_name: str, query: str) -> Optional[Any]:
    """测试 Agent 分发，返回 AIResponse"""
    from src.agents.voice_commander.ui_actions import AIResponse, fly_to_entity, highlight_entities
    
    try:
        if route_name == "spatial_query":
            from src.agents.voice_commander.spatial_graph import get_spatial_agent_graph
            
            graph = get_spatial_agent_graph()
            initial_state = {
                "query": query,
                "session_id": session.session_id,
                "parsed_intent": None,
                "selected_tool": None,
                "tool_input": {},
                "tool_results": [],
                "response": None,
                "trace": {},
            }
            
            result = await graph.ainvoke(initial_state)
            response_text = result.get("response")
            
            if response_text:
                ui_actions = []
                mentioned_entities = []
                
                tool_results = result.get("tool_results", [])
                if tool_results:
                    for tr in tool_results:
                        entities = tr.get("entities", [])
                        for entity in entities[:5]:
                            entity_id = entity.get("id")
                            entity_type = entity.get("entity_type", "").lower()
                            if entity_id:
                                full_id = f"{entity_type}-{entity_id}" if entity_type else str(entity_id)
                                mentioned_entities.append(full_id)
                
                if mentioned_entities:
                    ui_actions.append(fly_to_entity(mentioned_entities[0], zoom=14).model_dump(exclude_none=True))
                    ui_actions.append(highlight_entities(mentioned_entities, duration=8000).model_dump(exclude_none=True))
                
                return AIResponse(
                    text=response_text + (" 已在地图上标注。" if mentioned_entities else ""),
                    ui_actions=ui_actions,
                    context={"mentioned_entities": mentioned_entities} if mentioned_entities else None,
                )
            return None
            
        elif route_name == "task_status":
            from src.agents.voice_commander.task_agent import run_task_agent
            return await run_task_agent(query, session.session_id)
            
        elif route_name == "resource_status":
            from src.agents.voice_commander.resource_agent import run_resource_agent
            return await run_resource_agent(query, session.session_id)
            
        else:
            return None
            
    except Exception as e:
        logger.exception(f"Agent dispatch failed: {e}")
        return None


async def simulate_websocket_send(session: MockSession, ai_response) -> None:
    """模拟 WebSocket 消息发送（与 _send_ai_response_and_tts 逻辑一致）"""
    ai_text = ai_response.text
    
    # 发送 ai_response 消息
    response_data = {
        "type": "ai_response",
        "text": ai_text,
        "ui_actions": ai_response.ui_actions or [],
    }
    if ai_response.context:
        response_data["context"] = ai_response.context
    
    await session.websocket.send_json(response_data)
    
    # 发送 llm_done 保持兼容
    await session.websocket.send_json({
        "type": "llm_done",
        "text": ai_text,
        "llm_latency_ms": 0,
    })


def validate_ai_response(ai_response, route_name: str) -> List[str]:
    """验证 AIResponse 格式，返回错误列表"""
    errors = []
    
    if not ai_response:
        errors.append("AIResponse is None")
        return errors
    
    if not ai_response.text:
        errors.append("AIResponse.text is empty")
    
    if ai_response.ui_actions:
        for i, action in enumerate(ai_response.ui_actions):
            if isinstance(action, dict):
                if "action" not in action:
                    errors.append(f"ui_actions[{i}] missing 'action' field")
            else:
                errors.append(f"ui_actions[{i}] is not a dict: {type(action)}")
    
    # 验证特定路由的 UI 动作
    if route_name == "task_status":
        # 期望有 panel.open 动作
        has_panel_action = any(
            a.get("action") == "panel.open" 
            for a in (ai_response.ui_actions or []) 
            if isinstance(a, dict)
        )
        if not has_panel_action:
            errors.append("task_status should have panel.open action")
    
    return errors


def validate_websocket_messages(messages: List[Dict]) -> List[str]:
    """验证 WebSocket 消息格式"""
    errors = []
    
    # 检查必须的消息类型
    types = [m.get("type") for m in messages]
    
    if "ai_response" not in types:
        errors.append("Missing 'ai_response' message")
    
    if "llm_done" not in types:
        errors.append("Missing 'llm_done' message")
    
    # 验证 ai_response 消息格式
    ai_msgs = [m for m in messages if m.get("type") == "ai_response"]
    for msg in ai_msgs:
        if "text" not in msg:
            errors.append("ai_response missing 'text' field")
        if "ui_actions" not in msg:
            errors.append("ai_response missing 'ui_actions' field")
    
    return errors


async def run_single_test(test_case: Dict, test_num: int) -> Dict:
    """运行单个测试用例"""
    query = test_case["query"]
    expected_route = test_case["expected_route"]
    
    log_to_file(f"\n=== Test Case #{test_num} ===")
    log_to_file(f"Query: {query}")
    log_to_file(f"Expected Route: {expected_route}")
    
    result = {
        "query": query,
        "expected_route": expected_route,
        "actual_route": None,
        "route_correct": False,
        "confidence": 0,
        "is_fallback": False,
        "ai_response": None,
        "ws_messages": [],
        "errors": [],
        "latency_ms": 0,
        "passed": False,
    }
    
    session = MockSession()
    start_time = time.time()
    
    try:
        # 1. 语义路由测试
        route_name, confidence, is_fallback = await test_semantic_routing(query)
        result["actual_route"] = route_name
        result["confidence"] = confidence
        result["is_fallback"] = is_fallback
        result["route_correct"] = (route_name == expected_route)
        
        log_to_file(f"Actual Route: {route_name}")
        log_to_file(f"Confidence: {confidence:.3f}")
        log_to_file(f"Is Fallback: {is_fallback}")
        log_to_file(f"Route Correct: {'✓' if result['route_correct'] else '✗'}")
        
        # 2. Agent 分发测试（仅对非 chitchat 路由）
        if expected_route != "chitchat" and route_name in ("spatial_query", "task_status", "resource_status"):
            ai_response = await test_agent_dispatch(session, route_name, query)
            
            if ai_response:
                result["ai_response"] = {
                    "text": ai_response.text,
                    "ui_actions": ai_response.ui_actions,
                    "context": ai_response.context,
                }
                
                log_to_file("\n--- AIResponse ---")
                log_to_file(json.dumps(result["ai_response"], ensure_ascii=False, indent=2))
                
                # 3. 模拟 WebSocket 发送
                await simulate_websocket_send(session, ai_response)
                result["ws_messages"] = session.websocket.messages
                
                log_to_file("\n--- WebSocket Messages ---")
                for msg in session.websocket.messages:
                    log_to_file(f"[{msg.get('type')}]")
                    log_to_file(json.dumps(msg, ensure_ascii=False, indent=2))
                
                # 4. 验证
                ai_errors = validate_ai_response(ai_response, route_name)
                ws_errors = validate_websocket_messages(session.websocket.messages)
                result["errors"] = ai_errors + ws_errors
                
                if result["errors"]:
                    log_to_file("\n--- Errors ---")
                    for err in result["errors"]:
                        log_to_file(f"  - {err}")
            else:
                result["errors"].append("Agent returned None")
                log_to_file("\n--- AIResponse ---")
                log_to_file("None (Agent returned no response)")
        
        # 对 chitchat，只要路由正确就算通过
        if expected_route == "chitchat":
            result["passed"] = result["route_correct"]
        else:
            result["passed"] = result["route_correct"] and len(result["errors"]) == 0
        
    except Exception as e:
        result["errors"].append(f"Exception: {str(e)}")
        logger.exception(f"Test case failed: {e}")
    
    result["latency_ms"] = int((time.time() - start_time) * 1000)
    
    log_to_file(f"\nLatency: {result['latency_ms']}ms")
    log_to_file(f"Result: {'PASS ✓' if result['passed'] else 'FAIL ✗'}")
    log_separator()
    
    return result


async def run_all_tests():
    """运行所有测试"""
    print(f"\n{'='*60}")
    print(f"Voice Commander E2E Test")
    print(f"Log file: {LOG_FILE}")
    print(f"{'='*60}\n")
    
    # 重置路由器以加载最新样本配置
    await reset_router()
    
    results = []
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] Testing: {test_case['query'][:30]}...", end=" ")
        result = await run_single_test(test_case, i)
        results.append(result)
        
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"{status} ({result['latency_ms']}ms)")
    
    # 统计结果
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    route_correct = sum(1 for r in results if r["route_correct"])
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}/{total} ({passed/total*100:.1f}%)")
    print(f"Route Accuracy: {route_correct}/{total} ({route_correct/total*100:.1f}%)")
    
    # 按路由统计
    print(f"\n--- By Route ---")
    for route in ["task_status", "resource_status", "spatial_query", "chitchat"]:
        route_results = [r for r in results if r["expected_route"] == route]
        if route_results:
            route_passed = sum(1 for r in route_results if r["passed"])
            route_correct_count = sum(1 for r in route_results if r["route_correct"])
            print(f"{route}: {route_passed}/{len(route_results)} passed, {route_correct_count}/{len(route_results)} routed correctly")
    
    # 输出失败用例
    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n--- Failed Cases ({len(failed)}) ---")
        for r in failed:
            print(f"  - \"{r['query']}\"")
            print(f"    Expected: {r['expected_route']}, Got: {r['actual_route']}")
            if r["errors"]:
                for err in r["errors"]:
                    print(f"    Error: {err}")
    
    # 写入汇总到日志
    log_to_file("\n" + "=" * 60)
    log_to_file("SUMMARY")
    log_to_file("=" * 60)
    log_to_file(f"Total: {total}, Passed: {passed}, Route Accuracy: {route_correct}")
    log_to_file(f"Pass Rate: {passed/total*100:.1f}%")
    log_to_file(f"Finished at: {datetime.now().isoformat()}")
    
    print(f"\nLog saved to: {LOG_FILE}")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_all_tests())
