from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Order, OrderFeedback, User
from ..schemas import (
    OrderFeedbackCreate,
    OrderFeedbackListResponse, 
    OrderFeedbackResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedbacks", tags=["feedbacks"])


@router.post("/", response_model=OrderFeedbackResponse)
def create_feedback(
    feedback_data: OrderFeedbackCreate,
    session: Session = Depends(get_session)
) -> OrderFeedbackResponse:
    """Создание отклика на заказ"""
    
    # Проверяем существование заказа
    order = session.query(Order).filter(Order.id == feedback_data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order with id {feedback_data.order_id} not found")
    
    # Проверяем существование пользователя
    user = session.query(User).filter(User.uid == feedback_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {feedback_data.user_id} not found")
    
    # Проверяем, не оставлял ли пользователь уже отклик на этот заказ
    existing_feedback = session.query(OrderFeedback).filter(
        OrderFeedback.order_id == feedback_data.order_id,
        OrderFeedback.user_id == feedback_data.user_id
    ).first()
    
    if existing_feedback:
        raise HTTPException(
            status_code=400, 
            detail=f"User {feedback_data.user_id} already left feedback for order {feedback_data.order_id}"
        )
    
    # Создаем новый отклик
    feedback = OrderFeedback(
        order_id=feedback_data.order_id,
        user_id=feedback_data.user_id,
        feedback_text=feedback_data.feedback_text,
        status="pending"
    )
    
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    
    logger.info(
        "Feedback created",
        extra={
            "feedback_id": feedback.id,
            "order_id": feedback.order_id,
            "user_id": str(feedback.user_id)
        }
    )
    
    return OrderFeedbackResponse.model_validate(feedback)


@router.get("/order/{order_id}", response_model=OrderFeedbackListResponse)
def get_order_feedbacks(
    order_id: int,
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> OrderFeedbackListResponse:
    """Получение всех откликов на заказ"""
    
    # Проверяем существование заказа
    order = session.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order with id {order_id} not found")
    
    feedbacks = session.query(OrderFeedback).filter(
        OrderFeedback.order_id == order_id
    ).order_by(
        OrderFeedback.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    items = [OrderFeedbackResponse.model_validate(feedback) for feedback in feedbacks]
    
    return OrderFeedbackListResponse(
        items=items,
        limit=limit,
        offset=offset
    )


@router.get("/user/{user_id}", response_model=OrderFeedbackListResponse)
def get_user_feedbacks(
    user_id: UUID,
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> OrderFeedbackListResponse:
    """Получение всех откликов пользователя"""
    
    # Проверяем существование пользователя
    user = session.query(User).filter(User.uid == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
    
    feedbacks = session.query(OrderFeedback).filter(
        OrderFeedback.user_id == user_id
    ).order_by(
        OrderFeedback.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    items = [OrderFeedbackResponse.model_validate(feedback) for feedback in feedbacks]
    
    return OrderFeedbackListResponse(
        items=items,
        limit=limit,
        offset=offset
    )


@router.patch("/{feedback_id}/status", response_model=OrderFeedbackResponse)
def update_feedback_status(
    feedback_id: int,
    status: str,
    session: Session = Depends(get_session)
) -> OrderFeedbackResponse:
    """Обновление статуса отклика"""
    
    if status not in ["pending", "accepted", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {status}. Must be one of: pending, accepted, rejected"
        )
    
    feedback = session.query(OrderFeedback).filter(
        OrderFeedback.id == feedback_id
    ).first()
    
    if not feedback:
        raise HTTPException(status_code=404, detail=f"Feedback with id {feedback_id} not found")
    
    feedback.status = status
    session.commit()
    session.refresh(feedback)
    
    logger.info(
        "Feedback status updated",
        extra={
            "feedback_id": feedback.id,
            "new_status": status
        }
    )
    
    return OrderFeedbackResponse.model_validate(feedback)


@router.delete("/{feedback_id}")
def delete_feedback(
    feedback_id: int,
    session: Session = Depends(get_session)
) -> dict:
    """Удаление отклика"""
    
    feedback = session.query(OrderFeedback).filter(
        OrderFeedback.id == feedback_id
    ).first()
    
    if not feedback:
        raise HTTPException(status_code=404, detail=f"Feedback with id {feedback_id} not found")
    
    session.delete(feedback)
    session.commit()
    
    logger.info(
        "Feedback deleted",
        extra={"feedback_id": feedback_id}
    )
    
    return {"status": "success", "message": f"Feedback {feedback_id} deleted"}
