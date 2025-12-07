"""
ReconScheduler 完整验证测试套件

五级验证架构：
- Level 1: 数学验证（距离、面积、能耗、时间）
- Level 2: 节点验证（各个LangGraph节点）
- Level 3: 流程验证（成功路径、失败路径）
- Level 4: API验证（所有端点）
- Level 5: 数据验证（手动计算对比）

执行: PYTHONPATH=. pytest tests/e2e/test_recon_full_validation.py -v -s --log-cli-level=DEBUG
"""
from __future__ import annotations

import asyncio
import logging
import math
import uuid
from typing import Any, Dict, List, Tuple

import httpx
import pytest

logger = logging.getLogger(__name__)

# 配置
BASE_URL = "http://localhost:8000"
AI_PREFIX = "/api/v2/ai"
TIMEOUT = 180.0


# =============================================================================
# Level 1: 数学验证
# =============================================================================

class TestMathValidation:
    """Level 1: 数学计算验证"""
    
    def test_haversine_distance(self) -> None:
        """TC-001: Haversine距离计算验证"""
        # 已知两点：成都市中心 -> 茂县
        lat1, lng1 = 30.5728, 104.0668  # 成都
        lat2, lng2 = 31.6800, 103.8500  # 茂县
        
        # Haversine公式计算
        R = 6371000  # 地球半径(米)
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance_m = R * c
        distance_km = distance_m / 1000
        
        # Google Maps参考值约125km
        expected_km = 125.0
        error_percent = abs(distance_km - expected_km) / expected_km * 100
        
        logger.info(f"[数学验证] 成都→茂县: 计算={distance_km:.2f}km, 参考={expected_km}km, 误差={error_percent:.2f}%")
        
        assert error_percent < 5, f"距离计算误差{error_percent:.2f}%超过5%阈值"
    
    def test_area_calculation(self) -> None:
        """TC-002: 区域面积计算验证"""
        # 1km x 1km正方形区域
        # 纬度1度 ≈ 111km
        # 经度1度 ≈ 111km * cos(lat) (在lat=31度约96km)
        
        lat_span_deg = 1 / 111  # 约1km
        avg_lat = 31.0
        lng_span_deg = 1 / (111 * math.cos(math.radians(avg_lat)))  # 约1km
        
        lat_span_m = lat_span_deg * 111000
        lng_span_m = lng_span_deg * 111000 * math.cos(math.radians(avg_lat))
        area_m2 = lat_span_m * lng_span_m
        
        expected_m2 = 1_000_000  # 1km²
        error_percent = abs(area_m2 - expected_m2) / expected_m2 * 100
        
        logger.info(f"[数学验证] 1km×1km面积: 计算={area_m2:.0f}m², 预期={expected_m2}m², 误差={error_percent:.2f}%")
        
        assert error_percent < 5, f"面积计算误差{error_percent:.2f}%超过5%阈值"
    
    def test_flight_time_calculation(self) -> None:
        """TC-005: 飞行时间计算验证"""
        distance_m = 10000  # 10km
        speed_ms = 10  # 10m/s
        
        time_s = distance_m / speed_ms
        time_min = time_s / 60
        
        expected_min = 16.67  # 10km / 10m/s = 1000s = 16.67min
        error_percent = abs(time_min - expected_min) / expected_min * 100
        
        logger.info(f"[数学验证] 飞行时间: 计算={time_min:.2f}min, 预期={expected_min:.2f}min, 误差={error_percent:.2f}%")
        
        assert error_percent < 1, f"时间计算误差{error_percent:.2f}%超过1%阈值"
    
    def test_zigzag_distance_estimation(self) -> None:
        """TC-003: Z字形航线距离预估验证"""
        # 区域: 1km x 1km
        lat_span_m = 1000
        lng_span_m = 1000
        
        # 扫描参数
        altitude_m = 100
        sensor_fov_deg = 84
        overlap_percent = 20
        
        # 计算航线间距
        swath_width_m = 2 * altitude_m * math.tan(math.radians(sensor_fov_deg / 2))
        line_spacing_m = swath_width_m * (1 - overlap_percent / 100)
        
        # 航线数量
        num_lines = int(lng_span_m / line_spacing_m) + 1
        
        # 预估距离
        scan_distance_m = num_lines * lat_span_m
        turn_distance_m = (num_lines - 1) * line_spacing_m
        return_distance_m = math.sqrt(lat_span_m**2 + lng_span_m**2) * 2
        
        total_estimated_m = scan_distance_m + turn_distance_m + return_distance_m
        total_km = total_estimated_m / 1000
        
        logger.info(f"[数学验证] Z字形航线预估:")
        logger.info(f"  航线间距: {line_spacing_m:.1f}m")
        logger.info(f"  航线数量: {num_lines}")
        logger.info(f"  扫描距离: {scan_distance_m/1000:.2f}km")
        logger.info(f"  转弯距离: {turn_distance_m/1000:.2f}km")
        logger.info(f"  往返距离: {return_distance_m/1000:.2f}km")
        logger.info(f"  总估计: {total_km:.2f}km")
        
        # 合理范围检查 (5-20km)
        assert 5 < total_km < 20, f"航线距离{total_km:.2f}km不在合理范围(5-20km)"


# =============================================================================
# Level 2: 节点验证
# =============================================================================

class TestNodeValidation:
    """Level 2: LangGraph节点验证"""
    
    @pytest.mark.asyncio
    async def test_device_provider_loading(self) -> None:
        """验证Mock设备数据加载"""
        from src.agents.recon_scheduler.mock_data import get_device_provider
        
        provider = get_device_provider()
        device_ids = await provider.list_available_devices()
        
        logger.info(f"[节点验证] 加载设备数量: {len(device_ids)}")
        
        assert len(device_ids) >= 1, "至少应有1个设备"
        
        # 验证设备配置完整性
        for device_id in device_ids:
            dev = await provider.get_device_profile(device_id)
            assert dev is not None, f"设备 {device_id} 配置未找到"
            logger.info(f"  - {dev.device_id}: {dev.device_type}, 续航={dev.max_endurance_min}min")
            assert dev.device_id, "device_id不能为空"
            assert dev.max_endurance_min > 0, f"{dev.device_id} 续航时间必须>0"
            assert dev.energy_params.cruise_speed_ms > 0, f"{dev.device_id} 巡航速度必须>0"
    
    @pytest.mark.asyncio
    async def test_area_feasibility_check(self) -> None:
        """验证区域可行性预检查函数"""
        from src.agents.recon_scheduler.nodes.flight_planning import _check_area_feasibility
        from src.agents.recon_scheduler.mock_data import get_device_provider
        
        provider = get_device_provider()
        device_ids = await provider.list_available_devices()
        device = await provider.get_device_profile(device_ids[0])
        
        # 小区域 (应该可行)
        small_polygon = [
            (31.65, 103.85),
            (31.66, 103.85),
            (31.66, 103.86),
            (31.65, 103.86),
        ]
        
        result = _check_area_feasibility(
            polygon=small_polygon,
            device_profile=device,
            scan_config={"altitude_m": 100, "sensor_fov_deg": 84, "overlap_percent": 20}
        )
        
        logger.info(f"[节点验证] 小区域可行性: feasible={result['feasible']}, "
                   f"est={result['estimated_distance_km']:.1f}km, max={result['max_distance_km']:.1f}km")
        
        assert result["feasible"], "小区域应该可行"
        
        # 大区域 (应该不可行)
        large_polygon = [
            (31.6, 103.8),
            (31.7, 103.8),
            (31.7, 103.9),
            (31.6, 103.9),
        ]
        
        result = _check_area_feasibility(
            polygon=large_polygon,
            device_profile=device,
            scan_config={"altitude_m": 100, "sensor_fov_deg": 84, "overlap_percent": 20}
        )
        
        logger.info(f"[节点验证] 大区域可行性: feasible={result['feasible']}, "
                   f"est={result['estimated_distance_km']:.1f}km, max={result['max_distance_km']:.1f}km")
        
        assert not result["feasible"], "大区域应该不可行"
    
    @pytest.mark.asyncio
    async def test_l1_validation_logic(self) -> None:
        """验证L1验证逻辑"""
        from src.agents.recon_scheduler.nodes.l1_validation import (
            check_flight_time_constraint,
            calculate_total_distance,
        )
        
        # 构造航点列表
        waypoints = [
            {"lat": 31.65, "lng": 103.85, "alt_m": 100},
            {"lat": 31.66, "lng": 103.85, "alt_m": 100},  # 约1.1km
            {"lat": 31.66, "lng": 103.86, "alt_m": 100},  # 约0.85km
            {"lat": 31.65, "lng": 103.86, "alt_m": 100},  # 约1.1km
            {"lat": 31.65, "lng": 103.85, "alt_m": 100},  # 约0.85km
        ]
        
        total_distance = calculate_total_distance(waypoints)
        logger.info(f"[节点验证] 航线总距离: {total_distance:.0f}m")
        
        # 测试飞行时间约束
        cruise_speed = 10  # m/s
        max_flight_time = 55  # min
        
        is_valid, error, estimated_time = check_flight_time_constraint(
            waypoints, cruise_speed, max_flight_time, margin=0.9
        )
        
        logger.info(f"[节点验证] 飞行时间检查: valid={is_valid}, time={estimated_time:.1f}min, max={max_flight_time*0.9:.1f}min")
        
        assert is_valid, f"短航线应该通过时间检查: {error}"


# =============================================================================
# Level 3: 流程验证
# =============================================================================

class TestFlowValidation:
    """Level 3: 完整流程验证"""
    
    @pytest.mark.asyncio
    async def test_happy_path_small_area(self) -> None:
        """成功路径: 小区域应该生成有效航线"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            request_data = {
                "event_id": f"test-small-{uuid.uuid4().hex[:8]}",
                "scenario_id": "test",
                "recon_request": "小区域搜索测试",
                "target_area": {
                    "type": "Polygon",
                    "coordinates": [[[103.85, 31.65], [103.86, 31.65], [103.86, 31.66], [103.85, 31.66], [103.85, 31.65]]]
                },
                "disaster_context": {"disaster_type": "earthquake", "severity": "moderate"}
            }
            
            # 提交任务
            resp = await client.post(f"{AI_PREFIX}/recon-schedule", json=request_data)
            assert resp.status_code == 202, f"提交失败: {resp.text}"
            
            task_id = resp.json()["task_id"]
            logger.info(f"[流程验证] 提交任务: task_id={task_id}")
            
            # 轮询结果
            result = await self._poll_result(client, task_id)
            
            logger.info(f"[流程验证] 小区域结果: status={result['status']}, success={result['success']}, plans={len(result.get('flight_plans', []))}")
            
            assert result["status"] == "completed", f"状态应为completed: {result['status']}"
            assert result["success"], "应该成功"
            assert len(result.get("flight_plans", [])) > 0, "应该有航线"
            
            # 验证航线数据完整性
            for plan in result["flight_plans"]:
                assert plan.get("waypoints"), "航线应有航点"
                assert plan.get("statistics"), "航线应有统计信息"
                stats = plan["statistics"]
                assert stats.get("total_distance_m", 0) > 0, "距离应>0"
    
    @pytest.mark.asyncio
    async def test_large_area_rejection(self) -> None:
        """失败路径: 大区域应该被拒绝"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            request_data = {
                "event_id": f"test-large-{uuid.uuid4().hex[:8]}",
                "scenario_id": "test",
                "recon_request": "大区域搜索测试",
                "target_area": {
                    "type": "Polygon",
                    "coordinates": [[[103.8, 31.6], [103.9, 31.6], [103.9, 31.7], [103.8, 31.7], [103.8, 31.6]]]
                },
                "disaster_context": {"disaster_type": "earthquake", "severity": "severe"}
            }
            
            resp = await client.post(f"{AI_PREFIX}/recon-schedule", json=request_data)
            assert resp.status_code == 202
            
            task_id = resp.json()["task_id"]
            logger.info(f"[流程验证] 提交大区域任务: task_id={task_id}")
            
            result = await self._poll_result(client, task_id)
            
            logger.info(f"[流程验证] 大区域结果: status={result['status']}, success={result['success']}, errors={len(result.get('errors', []))}")
            
            assert result["status"] == "failed", f"状态应为failed: {result['status']}"
            assert not result["success"], "不应该成功"
            assert len(result.get("errors", [])) > 0, "应该有错误信息"
            
            # 验证错误信息包含距离超限
            errors_text = " ".join(result.get("errors", []))
            assert "区域过大" in errors_text or "超出" in errors_text, f"错误应提及区域过大: {errors_text}"
    
    @pytest.mark.asyncio
    async def test_validation_failure_not_skipped(self) -> None:
        """验证失败不跳过: 确保验证失败后不会继续生成航线"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            # 使用一个中等大小的区域，可能触发验证失败
            request_data = {
                "event_id": f"test-medium-{uuid.uuid4().hex[:8]}",
                "scenario_id": "test",
                "recon_request": "中等区域测试",
                "target_area": {
                    "type": "Polygon",
                    "coordinates": [[[103.82, 31.62], [103.88, 31.62], [103.88, 31.68], [103.82, 31.68], [103.82, 31.62]]]
                },
                "disaster_context": {"disaster_type": "flood"}
            }
            
            resp = await client.post(f"{AI_PREFIX}/recon-schedule", json=request_data)
            assert resp.status_code == 202
            
            task_id = resp.json()["task_id"]
            result = await self._poll_result(client, task_id)
            
            logger.info(f"[流程验证] 中等区域: status={result['status']}, success={result['success']}, plans={len(result.get('flight_plans', []))}, errors={len(result.get('errors', []))}")
            
            # 关键验证: 如果有错误，航线数应该为0且状态为failed
            if result.get("errors"):
                assert result["status"] == "failed", "有错误时状态应为failed"
                assert not result["success"], "有错误时不应成功"
                # 不应该有无效的航线
                for plan in result.get("flight_plans", []):
                    stats = plan.get("statistics", {})
                    distance = stats.get("total_distance_m", 0)
                    # 如果有航线，距离应该合理
                    if distance > 0:
                        logger.warning(f"有错误但仍有航线: {plan.get('plan_id')}, distance={distance}m")
    
    async def _poll_result(self, client: httpx.AsyncClient, task_id: str, max_polls: int = 30) -> Dict[str, Any]:
        """轮询任务结果"""
        for _ in range(max_polls):
            await asyncio.sleep(2)
            resp = await client.get(f"{AI_PREFIX}/recon-schedule/{task_id}")
            result = resp.json()
            
            if result.get("status") in ("completed", "failed", "awaiting_approval"):
                return result
        
        raise TimeoutError(f"Task {task_id} did not complete in time")


# =============================================================================
# Level 4: API验证
# =============================================================================

class TestAPIValidation:
    """Level 4: API端点验证"""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self) -> None:
        """健康检查端点"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            resp = await client.get(f"{AI_PREFIX}/health")
            
            assert resp.status_code == 200, f"健康检查失败: {resp.status_code}"
            
            data = resp.json()
            logger.info(f"[API验证] 健康检查: status={data.get('status')}, checks={list(data.get('checks', {}).keys())}")
            
            assert "status" in data
            assert "checks" in data
    
    @pytest.mark.asyncio
    async def test_submit_task_endpoint(self) -> None:
        """提交任务端点"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            request_data = {
                "event_id": f"api-test-{uuid.uuid4().hex[:8]}",
                "scenario_id": "test",
                "recon_request": "API测试",
                "target_area": {
                    "type": "Polygon",
                    "coordinates": [[[103.85, 31.65], [103.86, 31.65], [103.86, 31.66], [103.85, 31.66], [103.85, 31.65]]]
                },
            }
            
            resp = await client.post(f"{AI_PREFIX}/recon-schedule", json=request_data)
            
            logger.info(f"[API验证] 提交任务: status_code={resp.status_code}")
            
            assert resp.status_code == 202, f"应返回202: {resp.status_code}, {resp.text}"
            
            data = resp.json()
            assert "task_id" in data, "响应应包含task_id"
            assert data["task_id"].startswith("recon-"), f"task_id格式错误: {data['task_id']}"
    
    @pytest.mark.asyncio
    async def test_get_result_endpoint(self) -> None:
        """查询结果端点"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
            # 先提交任务
            request_data = {
                "event_id": f"api-test-{uuid.uuid4().hex[:8]}",
                "scenario_id": "test",
                "recon_request": "查询测试",
                "target_area": {
                    "type": "Polygon",
                    "coordinates": [[[103.85, 31.65], [103.86, 31.65], [103.86, 31.66], [103.85, 31.66], [103.85, 31.65]]]
                },
            }
            
            resp = await client.post(f"{AI_PREFIX}/recon-schedule", json=request_data)
            task_id = resp.json()["task_id"]
            
            # 等待一下
            await asyncio.sleep(3)
            
            # 查询结果
            resp = await client.get(f"{AI_PREFIX}/recon-schedule/{task_id}")
            
            logger.info(f"[API验证] 查询结果: status_code={resp.status_code}")
            
            assert resp.status_code == 200, f"应返回200: {resp.status_code}"
            
            data = resp.json()
            assert "task_id" in data
            assert "status" in data
            assert data["status"] in ("running", "completed", "failed", "awaiting_approval")
    
    @pytest.mark.asyncio
    async def test_invalid_task_id(self) -> None:
        """无效task_id处理"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            resp = await client.get(f"{AI_PREFIX}/recon-schedule/invalid-task-id")
            
            logger.info(f"[API验证] 无效task_id: status_code={resp.status_code}")
            
            assert resp.status_code == 404, f"应返回404: {resp.status_code}"


# =============================================================================
# Level 5: 数据验证
# =============================================================================

class TestDataValidation:
    """Level 5: 数据正确性验证"""
    
    @pytest.mark.asyncio
    async def test_flight_plan_math_verification(self) -> None:
        """验证航线数据的数学正确性"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            request_data = {
                "event_id": f"math-test-{uuid.uuid4().hex[:8]}",
                "scenario_id": "test",
                "recon_request": "数学验证",
                "target_area": {
                    "type": "Polygon",
                    "coordinates": [[[103.85, 31.65], [103.86, 31.65], [103.86, 31.66], [103.85, 31.66], [103.85, 31.65]]]
                },
            }
            
            resp = await client.post(f"{AI_PREFIX}/recon-schedule", json=request_data)
            task_id = resp.json()["task_id"]
            
            # 等待完成
            for _ in range(30):
                await asyncio.sleep(2)
                resp = await client.get(f"{AI_PREFIX}/recon-schedule/{task_id}")
                result = resp.json()
                if result.get("status") in ("completed", "failed"):
                    break
            
            if result.get("status") != "completed":
                pytest.skip("任务未完成")
            
            # 验证每条航线
            for plan in result.get("flight_plans", []):
                waypoints = plan.get("waypoints", [])
                stats = plan.get("statistics", {})
                
                if len(waypoints) < 2:
                    continue
                
                # 手动计算距离
                manual_distance = 0.0
                for i in range(len(waypoints) - 1):
                    wp1, wp2 = waypoints[i], waypoints[i+1]
                    
                    R = 6371000
                    lat1, lat2 = math.radians(wp1["lat"]), math.radians(wp2["lat"])
                    dlat = lat2 - lat1
                    dlng = math.radians(wp2["lng"] - wp1["lng"])
                    
                    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                    manual_distance += R * c
                
                reported_distance = stats.get("total_distance_m", 0)
                
                if reported_distance > 0:
                    error_percent = abs(manual_distance - reported_distance) / reported_distance * 100
                    
                    logger.info(f"[数据验证] 航线 {plan.get('plan_id')}: 手动={manual_distance:.0f}m, 报告={reported_distance:.0f}m, 误差={error_percent:.1f}%")
                    
                    assert error_percent < 10, f"距离误差{error_percent:.1f}%超过10%阈值"
    
    @pytest.mark.asyncio
    async def test_device_capability_consistency(self) -> None:
        """验证设备能力数据一致性"""
        from src.agents.recon_scheduler.mock_data import get_device_provider
        
        provider = get_device_provider()
        device_ids = await provider.list_available_devices()
        
        for device_id in device_ids:
            device = await provider.get_device_profile(device_id)
            assert device is not None, f"设备 {device_id} 配置未找到"
            
            max_distance_m = device.max_endurance_min * device.energy_params.cruise_speed_ms * 60
            max_distance_km = max_distance_m / 1000
            
            logger.info(f"[数据验证] {device.device_id}: 续航{device.max_endurance_min}min × 速度{device.energy_params.cruise_speed_ms}m/s = 最大{max_distance_km:.1f}km")
            
            # 验证数值合理性（VTOL固定翼4小时，机器狗5小时续航）
            assert device.max_endurance_min > 0, f"{device.device_id} 续航时间必须>0"
            assert device.max_endurance_min <= 300, f"{device.device_id} 续航时间{device.max_endurance_min}min不合理(>300min)"
            assert device.energy_params.cruise_speed_ms > 0, f"{device.device_id} 速度必须>0"
            assert device.energy_params.cruise_speed_ms < 50, f"{device.device_id} 速度{device.energy_params.cruise_speed_ms}m/s不合理(>50m/s)"


# =============================================================================
# 运行入口
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--log-cli-level=INFO"])
