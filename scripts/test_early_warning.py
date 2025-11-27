#!/usr/bin/env python3
"""
预警监测智能体测试脚本
"""
import sys
sys.path.insert(0, "/home/dev/gitcode/frontai/frontai-core")

from src.agents.early_warning import get_early_warning_agent


def test_basic_flow():
    """测试基本流程"""
    agent = get_early_warning_agent()
    
    # 模拟灾害数据
    disaster_data = {
        "disaster_type": "fire",
        "disaster_name": "XX路火灾",
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [116.397, 39.908],
                    [116.400, 39.908],
                    [116.400, 39.910],
                    [116.397, 39.910],
                    [116.397, 39.908],
                ]
            ]
        },
        "buffer_distance_m": 3000,
        "severity_level": 3,
        "source": "test",
    }
    
    # 处理灾害更新
    result = agent.process_disaster_update(
        disaster_data=disaster_data,
        scenario_id=None,
    )
    
    print("=" * 50)
    print("预警监测智能体测试结果")
    print("=" * 50)
    print(f"Success: {result['success']}")
    print(f"Warnings Generated: {result['warnings_generated']}")
    print(f"Affected Vehicles: {result['affected_vehicles']}")
    print(f"Affected Teams: {result['affected_teams']}")
    print(f"Notifications Sent: {result['notifications_sent']}")
    print(f"Summary: {result['summary']}")
    print(f"Execution Time: {result.get('execution_time_ms', 0)}ms")
    
    if result.get('errors'):
        print(f"Errors: {result['errors']}")
    
    print("=" * 50)
    print("Trace:")
    for key, value in result.get('trace', {}).items():
        print(f"  {key}: {value}")
    
    return result['success'] or result['warnings_generated'] == 0


def test_warning_level():
    """测试预警级别判断"""
    agent = get_early_warning_agent()
    
    test_cases = [
        (500, "red"),      # <1km
        (1500, "orange"),  # 1-3km
        (4000, "yellow"),  # 3-5km
        (6000, "blue"),    # >5km
    ]
    
    print("\n预警级别测试:")
    all_pass = True
    for distance, expected in test_cases:
        actual = agent.get_warning_level(distance)
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            all_pass = False
        print(f"  {distance}m -> {actual} (expected: {expected}) [{status}]")
    
    return all_pass


if __name__ == "__main__":
    print("Testing EarlyWarningAgent...\n")
    
    test1 = test_basic_flow()
    test2 = test_warning_level()
    
    print("\n" + "=" * 50)
    if test1 and test2:
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)
