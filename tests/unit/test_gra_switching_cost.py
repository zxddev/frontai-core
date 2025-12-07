import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import math

from src.planning.algorithms.arbitration.conflict_resolver import (
    ConflictResolver,
    ResourceState,
    ResourceClaim,
)


def test_switching_cost_calculation_with_deploy_distance():
    resolver = ConflictResolver()
    resource = ResourceState(
        resource_id="RES-1",
        current_position=(0.0, 0.0),
        home_position=(0.0, 1.0),
        remaining_capacity=50.0,  # 50%
        max_range=100.0,  # km
        current_task_progress=0.0,
    )

    # 距离约 111km (每度纬度约111km)，返航+部署=222km，剩余航程=50km
    cost = resolver.calc_switching_cost(resource, (0.0, 2.0))

    assert math.isclose(cost, 1.0)  # 超出剩余航程，封顶为1.0


def test_gra_can_preempt_respects_threshold_and_positions():
    resolver = ConflictResolver()
    resource = ResourceState(
        resource_id="RES-2",
        current_position=(0.0, 0.0),
        home_position=(0.0, 0.0),
        remaining_capacity=100.0,
        max_range=200.0,
        current_task_progress=0.0,
    )

    new_task = ResourceClaim(
        task_id="NEW",
        task_name="life_rescue",
        resource_id="RES-2",
        quantity=1,
        start_time=0,
        end_time=10,
        priority=1,
        is_preemptible=True,
        task_type="life_rescue_confirmed",
        start_position=(0.0, 1.0),
    )
    current_task = ResourceClaim(
        task_id="CUR",
        task_name="recon",
        resource_id="RES-2",
        quantity=1,
        start_time=0,
        end_time=10,
        priority=2,
        is_preemptible=True,
        task_type="suspect_point_recon",
        start_position=(0.0, 0.0),
    )

    can_preempt, reason, cost = resolver.gra_can_preempt(
        new_task=new_task,
        current_task=current_task,
        resource=resource,
        new_task_position=new_task.start_position,
    )

    assert can_preempt is True
    assert "抢占" in reason
    assert 0.0 <= cost <= 1.0
