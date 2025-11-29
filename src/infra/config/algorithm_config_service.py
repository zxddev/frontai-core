"""
算法参数配置服务

核心设计原则：
1. 无Fallback：配置缺失时必须抛出 ConfigurationMissingError，绝不静默降级
2. 优先级查找：部门定制 > 地区定制 > 全国通用
3. 缓存加速：使用Redis缓存减少数据库查询
4. 类型安全：返回JSONB解析后的dict，调用方负责验证结构

使用示例：
```python
service = AlgorithmConfigService(db_session, redis_client)

# 获取单个配置（缺失则报错）
params = await service.get_or_raise("sphere", "SPHERE-WASH-001")

# 获取某类别全部配置
all_sphere = await service.get_all_by_category("sphere")

# 带地区/部门定制
params = await service.get_or_raise(
    "routing", "ROAD-SPEED-MOTORWAY",
    region_code="510000",  # 四川省
    department_code="FIRE"  # 消防
)
```
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ConfigurationMissingError(Exception):
    """
    配置缺失错误
    
    当请求的算法参数在数据库中不存在时抛出。
    这是一个严重错误，表明系统配置不完整，必须修复后才能运行。
    
    绝对不允许通过Fallback绕过此错误。
    """
    
    def __init__(self, category: str, code: str, region_code: Optional[str] = None, 
                 department_code: Optional[str] = None):
        self.category = category
        self.code = code
        self.region_code = region_code
        self.department_code = department_code
        
        scope_info = []
        if region_code:
            scope_info.append(f"region={region_code}")
        if department_code:
            scope_info.append(f"department={department_code}")
        scope_str = f" ({', '.join(scope_info)})" if scope_info else ""
        
        message = (
            f"缺少必需配置: category='{category}', code='{code}'{scope_str}. "
            f"请在 config.algorithm_parameters 表中添加该配置，"
            f"或执行相应的迁移脚本 sql/v19_algorithm_parameters_*.sql"
        )
        super().__init__(message)


class AlgorithmConfigService:
    """
    算法参数配置服务 - 无Fallback设计
    
    从 config.algorithm_parameters 表加载算法参数，支持：
    - 地区/部门定制化（优先级查找）
    - Redis缓存（可选）
    - 批量加载
    
    Attributes:
        _db: 数据库会话
        _cache: Redis客户端（可选，为None则不缓存）
        _cache_ttl: 缓存过期时间（秒）
    """
    
    # 缓存键前缀
    CACHE_PREFIX = "algo_param"
    
    # 默认缓存过期时间（5分钟）
    DEFAULT_CACHE_TTL = 300
    
    def __init__(
        self, 
        db: AsyncSession, 
        cache: Optional[Redis] = None,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        self._db = db
        self._cache = cache
        self._cache_ttl = cache_ttl
    
    async def get_or_raise(
        self,
        category: str,
        code: str,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
        version: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        获取配置参数，缺失时抛出异常（无Fallback）
        
        查找优先级：
        1. 部门+地区定制
        2. 部门定制（全国）
        3. 地区定制
        4. 全国通用
        
        Args:
            category: 参数类别 (sphere/casualty/routing/assessment/confirmation)
            code: 参数编码 (如 SPHERE-WASH-001)
            region_code: 地区代码 (可选，如 510000 四川省)
            department_code: 部门代码 (可选，如 MEM/FIRE)
            version: 版本号 (可选，默认使用最新版本)
            
        Returns:
            JSONB解析后的参数字典
            
        Raises:
            ConfigurationMissingError: 配置不存在时抛出
        """
        cache_key = self._build_cache_key(category, code, region_code, department_code, version)
        
        # 1. 尝试从缓存获取
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.debug(f"[ConfigService] 缓存命中: {cache_key}")
                    return json.loads(cached)
            except Exception as e:
                # 缓存失败不影响主流程，只记录警告
                logger.warning(f"[ConfigService] 缓存读取失败: {e}")
        
        # 2. 数据库查询（按优先级排序）
        params = await self._query_from_db(category, code, region_code, department_code, version)
        
        if params is None:
            # ❌ 不Fallback，直接报错
            raise ConfigurationMissingError(category, code, region_code, department_code)
        
        # 3. 写入缓存
        if self._cache:
            try:
                await self._cache.setex(cache_key, self._cache_ttl, json.dumps(params))
                logger.debug(f"[ConfigService] 缓存写入: {cache_key}")
            except Exception as e:
                logger.warning(f"[ConfigService] 缓存写入失败: {e}")
        
        return params
    
    async def get_all_by_category(
        self,
        category: str,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> dict[str, dict[str, Any]]:
        """
        获取某类别的所有配置
        
        Args:
            category: 参数类别
            region_code: 地区代码 (可选)
            department_code: 部门代码 (可选)
            
        Returns:
            {code: params} 字典
            
        Raises:
            ConfigurationMissingError: 该类别没有任何配置时抛出
        """
        # 构建查询，按优先级去重（使用DISTINCT ON）
        sql = text("""
            SELECT DISTINCT ON (code) code, params
            FROM config.algorithm_parameters
            WHERE category = :category AND is_active = TRUE
            ORDER BY code, 
                CASE 
                    WHEN department_code = :dept AND region_code = :region THEN 1
                    WHEN department_code = :dept AND region_code IS NULL THEN 2
                    WHEN department_code IS NULL AND region_code = :region THEN 3
                    WHEN department_code IS NULL AND region_code IS NULL THEN 4
                    ELSE 5
                END
        """)
        
        result = await self._db.execute(sql, {
            "category": category,
            "region": region_code,
            "dept": department_code,
        })
        
        rows = result.fetchall()
        
        if not rows:
            raise ConfigurationMissingError(
                category=category,
                code="*",  # 表示整个类别
                region_code=region_code,
                department_code=department_code,
            )
        
        return {row.code: row.params for row in rows}
    
    async def exists(self, category: str, code: str) -> bool:
        """
        检查配置是否存在（不抛异常）
        
        用于启动时校验必需配置是否完整。
        """
        sql = text("""
            SELECT 1 FROM config.algorithm_parameters
            WHERE category = :category AND code = :code AND is_active = TRUE
            LIMIT 1
        """)
        
        result = await self._db.execute(sql, {"category": category, "code": code})
        return result.fetchone() is not None
    
    async def validate_required(
        self,
        requirements: dict[str, list[str]],
    ) -> tuple[bool, list[str]]:
        """
        批量校验必需配置是否存在
        
        Args:
            requirements: {category: [code1, code2, ...]} 必需配置清单
            
        Returns:
            (is_valid, missing_codes) 元组
            - is_valid: 所有配置都存在则为True
            - missing_codes: 缺失的配置编码列表
        """
        missing = []
        
        for category, codes in requirements.items():
            for code in codes:
                if not await self.exists(category, code):
                    missing.append(f"{category}:{code}")
        
        return (len(missing) == 0, missing)
    
    async def invalidate_cache(
        self,
        category: Optional[str] = None,
        code: Optional[str] = None,
    ) -> int:
        """
        清除缓存
        
        Args:
            category: 类别（可选，为空则清除所有）
            code: 编码（可选）
            
        Returns:
            清除的缓存键数量
        """
        if not self._cache:
            return 0
        
        pattern = f"{self.CACHE_PREFIX}:"
        if category:
            pattern += f"{category}:"
            if code:
                pattern += f"{code}:*"
            else:
                pattern += "*"
        else:
            pattern += "*"
        
        try:
            # 使用SCAN避免阻塞
            keys = []
            async for key in self._cache.scan_iter(match=pattern, count=100):
                keys.append(key)
            
            if keys:
                await self._cache.delete(*keys)
                logger.info(f"[ConfigService] 清除缓存: {len(keys)}个键")
            
            return len(keys)
        except Exception as e:
            logger.warning(f"[ConfigService] 清除缓存失败: {e}")
            return 0
    
    def _build_cache_key(
        self,
        category: str,
        code: str,
        region_code: Optional[str],
        department_code: Optional[str],
        version: Optional[str],
    ) -> str:
        """构建缓存键"""
        parts = [
            self.CACHE_PREFIX,
            category,
            code,
            region_code or "_",
            department_code or "_",
            version or "_",
        ]
        return ":".join(parts)
    
    async def _query_from_db(
        self,
        category: str,
        code: str,
        region_code: Optional[str],
        department_code: Optional[str],
        version: Optional[str],
    ) -> Optional[dict[str, Any]]:
        """
        从数据库查询配置（按优先级排序）
        
        优先级：
        1. 部门+地区定制
        2. 部门定制（全国）
        3. 地区定制
        4. 全国通用
        """
        # 构建查询
        sql_parts = ["""
            SELECT params FROM config.algorithm_parameters
            WHERE category = :category AND code = :code AND is_active = TRUE
        """]
        
        params: dict[str, Any] = {
            "category": category,
            "code": code,
        }
        
        # 版本过滤
        if version:
            sql_parts.append("AND version = :version")
            params["version"] = version
        
        # 按优先级排序
        sql_parts.append("""
            ORDER BY 
                CASE 
                    WHEN department_code = :dept AND region_code = :region THEN 1
                    WHEN department_code = :dept AND region_code IS NULL THEN 2
                    WHEN department_code IS NULL AND region_code = :region THEN 3
                    WHEN department_code IS NULL AND region_code IS NULL THEN 4
                    ELSE 5
                END,
                version DESC
            LIMIT 1
        """)
        
        params["region"] = region_code
        params["dept"] = department_code
        
        sql = text(" ".join(sql_parts))
        result = await self._db.execute(sql, params)
        row = result.fetchone()
        
        if row:
            logger.debug(f"[ConfigService] 数据库查询成功: {category}:{code}")
            return row.params
        
        return None
