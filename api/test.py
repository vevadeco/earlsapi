import json

def handler(request):
    return json.dumps({
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"test": "works", "path": request.get("path", "/")})
    })
