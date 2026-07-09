import os
import logging
import requests
from livekit.agents import llm

logger = logging.getLogger("gaply-tools")

# Get backend URL from environment variables
BACKEND_URL = os.getenv("GAPLYTIQ_BACKEND_URL", "http://localhost:5000/api")

class GaplytiqAPI:
    """
    Function context for Gaplytiq Institute APIs.
    These methods allow the LLM to fetch live data autonomously.
    """
    
    @llm.function_tool(description="Get a list of all available courses and their basic information.")
    async def get_all_courses(self):
        try:
            resp = requests.get(f"{BACKEND_URL}/courses", timeout=5)
            if resp.status_code == 200:
                return f"Available courses: {resp.json()}"
            return "Failed to fetch courses. Please check the website."
        except Exception as e:
            logger.error(f"Error in get_all_courses: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Get detailed information about a specific course by its name.")
    async def get_course_details(self, course_name: str):
        try:
            resp = requests.get(f"{BACKEND_URL}/courses", params={"search": course_name}, timeout=5)
            if resp.status_code == 200:
                return f"Course details for {course_name}: {resp.json()}"
            return f"Failed to fetch details for {course_name}."
        except Exception as e:
            logger.error(f"Error in get_course_details: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Get the current pricing and fees for a specific course.")
    async def get_pricing(self, course_name: str):
        try:
            resp = requests.get(f"{BACKEND_URL}/courses/{course_name}/pricing", timeout=5)
            if resp.status_code == 200:
                return f"Pricing for {course_name}: {resp.json()}"
            return f"Could not retrieve pricing for {course_name}."
        except Exception as e:
            logger.error(f"Error in get_pricing: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Check seat availability for a specific course batch.")
    async def check_availability(self, course_name: str):
        try:
            resp = requests.get(f"{BACKEND_URL}/courses/{course_name}/availability", timeout=5)
            if resp.status_code == 200:
                return f"Availability for {course_name}: {resp.json()}"
            return f"Could not check availability for {course_name}."
        except Exception as e:
            logger.error(f"Error in check_availability: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Get the schedule and upcoming batch dates for a specific course.")
    async def get_upcoming_batches(self, course_name: str):
        try:
            resp = requests.get(f"{BACKEND_URL}/courses/{course_name}/schedule", timeout=5)
            if resp.status_code == 200:
                return f"Upcoming batches for {course_name}: {resp.json()}"
            return f"Could not fetch batch schedule for {course_name}."
        except Exception as e:
            logger.error(f"Error in get_upcoming_batches: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Get contact information for Gaplytiq Institute.")
    async def get_contact_info(self):
        try:
            resp = requests.get(f"{BACKEND_URL}/contact", timeout=5)
            if resp.status_code == 200:
                return f"Contact info: {resp.json()}"
            return "Contact info: Email us at support@gaplytiq.com or call our helpline."
        except Exception as e:
            logger.error(f"Error in get_contact_info: {e}")
            return "Service temporarily unavailable. Please contact us directly."

    @llm.function_tool(description="Search for Frequently Asked Questions (FAQs) by topic.")
    async def search_faqs(self, topic: str):
        try:
            resp = requests.get(f"{BACKEND_URL}/faqs", params={"topic": topic}, timeout=5)
            if resp.status_code == 200:
                return f"FAQ results for {topic}: {resp.json()}"
            return f"No specific FAQs found for {topic}."
        except Exception as e:
            logger.error(f"Error in search_faqs: {e}")
            return "Service temporarily unavailable. Please contact us directly."
