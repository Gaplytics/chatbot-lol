import os
import logging
import requests
import json
import asyncio
from livekit.agents import llm

logger = logging.getLogger("gaply-tools")

# =====================================================================
# UNIVERSAL TOOLS
# =====================================================================

class UniversalTools:
    """
    Tools available to EVERY Gaplytiq tenant (Institutes, Enterprise, etc.)
    Contains core platform utilities like UI control.
    """
    def __init__(self):
        self.agent = None  # Will be injected by the main agent loop

    @llm.function_tool(description="Control the user's web browser/UI. Use this when the user asks to be navigated to a specific page or when you want to highlight a UI element. action can be 'navigate' or 'highlight'. payload is a JSON string containing action-specific data (e.g. {'url': '/courses'} for navigate, or {'selector': '#apply-button'} for highlight).")
    async def control_website(self, action: str, payload_json: str):
        try:
            if hasattr(self, 'agent') and self.agent and hasattr(self.agent, 'session'):
                room = self.agent.session.room_io.room
                data = json.dumps({
                    "type": "website_control",
                    "action": action,
                    "payload": json.loads(payload_json)
                }).encode("utf-8")
                
                # Emit data channel message to the frontend React widget
                await room.local_participant.publish_data(data, reliable=True)
                return f"Successfully executed website control action: {action}."
            return "Failed to control website. Agent session not available."
        except Exception as e:
            logger.error(f"Error in control_website: {e}")
            return f"Error executing website control: {str(e)}"

# =====================================================================
# INSTITUTE TOOLS
# =====================================================================

class InstituteTools:
    """
    Tools exclusively for College/Institute tenants.
    """
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        env_key = f"{tenant_id.upper()}_API_URL"
        self.backend_url = os.getenv(env_key, os.getenv("GAPLYTIQ_BACKEND_URL", "http://localhost:5000/api"))
        self.agent = None # For compatibility if needed
    
    @llm.function_tool(description="Get a list of all available courses and their basic information.")
    async def get_all_courses(self):
        try:
            resp = requests.get(f"{self.backend_url}/courses", timeout=5)
            if resp.status_code == 200:
                return f"Available courses: {resp.json()}"
            return "Failed to fetch courses. Please check the website."
        except Exception as e:
            logger.error(f"Error in get_all_courses: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Get detailed information about a specific course by its name.")
    async def get_course_details(self, course_name: str):
        try:
            resp = requests.get(f"{self.backend_url}/courses", params={"search": course_name}, timeout=5)
            if resp.status_code == 200:
                return f"Course details for {course_name}: {resp.json()}"
            return f"Failed to fetch details for {course_name}."
        except Exception as e:
            logger.error(f"Error in get_course_details: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Get the current pricing and fees for a specific course.")
    async def get_pricing(self, course_name: str):
        try:
            resp = requests.get(f"{self.backend_url}/courses/{course_name}/pricing", timeout=5)
            if resp.status_code == 200:
                return f"Pricing for {course_name}: {resp.json()}"
            return f"Could not retrieve pricing for {course_name}."
        except Exception as e:
            logger.error(f"Error in get_pricing: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Check seat availability for a specific course batch.")
    async def check_availability(self, course_name: str):
        try:
            resp = requests.get(f"{self.backend_url}/courses/{course_name}/availability", timeout=5)
            if resp.status_code == 200:
                return f"Availability for {course_name}: {resp.json()}"
            return f"Could not check availability for {course_name}."
        except Exception as e:
            logger.error(f"Error in check_availability: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Get the schedule and upcoming batch dates for a specific course.")
    async def get_upcoming_batches(self, course_name: str):
        try:
            resp = requests.get(f"{self.backend_url}/courses/{course_name}/schedule", timeout=5)
            if resp.status_code == 200:
                return f"Upcoming batches for {course_name}: {resp.json()}"
            return f"Could not fetch batch schedule for {course_name}."
        except Exception as e:
            logger.error(f"Error in get_upcoming_batches: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Get contact information for Gaplytiq Institute.")
    async def get_contact_info(self):
        try:
            resp = requests.get(f"{self.backend_url}/contact", timeout=5)
            if resp.status_code == 200:
                return f"Contact info: {resp.json()}"
            return "Contact info: Email us at support@gaplytiq.com or call our helpline."
        except Exception as e:
            logger.error(f"Error in get_contact_info: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Search for Frequently Asked Questions (FAQs) by topic.")
    async def search_faqs(self, topic: str):
        try:
            resp = requests.get(f"{self.backend_url}/faqs", params={"topic": topic}, timeout=5)
            if resp.status_code == 200:
                return f"FAQ results for {topic}: {resp.json()}"
            return f"No specific FAQs found for {topic}."
        except Exception as e:
            logger.error(f"Error in search_faqs: {e}")
            return "Service temporarily unavailable. Please contact us directly."

# =====================================================================
# LABS TOOLS
# =====================================================================

class LabsTools:
    """
    Tools exclusively for Gaplytiq Labs (Student Assessment Portal).
    """
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        env_key = f"{tenant_id.upper()}_API_URL"
        self.backend_url = os.getenv(env_key, os.getenv("GAPLYTIQ_BACKEND_URL", "http://localhost:5000/api"))
        self.agent = None

    @llm.function_tool(description="Get the list of all available assessment modules that can be added to a mock test, including their unique keys, descriptions, and default difficulty.")
    async def get_available_assessment_modules(self):
        # Synchronized with frontend PipelineBuilder.tsx MODULE_LIB
        modules = [
            {"key": "reasoning", "label": "Logical Reasoning", "desc": "Tests logical puzzles, pattern matching, and text-based reasoning.", "default_difficulty": "Medium", "questions": 10, "time_mins": 15},
            {"key": "non_verbal", "label": "Non Verbal and Verbal Reasoning", "desc": "Tests spatial logic, pattern completion, and visual diagram puzzles.", "default_difficulty": "Medium", "questions": 10, "time_mins": 15},
            {"key": "aptitude", "label": "Quantitative Aptitude", "desc": "Evaluates arithmetic, algebra, math, and logical problem-solving.", "default_difficulty": "Medium", "questions": 10, "time_mins": 15},
            {"key": "coding", "label": "Hands-on Coding", "desc": "Interactive sandbox to write, compile, and run code (Python, SQL, DSA).", "default_difficulty": "Hard", "questions": 2, "time_mins": 30},
            {"key": "functional", "label": "Subject MCQ Test", "desc": "Domain-specific multiple choice questions (Finance, Marketing, Strategy).", "default_difficulty": "Medium", "questions": 10, "time_mins": 15},
            {"key": "tech_interview", "label": "Technical AI Interview", "desc": "Live voice interview simulation covering programming, SQL, and design.", "default_difficulty": "Hard", "questions": 3, "time_mins": 15},
            {"key": "domain_interview", "label": "Domain Case Interview", "desc": "Conversational case studies, strategy, and business management rounds.", "default_difficulty": "Medium", "questions": 3, "time_mins": 15},
            {"key": "hr_interview", "label": "HR AI Interview", "desc": "Interactive conversational practice for standard HR and culture-fit rounds.", "default_difficulty": "Medium", "questions": 3, "time_mins": 10},
            {"key": "behavioral_interview", "label": "Behavioral AI Interview", "desc": "Interactive conversational practice for behavioral, conflict, and situational rounds.", "default_difficulty": "Medium", "questions": 3, "time_mins": 10},
        ]
        return f"Available modules: {json.dumps(modules)}"

    @llm.function_tool(description="Help the student create a custom self-assessment mock test. 'title' is the test name. 'moduleKeys' MUST be a comma-separated list of exact keys obtained from get_available_assessment_modules (e.g., 'aptitude,coding,hr_interview'). Do not guess keys.")
    async def create_self_assessment(self, title: str, moduleKeys: str):
        try:
            if hasattr(self, 'agent') and self.agent and hasattr(self.agent, 'session'):
                room = self.agent.session.room_io.room
                # Safely parse moduleKeys which might be a string or already a list from LLM
                if isinstance(moduleKeys, list):
                    parsed_modules = [k.strip() for k in moduleKeys if k and isinstance(k, str) and k.strip()]
                else:
                    parsed_modules = [k.strip() for k in str(moduleKeys).split(',') if k.strip()]
                
                data = json.dumps({
                    "type": "website_control",
                    "action": "create_assessment",
                    "payload": {"title": title, "modules": parsed_modules}
                }).encode("utf-8")
                await room.local_participant.publish_data(data, reliable=True)
            return f"Opened the Assessment Builder for '{title}'. The student can now select their modules on screen."
        except Exception as e:
            logger.error(f"Error in create_self_assessment: {e}")
            return f"Error: {str(e)}"

    @llm.function_tool(description="Check the student's wallet balance and available credits for taking premium tests.")
    async def check_wallet_balance(self):
        try:
            if hasattr(self, 'agent') and self.agent and hasattr(self.agent, 'session'):
                room = self.agent.session.room_io.room
                data = json.dumps({
                    "type": "website_control",
                    "action": "navigate",
                    "payload": {"url": "/student/wallet"}
                }).encode("utf-8")
                await room.local_participant.publish_data(data, reliable=True)
            return "Navigated user to their wallet. Tell them they can view their balance there."
        except Exception as e:
            return f"Error: {e}"

    @llm.function_tool(description="Get a list of the student's completed assessments and their scores.")
    async def get_completed_assessments(self):
        return "Tell the user they can view their completed assessments and scorecards in the 'Completed & Graded' tab on their dashboard."

    @llm.function_tool(description="Redeem a promo code or voucher for wallet credits.")
    async def redeem_promo_code(self, code: str):
        return f"Instruct the user to click the 'Redeem Code' button on their dashboard to apply the promo code '{code}'."

# =====================================================================
# ENTERPRISE / B2B TOOLS (Example for future)
# =====================================================================

class EnterpriseTools:
    """
    Tools exclusively for Enterprise/B2B SaaS tenants.
    """
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        env_key = f"{tenant_id.upper()}_API_URL"
        self.backend_url = os.getenv(env_key, os.getenv("GAPLYTIQ_BACKEND_URL", "http://localhost:5000/api"))
        self.agent = None

    @llm.function_tool(description="Get a list of B2B SaaS plans and enterprise packages.")
    async def get_enterprise_plans(self):
        return "Enterprise plans include: Startup ($49/mo), Growth ($199/mo), and Custom Enterprise (Contact Sales)."
