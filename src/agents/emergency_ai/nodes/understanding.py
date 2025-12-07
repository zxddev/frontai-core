"""
阶段1: 灾情理解节点

使用LLM解析灾情描述，使用RAG检索相似案例。
支持LLM和RAG并行调用以提高性能。
包含LLM输出验证器，检查解析结果的合理性。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Any, Tuple, List, Optional

from langchain_core.messages import HumanMessage, AIMessage

from ..state import EmergencyAIState, ParsedDisasterInfo
from ..tools.llm_tools import parse_disaster_description_async
from ..tools.rag_tools import search_similar_cases_async
from src.planning.algorithms.assessment.disaster_assessment import DisasterAssessment, AlgorithmStatus

logger = logging.getLogger(__name__)


# ============================================================================
# LLM输出验证器
# ============================================================================

class DisasterInfoValidator:
    """
    灾情信息验证器
    
    检查LLM解析结果的合理性，防止幻觉导致的错误数据进入后续流程。
    生成的警告会传递给HITL审批点，由指挥官确认。
    """
    
    # 中国大陆经纬度边界
    CHINA_LAT_MIN: float = 3.86
    CHINA_LAT_MAX: float = 53.55
    CHINA_LNG_MIN: float = 73.66
    CHINA_LNG_MAX: float = 135.05
    
    # 合理的人数上限（单次灾害事件）
    MAX_TRAPPED_PERSONS: int = 100000
    MAX_AFFECTED_POPULATION: int = 10000000
    
    # 震级范围
    MAGNITUDE_MIN: float = 0.0
    MAGNITUDE_MAX: float = 10.0
    
    @classmethod
    def validate(
        cls,
        parsed: ParsedDisasterInfo,
        structured_input: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        验证LLM解析结果的合理性
        
        Args:
            parsed: LLM解析的灾情信息
            structured_input: 原始结构化输入（用于交叉验证）
            
        Returns:
            (is_valid, warnings) - is_valid为False表示有严重问题
        """
        warnings: List[str] = []
        
        # 坐标范围检查
        location = parsed.get("location", {})
        lat = location.get("latitude", 0)
        lng = location.get("longitude", 0)
        
        if lat != 0 or lng != 0:
            if not (cls.CHINA_LAT_MIN <= lat <= cls.CHINA_LAT_MAX):
                warnings.append(f"纬度超出中国范围: {lat}（有效范围{cls.CHINA_LAT_MIN}-{cls.CHINA_LAT_MAX}）")
            if not (cls.CHINA_LNG_MIN <= lng <= cls.CHINA_LNG_MAX):
                warnings.append(f"经度超出中国范围: {lng}（有效范围{cls.CHINA_LNG_MIN}-{cls.CHINA_LNG_MAX}）")
        
        # 被困人数检查
        trapped = parsed.get("estimated_trapped", 0)
        if trapped < 0:
            warnings.append(f"被困人数为负数: {trapped}")
        elif trapped > cls.MAX_TRAPPED_PERSONS:
            warnings.append(f"被困人数异常偏大: {trapped}人（超过{cls.MAX_TRAPPED_PERSONS}）")
        
        # 受影响人口检查
        affected = parsed.get("affected_population", 0)
        if affected < 0:
            warnings.append(f"受影响人口为负数: {affected}")
        elif affected > cls.MAX_AFFECTED_POPULATION:
            warnings.append(f"受影响人口异常偏大: {affected}人")
        
        # 逻辑一致性：有被困人员标记但人数为0
        if parsed.get("has_trapped_persons") and trapped == 0:
            warnings.append("标记存在被困人员但被困人数为0，请确认")
        
        # 震级范围检查（地震专用）
        magnitude = parsed.get("magnitude")
        if magnitude is not None:
            if not (cls.MAGNITUDE_MIN <= magnitude <= cls.MAGNITUDE_MAX):
                warnings.append(f"震级超出合理范围: {magnitude}（有效范围0-10）")
        
        # 灾害类型与次生灾害一致性
        disaster_type = parsed.get("disaster_type", "")
        if disaster_type == "flood" and parsed.get("has_secondary_fire"):
            warnings.append("洪水灾害标记存在次生火灾，请确认是否正确")
        
        # 与原始输入交叉验证
        input_trapped = structured_input.get("estimated_trapped")
        if input_trapped is not None and trapped != 0:
            diff_ratio = abs(trapped - input_trapped) / max(input_trapped, 1)
            if diff_ratio > 0.5:
                warnings.append(
                    f"LLM解析的被困人数({trapped})与输入({input_trapped})差异较大({diff_ratio*100:.0f}%)"
                )
        
        is_valid = len(warnings) == 0
        
        if warnings:
            logger.warning(
                f"[验证器] 灾情信息验证发现{len(warnings)}个警告",
                extra={"warnings": warnings}
            )
        else:
            logger.info("[验证器] 灾情信息验证通过")
        
        return is_valid, warnings


def _assess_with_physics_model(
    parsed_disaster: ParsedDisasterInfo,
    structured_input: Dict[str, Any]
) -> Tuple[ParsedDisasterInfo, List[Dict[str, Any]]]:
    """
    使用物理模型校准灾情评估
    
    利用src/planning中的高精度物理模型（烈度衰减、高斯烟羽等）
    对LLM提取的参数进行二次计算和校准。
    
    Returns:
        (parsed_disaster, data_gap_warnings) - 校准后的灾情信息和数据缺口警告
    """
    data_gap_warnings: List[Dict[str, Any]] = []
    
    try:
        assessor = DisasterAssessment()
        disaster_type = parsed_disaster.get("disaster_type", "unknown")
        
        # 构造评估参数
        params = {}
        
        # 统一位置格式
        location = structured_input.get("location", {"latitude": 0, "longitude": 0})
        if "lat" in location: location["latitude"] = location["lat"]
        if "lng" in location: location["longitude"] = location["lng"]
        
        if disaster_type == "earthquake":
            # 必须有震级数据才能进行物理模型评估
            magnitude = parsed_disaster.get("magnitude") or structured_input.get("magnitude")
            if not magnitude:
                logger.info("[物理模型] 跳过地震评估：缺少震级数据")
                data_gap_warnings.append({
                    "type": "data_gap",
                    "field": "magnitude",
                    "disaster_type": "earthquake",
                    "message": "缺少震级数据，无法评估地震影响范围和伤亡",
                    "suggestion": "请补充震级(级)数据",
                    "affects": ["affected_population", "casualty_estimate", "disaster_level"],
                })
            else:
                params = {
                    "magnitude": float(magnitude),
                    "depth_km": float(parsed_disaster.get("depth_km") or structured_input.get("depth_km", 10.0)),
                    "epicenter": location,
                    "population_density": float(structured_input.get("population_density", 1000)),
                    "building_vulnerability": float(structured_input.get("building_vulnerability", 0.5)),
                }
            
        elif disaster_type == "flood":
            # 必须有用户提供的关键洪水参数才能评估，避免使用默认值生成虚假数据
            has_flood_data = any([
                structured_input.get("rainfall_mm"),
                structured_input.get("affected_area_km2"),
                structured_input.get("water_depth"),
            ])
            if not has_flood_data:
                logger.info("[物理模型] 跳过洪水评估：缺少用户提供的关键参数（降雨量/受灾面积/水深）")
                data_gap_warnings.append({
                    "type": "data_gap",
                    "field": "flood_params",
                    "disaster_type": "flood",
                    "message": "缺少洪水关键参数，无法评估受灾人口和伤亡",
                    "suggestion": "请补充以下任意数据：降雨量(mm)、受灾面积(km²)、水深(m)",
                    "affects": ["affected_population", "casualty_estimate"],
                })
            else:
                params = {
                    "rainfall_mm": float(structured_input.get("rainfall_mm", 100.0)),
                    "duration_hours": float(structured_input.get("duration_hours", 24.0)),
                    "affected_area_km2": float(structured_input.get("affected_area_km2", 10.0)),
                    "population_density": float(structured_input.get("population_density", 3000)),
                }
             
        elif disaster_type == "hazmat":
            # 必须有泄漏速率数据才能进行危化品评估
            leak_rate = structured_input.get("leak_rate")
            if not leak_rate:
                logger.info("[物理模型] 跳过危化品评估：缺少泄漏速率数据")
                data_gap_warnings.append({
                    "type": "data_gap",
                    "field": "leak_rate",
                    "disaster_type": "hazmat",
                    "message": "缺少泄漏速率数据，无法评估危化品扩散范围",
                    "suggestion": "请补充泄漏速率(kg/s)数据",
                    "affects": ["affected_population", "risk_zones"],
                })
            else:
                chemical_type = "unknown"
                if "additional_info" in parsed_disaster:
                    chemical_type = parsed_disaster["additional_info"].get("chemical_type", "unknown")
                params = {
                    "chemical_type": chemical_type,
                    "leak_rate_kg_s": float(leak_rate),
                    "wind_speed_ms": float(structured_input.get("wind_speed", 2.0)),
                    "wind_direction": float(structured_input.get("wind_direction", 0.0)),
                    "source_location": location,
                }
        
        if params:
            logger.info(f"[物理模型] 启动评估: type={disaster_type}, params={params}")
            result = assessor.run({
                "disaster_type": disaster_type,
                "params": params
            })
            
            if result.status == AlgorithmStatus.SUCCESS and result.solution:
                solution = result.solution
                
                # 校准数据 - 保留用户输入的受影响人口，仅补充缺失数据
                # 物理模型的面积和等级更精确，可以覆盖
                parsed_disaster["affected_area_km2"] = solution.affected_area_km2
                parsed_disaster["disaster_level"] = solution.level.value
                
                # 受影响人口：优先使用用户输入/LLM解析值，仅当为空时使用物理模型估算
                user_affected_pop = parsed_disaster.get("affected_population", 0)
                if not user_affected_pop or user_affected_pop <= 0:
                    parsed_disaster["affected_population"] = solution.affected_population
                    logger.info(f"[物理模型] 使用模型估算人口: {solution.affected_population}")
                else:
                    logger.info(f"[物理模型] 保留用户输入人口: {user_affected_pop} (模型估算: {solution.affected_population})")
                
                # 伤亡估算：基于实际受影响人口重新计算（如果用户提供了人口数据）
                if user_affected_pop and user_affected_pop > 0 and solution.estimated_casualties:
                    # 按比例调整伤亡估算
                    ratio = user_affected_pop / max(solution.affected_population, 1)
                    parsed_disaster["estimated_casualties"] = {
                        "deaths": int(solution.estimated_casualties.get("deaths", 0) * ratio),
                        "injuries": int(solution.estimated_casualties.get("injuries", 0) * ratio),
                        "missing": int(solution.estimated_casualties.get("missing", 0) * ratio),
                    }
                else:
                    parsed_disaster["estimated_casualties"] = solution.estimated_casualties
                
                # 标记校准状态
                if "additional_info" not in parsed_disaster:
                    parsed_disaster["additional_info"] = {}
                parsed_disaster["additional_info"]["physics_model_calibrated"] = True
                parsed_disaster["additional_info"]["calibration_source"] = "src.planning.algorithms.assessment"
                
                logger.info(
                    f"[物理模型] 校准成功: "
                    f"面积={solution.affected_area_km2:.2f}km2, "
                    f"人口={parsed_disaster['affected_population']}, "
                    f"等级={solution.level.value}"
                )
            else:
                logger.warning(f"[物理模型] 评估未成功: {result.message}")
        else:
            logger.info(f"[物理模型] 跳过: 不支持的灾害类型或参数缺失 ({disaster_type})")
                
    except Exception as e:
        logger.warning(f"[物理模型] 执行异常: {e}", exc_info=True)
        
    return parsed_disaster, data_gap_warnings


async def _parse_disaster_with_llm(
    description: str,
    structured_input: Dict[str, Any],
) -> Tuple[Optional[ParsedDisasterInfo], Optional[str]]:
    """LLM解析灾情（内部函数，用于并行调用）"""
    try:
        parsed_result = await parse_disaster_description_async(
            description=description,
            context=structured_input,
        )
        
        parsed_disaster: ParsedDisasterInfo = {
            "disaster_type": parsed_result.get("disaster_type", "unknown"),
            "location": structured_input.get("location", {"longitude": 0, "latitude": 0}),
            "severity": parsed_result.get("severity", "medium"),
            "magnitude": parsed_result.get("magnitude"),  # 震级（地震专用）
            "has_building_collapse": parsed_result.get("has_building_collapse", False),
            "has_trapped_persons": parsed_result.get("has_trapped_persons", False),
            "estimated_trapped": parsed_result.get("estimated_trapped", 0),
            "has_secondary_fire": parsed_result.get("has_secondary_fire", False),
            "has_hazmat_leak": parsed_result.get("has_hazmat_leak", False),
            "has_road_damage": parsed_result.get("has_road_damage", False),
            "affected_population": parsed_result.get("affected_population", 0),
            "building_damage_level": parsed_result.get("building_damage_level", "unknown"),
            "additional_info": {
                "key_entities": parsed_result.get("key_entities", []),
                "urgency_factors": parsed_result.get("urgency_factors", []),
            },
        }
        return parsed_disaster, None
    except Exception as e:
        return None, str(e)


async def _search_cases_with_rag(
    description: str,
    disaster_type: str,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """RAG检索相似案例（内部函数，用于并行调用）"""
    try:
        cases = await search_similar_cases_async(
            query=description,
            disaster_type=disaster_type,
            top_k=5,
        )
        return cases, None
    except Exception as e:
        return [], str(e)


async def understand_disaster(state: EmergencyAIState) -> Dict[str, Any]:
    """
    灾情理解节点：使用LLM解析灾情描述
    
    并行执行LLM解析和RAG检索以提高性能。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info(
        "执行灾情理解节点（并行模式）",
        extra={"event_id": state["event_id"], "description_length": len(state["disaster_description"])}
    )
    start_time = time.time()
    
    description = state["disaster_description"]
    structured_input = state.get("structured_input", {})
    
    # 从structured_input获取灾害类型（用于RAG预搜索）
    hint_disaster_type = structured_input.get("disaster_type", "earthquake")
    
    # 并行执行LLM解析和RAG检索
    logger.info("[并行] 同时启动LLM解析和RAG检索...")
    llm_task = _parse_disaster_with_llm(description, structured_input)
    rag_task = _search_cases_with_rag(description, hint_disaster_type)
    
    (parsed_disaster, llm_error), (cases, rag_error) = await asyncio.gather(llm_task, rag_task)
    
    parallel_time = int((time.time() - start_time) * 1000)
    logger.info(f"[并行] LLM和RAG并行完成，耗时{parallel_time}ms")
    
    # LLM失败时抛出异常，与RAG处理保持一致，不允许降级
    if llm_error:
        logger.error(f"[灾情理解] LLM解析失败: {llm_error}")
        raise RuntimeError(f"[灾情理解] LLM解析失败: {llm_error}")
    
    # RAG失败时抛出异常
    if rag_error:
        raise RuntimeError(f"[灾情理解] RAG检索失败: {rag_error}")
    
    # 使用物理模型进行二次校准，同时收集数据缺口警告
    data_gap_warnings: List[Dict[str, Any]] = []
    if parsed_disaster:
        parsed_disaster, data_gap_warnings = _assess_with_physics_model(parsed_disaster, structured_input)
    
    # 验证LLM解析结果的合理性
    validation_warnings: List[str] = []
    if parsed_disaster:
        _, validation_warnings = DisasterInfoValidator.validate(
            parsed=parsed_disaster,
            structured_input=structured_input,
        )
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["understand_disaster"]
    trace["llm_calls"] = trace.get("llm_calls", 0) + 1
    trace["rag_calls"] = trace.get("rag_calls", 0) + 1
    trace["parallel_optimization"] = True
    if parsed_disaster.get("additional_info", {}).get("physics_model_calibrated"):
        trace["physics_model_used"] = True
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "灾情理解完成（并行模式）",
        extra={
            "disaster_type": parsed_disaster["disaster_type"],
            "severity": parsed_disaster["severity"],
            "cases_found": len(cases),
            "elapsed_ms": elapsed_ms,
        }
    )
    
    # 合并已有警告和验证器警告
    existing_warnings = list(state.get("validation_warnings", []))
    all_warnings = existing_warnings + validation_warnings
    
    # 记录数据缺口警告数量
    if data_gap_warnings:
        logger.warning(
            f"[灾情理解] 发现{len(data_gap_warnings)}个数据缺口，指挥员需补充数据",
            extra={"data_gaps": [g["field"] for g in data_gap_warnings]}
        )
    
    return {
        "parsed_disaster": parsed_disaster,
        "similar_cases": cases,  # 直接返回案例，跳过enhance_with_cases
        "current_phase": "understanding",
        "trace": trace,
        "validation_warnings": all_warnings,
        "data_gap_warnings": data_gap_warnings,  # 数据缺口警告（供指挥员补充）
        "messages": [
            HumanMessage(content=f"请分析灾情：{description}"),
            AIMessage(content=f"灾情分析完成：类型={parsed_disaster['disaster_type']}，严重程度={parsed_disaster['severity']}"),
        ],
    }


async def enhance_with_cases(state: EmergencyAIState) -> Dict[str, Any]:
    """
    案例增强节点：使用RAG检索相似历史案例
    
    从向量数据库中检索相似案例，提取经验教训和最佳实践。
    如果 understand_disaster 已并行检索了案例，则直接跳过。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    # 如果已执行过RAG（并行模式），直接生成总结并返回
    # 使用is not None判断，空列表[]表示RAG已执行但无结果，不应重试
    existing_cases = state.get("similar_cases")
    if existing_cases is not None:
        logger.info(f"[跳过] 案例已由并行模式检索，共{len(existing_cases)}个案例")
        parsed_disaster = state.get("parsed_disaster", {})
        disaster_type = parsed_disaster.get("disaster_type", "unknown")
        
        summary_parts = [f"灾害类型: {disaster_type}"]
        if parsed_disaster.get("has_building_collapse"):
            summary_parts.append(f"建筑倒塌，预估被困{parsed_disaster.get('estimated_trapped', 0)}人")
        if existing_cases:
            summary_parts.append(f"找到{len(existing_cases)}个相似历史案例可供参考")
        
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["enhance_with_cases"]
        
        return {
            "understanding_summary": "；".join(summary_parts),
            "trace": trace,
        }
    
    logger.info("执行案例增强节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 获取灾情信息
    parsed_disaster = state.get("parsed_disaster")
    if not parsed_disaster:
        logger.warning("无灾情解析结果，跳过案例检索")
        return {"similar_cases": []}
    
    disaster_type = parsed_disaster.get("disaster_type", "earthquake")
    description = state["disaster_description"]
    
    # 调用RAG检索
    try:
        cases = await search_similar_cases_async(
            query=description,
            disaster_type=disaster_type,
            top_k=5,
        )
        
        # 生成理解总结
        summary_parts = [
            f"灾害类型: {disaster_type}",
            f"严重程度: {parsed_disaster.get('severity', 'unknown')}",
        ]
        
        if parsed_disaster.get("has_building_collapse"):
            summary_parts.append(f"建筑倒塌，预估被困{parsed_disaster.get('estimated_trapped', 0)}人")
        if parsed_disaster.get("has_secondary_fire"):
            summary_parts.append("存在次生火灾")
        if parsed_disaster.get("has_hazmat_leak"):
            summary_parts.append("存在危化品泄漏")
            
        if cases:
            summary_parts.append(f"找到{len(cases)}个相似历史案例可供参考")
        
        understanding_summary = "；".join(summary_parts)
        
        # 更新追踪信息
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["enhance_with_cases"]
        trace["rag_calls"] = trace.get("rag_calls", 0) + 1
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "案例增强完成",
            extra={"cases_found": len(cases), "elapsed_ms": elapsed_ms}
        )
        
        return {
            "similar_cases": cases,
            "understanding_summary": understanding_summary,
            "trace": trace,
        }
        
    except Exception as e:
        # RAG检索失败直接报错，不允许降级
        logger.error("案例检索失败", extra={"error": str(e)})
        raise RuntimeError(f"RAG案例检索失败: {e}") from e
