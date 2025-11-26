from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from src.core.database import get_db
from .service import SchemeService
from .schemas import (
    SchemeCreate, SchemeUpdate, SchemeResponse, SchemeListResponse,
    SchemeSubmitReview, SchemeApprove, SchemeReject,
    ResourceAllocationCreate, ResourceAllocationModify, ResourceAllocationResponse
)


router = APIRouter(prefix="/schemes", tags=["schemes"])


def get_service(db: AsyncSession = Depends(get_db)) -> SchemeService:
    return SchemeService(db)


@router.post("", response_model=SchemeResponse, status_code=201)
async def create_scheme(
    data: SchemeCreate,
    service: SchemeService = Depends(get_service),
):
    """创建救援方案"""
    return await service.create(data)


@router.get("", response_model=SchemeListResponse)
async def list_schemes(
    scenario_id: Optional[UUID] = None,
    event_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    service: SchemeService = Depends(get_service),
):
    """获取方案列表"""
    return await service.list(scenario_id, event_id, page, page_size, status)


@router.get("/{scheme_id}", response_model=SchemeResponse)
async def get_scheme(
    scheme_id: UUID,
    service: SchemeService = Depends(get_service),
):
    """获取方案详情（含资源分配）"""
    return await service.get_by_id(scheme_id)


@router.put("/{scheme_id}", response_model=SchemeResponse)
async def update_scheme(
    scheme_id: UUID,
    data: SchemeUpdate,
    service: SchemeService = Depends(get_service),
):
    """更新方案"""
    return await service.update(scheme_id, data)


@router.post("/{scheme_id}/submit", response_model=SchemeResponse)
async def submit_scheme_for_review(
    scheme_id: UUID,
    data: SchemeSubmitReview,
    service: SchemeService = Depends(get_service),
):
    """提交方案审批"""
    return await service.submit_for_review(scheme_id, data)


@router.post("/{scheme_id}/approve", response_model=SchemeResponse)
async def approve_scheme(
    scheme_id: UUID,
    data: SchemeApprove,
    service: SchemeService = Depends(get_service),
):
    """审批通过方案"""
    return await service.approve(scheme_id, data)


@router.post("/{scheme_id}/reject", response_model=SchemeResponse)
async def reject_scheme(
    scheme_id: UUID,
    data: SchemeReject,
    service: SchemeService = Depends(get_service),
):
    """驳回方案"""
    return await service.reject(scheme_id, data)


@router.post("/{scheme_id}/execute", response_model=SchemeResponse)
async def start_scheme_execution(
    scheme_id: UUID,
    service: SchemeService = Depends(get_service),
):
    """开始执行方案"""
    return await service.start_execution(scheme_id)


@router.post("/{scheme_id}/complete", response_model=SchemeResponse)
async def complete_scheme(
    scheme_id: UUID,
    service: SchemeService = Depends(get_service),
):
    """完成方案"""
    return await service.complete(scheme_id)


@router.post("/{scheme_id}/cancel", response_model=SchemeResponse)
async def cancel_scheme(
    scheme_id: UUID,
    service: SchemeService = Depends(get_service),
):
    """取消方案"""
    return await service.cancel(scheme_id)


@router.delete("/{scheme_id}", status_code=204)
async def delete_scheme(
    scheme_id: UUID,
    service: SchemeService = Depends(get_service),
):
    """删除方案（仅draft/cancelled可删除）"""
    await service.delete(scheme_id)


@router.post("/{scheme_id}/allocations", response_model=ResourceAllocationResponse, status_code=201)
async def add_resource_allocation(
    scheme_id: UUID,
    data: ResourceAllocationCreate,
    service: SchemeService = Depends(get_service),
):
    """添加资源分配"""
    return await service.add_allocation(scheme_id, data)


@router.put("/allocations/{allocation_id}", response_model=ResourceAllocationResponse)
async def modify_resource_allocation(
    allocation_id: UUID,
    data: ResourceAllocationModify,
    service: SchemeService = Depends(get_service),
):
    """人工修改资源分配"""
    return await service.modify_allocation(allocation_id, data)


@router.post("/allocations/{allocation_id}/confirm", response_model=ResourceAllocationResponse)
async def confirm_resource_allocation(
    allocation_id: UUID,
    service: SchemeService = Depends(get_service),
):
    """确认资源分配"""
    return await service.confirm_allocation(allocation_id)


@router.delete("/allocations/{allocation_id}", status_code=204)
async def delete_resource_allocation(
    allocation_id: UUID,
    service: SchemeService = Depends(get_service),
):
    """删除资源分配"""
    await service.delete_allocation(allocation_id)
