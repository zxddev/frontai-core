"""
Task Coordinator 节点单元测试

测试各个节点的核心逻辑。
"""
import pytest
from unittest.mock import patch, AsyncMock

from src.agents.task_coordinator.schemas import (
    TaskAllocation,
    TeamInfo,
    TeamRole,
    TeamRoleType,
    SOPTemplate,
    SOPStep,
    StepAssignment,
    CooperationMode,
    CoordinatorWarning,
)
from src.agents.task_coordinator.state import TaskCoordinatorState
from src.agents.task_coordinator.nodes.receive import receive_allocation
from src.agents.task_coordinator.nodes.role_assign import (
    _calculate_capability_match,
    _assign_teams_to_step,
    _determine_cooperation_mode,
)
from src.agents.task_coordinator.nodes.equipment import (
    _match_equipment_for_team,
)
from src.agents.task_coordinator.nodes.instruction import (
    _calculate_total_duration,
)


# ============================================================================
# receive_allocation 节点测试
# ============================================================================

class TestReceiveAllocation:
    """接收任务分配节点测试"""

    def test_receive_valid_allocation(self):
        """测试接收有效的任务分配"""
        task_allocation = TaskAllocation(
            task_id="task-001",
            task_name="地震救援",
            disaster_type="earthquake",
            allocated_teams=[
                TeamInfo(
                    team_id="team-001",
                    team_name="救援一队",
                    capabilities=["RESCUE", "LIFE_DETECTION"],
                )
            ],
        )

        state: TaskCoordinatorState = {
            "event_id": "event-001",
            "task_allocation": task_allocation,
            "warnings": [],
            "errors": [],
        }

        result = receive_allocation(state)

        assert result["current_phase"] == "match_sop"
        assert len(result["errors"]) == 0
        assert "receive_allocation" in result["trace"]["phases_executed"]

    def test_receive_missing_allocation(self):
        """测试缺少任务分配的情况"""
        state: TaskCoordinatorState = {
            "event_id": "event-001",
            "task_allocation": None,
            "warnings": [],
            "errors": [],
        }

        result = receive_allocation(state)

        assert result["current_phase"] == "failed"
        assert "缺少任务分配信息" in result["errors"]

    def test_receive_no_teams_warning(self):
        """测试无队伍时生成警告"""
        task_allocation = TaskAllocation(
            task_id="task-001",
            task_name="救援任务",
            disaster_type="earthquake",
            allocated_teams=[],  # 无队伍
        )

        state: TaskCoordinatorState = {
            "event_id": "event-001",
            "task_allocation": task_allocation,
            "warnings": [],
            "errors": [],
        }

        result = receive_allocation(state)

        assert result["current_phase"] == "match_sop"
        assert any(w.code == "NO_TEAMS" for w in result["warnings"])


# ============================================================================
# role_assign 节点测试
# ============================================================================

class TestCapabilityMatch:
    """能力匹配测试"""

    def test_full_match(self):
        """测试完全匹配"""
        team_caps = ["RESCUE", "LIFE_DETECTION", "MEDICAL"]
        required_caps = ["RESCUE", "LIFE_DETECTION"]

        score = _calculate_capability_match(team_caps, required_caps)

        assert score == 1.0

    def test_partial_match(self):
        """测试部分匹配"""
        team_caps = ["RESCUE"]
        required_caps = ["RESCUE", "LIFE_DETECTION"]

        score = _calculate_capability_match(team_caps, required_caps)

        assert score == 0.5

    def test_no_match(self):
        """测试无匹配"""
        team_caps = ["FIRE_SUPPRESSION"]
        required_caps = ["RESCUE", "LIFE_DETECTION"]

        score = _calculate_capability_match(team_caps, required_caps)

        assert score == 0.0

    def test_empty_requirements(self):
        """测试无要求时返回中等分"""
        team_caps = ["RESCUE"]
        required_caps = []

        score = _calculate_capability_match(team_caps, required_caps)

        assert score == 0.5

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        team_caps = ["rescue", "life_detection"]
        required_caps = ["RESCUE", "LIFE_DETECTION"]

        score = _calculate_capability_match(team_caps, required_caps)

        assert score == 1.0


class TestAssignTeamsToStep:
    """队伍分配测试"""

    def test_assign_single_team(self):
        """测试分配单个队伍 - 所有队伍都参与"""
        step = SOPStep(
            id="step-001",
            name="生命探测",
            sequence=1,
            roles=["主攻"],
            required_capabilities=["LIFE_DETECTION"],
        )

        teams = [
            TeamInfo(
                team_id="team-001",
                team_name="探测队",
                capabilities=["LIFE_DETECTION"],
            ),
        ]

        roles = _assign_teams_to_step(step, teams, set())

        assert len(roles) == 1  # 所有队伍都参与
        assert roles[0].team_id == "team-001"
        assert roles[0].role == TeamRoleType.PRIMARY

    def test_assign_multiple_teams(self):
        """测试分配多个队伍 - 所有队伍都参与，按能力分配角色"""
        step = SOPStep(
            id="step-002",
            name="破拆救援",
            sequence=2,
            roles=["主攻", "配合"],
            required_capabilities=["HEAVY_RESCUE"],
        )

        teams = [
            TeamInfo(
                team_id="team-001",
                team_name="重型救援队",
                capabilities=["HEAVY_RESCUE"],
            ),
            TeamInfo(
                team_id="team-002",
                team_name="支援队",
                capabilities=["SUPPORT"],
            ),
        ]

        roles = _assign_teams_to_step(step, teams, set())

        assert len(roles) == 2  # 所有队伍都参与
        assert roles[0].role == TeamRoleType.PRIMARY  # 能力匹配度高的是主攻
        assert roles[1].role == TeamRoleType.SUPPORT  # 第二个是配合

    def test_all_teams_participate(self):
        """测试所有队伍都参与（新增测试）"""
        step = SOPStep(
            id="step-001",
            name="测试步骤",
            sequence=1,
            roles=["主攻"],
            required_capabilities=["RESCUE"],
        )

        teams = [
            TeamInfo(team_id="team-001", team_name="队伍1", capabilities=["RESCUE"]),
            TeamInfo(team_id="team-002", team_name="队伍2", capabilities=["RESCUE"]),
            TeamInfo(team_id="team-003", team_name="队伍3", capabilities=["SUPPORT"]),
            TeamInfo(team_id="team-004", team_name="队伍4", capabilities=["LOGISTICS"]),
        ]

        roles = _assign_teams_to_step(step, teams, set())

        # 所有4个队伍都应该参与
        assert len(roles) == 4
        # 第1个是主攻，第2-3个是配合，第4个是保障
        assert roles[0].role == TeamRoleType.PRIMARY
        assert roles[1].role == TeamRoleType.SUPPORT
        assert roles[2].role == TeamRoleType.SUPPORT
        assert roles[3].role == TeamRoleType.LOGISTICS


class TestCooperationMode:
    """协作模式测试"""

    def test_single_team_sequential(self):
        """单队伍默认顺序模式"""
        step = SOPStep(id="s1", name="test", sequence=1, parallel_allowed=False)
        mode = _determine_cooperation_mode(step, 1)
        assert mode == CooperationMode.SEQUENTIAL

    def test_multiple_teams_parallel(self):
        """多队伍且允许并行"""
        step = SOPStep(id="s1", name="test", sequence=1, parallel_allowed=True)
        mode = _determine_cooperation_mode(step, 2)
        assert mode == CooperationMode.PARALLEL

    def test_multiple_teams_support(self):
        """多队伍但不允许并行"""
        step = SOPStep(id="s1", name="test", sequence=1, parallel_allowed=False)
        mode = _determine_cooperation_mode(step, 2)
        assert mode == CooperationMode.SUPPORT


# ============================================================================
# equipment 节点测试
# ============================================================================

class TestEquipmentMatch:
    """设备匹配测试"""

    def test_full_match(self):
        """测试完全匹配"""
        required = ["生命探测仪", "蛇眼探测器"]
        team_equipment = ["生命探测仪", "蛇眼探测器", "标记旗"]

        matched = _match_equipment_for_team(required, team_equipment)

        assert len(matched) == 2
        assert "生命探测仪" in matched
        assert "蛇眼探测器" in matched

    def test_partial_match(self):
        """测试部分匹配"""
        required = ["生命探测仪", "蛇眼探测器"]
        team_equipment = ["生命探测仪"]

        matched = _match_equipment_for_team(required, team_equipment)

        assert len(matched) == 1
        assert "生命探测仪" in matched

    def test_no_match(self):
        """测试无匹配"""
        required = ["生命探测仪"]
        team_equipment = ["消防水带"]

        matched = _match_equipment_for_team(required, team_equipment)

        assert len(matched) == 0

    def test_empty_required(self):
        """测试无需求"""
        required = []
        team_equipment = ["生命探测仪"]

        matched = _match_equipment_for_team(required, team_equipment)

        assert len(matched) == 0

    def test_empty_team_equipment(self):
        """测试队伍无设备"""
        required = ["生命探测仪"]
        team_equipment = []

        matched = _match_equipment_for_team(required, team_equipment)

        assert len(matched) == 0


# ============================================================================
# instruction 节点测试
# ============================================================================

class TestDurationCalculation:
    """时长计算测试"""

    def test_sequential_steps(self):
        """测试顺序步骤时长累加"""
        from src.agents.task_coordinator.schemas import StepInstruction

        instructions = [
            StepInstruction(
                step_id="s1", step_name="步骤1", sequence=1,
                teams=[], cooperation_mode="sequential",
                depends_on=[], estimated_duration=30,
            ),
            StepInstruction(
                step_id="s2", step_name="步骤2", sequence=2,
                teams=[], cooperation_mode="sequential",
                depends_on=["s1"], estimated_duration=60,
            ),
        ]

        total = _calculate_total_duration(instructions)

        assert total == 90  # 30 + 60

    def test_parallel_steps_take_max(self):
        """测试并行步骤取最大值"""
        from src.agents.task_coordinator.schemas import StepInstruction

        instructions = [
            StepInstruction(
                step_id="s1", step_name="步骤1", sequence=1,
                teams=[], cooperation_mode="parallel",
                depends_on=[], estimated_duration=30,
            ),
            StepInstruction(
                step_id="s2", step_name="步骤2", sequence=1,  # 同序列号
                teams=[], cooperation_mode="parallel",
                depends_on=[], estimated_duration=60,
            ),
        ]

        total = _calculate_total_duration(instructions)

        assert total == 60  # max(30, 60)

    def test_empty_instructions(self):
        """测试空指令列表"""
        total = _calculate_total_duration([])
        assert total == 0
