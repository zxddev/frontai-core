"""
EmergencyAI LangGraph流程定义

基于LangGraph 1.0构建4阶段AI+规则混合流程。
支持状态持久化，服务崩溃后可从断点恢复。
支持人在回路(HITL)机制，关键决策点需指挥官审批。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Dict, Any, Literal, Optional, List

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import interrupt

from .state import (
    EmergencyAIState,
    HumanApprovalRequest,
    HumanApprovalResponse,
)
from .nodes import (
    # 阶段1
    understand_disaster,
    enhance_with_cases,
    # 阶段2
    query_rules,
    apply_rules,
    # 阶段2.5: HTN任务分解
    htn_decompose,
    # 阶段2.6: 战略层 - 任务域/阶段/模块
    classify_domains,
    apply_phase_priority,
    assemble_modules,
    # 阶段3
    match_resources,
    optimize_allocation,
    # 阶段3.5: 战略层 - 运力
    check_transport,
    # 阶段4
    filter_hard_rules,
    # 阶段4.1: 战略层 - 安全
    check_safety_rules,
    score_soft_rules,
    explain_scheme,
    # 阶段4.5: 战略层 - 报告
    generate_reports,
    # 阶段5: 仿真闭环
    run_simulation,
    # 输出
    generate_output,
)

logger = logging.getLogger(__name__)


def should_continue_after_understanding(state: EmergencyAIState) -> Literal["query_rules", "generate_output"]:
    """
    判断灾情理解后是否继续
    
    如果灾情解析失败，直接生成输出；否则继续规则推理。
    """
    if state.get("parsed_disaster") is None:
        logger.warning("灾情解析失败，跳转到输出")
        return "generate_output"
    return "query_rules"


def should_continue_after_rules(state: EmergencyAIState) -> Literal["classify_domains", "generate_output"]:
    """
    判断规则推理后是否继续
    
    如果没有匹配到任何规则，直接生成输出；否则进入战略层任务域分类。
    修改: 战略层优先于HTN分解执行，避免战略滞后。
    """
    matched_rules = state.get("matched_rules", [])
    if not matched_rules:
        logger.warning("无匹配规则，跳转到输出")
        return "generate_output"
    return "classify_domains"


def should_continue_after_strategy(state: EmergencyAIState) -> Literal["htn_decompose", "generate_output"]:
    """
    判断战略层审批后是否继续HTN分解
    
    如果战略层配置完成（有domain_priorities），则进入HTN任务分解；
    否则直接生成输出。
    """
    domain_priorities = state.get("domain_priorities", [])
    if not domain_priorities:
        logger.warning("无任务域优先级配置，跳转到输出")
        return "generate_output"
    return "htn_decompose"


def should_continue_after_strategic_module(state: EmergencyAIState) -> Literal["match_resources", "generate_output"]:
    """
    判断模块装配后是否继续
    
    只要有任务序列就继续资源匹配（即使没有预编组模块推荐）
    """
    task_sequence = state.get("task_sequence", [])
    if not task_sequence:
        logger.warning("无任务序列，跳转到输出")
        return "generate_output"
    return "match_resources"


def should_continue_after_matching(state: EmergencyAIState) -> Literal["filter_hard_rules", "generate_output"]:
    """
    判断资源匹配后是否继续
    
    如果没有候选方案，直接生成输出。
    """
    solutions = state.get("allocation_solutions", [])
    if not solutions:
        logger.warning("无候选方案，跳转到输出")
        return "generate_output"
    return "filter_hard_rules"


def should_explain_scheme(state: EmergencyAIState) -> Literal["explain_scheme", "generate_output"]:
    """
    判断是否需要生成方案解释
    
    如果有推荐方案，生成解释；否则直接输出。
    """
    recommended = state.get("recommended_scheme")
    if recommended:
        return "explain_scheme"
    return "generate_output"


# ============================================================================
# 人在回路(HITL)审批节点
# ============================================================================

def human_review_understanding(state: EmergencyAIState) -> Dict[str, Any]:
    """
    灾情理解人工审批点
    
    在LLM解析灾情后暂停流程，等待指挥官确认解析结果。
    指挥官可以：approve(批准)/reject(拒绝)/modify(修改)
    展示数据缺口警告，供指挥员补充缺失数据。
    """
    parsed = state.get("parsed_disaster")
    if not parsed:
        return {}
    
    # 合并验证警告和数据缺口警告
    validation_warnings = state.get("validation_warnings", [])
    data_gap_warnings = state.get("data_gap_warnings", [])
    
    # 将数据缺口的 message 字段提取为字符串警告
    data_gap_messages = [g.get("message", "") for g in data_gap_warnings if g.get("message")]
    all_warnings = validation_warnings + data_gap_messages
    
    approval_request: HumanApprovalRequest = {
        "approval_type": "understanding",
        "summary": f"灾害类型: {parsed.get('disaster_type', 'unknown')}, "
                   f"严重程度: {parsed.get('severity', 'unknown')}, "
                   f"预估被困: {parsed.get('estimated_trapped', 0)}人",
        "details": {
            "parsed_disaster": parsed,
            "similar_cases_count": len(state.get("similar_cases", [])),
            "data_gaps": data_gap_warnings,  # 结构化数据缺口信息（供前端展示补充入口）
        },
        "options": ["approve", "reject", "modify"],
        "warnings": all_warnings,
        "confidence_score": None,
        "timestamp": datetime.now().isoformat(),
    }
    
    logger.info(f"[HITL] 灾情理解审批点，等待指挥官确认: {approval_request['summary']}")
    
    # TODO: 演示后恢复HITL人机交互审批机制
    # response: HumanApprovalResponse = interrupt(approval_request)
    # 临时自动批准，用于演示
    response: HumanApprovalResponse = {"decision": "approved", "reason": "自动批准（演示模式）"}
    
    logger.info(f"[HITL] 指挥官决策: {response.get('decision')}, 理由: {response.get('reason', '')}")
    
    if response.get("decision") == "rejected":
        raise RuntimeError(f"指挥官拒绝灾情理解结果: {response.get('reason', '未说明原因')}")
    
    result: Dict[str, Any] = {
        "approval_history": state.get("approval_history", []) + [response],
    }
    
    if response.get("decision") == "modified" and response.get("modifications"):
        result["parsed_disaster"] = response["modifications"]
        logger.info("[HITL] 应用指挥官修改的灾情信息")
    
    return result


def human_review_strategy(state: EmergencyAIState) -> Dict[str, Any]:
    """
    战略优先级人工审批点
    
    在战略层确定任务域优先级后暂停，等待指挥官确认战略方向。
    """
    domain_priorities = state.get("domain_priorities", [])
    disaster_phase = state.get("disaster_phase", "")
    rule_conflicts = state.get("rule_conflicts", [])
    
    priority_summary = ", ".join([
        f"{d.get('name', '')}(优先级{d.get('priority', 0)})" 
        for d in domain_priorities[:3]
    ])
    
    approval_request: HumanApprovalRequest = {
        "approval_type": "strategy",
        "summary": f"当前阶段: {state.get('disaster_phase_name', disaster_phase)}, "
                   f"任务域优先级: {priority_summary}",
        "details": {
            "disaster_phase": disaster_phase,
            "disaster_phase_name": state.get("disaster_phase_name", ""),
            "domain_priorities": domain_priorities,
            "task_sequence_count": len(state.get("task_sequence", [])),
            "rule_conflicts": rule_conflicts,
        },
        "options": ["approve", "reject", "modify"],
        "warnings": [c.get("description", "") for c in rule_conflicts],
        "confidence_score": None,
        "timestamp": datetime.now().isoformat(),
    }
    
    logger.info(f"[HITL] 战略优先级审批点: {approval_request['summary']}")
    
    # TODO: 演示后恢复HITL人机交互审批机制
    # response: HumanApprovalResponse = interrupt(approval_request)
    # 临时自动批准，用于演示
    response: HumanApprovalResponse = {"decision": "approved", "reason": "自动批准（演示模式）"}
    
    logger.info(f"[HITL] 指挥官决策: {response.get('decision')}")
    
    if response.get("decision") == "rejected":
        raise RuntimeError(f"指挥官拒绝战略优先级: {response.get('reason', '未说明原因')}")
    
    result: Dict[str, Any] = {
        "approval_history": state.get("approval_history", []) + [response],
    }
    
    if response.get("decision") == "modified" and response.get("modifications"):
        mods = response["modifications"]
        if "domain_priorities" in mods:
            result["domain_priorities"] = mods["domain_priorities"]
        if "disaster_phase" in mods:
            result["disaster_phase"] = mods["disaster_phase"]
        logger.info("[HITL] 应用指挥官修改的战略优先级")
    
    return result


def human_review_scheme(state: EmergencyAIState) -> Dict[str, Any]:
    """
    最终方案人工审批点
    
    在方案评分后、生成解释前暂停，等待指挥官选择最终方案。
    展示所有方案（包括高风险方案），指挥官可以选择任意方案。
    """
    scheme_scores = state.get("scheme_scores", [])
    recommended = state.get("recommended_scheme")
    
    if not recommended:
        return {}
    
    high_risk_schemes = [
        s for s in scheme_scores 
        if s.get("requires_authorization", False)
    ]
    
    approval_request: HumanApprovalRequest = {
        "approval_type": "scheme",
        "summary": f"推荐方案: {recommended.get('solution_id', '')}, "
                   f"总分: {recommended.get('total_score', 0):.2f}, "
                   f"响应时间: {recommended.get('response_time_min', 0):.0f}分钟",
        "details": {
            "recommended_scheme": recommended,
            "all_schemes": scheme_scores,
            "high_risk_schemes": high_risk_schemes,
            "pareto_solutions_count": len(state.get("pareto_solutions", [])),
        },
        "options": ["approve", "reject", "select_alternative"],
        "warnings": [
            f"高风险方案数: {len(high_risk_schemes)}（需授权）" 
        ] if high_risk_schemes else [],
        "confidence_score": recommended.get("total_score"),
        "timestamp": datetime.now().isoformat(),
    }
    
    logger.info(f"[HITL] 最终方案审批点: {approval_request['summary']}")
    
    # TODO: 演示后恢复HITL人机交互审批机制
    # response: HumanApprovalResponse = interrupt(approval_request)
    # 临时自动批准，用于演示
    response: HumanApprovalResponse = {"decision": "approved", "reason": "自动批准（演示模式）"}
    
    logger.info(f"[HITL] 指挥官决策: {response.get('decision')}")
    
    if response.get("decision") == "rejected":
        raise RuntimeError(f"指挥官拒绝所有方案: {response.get('reason', '未说明原因')}")
    
    result: Dict[str, Any] = {
        "approval_history": state.get("approval_history", []) + [response],
    }
    
    if response.get("decision") == "select_alternative" and response.get("modifications"):
        selected_id = response["modifications"].get("selected_scheme_id")
        if selected_id:
            pareto = state.get("pareto_solutions", [])
            for sol in pareto:
                if sol.get("solution_id") == selected_id:
                    result["recommended_scheme"] = sol
                    logger.info(f"[HITL] 指挥官选择备选方案: {selected_id}")
                    break
    
    return result


def build_emergency_ai_graph() -> StateGraph:
    """
    构建EmergencyAI状态图
    
    流程：
    ```
    START
      │
      ▼
    ┌─────────────────────────────────────┐
    │ Phase 1: 灾情理解                   │
    │ understand_disaster → enhance_cases │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 解析成功?)
    ┌─────────────────────────────────────┐
    │ Phase 2: 规则推理                   │
    │ query_rules → apply_rules           │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 有匹配规则?)
    ┌─────────────────────────────────────┐
    │ Phase 2.5: HTN任务分解              │
    │ 场景识别 → 任务链合并 → 拓扑排序    │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 有任务序列?)
    ┌─────────────────────────────────────┐
    │ Phase 3: 资源匹配                   │
    │ match_resources → optimize_alloc    │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 有候选方案?)
    ┌─────────────────────────────────────┐
    │ Phase 4: 方案优化                   │
    │ filter_hard → score_soft → explain  │
    └─────────────────────────────────────┘
      │
      ▼
    generate_output
      │
      ▼
    END
    ```
    
    Returns:
        编译后的StateGraph
    """
    logger.info("构建EmergencyAI LangGraph...")
    
    # 创建状态图
    workflow = StateGraph(EmergencyAIState)
    
    # ========== 添加节点 ==========
    
    # 阶段1: 灾情理解
    workflow.add_node("understand_disaster", understand_disaster)
    workflow.add_node("enhance_with_cases", enhance_with_cases)
    
    # 阶段2: 规则推理
    workflow.add_node("query_rules", query_rules)
    workflow.add_node("apply_rules", apply_rules)
    
    # 阶段2.5: HTN任务分解
    workflow.add_node("htn_decompose", htn_decompose)
    
    # 阶段2.6: 战略层 - 任务域/阶段/模块
    workflow.add_node("classify_domains", classify_domains)
    workflow.add_node("apply_phase_priority", apply_phase_priority)
    workflow.add_node("assemble_modules", assemble_modules)
    
    # 阶段3: 资源匹配
    workflow.add_node("match_resources", match_resources)
    workflow.add_node("optimize_allocation", optimize_allocation)
    
    # 阶段3.5: 战略层 - 运力
    workflow.add_node("check_transport", check_transport)
    
    # 阶段4: 方案优化
    workflow.add_node("filter_hard_rules", filter_hard_rules)
    
    # 阶段4.1: 战略层 - 安全规则
    workflow.add_node("check_safety_rules", check_safety_rules)
    
    workflow.add_node("score_soft_rules", score_soft_rules)
    workflow.add_node("explain_scheme", explain_scheme)
    
    # 阶段4.5: 战略层 - 报告
    workflow.add_node("generate_reports", generate_reports)
    
    # 阶段5: 仿真闭环
    workflow.add_node("run_simulation", run_simulation)
    
    # HITL审批节点
    workflow.add_node("human_review_understanding", human_review_understanding)
    workflow.add_node("human_review_strategy", human_review_strategy)
    workflow.add_node("human_review_scheme", human_review_scheme)
    
    # 输出
    workflow.add_node("generate_output", generate_output)
    
    # ========== 定义边 ==========
    
    # START → Phase 1
    workflow.add_edge(START, "understand_disaster")
    workflow.add_edge("understand_disaster", "enhance_with_cases")
    
    # Phase 1 → HITL审批点1 → Phase 2 (conditional)
    workflow.add_conditional_edges(
        "enhance_with_cases",
        should_continue_after_understanding,
        {
            "query_rules": "human_review_understanding",
            "generate_output": "generate_output",
        }
    )
    workflow.add_edge("human_review_understanding", "query_rules")
    
    # Phase 2 内部
    workflow.add_edge("query_rules", "apply_rules")
    
    # Phase 2 → 战略层任务域分类 (conditional)
    # 修改: 战略层优先于HTN分解执行，避免战略滞后
    workflow.add_conditional_edges(
        "apply_rules",
        should_continue_after_rules,
        {
            "classify_domains": "classify_domains",
            "generate_output": "generate_output",
        }
    )
    
    # 战略层: 任务域 → 阶段优先级 → HITL审批点2 → HTN分解
    workflow.add_edge("classify_domains", "apply_phase_priority")
    workflow.add_edge("apply_phase_priority", "human_review_strategy")
    
    # HTN分解 → 模块装配 (conditional)
    # HTN分解现在可以利用战略层的domain_priorities输出
    workflow.add_conditional_edges(
        "human_review_strategy",
        should_continue_after_strategy,
        {
            "htn_decompose": "htn_decompose",
            "generate_output": "generate_output",
        }
    )
    workflow.add_edge("htn_decompose", "assemble_modules")
    
    # 模块装配 → Phase 3 (conditional)
    workflow.add_conditional_edges(
        "assemble_modules",
        should_continue_after_strategic_module,
        {
            "match_resources": "match_resources",
            "generate_output": "generate_output",
        }
    )
    
    # Phase 3 内部
    workflow.add_edge("match_resources", "optimize_allocation")
    
    # Phase 3 → 运力检查
    workflow.add_edge("optimize_allocation", "check_transport")
    
    # 运力检查 → Phase 4 (conditional)
    workflow.add_conditional_edges(
        "check_transport",
        should_continue_after_matching,
        {
            "filter_hard_rules": "filter_hard_rules",
            "generate_output": "generate_output",
        }
    )
    
    # Phase 4 内部
    workflow.add_edge("filter_hard_rules", "check_safety_rules")
    workflow.add_edge("check_safety_rules", "score_soft_rules")
    
    # Phase 4 → HITL审批点3 → explain (conditional)
    workflow.add_conditional_edges(
        "score_soft_rules",
        should_explain_scheme,
        {
            "explain_scheme": "human_review_scheme",
            "generate_output": "generate_output",
        }
    )
    workflow.add_edge("human_review_scheme", "explain_scheme")
    
    # explain_scheme → 战略层报告生成 → 仿真闭环 → 输出
    workflow.add_edge("explain_scheme", "generate_reports")
    workflow.add_edge("generate_reports", "run_simulation")
    workflow.add_edge("run_simulation", "generate_output")
    
    # 输出 → END
    workflow.add_edge("generate_output", END)
    
    logger.info("EmergencyAI LangGraph构建完成")
    
    return workflow


# 编译图（懒加载）
_compiled_graph = None
_checkpointer: Optional[BaseCheckpointSaver] = None


def _get_checkpointer() -> Optional[BaseCheckpointSaver]:
    """
    获取状态持久化器
    
    尝试从环境变量LANGGRAPH_CHECKPOINTER_URI获取PostgreSQL连接字符串。
    如果未配置或连接失败，返回None（无持久化，开发阶段可接受）。
    
    生产环境必须配置此环境变量，格式: postgresql://user:pass@host:port/db
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    
    checkpointer_uri = os.environ.get("LANGGRAPH_CHECKPOINTER_URI")
    if not checkpointer_uri:
        logger.warning(
            "【状态持久化】未配置LANGGRAPH_CHECKPOINTER_URI环境变量，"
            "状态不会持久化，服务崩溃时数据将丢失"
        )
        return None
    
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        _checkpointer = PostgresSaver.from_conn_string(checkpointer_uri)
        _checkpointer.setup()
        logger.info("【状态持久化】PostgresSaver初始化成功")
        return _checkpointer
    except ImportError:
        raise RuntimeError(
            "langgraph-checkpoint-postgres未安装，请执行: "
            "pip install langgraph-checkpoint-postgres"
        )
    except Exception as e:
        raise RuntimeError(f"【状态持久化】PostgresSaver初始化失败: {e}") from e


def get_emergency_ai_graph():
    """
    获取编译后的图（单例）
    
    如果配置了LANGGRAPH_CHECKPOINTER_URI环境变量，将启用状态持久化。
    """
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_emergency_ai_graph()
        checkpointer = _get_checkpointer()
        _compiled_graph = workflow.compile(checkpointer=checkpointer)
        if checkpointer:
            logger.info("EmergencyAI图编译完成（启用状态持久化）")
        else:
            logger.info("EmergencyAI图编译完成（无状态持久化）")
    return _compiled_graph
