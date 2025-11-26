"""
算法基类与通用接口定义
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class AlgorithmStatus(Enum):
    """算法执行状态"""
    SUCCESS = "success"
    PARTIAL = "partial"  # 部分成功
    INFEASIBLE = "infeasible"  # 无可行解
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class AlgorithmResult:
    """算法执行结果"""
    status: AlgorithmStatus
    solution: Any
    metrics: Dict[str, float]
    trace: Dict[str, Any]  # 追溯信息
    time_ms: float
    message: str = ""


class AlgorithmBase(ABC):
    """
    算法基类
    
    所有算法必须实现:
    1. solve() - 求解方法
    2. validate_input() - 输入验证
    3. get_default_params() - 默认参数
    """
    
    def __init__(self, params: Dict[str, Any] = None):
        self.params = {**self.get_default_params(), **(params or {})}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """
        求解问题
        
        Args:
            problem: 问题定义字典
            
        Returns:
            AlgorithmResult 包含解、指标、追溯信息
        """
        pass
    
    @abstractmethod
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证输入合法性
        
        Returns:
            (是否合法, 错误信息)
        """
        pass
    
    @abstractmethod
    def get_default_params(self) -> Dict[str, Any]:
        """获取默认参数"""
        pass
    
    def run(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """
        执行算法(带计时和异常处理)
        """
        # 1. 验证输入
        valid, msg = self.validate_input(problem)
        if not valid:
            return AlgorithmResult(
                status=AlgorithmStatus.ERROR,
                solution=None,
                metrics={},
                trace={"error": msg},
                time_ms=0,
                message=msg
            )
        
        # 2. 执行求解
        start_time = time.time()
        try:
            result = self.solve(problem)
            result.time_ms = (time.time() - start_time) * 1000
            return result
        except Exception as e:
            self.logger.exception(f"算法执行异常: {e}")
            return AlgorithmResult(
                status=AlgorithmStatus.ERROR,
                solution=None,
                metrics={},
                trace={"exception": str(e)},
                time_ms=(time.time() - start_time) * 1000,
                message=str(e)
            )


# ============ 通用数据结构 ============

@dataclass
class Location:
    """位置坐标"""
    lat: float
    lng: float
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.lat, self.lng)
    
    @classmethod
    def from_dict(cls, d: Dict) -> "Location":
        return cls(lat=d.get("lat", 0), lng=d.get("lng", 0))


@dataclass  
class TimeWindow:
    """时间窗"""
    start: int  # 分钟
    end: int    # 分钟
    
    def contains(self, t: int) -> bool:
        return self.start <= t <= self.end


@dataclass
class Resource:
    """资源/力量"""
    id: str
    name: str
    type: str
    category: str
    capabilities: List[str]
    location: Location
    status: str
    capacity: Dict[str, Any]
    constraints: Dict[str, Any]
    properties: Dict[str, Any]


@dataclass
class Task:
    """任务"""
    id: str
    name: str
    category: str
    required_capabilities: List[str]
    location: Optional[Location]
    duration_min: int
    duration_max: int
    priority: int
    time_window: Optional[TimeWindow] = None


@dataclass
class DisasterProfile:
    """灾情画像"""
    type: str  # earthquake/fire/hazmat/flood/landslide
    level: str  # I/II/III/IV
    location: Location
    magnitude: Optional[float] = None  # 震级
    affected_area_km2: Optional[float] = None
    estimated_casualties: Optional[int] = None
    features: Dict[str, Any] = None


# ============ 通用工具函数 ============

def haversine_distance(loc1: Location, loc2: Location) -> float:
    """
    计算两点间的球面距离(km)
    
    使用Haversine公式
    """
    import math
    
    R = 6371  # 地球半径(km)
    
    lat1, lon1 = math.radians(loc1.lat), math.radians(loc1.lng)
    lat2, lon2 = math.radians(loc2.lat), math.radians(loc2.lng)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def estimate_travel_time(distance_km: float, speed_kmh: float = 40) -> int:
    """估算行驶时间(分钟)"""
    if speed_kmh <= 0:
        return 9999
    return int(distance_km / speed_kmh * 60)
