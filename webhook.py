"""
Prithvi Mangal Realty - WhatsApp Webhook for Wati Integration
Receives incoming WhatsApp messages and responds using the AI real estate agent.
Deploy to Railway and configure webhook URL in Wati dashboard.
"""

import os
import json
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import anthropic
from supabase import create_client, Client

# =============================================================================
# CONFIGURATION
# =============================================================================

# Wati API Configuration
WATI_API_TOKEN = os.getenv("WATI_API_TOKEN", "wati_e1cd1165-a13d-4523-9d9b-0e5ddd861cf5.Z68anuxEj9fDNoZTbNlFNRDlbeNqYPQimipOJlX6-jmzCnsVZlyXw9Icd1HhJC8iBPejD_Q6OD2fvlgauRVxQJ_Ru66h8ghnCBxUvZjj3GcIaTUn6LiHCwc72nDsS5-G")
WATI_API_ENDPOINT = os.getenv("WATI_API_ENDPOINT", "https://live-server-10128865.wati.io")

# Anthropic API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Supabase Configuration (from your existing setup)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize clients
app = FastAPI(title="Prithvi Mangal Realty WhatsApp Bot")
claude_client = None
supabase: Client = None

# =============================================================================
# INITIALIZATION
# =============================================================================

@app.on_event("startup")
async def startup():
    global claude_client, supabase
    
    if ANTHROPIC_API_KEY:
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("✅ Anthropic client initialized")
    else:
        print("⚠️ ANTHROPIC_API_KEY not set - AI responses disabled")
    
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client initialized")
    else:
        print("⚠️ Supabase not configured - database features disabled")

# =============================================================================
# WATI API FUNCTIONS
# =============================================================================

async def send_whatsapp_message(phone_number: str, message: str) -> dict:
    """
    Send a WhatsApp message via Wati API.
    
    Args:
        phone_number: Phone number without + (e.g., "919876543210")
        message: Message text to send
    
    Returns:
        API response dict
    """
    url = f"{WATI_API_ENDPOINT}/api/v1/sendSessionMessage/{phone_number}"
    
    headers = {
        "Authorization": f"Bearer {WATI_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messageText": message
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"❌ Wati API error: {e.response.status_code} - {e.response.text}")
            return {"error": str(e)}
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return {"error": str(e)}


async def send_template_message(phone_number: str, template_name: str, parameters: list = None) -> dict:
    """
    Send a template message via Wati API (for broadcast/marketing messages).
    
    Args:
        phone_number: Phone number without + (e.g., "919876543210")
        template_name: Name of the approved WhatsApp template
        parameters: List of template parameters
    
    Returns:
        API response dict
    """
    url = f"{WATI_API_ENDPOINT}/api/v1/sendTemplateMessage"
    
    headers = {
        "Authorization": f"Bearer {WATI_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "whatsappNumber": phone_number,
        "template_name": template_name,
        "broadcast_name": f"prithvi_mangal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }
    
    if parameters:
        payload["parameters"] = [{"name": f"param{i+1}", "value": p} for i, p in enumerate(parameters)]
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Error sending template: {e}")
            return {"error": str(e)}

# =============================================================================
# AI AGENT RESPONSE
# =============================================================================

SYSTEM_PROMPT = """You are the AI assistant for Prithvi Mangal Realty, a real estate company in Navi Mumbai.

Your role:
- Help potential buyers find their dream home in Navi Mumbai
- Answer questions about properties, locations, and pricing
- Collect lead information (name, budget, preferred location, timeline)
- Schedule property visits
- Be friendly, professional, and helpful

Key areas we serve: Panvel, Kharghar, Ulwe, Taloja, Dronagiri, New Panvel

Response guidelines:
- Keep responses concise (under 300 characters for WhatsApp)
- Use simple Hindi-English mix if the customer does
- Always try to collect: Name, Budget, Preferred Location
- Offer to schedule a site visit
- Be warm and welcoming

If asked about specific properties, mention we have 1BHK, 2BHK, and 3BHK options available.
Price ranges: 1BHK (35-50L), 2BHK (55-85L), 3BHK (80L-1.5Cr)
"""

async def generate_ai_response(user_message: str, phone_number: str) -> str:
    """
    Generate an AI response using Claude.
    
    Args:
        user_message: The incoming message from the user
        phone_number: User's phone number for context
    
    Returns:
        AI-generated response string
    """
    if not claude_client:
        return "Thank you for your message! Our team will get back to you shortly. 🏠"
    
    try:
        # Get conversation history from Supabase if available
        context = ""
        if supabase:
            try:
                result = supabase.table("leads").select("name, budget, preferred_location").eq("phone", phone_number).execute()
                if result.data:
                    lead = result.data[0]
                    context = f"\nKnown customer info: Name: {lead.get('name', 'Unknown')}, Budget: {lead.get('budget', 'Unknown')}, Location preference: {lead.get('preferred_location', 'Unknown')}"
            except:
                pass
        
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=SYSTEM_PROMPT + context,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        return response.content[0].text
        
    except Exception as e:
        print(f"❌ Claude API error: {e}")
        return "Thank you for reaching out! Our property consultant will contact you soon. 🏠"

# =============================================================================
# LEAD MANAGEMENT
# =============================================================================

async def save_or_update_lead(phone_number: str, name: str = None, message: str = None):
    """Save or update lead in Supabase."""
    if not supabase:
        return
    
    try:
        # Check if lead exists
        existing = supabase.table("leads").select("*").eq("phone", phone_number).execute()
        
        lead_data = {
            "phone": phone_number,
            "last_message": message,
            "last_contact": datetime.now().isoformat(),
            "source": "whatsapp"
        }
        
        if name:
            lead_data["name"] = name
        
        if existing.data:
            # Update existing lead
            supabase.table("leads").update(lead_data).eq("phone", phone_number).execute()
        else:
            # Create new lead
            lead_data["status"] = "new"
            lead_data["created_at"] = datetime.now().isoformat()
            supabase.table("leads").insert(lead_data).execute()
            
        print(f"✅ Lead saved/updated: {phone_number}")
        
    except Exception as e:
        print(f"❌ Error saving lead: {e}")

# =============================================================================
# WEBHOOK ENDPOINTS
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
    """Health check for Railway."""
    return {"status": "healthy"}


@app.post("/webhook")
async def wati_webhook(request: Request):
    """
    Main webhook endpoint for Wati.
    Configure this URL in Wati Dashboard → Settings → Webhooks
    URL format: https://your-railway-app.up.railway.app/webhook
    """
    try:
        # Parse incoming webhook data
        body = await request.json()
        print(f"📩 Webhook received: {json.dumps(body, indent=2)}")
        
        # Extract message details
        # Wati webhook payload structure may vary - adjust as needed
        wa_id = body.get("waId") or body.get("whatsappNumber") or body.get("from")
        message_text = body.get("text") or body.get("message") or body.get("body", "")
        message_type = body.get("type", "text")
        sender_name = body.get("senderName") or body.get("pushName") or body.get("name", "")
        
        if not wa_id:
            print("⚠️ No phone number in webhook payload")
            return JSONResponse({"status": "ok", "message": "No phone number"})
        
        # Clean phone number (remove + if present)
        phone_number = wa_id.replace("+", "").replace(" ", "")
        
        print(f"📱 Message from {phone_number}: {message_text}")
        
        # Only process text messages
        if message_type not in ["text", "TEXT", None]:
            print(f"⚠️ Skipping non-text message type: {message_type}")
            return JSONResponse({"status": "ok", "message": "Non-text message skipped"})
        
        # Save/update lead
        await save_or_update_lead(phone_number, sender_name, message_text)
        
        # Generate AI response
        ai_response = await generate_ai_response(message_text, phone_number)
        
        # Send response via Wati
        send_result = await send_whatsapp_message(phone_number, ai_response)
        
        print(f"✅ Response sent: {ai_response[:100]}...")
        
        return JSONResponse({
            "status": "ok",
            "response_sent": True,
            "phone": phone_number
        })
        
    except json.JSONDecodeError:
        print("❌ Invalid JSON in webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.post("/webhook/wati")
async def wati_webhook_alt(request: Request):
    """Alternative webhook path for Wati."""
    return await wati_webhook(request)


# =============================================================================
# MANUAL MESSAGING ENDPOINTS (for testing)
# =============================================================================

@app.post("/send")
async def send_message(request: Request):
    """
    Manual endpoint to send a message.
    
    POST /send
    Body: {"phone": "919876543210", "message": "Hello!"}
    """
    try:
        body = await request.json()
        phone = body.get("phone")
        message = body.get("message")
        
        if not phone or not message:
            raise HTTPException(status_code=400, detail="phone and message required")
        
        result = await send_whatsapp_message(phone, message)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
