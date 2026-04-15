"""
Prithvi Mangal Realty - WhatsApp Webhook for Wati Integration
Simple version for Render deployment.
"""

import os
import json
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

WATI_API_TOKEN = os.getenv("WATI_API_TOKEN", "wati_e1cd1165-a13d-4523-9d9b-0e5ddd861cf5.Z68anuxEj9fDNoZTbNlFNRDlbeNqYPQimipOJlX6-jmzCnsVZlyXw9Icd1HhJC8iBPejD_Q6OD2fvlgauRVxQJ_Ru66h8ghnCBxUvZjj3GcIaTUn6LiHCwc72nDsS5-G")
WATI_API_ENDPOINT = os.getenv("WATI_API_ENDPOINT", "https://live-server-10128865.wati.io")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

app = FastAPI(title="Prithvi Mangal Realty WhatsApp Bot")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def send_whatsapp_message(phone_number: str, message: str) -> dict:
    """Send a WhatsApp message via Wati API."""
    url = f"{WATI_API_ENDPOINT}/api/v1/sendSessionMessage/{phone_number}"
    
    headers = {
        "Authorization": f"Bearer {WATI_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {"messageText": message}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            return {"success": True, "status": response.status_code}
        except Exception as e:
            print(f"Error sending message: {e}")
            return {"success": False, "error": str(e)}


async def generate_ai_response(user_message: str) -> str:
    """Generate AI response using Claude API."""
    if not ANTHROPIC_API_KEY:
        return "Thank you for your message! Our team will get back to you shortly. 🏠"
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system="""You are the AI assistant for Prithvi Mangal Realty, a real estate company in Navi Mumbai.
Help potential buyers find homes. Be friendly and concise (under 300 chars for WhatsApp).
Key areas: Panvel, Kharghar, Ulwe, Taloja. Price: 1BHK 35-50L, 2BHK 55-85L, 3BHK 80L-1.5Cr.""",
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"Claude API error: {e}")
        return "Thank you for reaching out! Our property consultant will contact you soon. 🏠"


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "service": "Prithvi Mangal Realty WhatsApp Bot",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check for Render."""
    return {"status": "healthy"}


@app.post("/webhook")
async def wati_webhook(request: Request):
    """Main webhook endpoint for Wati."""
    try:
        body = await request.json()
        print(f"Webhook received: {json.dumps(body, indent=2)}")
        
        # Extract message details
        wa_id = body.get("waId") or body.get("whatsappNumber") or body.get("from", "")
        message_text = body.get("text") or body.get("message") or body.get("body", "")
        message_type = body.get("type", "text")
        
        if not wa_id:
            return JSONResponse({"status": "ok", "message": "No phone number"})
        
        phone_number = wa_id.replace("+", "").replace(" ", "")
        print(f"Message from {phone_number}: {message_text}")
        
        # Only process text messages
        if message_type not in ["text", "TEXT", None]:
            return JSONResponse({"status": "ok", "message": "Non-text message skipped"})
        
        # Generate AI response
        ai_response = await generate_ai_response(message_text)
        
        # Send response via Wati
        await send_whatsapp_message(phone_number, ai_response)
        
        print(f"Response sent: {ai_response[:100]}...")
        
        return JSONResponse({"status": "ok", "response_sent": True})
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
