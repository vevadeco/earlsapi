from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import resend

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Resend setup
resend.api_key = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
NOTIFICATION_EMAILS = ['info@earlslandscaping.ca', 'shahbaz@vevade.com']

# JWT setup
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret-key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Admin credentials
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'shahbaz')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Shaherzad123!')

# Create the main app
app = FastAPI()

# Create routers
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== MODELS ==============

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class LeadCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=5, max_length=100, pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    phone: str = Field(..., min_length=7, max_length=20)
    service_type: str = Field(..., min_length=1)

class Lead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    phone: str
    service_type: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "new"

class LeadResponse(BaseModel):
    success: bool
    message: str
    lead_id: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str

class PageView(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page: str
    referrer: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None

class PageViewCreate(BaseModel):
    page: str
    referrer: Optional[str] = None
    session_id: Optional[str] = None

class AnalyticsSummary(BaseModel):
    total_visitors: int
    total_page_views: int
    total_leads: int
    conversion_rate: float
    visitors_today: int
    leads_today: int
    visitors_this_week: int
    leads_this_week: int
    top_pages: List[dict]
    daily_stats: List[dict]

# Promo Banner Models
class PromoBannerSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    title: str = "Spring Cleanup Special - 15% OFF!"
    subtitle: str = "Book by March 1st to save on your spring landscaping"
    discount_text: str = "15% OFF"
    cta_text: str = "Claim Offer"
    deadline_date: str = "2026-03-01"  # ISO format date
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PromoBannerUpdate(BaseModel):
    enabled: Optional[bool] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    discount_text: Optional[str] = None
    cta_text: Optional[str] = None
    deadline_date: Optional[str] = None

# ============== AUTH HELPERS ==============

def create_token(username: str) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "sub": username,
        "exp": expiration,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============== EMAIL HELPER ==============

async def send_lead_notification(lead: Lead):
    """Send email notification for new lead"""
    if not resend.api_key:
        logger.warning("Resend API key not configured, skipping email notification")
        return
    
    service_labels = {
        "lawn-care": "Lawn Care & Maintenance",
        "garden-planting": "Garden Planting",
        "hardscaping": "Hardscaping (Patios, Walkways)",
        "full-service": "Full Landscaping Service"
    }
    
    service_name = service_labels.get(lead.service_type, lead.service_type)
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #2F5233; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">New Lead Received!</h1>
        </div>
        <div style="padding: 30px; background-color: #F9F7F2;">
            <h2 style="color: #2F5233; margin-top: 0;">Contact Details</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 10px 0; border-bottom: 1px solid #ddd; font-weight: bold; width: 120px;">Name:</td>
                    <td style="padding: 10px 0; border-bottom: 1px solid #ddd;">{lead.name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px 0; border-bottom: 1px solid #ddd; font-weight: bold;">Email:</td>
                    <td style="padding: 10px 0; border-bottom: 1px solid #ddd;"><a href="mailto:{lead.email}">{lead.email}</a></td>
                </tr>
                <tr>
                    <td style="padding: 10px 0; border-bottom: 1px solid #ddd; font-weight: bold;">Phone:</td>
                    <td style="padding: 10px 0; border-bottom: 1px solid #ddd;"><a href="tel:{lead.phone}">{lead.phone}</a></td>
                </tr>
                <tr>
                    <td style="padding: 10px 0; border-bottom: 1px solid #ddd; font-weight: bold;">Service:</td>
                    <td style="padding: 10px 0; border-bottom: 1px solid #ddd;">{service_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px 0; font-weight: bold;">Submitted:</td>
                    <td style="padding: 10px 0;">{lead.created_at.strftime('%B %d, %Y at %I:%M %p')}</td>
                </tr>
            </table>
            <div style="margin-top: 30px; padding: 15px; background-color: #D2691E; border-radius: 8px; text-align: center;">
                <p style="color: white; margin: 0; font-weight: bold;">Remember to follow up within 24 hours!</p>
            </div>
        </div>
        <div style="padding: 15px; background-color: #2F5233; text-align: center;">
            <p style="color: white; margin: 0; font-size: 12px;">Earl's Landscaping - Hamilton, Ontario</p>
        </div>
    </div>
    """
    
    for recipient in NOTIFICATION_EMAILS:
        try:
            params = {
                "from": SENDER_EMAIL,
                "to": [recipient],
                "subject": f"New Lead: {lead.name} - {service_name}",
                "html": html_content
            }
            await asyncio.to_thread(resend.Emails.send, params)
            logger.info(f"Lead notification sent to {recipient}")
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {str(e)}")

# ============== PUBLIC ROUTES ==============

@api_router.get("/")
async def root():
    return {"message": "Earl's Landscaping API"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

@api_router.post("/leads", response_model=LeadResponse)
async def create_lead(lead_input: LeadCreate):
    """Create a new lead from the contact form"""
    try:
        lead = Lead(
            name=lead_input.name,
            email=lead_input.email,
            phone=lead_input.phone,
            service_type=lead_input.service_type
        )
        
        doc = lead.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        
        await db.leads.insert_one(doc)
        
        # Send email notification (non-blocking)
        asyncio.create_task(send_lead_notification(lead))
        
        return LeadResponse(
            success=True,
            message="Thank you! We'll contact you within 24 hours.",
            lead_id=lead.id
        )
    except Exception as e:
        logger.error(f"Error creating lead: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit form. Please try again.")

# ============== ANALYTICS ROUTES ==============

@api_router.post("/analytics/pageview")
async def track_pageview(pageview: PageViewCreate, request: Request):
    """Track a page view for analytics"""
    try:
        pv = PageView(
            page=pageview.page,
            referrer=pageview.referrer,
            session_id=pageview.session_id,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None
        )
        
        doc = pv.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        
        await db.page_views.insert_one(doc)
        return {"success": True}
    except Exception as e:
        logger.error(f"Error tracking pageview: {e}")
        return {"success": False}

# ============== AUTH ROUTES ==============

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Admin login"""
    if request.username == ADMIN_USERNAME and request.password == ADMIN_PASSWORD:
        token = create_token(request.username)
        return LoginResponse(success=True, token=token, message="Login successful")
    raise HTTPException(status_code=401, detail="Invalid credentials")

@api_router.get("/auth/verify")
async def verify_auth(username: str = Depends(verify_token)):
    """Verify token is valid"""
    return {"valid": True, "username": username}

# ============== ADMIN ROUTES ==============

@api_router.get("/admin/leads", response_model=List[Lead])
async def get_all_leads(username: str = Depends(verify_token)):
    """Get all leads (admin only)"""
    leads = await db.leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for lead in leads:
        if isinstance(lead['created_at'], str):
            lead['created_at'] = datetime.fromisoformat(lead['created_at'])
    return leads

@api_router.patch("/admin/leads/{lead_id}/status")
async def update_lead_status(lead_id: str, status: str, username: str = Depends(verify_token)):
    """Update lead status"""
    valid_statuses = ["new", "contacted", "qualified", "converted", "lost"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    result = await db.leads.update_one(
        {"id": lead_id},
        {"$set": {"status": status}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {"success": True, "message": f"Lead status updated to {status}"}

@api_router.delete("/admin/leads/{lead_id}")
async def delete_lead(lead_id: str, username: str = Depends(verify_token)):
    """Delete a lead"""
    result = await db.leads.delete_one({"id": lead_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {"success": True, "message": "Lead deleted"}

@api_router.get("/admin/analytics", response_model=AnalyticsSummary)
async def get_analytics(username: str = Depends(verify_token)):
    """Get analytics summary"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    
    # Get total counts
    total_leads = await db.leads.count_documents({})
    total_page_views = await db.page_views.count_documents({})
    
    # Get unique visitors (by session_id or ip)
    unique_sessions = await db.page_views.distinct("session_id")
    total_visitors = len([s for s in unique_sessions if s])
    if total_visitors == 0:
        total_visitors = total_page_views  # Fallback
    
    # Today stats
    visitors_today_list = await db.page_views.distinct("session_id", {
        "timestamp": {"$gte": today_start.isoformat()}
    })
    visitors_today = len([s for s in visitors_today_list if s]) or await db.page_views.count_documents({
        "timestamp": {"$gte": today_start.isoformat()}
    })
    
    leads_today = await db.leads.count_documents({
        "created_at": {"$gte": today_start.isoformat()}
    })
    
    # This week stats
    visitors_week_list = await db.page_views.distinct("session_id", {
        "timestamp": {"$gte": week_start.isoformat()}
    })
    visitors_this_week = len([s for s in visitors_week_list if s]) or await db.page_views.count_documents({
        "timestamp": {"$gte": week_start.isoformat()}
    })
    
    leads_this_week = await db.leads.count_documents({
        "created_at": {"$gte": week_start.isoformat()}
    })
    
    # Conversion rate
    conversion_rate = (total_leads / total_visitors * 100) if total_visitors > 0 else 0
    
    # Top pages
    pipeline = [
        {"$group": {"_id": "$page", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    top_pages_cursor = db.page_views.aggregate(pipeline)
    top_pages = [{"page": doc["_id"], "views": doc["count"]} async for doc in top_pages_cursor]
    
    # Daily stats for last 7 days
    daily_stats = []
    for i in range(7):
        day = today_start - timedelta(days=i)
        day_end = day + timedelta(days=1)
        
        day_views = await db.page_views.count_documents({
            "timestamp": {"$gte": day.isoformat(), "$lt": day_end.isoformat()}
        })
        day_leads = await db.leads.count_documents({
            "created_at": {"$gte": day.isoformat(), "$lt": day_end.isoformat()}
        })
        
        daily_stats.append({
            "date": day.strftime("%Y-%m-%d"),
            "visitors": day_views,
            "leads": day_leads
        })
    
    daily_stats.reverse()
    
    return AnalyticsSummary(
        total_visitors=total_visitors,
        total_page_views=total_page_views,
        total_leads=total_leads,
        conversion_rate=round(conversion_rate, 2),
        visitors_today=visitors_today,
        leads_today=leads_today,
        visitors_this_week=visitors_this_week,
        leads_this_week=leads_this_week,
        top_pages=top_pages,
        daily_stats=daily_stats
    )

@api_router.get("/admin/leads/export")
async def export_leads(username: str = Depends(verify_token)):
    """Export leads as CSV data"""
    leads = await db.leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    csv_lines = ["Name,Email,Phone,Service,Status,Created At"]
    for lead in leads:
        created_at = lead.get('created_at', '')
        if isinstance(created_at, str):
            created_at = created_at.split('T')[0]
        csv_lines.append(f"{lead.get('name','')},{lead.get('email','')},{lead.get('phone','')},{lead.get('service_type','')},{lead.get('status','new')},{created_at}")
    
    return {"csv": "\n".join(csv_lines), "filename": f"leads_export_{datetime.now().strftime('%Y%m%d')}.csv"}

# ============== PROMO BANNER ROUTES ==============

# Default promo banner settings
DEFAULT_PROMO_SETTINGS = {
    "enabled": True,
    "title": "Spring Cleanup Special - 15% OFF!",
    "subtitle": "Book by March 1st to save on your spring landscaping",
    "discount_text": "15% OFF",
    "cta_text": "Claim Offer",
    "deadline_date": "2026-03-01"
}

@api_router.get("/promo-banner")
async def get_promo_banner():
    """Get promo banner settings (public endpoint)"""
    settings = await db.promo_settings.find_one({}, {"_id": 0})
    if not settings:
        return DEFAULT_PROMO_SETTINGS
    return settings

@api_router.get("/admin/promo-banner", response_model=PromoBannerSettings)
async def get_admin_promo_banner(username: str = Depends(verify_token)):
    """Get promo banner settings (admin)"""
    settings = await db.promo_settings.find_one({}, {"_id": 0})
    if not settings:
        # Initialize with defaults
        settings = {**DEFAULT_PROMO_SETTINGS, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.promo_settings.insert_one(settings)
    if isinstance(settings.get('updated_at'), str):
        settings['updated_at'] = datetime.fromisoformat(settings['updated_at'])
    return PromoBannerSettings(**settings)

@api_router.put("/admin/promo-banner")
async def update_promo_banner(update: PromoBannerUpdate, username: str = Depends(verify_token)):
    """Update promo banner settings"""
    # Get current settings or defaults
    current = await db.promo_settings.find_one({}, {"_id": 0})
    if not current:
        current = DEFAULT_PROMO_SETTINGS.copy()
    
    # Update only provided fields
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    current.update(update_data)
    
    # Upsert the settings
    await db.promo_settings.update_one(
        {},
        {"$set": current},
        upsert=True
    )
    
    return {"success": True, "message": "Promo banner updated", "settings": current}

# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
