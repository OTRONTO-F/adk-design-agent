import logging
import uuid
import os
from typing import Optional
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest
from google.adk.artifacts import InMemoryArtifactService
from google.adk.runners import Runner
from google.adk.tools.load_artifacts_tool import load_artifacts_tool
from google.genai.types import Content, Part
from .tools.tryon_tool import virtual_tryon, list_tryon_results, list_reference_images, clear_reference_images, get_rate_limit_status, compare_tryon_results, get_comparison_summary
from .deep_think_loop import deep_think_agent_tool, deep_think_loop
from .prompt import SOCIAL_MEDIA_AGENT_INSTRUCTION

# Load environment variables
load_dotenv()

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('virtual_tryon_agent.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

async def process_reference_images_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[Content]:
    """
    A before_model_callback to process uploaded reference images.
    
    This function intercepts the request before it goes to the LLM.
    If it finds an image upload, it saves it as a reference artifact.
    """
    if not llm_request.contents:
        return None
        
    latest_user_message = llm_request.contents[-1]
    image_part = None
    
    # Look for uploaded images in the latest user message
    for part in latest_user_message.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            logger.info(f"Found reference image to process: {part.inline_data.mime_type}")
            image_part = part
            break
    
    # Process reference image if found
    if image_part:
        # Generate versioned filename for reference image
        reference_images = callback_context.state.get("reference_images", {})
        ref_count = len(reference_images) + 1
        filename = f"reference_image_v{ref_count}.png"
        logger.info(f"Saving reference image as artifact: {filename}")
        
        try:
            version = await callback_context.save_artifact(
                filename=filename, artifact=image_part
            )
            
            # Store reference image info in session state
            if "reference_images" not in callback_context.state:
                callback_context.state["reference_images"] = {}
            
            callback_context.state["reference_images"][filename] = {
                "version": ref_count,
                "uploaded_version": version
            }
            callback_context.state["latest_reference_image"] = filename
            
            logger.info(f"Saved reference image as '{filename}' version {version}")
            
        except Exception as e:
            logger.error(f"Error saving reference image artifact: {e}")
    
    return None

# --- Define the Agent ---
root_agent = LlmAgent(
    name="virtual_tryon_agent",
    model="gemini-2.5-flash",
    instruction=SOCIAL_MEDIA_AGENT_INSTRUCTION,
    tools=[virtual_tryon, list_tryon_results, list_reference_images, clear_reference_images, get_rate_limit_status, compare_tryon_results, get_comparison_summary, load_artifacts_tool],
    sub_agents=[deep_think_loop],
    before_model_callback=process_reference_images_callback
)

# --- Configure and Expose the Runner ---
runner = Runner(
    agent=root_agent,
    app_name="virtual_tryon_app",
    session_service=None,  # Using default InMemorySessionService
    artifact_service=InMemoryArtifactService(),
)