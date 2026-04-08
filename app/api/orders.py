from typing import List, Optional, Dict, Literal
from fastapi import APIRouter, HTTPException, Header, Query, Depends
from pydantic import BaseModel
from app.domain.models import Order, OrderStatus, InvalidTransitionError, BusinessRuleViolationError, Customer, Product, Money
from app.services.order_service import OrderService, EventPublisher
from app.repositories.order_repository import InMemoryOrderRepository
from app.api.errors import ErrorResponse
import uuid

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


class CreateOrderItem(BaseModel):
    product: Product
    quantity: int
    unit_price: Money


class CreateOrderRequest(BaseModel):
    customer: Customer
    items: List[CreateOrderItem]


class TransitionRequest(BaseModel):
    event: Literal["confirm", "ship", "cancel"]


# In-memory state is preserved for this demo via module-level singletons.
order_repository = InMemoryOrderRepository()
event_publisher = EventPublisher()
order_service = OrderService(order_repository, event_publisher)


def get_order_service() -> OrderService:
    return order_service


# Idempotency store (in production, use Redis or DB)
idempotency_store: Dict[str, str] = {}  # key: idempotency_key, value: order_id


@router.post("/", response_model=Order)
async def create_order(
    order_data: CreateOrderRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    service: OrderService = Depends(get_order_service)
):
    """
    Create a new order (idempotent with Idempotency-Key header).

    Idempotency implementation:
    - Store idempotency_key -> order_id mapping in a durable store (e.g., Redis, DynamoDB, or SQL table).
    - On duplicate key, return the existing order and do not create a second order.
    - Use atomic operations to prevent race conditions (e.g., SETNX in Redis or a unique constraint on the idempotency key).
    - Guard against a partial failure where the order is created but the idempotency entry is not stored.
    """
    if idempotency_key:
        if idempotency_key in idempotency_store:
            order_id = idempotency_store[idempotency_key]
            order = service.get_order(order_id)
            if order:
                return order
            # If order not found, perhaps recreate or error

    try:
        order = service.create_order(order_data)
        if idempotency_key:
            idempotency_store[idempotency_key] = order.id
        return order
    except ValueError as e:
        raise HTTPException(status_code=400, detail=ErrorResponse(
            status_code=400,
            error_code="VALIDATION_ERROR",
            message=str(e),
            request_id=str(uuid.uuid4())
        ).model_dump())


@router.patch("/{order_id}/transition", response_model=Order)
async def transition_order(order_id: str, event: TransitionRequest, service: OrderService = Depends(get_order_service)):
    """
    Trigger a state transition (event-driven, not direct status set).

    Prefer event names over raw status because event names express intent and keep the API contract stable.
    This prevents clients from bypassing business rules by writing arbitrary statuses, and it lets the service
    decide which state changes are valid.
    """
    event_name = event.event
    status_map = {
        "confirm": OrderStatus.CONFIRMED,
        "ship": OrderStatus.SHIPPED,
        "cancel": OrderStatus.CANCELLED,
        # Add more events as needed
    }
    if event_name not in status_map:
        raise HTTPException(status_code=400, detail=ErrorResponse(
            status_code=400,
            error_code="INVALID_EVENT",
            message=f"Invalid event: {event_name}",
            request_id=str(uuid.uuid4())
        ).model_dump())

    try:
        order = service.change_status(order_id, status_map[event_name])
        return order
    except ValueError as e:
        raise HTTPException(status_code=404, detail=ErrorResponse(
            status_code=404,
            error_code="ORDER_NOT_FOUND",
            message=str(e),
            request_id=str(uuid.uuid4())
        ).model_dump())
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=400, detail=ErrorResponse(
            status_code=400,
            error_code="BUSINESS_RULE_VIOLATION",
            message=str(e),
            request_id=str(uuid.uuid4())
        ).model_dump())
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=ErrorResponse(
            status_code=400,
            error_code="INVALID_TRANSITION",
            message=str(e),
            request_id=str(uuid.uuid4())
        ).model_dump())


@router.get("/{order_id}", response_model=Order)
async def get_order(order_id: str, expand: Optional[List[str]] = Query(None), service: OrderService = Depends(get_order_service)):
    """
    Get order with optional field expansion (?expand=customer,lines).
    """
    order = service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=ErrorResponse(
            status_code=404,
            error_code="ORDER_NOT_FOUND",
            message="Order not found",
            request_id=str(uuid.uuid4())
        ).model_dump())

    # For expand, in real app, could lazy load or include related data
    return order


@router.get("/", response_model=List[Order])
async def list_orders(
    cursor: Optional[str] = None,
    limit: int = Query(10, le=100),
    status: Optional[str] = None,
    service: OrderService = Depends(get_order_service)
):
    """
    List orders with cursor-based pagination, filtering, sorting.
    Simplified: no actual cursor, just offset-like.
    """
    orders = service.get_orders(status)
    # In real app, implement proper cursor pagination with sorting
    start = int(cursor) if cursor else 0
    end = start + limit
    return orders[start:end]