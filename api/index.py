"""
Vercel Serverless Adapter for Earl's Landscaping Backend
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import FastAPI app
from server import app

# Mangum handler for serverless
from mangum import Mangum
handler = Mangum(app, lifespan="off")

# Vercel expects this export
app = handler
