#!/usr/bin/env python3
"""
应急分析测试脚本 - 查看完整方案

使用方法:
    python scripts/test_emergency_analyze.py

    # 自定义灾情描述
    python scripts/test_emergency_analyze.py --description "成都市发生5.0级地震，10人被困"

    # 自定义位置
    python scripts/test_emergency_analyze.py --lat 30.67 --lng 104.06
"""
import asyncio
import argparse
import json
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.WARNING)


async def run_analysis(description: str, lat: float, lng: float, output_json: bool = False):
    """运行应急分析"""
    from src.agents.emergency_ai.agent import EmergencyAIAgent
    
    agent = EmergencyAIAgent()
    
    result = await agent.analyze(
        event_id=f'EVENT-TEST-{int(asyncio.get_event_loop().time())}',
        scenario_id='SCENARIO-EARTHQUAKE-001',
        disaster_description=description,
        structured_input={
            'location': {'latitude': lat, 'longitude': lng},
            'urgency_level': 'critical',
        },
    )
    
    return result


def print_result(result: dict, output_json: bool = False):
    """打印结果"""
    if output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    
    print("=" * 80)
    print("应急救援方案分析结果")
    print("=" * 80)
    
    if not result.get('success'):
        print(f"\n❌ 分析失败")
        print(f"错误: {result.get('errors')}")
        return
    
    print(f"\n✅ 分析成功")
    print(f"执行时间: {result.get('execution_time_ms', 0)}ms")
    
    # HTN分解
    htn = result.get('htn_decomposition', {})
    print(f"\n【HTN任务分解】")
    print(f"  场景: {htn.get('scene_codes', [])}")
    print(f"  任务数: {len(htn.get('task_sequence', []))}")
    print(f"  并行组: {len(htn.get('parallel_tasks', []))}")
    
    # 任务序列
    task_seq = htn.get('task_sequence', [])
    if task_seq:
        print(f"\n【任务执行序列】")
        for t in task_seq:
            deps = t.get('depends_on', [])
            deps_str = f" (依赖: {deps})" if deps else ""
            print(f"  {t.get('sequence', 0):2d}. [{t.get('task_id')}] {t.get('task_name')}{deps_str}")
    
    # 资源分配
    matching = result.get('matching', {})
    print(f"\n【资源匹配】")
    print(f"  候选资源: {matching.get('candidates_count', 0)}")
    print(f"  生成方案: {matching.get('solutions_count', 0)}")
    print(f"  Pareto解: {matching.get('pareto_solutions_count', 0)}")
    
    # 候选资源详情
    candidates = matching.get('candidates_detail', [])
    if candidates:
        print(f"\n【候选资源详情】")
        for c in candidates[:10]:
            print(f"  - {c.get('resource_name')}")
            print(f"    类型: {c.get('resource_type')}, 距离: {c.get('distance_km')}km, ETA: {c.get('eta_minutes')}分钟")
            print(f"    能力: {c.get('capabilities')}")
    
    # 5维评估
    opt = result.get('optimization', {})
    scores = opt.get('scheme_scores', [])
    if scores:
        s = scores[0]
        dims = s.get('dimension_scores', {})
        print(f"\n【5维评估】")
        print(f"  综合得分: {s.get('total_score', 0):.3f}")
        print(f"  成功率:   {dims.get('success_rate', 0):.3f}")
        print(f"  响应时间: {dims.get('response_time', 0):.3f}")
        print(f"  覆盖率:   {dims.get('coverage_rate', 0):.3f}")
        print(f"  风险:     {dims.get('risk', 0):.3f}")
        print(f"  冗余性:   {dims.get('redundancy', 0):.3f}")
    
    # 推荐方案
    rec = result.get('recommended_scheme')
    if rec:
        print(f"\n【推荐方案】")
        print(f"  方案ID: {rec.get('solution_id')}")
        print(f"  队伍数: {len(rec.get('allocations', []))}")
        print(f"  响应时间: {rec.get('response_time_min', 0):.0f}分钟")
        print(f"  覆盖率: {rec.get('coverage_rate', 0)*100:.0f}%")
        
        print(f"\n  资源分配:")
        for alloc in rec.get('allocations', []):
            print(f"    - {alloc.get('resource_name')}")
            print(f"      能力: {alloc.get('assigned_capabilities')}")
            print(f"      距离: {alloc.get('distance_km', 0):.1f}km, ETA: {alloc.get('eta_minutes', 0):.0f}分钟")
    
    # 方案解释
    explanation = result.get('scheme_explanation', '')
    if explanation:
        print(f"\n{'=' * 80}")
        print("【详细方案解释】")
        print("=" * 80)
        print(explanation)
    
    print(f"\n{'=' * 80}")


def main():
    parser = argparse.ArgumentParser(description='应急分析测试脚本')
    parser.add_argument('--description', '-d', type=str, 
                        default='四川省阿坝州茂县发生6.5级地震，震中位于茂县凤仪镇，震源深度20公里。已知多处房屋倒塌，道路阻断，估计被困群众约200人，受影响人口约15000人。需要紧急救援、医疗救助、物资供应和临时安置。',
                        help='灾情描述')
    parser.add_argument('--lat', type=float, default=31.68, help='纬度')
    parser.add_argument('--lng', type=float, default=103.85, help='经度')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    
    args = parser.parse_args()
    
    print(f"正在分析灾情...")
    print(f"位置: ({args.lat}, {args.lng})")
    print(f"描述: {args.description[:50]}...")
    print()
    
    result = asyncio.run(run_analysis(args.description, args.lat, args.lng))
    print_result(result, args.json)


if __name__ == '__main__':
    main()
