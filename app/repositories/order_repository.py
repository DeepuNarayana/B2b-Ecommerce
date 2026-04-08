from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models import Order


class OrderRepository(ABC):
    @abstractmethod
    def save(self, order: Order) -> None:
        raise NotImplementedError("save must be implemented by repository subclasses")

    @abstractmethod
    def get_by_id(self, order_id: str) -> Optional[Order]:
        raise NotImplementedError("get_by_id must be implemented by repository subclasses")

    @abstractmethod
    def get_all(self, status: Optional[str] = None) -> List[Order]:
        raise NotImplementedError("get_all must be implemented by repository subclasses")


class InMemoryOrderRepository(OrderRepository):
    def __init__(self):
        self._orders: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._orders[order.id] = order

    def get_by_id(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_all(self, status: Optional[str] = None) -> List[Order]:
        orders = list(self._orders.values())
        if status:
            orders = [o for o in orders if o.status.value == status]
        return orders