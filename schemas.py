from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

# Collections
class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")
    image: Optional[str] = Field(None, description="Image URL")

class OrderItem(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int = Field(ge=1)

class Customer(BaseModel):
    name: str
    email: EmailStr
    address: Optional[str] = None

class Order(BaseModel):
    items: List[OrderItem]
    customer: Customer
    note: Optional[str] = None
