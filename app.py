import os
import uvicorn
from main import app
from config import Config

if __name__ == "__main__":
    # Support all standard cloud environment port variables (Botkeep, Pterodactyl, Heroku, Render)
    port_str = (
        os.environ.get("PORT") or 
        os.environ.get("SERVER_PORT") or 
        os.environ.get("APP_PORT") or 
        str(Config.PORT or 8000)
    )
    port = int(port_str.strip())
    
    print(f"[*] Starting Server on 0.0.0.0:{port}...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
