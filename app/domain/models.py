from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, model_validator
from decimal import Decimal


class OrderStatus(str, Enum):
    DRAFT = "draft"
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class DomainException(Exception):
    """Base exception for domain errors."""
    ...


class InvalidTransitionError(DomainException):
    """Raised when an invalid order status transition is attempted."""
    ...


class BusinessRuleViolationError(DomainException):
    """Raised when a domain business rule is violated."""
    ...


class Money(BaseModel):
    """Value object for monetary amounts."""
    amount: Decimal = Field(..., gt=0, description="Monetary amount")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="Currency code")

    def __str__(self):
        return f"{self.currency} {self.amount}"


class Address(BaseModel):
    """Value object for addresses."""
    street: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    zip_code: str = Field(..., min_length=1, max_length=20)
    country: str = Field(default="US", min_length=2, max_length=2)


class Customer(BaseModel):
    """Entity for customers."""
    id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    address: Address


class Product(BaseModel):
    """Simplified product model for order lines."""
    id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    out_of_stock: bool = Field(default=False)


class OrderLine(BaseModel):
    """Entity for order line items."""
    product: Product
    quantity: int = Field(..., gt=0)
    unit_price: Money

    @property
    def total_price(self) -> Money:
        return Money(amount=self.unit_price.amount * self.quantity, currency=self.unit_price.currency)


class Order(BaseModel):
    """Aggregate root for orders."""
    id: str = Field(..., min_length=1, max_length=50)
    customer: Customer
    lines: List[OrderLine] = Field(..., min_items=1)
    status: OrderStatus = Field(default=OrderStatus.DRAFT)
    total_amount: Optional[Money] = None

    @model_validator(mode='after')
    def validate_confirmation_rules(self):
        """Enforce business rules for order confirmation."""
        if self.status == OrderStatus.CONFIRMED:
            # Check if any line item references out-of-stock product
            for line in self.lines:
                if line.product.out_of_stock:
                    raise ValueError("Cannot confirm order with out-of-stock items")
            # Extensible: add more rules here, e.g., credit limit checks
            # if self.customer.credit_limit < self.total_amount.amount:
            #     raise ValueError("Credit limit exceeded")
        return self

    def transition_to(self, new_status: OrderStatus):
        """Transition order to a new status, raising exception on invalid transitions."""
        valid_transitions = {
            OrderStatus.DRAFT: [OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED],
            OrderStatus.PENDING_PAYMENT: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
            OrderStatus.CONFIRMED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
            OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
            OrderStatus.SHIPPED: [OrderStatus.DELIVERED, OrderStatus.CANCELLED],
            OrderStatus.DELIVERED: [],  # No transitions from delivered
            OrderStatus.CANCELLED: [],  # No transitions from cancelled
        }

        if new_status not in valid_transitions[self.status]:
            raise InvalidTransitionError(f"Cannot transition from {self.status} to {new_status}")

        if new_status == OrderStatus.CONFIRMED:
            for line in self.lines:
                if line.product.out_of_stock:
                    raise BusinessRuleViolationError("Cannot confirm order with out-of-stock items")

        self.status = new_status

    def calculate_total(self) -> Money:
        """Calculate total amount from line items."""
        total = sum((line.total_price.amount for line in self.lines), Decimal(0))
        currency = self.lines[0].unit_price.currency if self.lines else "USD"
        return Money(amount=total, currency=currency)