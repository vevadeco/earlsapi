"""
Vercel Serverless Adapter for Earl's Landscaping Backend
"""
import sys
import os
import traceback

# Add parent directory to path  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Simple WSGI handler for Vercel
def handler(event, context):
    """AWS Lambda/Vercel handler"""
    try:
        # Import here to catch import errors
        from server import app
        from mangum import Mangum
        
        mangum = Mangum(app, lifespan="off")
        return mangum(event, context)
    except Exception as e:
        error_details = f"Error: {str(e)}\nTraceback: {traceback.format_exc()}"
        print(error_details)  # Log to Vercel logs
        
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": f'{{"error": "Server initialization error", "message": "{str(e).replace(chr(34), chr(92)+chr(34))}"}}'
        }

# For direct import
app = handler
