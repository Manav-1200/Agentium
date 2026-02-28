import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from main import app
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            methods = ",".join(route.methods - {"OPTIONS"}) if route.methods else ""
            routes.append(f"{methods} {route.path}")
    
    routes.sort()
    for r in routes:
        print(r)
except Exception as e:
    print(f"Error: {e}")
