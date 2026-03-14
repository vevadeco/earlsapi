"""
Vercel Serverless Adapter for Earl's Landscaping Backend
"""
import sys
import os
import traceback
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        try:
            # Check env vars
            env_vars = {
                'MONGO_URL': os.environ.get('MONGO_URL', 'NOT SET'),
                'DB_NAME': os.environ.get('DB_NAME', 'NOT SET'),
                'JWT_SECRET': 'SET' if os.environ.get('JWT_SECRET') else 'NOT SET',
                'ADMIN_USERNAME': os.environ.get('ADMIN_USERNAME', 'NOT SET'),
            }
            
            import json
            response = {
                "status": "ok",
                "message": "Earl's Landscaping API",
                "env_check": env_vars,
                "path": self.path
            }
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            self.wfile.write(json.dumps({
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }).encode())
    
    def do_POST(self):
        self.do_GET()
