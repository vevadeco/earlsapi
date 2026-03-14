"""
Vercel Serverless Adapter
"""
from mangum import Mangum
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import FastAPI app - lazy import to catch errors
app = None

class SafeMangum:
    def __init__(self):
        self.app = None
        self.error = None
        self._load_app()
    
    def _load_app(self):
        global app
        try:
            from server import app as fastapi_app
            app = fastapi_app
            self.app = Mangum(fastapi_app, lifespan="off")
        except Exception as e:
            self.error = str(e)
            import traceback
            self.error_trace = traceback.format_exc()
    
    def __call__(self, event, context):
        if self.app:
            return self.app(event, context)
        
        import json
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "error",
                "message": "Failed to load FastAPI app",
                "error": self.error,
                "traceback": getattr(self, 'error_trace', None),
                "path": event.get('path'),
                "method": event.get('httpMethod')
            })
        }

# Create handler
handler = SafeMangum()
