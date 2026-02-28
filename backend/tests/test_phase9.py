import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.database import SessionLocal, init_db
from backend.services.monitoring_service import MonitoringService
from backend.services.db_maintenance import DatabaseMaintenanceService
from backend.services.api_key_manager import init_api_key_manager, api_key_manager

async def run_smoke_test():
    print("Initializing DB...")
    init_db()
    
    db = SessionLocal()
    try:
        print("Initializing API Key Manager...")
        init_api_key_manager(db)
        
        print("\n--- Testing API Key Manager Health Report ---")
        health = api_key_manager.get_key_health_report(db=db)
        print(f"Overall Status: {health.get('overall_status')}")
        print(f"Total Keys: {health.get('summary', {}).get('total_keys')}")
        
        print("\n--- Testing Monitoring Service Init ---")
        MonitoringService.start_background_monitors()
        print("Monitoring service background loops dispatched.")
        
        print("\n--- Testing DB Maintenance Service Init ---")
        DatabaseMaintenanceService.start_maintenance_monitors()
        print("Database maintenance loops dispatched.")
        
        print("\nSmoke tests passed successfully.")
    except Exception as e:
        print(f"Smoke test failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
