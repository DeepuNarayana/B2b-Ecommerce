import logging
from typing import List, Optional, Dict
from app.domain.models import Order, OrderStatus, InvalidTransitionError
from app.repositories.order_repository import OrderRepository
import uuid

logger = logging.getLogger(__name__)


class EventPublisher:
    """Simple event publisher for side effects."""
    def publish(self, event: str, data: Dict):
        # In production, use message queue like RabbitMQ or Kafka
        logger.info(f"Publishing event {event}: {data}")
        # For warehouse notification, emit an event for an async consumer.
        if event == "order_created":
            logger.info("Queued warehouse notification for order %s", data.get("order_id"))


class OrderService:
    def __init__(self, repository: OrderRepository, event_publisher: EventPublisher):
        self.repository = repository
        self.event_publisher = event_publisher

    def create_order(self, order_data: dict) -> Order:
        customer = order_data.customer if hasattr(order_data, "customer") else order_data["customer"]
        items = order_data.items if hasattr(order_data, "items") else order_data["items"]
        logger.info(f"Creating order for customer {customer.id}")
        order_id = str(uuid.uuid4())
        order = Order(id=order_id, customer=customer, lines=items)
        order.total_amount = order.calculate_total()

        self.repository.save(order)
        self.event_publisher.publish("order_created", {"order_id": order_id})
        logger.info(f"Order {order_id} created successfully")
        return order

    def change_status(self, order_id: str, new_status: OrderStatus) -> Order:
        logger.info(f"Changing status of order {order_id} to {new_status}")
        order = self.repository.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        try:
            order.transition_to(new_status)
        except InvalidTransitionError as e:
            logger.error(f"Invalid transition for order {order_id}: {e}")
            raise

        self.repository.save(order)
        self.event_publisher.publish("order_status_changed", {"order_id": order_id, "new_status": new_status.value})
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.repository.get_by_id(order_id)

    def get_orders(self, status: Optional[str] = None) -> List[Order]:
        return self.repository.get_all(status)