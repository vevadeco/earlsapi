"""
Vercel Serverless Adapter
"""
import sys
import os

def handler(event, context):
    """Lambda handler for Vercel"""
    import json
    import traceback
    
    try:
        # Add parent to path
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        
        # Try to import
        from fastapi import FastAPI
        
        # Try to import server app
        from server import app
        
        from mangum import Mangum
        mangum = Mangum(app, lifespan="off")
        return mangum(event, context)
        
    except Exception as e:
        tb = traceback.format_exc()
        return {
            "statusCode": 200,  # Return 200 so we can see error
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "startup_error",
                "error": str(e),
                "traceback": tb,
                "cwd": os.getcwd(),
                "path": sys.path,
                "env_keys": list(os.environ.keys())
            })
        }
