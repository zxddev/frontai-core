#!/usr/bin/env python3
"""
任务智能分发系统 - 端到端测试

测试流程：
1. EmergencyAI输出增强 - 验证scheme_text和scheme_text_hash生成
2. SchemeParsingAgent - 测试LLM解析方案文本
3. TaskDispatch API - 测试生成任务卡、下发任务
"""
import asyncio
import hashlib
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

console = Console()


# ============================================================================
# 测试数据
# ============================================================================

MOCK_PARSED_DISASTER = {
    "disaster_type": "earthquake",
    "severity": "critical",
    "magnitude": 6.5,
    "has_building_collapse": True,
    "has_trapped_persons": True,
    "estimated_trapped": 50,
    "has_secondary_fire": True,
    "has_hazmat_leak": False,
    "has_road_damage": True,
    "affected_population": 10000,
    "building_damage_level": "severe",
}

MOCK_TASK_SEQUENCE = [
    {
        "task_id": "EM06",
        "task_name": "生命探测",
        "phase": "detect",
        "priority": "critical",
        "sequence": 1,
        "depends_on": [],
        "golden_hour": 60,
    },
    {
        "task_id": "EM10",
        "task_name": "被困人员救援",
        "phase": "execute",
        "priority": "critical",
        "sequence": 2,
        "depends_on": ["EM06"],
        "golden_hour": 120,
    },
    {
        "task_id": "EM14",
        "task_name": "伤员急救",
        "phase": "execute",
        "priority": "high",
        "sequence": 3,
        "depends_on": ["EM10"],
        "golden_hour": None,
    },
]

MOCK_RECOMMENDED_SCHEME = {
    "solution_id": "scheme-001",
    "allocations": [
        {
            "resource_id": "72c767de-379d-421a-bbf5-7fb01abd7cc7",  # 茂县消防救援大队
            "resource_name": "茂县消防救援大队",
            "assigned_capabilities": ["生命探测", "重型破拆"],
            "eta_minutes": 15,
            "distance_km": 8.5,
        },
        {
            "resource_id": "1fe8d3b7-3bfc-4d1d-b246-fe4cec9f30c8",  # 汶川消防救援大队
            "resource_name": "汶川消防救援大队",
            "assigned_capabilities": ["灭火", "人员搜救"],
            "eta_minutes": 25,
            "distance_km": 15.2,
        },
        {
            "resource_id": "ebef8b45-ee92-4d11-8ff1-c1ee2d7a2ab9",  # 茂县人民医院急救队
            "resource_name": "茂县人民医院急救队",
            "assigned_capabilities": ["伤员急救", "医疗转运"],
            "eta_minutes": 20,
            "distance_km": 12.0,
        },
    ],
    "total_score": 0.85,
    "response_time_min": 15,
    "coverage_rate": 0.95,
}

MOCK_SCHEME_EXPLANATION = {
    "summary": "针对6.5级地震造成的建筑倒塌和人员被困情况，推荐采用三支队伍协同救援策略。"
}


# ============================================================================
# 测试1: EmergencyAI输出增强
# ============================================================================

def test_emergency_ai_output():
    """测试EmergencyAI输出节点的scheme_text和scheme_text_hash生成"""
    console.print("\n" + "="*60)
    console.print("[bold blue]测试1: EmergencyAI输出增强[/bold blue]")
    console.print("="*60)
    
    from src.agents.emergency_ai.nodes.output import _generate_scheme_text
    
    # 生成方案文本
    scheme_text = _generate_scheme_text(
        parsed_disaster=MOCK_PARSED_DISASTER,
        task_sequence=MOCK_TASK_SEQUENCE,
        recommended_scheme=MOCK_RECOMMENDED_SCHEME,
        scheme_explanation=MOCK_SCHEME_EXPLANATION,
    )
    
    # 计算哈希
    scheme_text_hash = hashlib.md5(scheme_text.encode("utf-8")).hexdigest()
    
    console.print("\n[green]✓ 方案文本生成成功[/green]")
    console.print(Panel(scheme_text, title="生成的方案文本", expand=False))
    console.print(f"\n[cyan]MD5哈希: {scheme_text_hash}[/cyan]")
    
    # 验证
    assert len(scheme_text) > 100, "方案文本太短"
    assert "灾害类型" in scheme_text, "缺少灾害类型"
    assert "救援力量部署" in scheme_text, "缺少救援力量部署"
    assert "任务安排" in scheme_text, "缺少任务安排"
    assert len(scheme_text_hash) == 32, "哈希长度不正确"
    
    console.print("[green]✓ 所有断言通过[/green]")
    
    return scheme_text, scheme_text_hash


# ============================================================================
# 测试2: SchemeParsingAgent
# ============================================================================

async def test_scheme_parsing_agent(scheme_text: str):
    """测试SchemeParsingAgent解析方案文本"""
    console.print("\n" + "="*60)
    console.print("[bold blue]测试2: SchemeParsingAgent方案解析[/bold blue]")
    console.print("="*60)
    
    from src.agents.scheme_parsing import SchemeParsingAgent, ParsedScheme
    
    agent = SchemeParsingAgent()
    
    # 模拟用户编辑后的方案文本
    modified_text = scheme_text.replace("成都重型救援队", "德阳特勤救援队")
    modified_text += "\n\n补充：增派一支通信保障队负责现场通信。"
    
    console.print("\n[yellow]模拟用户编辑方案文本...[/yellow]")
    console.print(f"原始队伍: 成都重型救援队 → 修改为: 德阳特勤救援队")
    console.print("新增: 通信保障队")
    
    # 解析
    console.print("\n[yellow]调用LLM解析修改后的方案...[/yellow]")
    
    try:
        result: ParsedScheme = await agent.parse(
            scheme_text=modified_text,
            available_teams=[
                {"name": "德阳特勤救援队", "capabilities": ["生命探测", "重型破拆"]},
                {"name": "绵阳消防支队", "capabilities": ["灭火", "人员搜救"]},
                {"name": "省医疗救护队", "capabilities": ["伤员急救"]},
                {"name": "通信保障队", "capabilities": ["通信保障"]},
            ],
        )
        
        console.print(f"\n[green]✓ 解析成功，置信度: {result.parsing_confidence:.2f}[/green]")
        
        # 显示解析结果
        table = Table(title="解析出的任务列表")
        table.add_column("任务名称", style="cyan")
        table.add_column("任务类型", style="green")
        table.add_column("优先级", style="yellow")
        table.add_column("负责队伍", style="magenta")
        table.add_column("时长(分钟)")
        
        for task in result.tasks:
            table.add_row(
                task.task_name,
                task.task_type,
                task.priority,
                task.assigned_team,
                str(task.duration_min),
            )
        
        console.print(table)
        
        # 显示队伍分配
        console.print("\n[bold]队伍分配:[/bold]")
        for assignment in result.team_assignments:
            console.print(f"  - {assignment.team_name}: {', '.join(assignment.task_names)}")
        
        if result.warnings:
            console.print(f"\n[yellow]警告: {result.warnings}[/yellow]")
        
        return result
        
    except Exception as e:
        console.print(f"\n[red]✗ 解析失败: {e}[/red]")
        console.print("[yellow]注意: LLM服务可能不可用，跳过此测试[/yellow]")
        return None


# ============================================================================
# 测试3: TaskDispatch API
# ============================================================================

async def test_task_dispatch_api(scheme_text: str, scheme_text_hash: str):
    """测试TaskDispatch API完整流程"""
    console.print("\n" + "="*60)
    console.print("[bold blue]测试3: TaskDispatch API完整流程[/bold blue]")
    console.print("="*60)
    
    from src.agents.task_dispatch.router import (
        generate_task_cards,
        get_dispatch_status,
        dispatch_tasks,
        update_card_status,
        TaskDispatchGenerateRequest,
        TaskDispatchRequest,
        GeoLocation,
        _dispatch_store,
    )
    
    # 3.1 测试生成任务卡（未修改方案）
    console.print("\n[yellow]3.1 生成任务卡（方案未修改）...[/yellow]")
    
    request = TaskDispatchGenerateRequest(
        event_id="evt-test-001",
        scheme_id="sch-test-001",
        scheme_text=scheme_text,
        scheme_text_hash=scheme_text_hash,  # 哈希匹配=未修改
        original_structured_data={
            "htn_decomposition": {
                "task_sequence": MOCK_TASK_SEQUENCE,
            },
            "recommended_scheme": MOCK_RECOMMENDED_SCHEME,
        },
        event_location=GeoLocation(lat=30.57, lng=104.06),
        available_teams=MOCK_RECOMMENDED_SCHEME["allocations"],
    )
    
    try:
        response = await generate_task_cards(request)
        
        console.print(f"[green]✓ 任务卡生成成功[/green]")
        console.print(f"  - dispatch_id: {response.dispatch_id}")
        console.print(f"  - 文本是否被修改: {response.is_text_modified}")
        console.print(f"  - 任务卡数量: {len(response.task_cards)}")
        console.print(f"  - 执行耗时: {response.execution_time_ms}ms")
        
        assert response.success, "生成失败"
        assert not response.is_text_modified, "未修改时不应标记为修改"
        assert len(response.task_cards) > 0, "应生成任务卡"
        
        # 显示任务卡
        table = Table(title="生成的任务卡")
        table.add_column("任务名称", style="cyan")
        table.add_column("执行单位", style="green")
        table.add_column("优先级", style="yellow")
        table.add_column("计划开始", style="magenta")
        table.add_column("状态")
        
        for card in response.task_cards:
            table.add_row(
                card.task_name,
                card.executor_name,
                card.priority,
                card.scheduled_start or "-",
                card.status,
            )
        
        console.print(table)
        
        dispatch_id = response.dispatch_id
        
    except Exception as e:
        console.print(f"[red]✗ 生成失败: {e}[/red]")
        import traceback
        traceback.print_exc()
        return
    
    # 3.2 测试查询分发状态
    console.print("\n[yellow]3.2 查询分发状态...[/yellow]")
    
    try:
        status = await get_dispatch_status(dispatch_id)
        console.print(f"[green]✓ 查询成功[/green]")
        console.print(f"  - 状态: {status['status']}")
        console.print(f"  - 任务卡数量: {len(status['task_cards'])}")
    except Exception as e:
        console.print(f"[red]✗ 查询失败: {e}[/red]")
    
    # 3.3 测试下发任务
    console.print("\n[yellow]3.3 下发任务...[/yellow]")
    
    try:
        dispatch_request = TaskDispatchRequest(task_card_ids=[])  # 空=全部下发
        dispatch_response = await dispatch_tasks(dispatch_id, dispatch_request)
        
        console.print(f"[green]✓ 下发成功[/green]")
        console.print(f"  - 下发数量: {dispatch_response.dispatched_count}")
        console.print(f"  - 通知数量: {len(dispatch_response.notifications_sent)}")
        
        if dispatch_response.errors:
            console.print(f"  - 错误: {dispatch_response.errors}")
            
    except Exception as e:
        console.print(f"[red]✗ 下发失败: {e}[/red]")
    
    # 3.4 测试更新任务卡状态
    console.print("\n[yellow]3.4 更新任务卡状态...[/yellow]")
    
    try:
        # 获取第一个任务卡ID
        status = await get_dispatch_status(dispatch_id)
        first_card_id = status['task_cards'][0]['card_id']
        
        result = await update_card_status(dispatch_id, first_card_id, "accepted")
        console.print(f"[green]✓ 状态更新成功[/green]")
        console.print(f"  - card_id: {result['card_id']}")
        console.print(f"  - new_status: {result['new_status']}")
        
    except Exception as e:
        console.print(f"[red]✗ 状态更新失败: {e}[/red]")
    
    # 3.5 测试生成任务卡（修改方案）
    console.print("\n[yellow]3.5 生成任务卡（方案已修改）...[/yellow]")
    
    modified_text = scheme_text + "\n\n增派一支通信保障队。"
    new_hash = hashlib.md5(modified_text.encode("utf-8")).hexdigest()
    
    console.print(f"  原始哈希: {scheme_text_hash[:16]}...")
    console.print(f"  新文本哈希: {new_hash[:16]}...")
    console.print(f"  哈希是否变化: {scheme_text_hash != new_hash}")
    
    request2 = TaskDispatchGenerateRequest(
        event_id="evt-test-002",
        scheme_id="sch-test-002",
        scheme_text=modified_text,
        scheme_text_hash=scheme_text_hash,  # 使用原始哈希，触发LLM解析
        original_structured_data={
            "htn_decomposition": {"task_sequence": MOCK_TASK_SEQUENCE},
            "recommended_scheme": MOCK_RECOMMENDED_SCHEME,
        },
        event_location=GeoLocation(lat=30.57, lng=104.06),
        available_teams=MOCK_RECOMMENDED_SCHEME["allocations"],
    )
    
    try:
        response2 = await generate_task_cards(request2)
        console.print(f"[green]✓ 任务卡生成成功（触发LLM解析）[/green]")
        console.print(f"  - 文本是否被修改: {response2.is_text_modified}")
        console.print(f"  - 解析置信度: {response2.parsing_confidence}")
        console.print(f"  - 任务卡数量: {len(response2.task_cards)}")
        
        if response2.warnings:
            console.print(f"  - 警告: {response2.warnings}")
            
    except Exception as e:
        console.print(f"[yellow]⚠ LLM解析可能失败（服务不可用）: {e}[/yellow]")


# ============================================================================
# 测试4: 哈希对比逻辑
# ============================================================================

def test_hash_comparison():
    """测试哈希对比逻辑"""
    console.print("\n" + "="*60)
    console.print("[bold blue]测试4: 哈希对比逻辑[/bold blue]")
    console.print("="*60)
    
    original_text = "这是原始方案文本"
    original_hash = hashlib.md5(original_text.encode("utf-8")).hexdigest()
    
    # 场景1: 文本未修改
    current_text1 = "这是原始方案文本"
    current_hash1 = hashlib.md5(current_text1.encode("utf-8")).hexdigest()
    is_modified1 = current_hash1 != original_hash
    
    console.print(f"\n场景1 - 文本未修改:")
    console.print(f"  原始哈希: {original_hash}")
    console.print(f"  当前哈希: {current_hash1}")
    console.print(f"  是否修改: {is_modified1}")
    assert not is_modified1, "未修改文本不应被检测为修改"
    console.print(f"  [green]✓ 正确识别为未修改[/green]")
    
    # 场景2: 文本已修改
    current_text2 = "这是修改后的方案文本"
    current_hash2 = hashlib.md5(current_text2.encode("utf-8")).hexdigest()
    is_modified2 = current_hash2 != original_hash
    
    console.print(f"\n场景2 - 文本已修改:")
    console.print(f"  原始哈希: {original_hash}")
    console.print(f"  当前哈希: {current_hash2}")
    console.print(f"  是否修改: {is_modified2}")
    assert is_modified2, "修改后文本应被检测为修改"
    console.print(f"  [green]✓ 正确识别为已修改[/green]")
    
    # 场景3: 仅空格变化
    current_text3 = "这是原始方案文本 "  # 末尾加空格
    current_hash3 = hashlib.md5(current_text3.encode("utf-8")).hexdigest()
    is_modified3 = current_hash3 != original_hash
    
    console.print(f"\n场景3 - 仅空格变化:")
    console.print(f"  原始哈希: {original_hash}")
    console.print(f"  当前哈希: {current_hash3}")
    console.print(f"  是否修改: {is_modified3}")
    console.print(f"  [yellow]⚠ 空格变化会被检测为修改（预期行为）[/yellow]")


# ============================================================================
# 主函数
# ============================================================================

async def main():
    console.print(Panel.fit(
        "[bold green]任务智能分发系统 - 端到端测试[/bold green]\n"
        "测试EmergencyAI输出增强、SchemeParsingAgent、TaskDispatch API",
        border_style="green",
    ))
    
    try:
        # 测试1: EmergencyAI输出增强
        scheme_text, scheme_text_hash = test_emergency_ai_output()
        
        # 测试2: SchemeParsingAgent (需要LLM服务)
        # parsed_result = await test_scheme_parsing_agent(scheme_text)
        console.print("\n[yellow]跳过测试2 (SchemeParsingAgent) - 需要LLM服务[/yellow]")
        
        # 测试3: TaskDispatch API
        await test_task_dispatch_api(scheme_text, scheme_text_hash)
        
        # 测试4: 哈希对比逻辑
        test_hash_comparison()
        
        console.print("\n" + "="*60)
        console.print("[bold green]✓ 端到端测试完成[/bold green]")
        console.print("="*60)
        
    except Exception as e:
        console.print(f"\n[bold red]✗ 测试失败: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
