import os
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product

app = FastAPI(title="DeskSetups Shop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc = dict(doc)
    _id = doc.get("_id")
    if isinstance(_id, ObjectId):
        doc["id"] = str(_id)
        del doc["_id"]
    # Convert datetime to isoformat
    for k, v in list(doc.items()):
        try:
            import datetime as _dt
            if isinstance(v, (_dt.datetime, _dt.date)):
                doc[k] = v.isoformat()
        except Exception:
            pass
    return doc


# Models
class OrderItem(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int = Field(ge=1)

class CustomerInfo(BaseModel):
    name: str
    email: EmailStr
    address: Optional[str] = None

class CreateOrder(BaseModel):
    items: List[OrderItem]
    customer: CustomerInfo
    note: Optional[str] = None

class OrderOut(BaseModel):
    id: str


@app.get("/")
def read_root():
    return {"message": "DeskSetups Shop API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    return response


# Seed sample products if empty
SAMPLE_PRODUCTS = [
    {
        "title": "Retro Gamer Setup",
        "description": "Pink CRT monitor, mechanical keyboard, RGB mouse, and neon desk mat.",
        "price": 699.0,
        "category": "gaming",
        "in_stock": True,
        "image": "https://images.unsplash.com/photo-1603484477859-abe6a73f9360?q=80&w=1400&auto=format&fit=crop"
    },
    {
        "title": "Deep Work Productivity",
        "description": "Dual 27\" IPS monitors, ergonomic chair, and silent peripherals.",
        "price": 1199.0,
        "category": "productivity",
        "in_stock": True,
        "image": "https://images.unsplash.com/photo-1559163499-413811fb2344?q=80&w=1400&auto=format&fit=crop"
    },
    {
        "title": "Creator Studio",
        "description": "Ultra-wide 34\" display, studio speakers, and adjustable boom arm.",
        "price": 1899.0,
        "category": "creator",
        "in_stock": True,
        "image": "https://images.unsplash.com/photo-1518779578993-ec3579fee39f?q=80&w=1400&auto=format&fit=crop"
    },
    {
        "title": "Minimal Zen Desk",
        "description": "Clean aluminum monitor stand, wireless keyboard, and warm lighting.",
        "price": 899.0,
        "category": "minimal",
        "in_stock": True,
        "image": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?q=80&w=1400&auto=format&fit=crop"
    },
    {
        "title": "Streamer Pro Rig",
        "description": "High FPS monitor, condenser mic, key light, and capture card.",
        "price": 1599.0,
        "category": "streaming",
        "in_stock": True,
        "image": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?q=80&w=1400&auto=format&fit=crop"
    },
]


def ensure_seed_data():
    try:
        if db is None:
            return
        count = db["product"].count_documents({})
        if count == 0:
            # Validate and insert
            to_insert = []
            for p in SAMPLE_PRODUCTS:
                # Use Product schema validation
                Product(**{k: p[k] for k in ["title", "description", "price", "category", "in_stock"]})
                p_with_meta = p.copy()
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                p_with_meta["created_at"] = now
                p_with_meta["updated_at"] = now
                to_insert.append(p_with_meta)
            if to_insert:
                db["product"].insert_many(to_insert)
    except Exception:
        pass


@app.get("/api/products")
def list_products(category: Optional[str] = Query(None), q: Optional[str] = Query(None)):
    ensure_seed_data()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    query: Dict[str, Any] = {}
    if category and category.lower() != "all":
        query["category"] = category.lower()
    if q:
        # Simple case-insensitive search on title/description
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]

    items = db["product"].find(query).sort("created_at", -1)
    results = [serialize_doc(doc) for doc in items]
    return {"items": results}


@app.get("/api/categories")
def list_categories():
    ensure_seed_data()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    cats = db["product"].distinct("category")
    cats = sorted(cats)
    return {"categories": ["all", *cats]}


@app.post("/api/orders", response_model=OrderOut)
def create_order(payload: CreateOrder):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    data = payload.model_dump()
    order_id = create_document("order", data)
    return {"id": order_id}


@app.get("/schema")
def get_schema_file():
    """Expose schema definitions for tooling/inspection."""
    try:
        import pathlib
        path = pathlib.Path(__file__).parent / "schemas.py"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
