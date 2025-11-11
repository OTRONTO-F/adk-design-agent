"""
Interactive Multi-Agent System for Virtual Try-On
v3.1.0 - User-driven continuous workflow

Architecture:
- Coordinator Agent (with LLM): Manages workflow and user interaction
  └─ Sub-Agents (on-demand):
     ├─ Image Manager Agent (3 tools)
     ├─ Catalog Manager Agent (2 tools)
     └─ Try-On Specialist Agent (5 tools)

Workflow (User-Driven):
1. User starts → Coordinator greets and explains
2. User uploads person image → Coordinator transfers to Image Manager
3. Image Manager validates → Returns to Coordinator → **WAITS for user**
4. User ready → Coordinator transfers to Catalog Manager
5. Catalog Manager shows options → User selects → **WAITS for user**
6. User confirms → Coordinator transfers to Try-On Specialist
7. Try-On executes → Result shown → **WAITS for user**
8. User decides: Continue (back to step 2 or 4) or Finish

Benefits:
- ✅ User controls pace (waits between each phase)
- ✅ No automatic step execution
- ✅ Continuous workflow with natural conversation
- ✅ LLM-powered coordination (flexible and conversational)
- ✅ Sub-agents handle specialized tasks
- ✅ Auto-versioning (reference_image_v1, v2... & tryon_result_v1, v2...)
- ✅ Unlimited iterations (user-controlled)
"""

import logging
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

# Handle both relative and absolute imports for compatibility
try:
    # Try relative imports first (for ADK module loading)
    from .tools.tryon_tool import (
        virtual_tryon, 
        list_tryon_results, 
        list_reference_images, 
        clear_reference_images, 
        get_rate_limit_status,
        generate_multiview_person,
        batch_multiview_tryon,
        generate_video_from_results
    )
    from .tools.catalog_tool import list_catalog_clothes, select_catalog_cloth
    from .prompts import (
        IMAGE_MANAGER_INSTRUCTION,
        CATALOG_MANAGER_INSTRUCTION,
        TRYON_SPECIALIST_INSTRUCTION,
        INTERACTIVE_COORDINATOR_INSTRUCTION
    )
except ImportError:
    # Fall back to absolute imports (for direct execution)
    from tools.tryon_tool import (
        virtual_tryon, 
        list_tryon_results, 
        list_reference_images, 
        clear_reference_images, 
        get_rate_limit_status,
        generate_multiview_person,
        batch_multiview_tryon,
        generate_video_from_results
    )
    from tools.catalog_tool import list_catalog_clothes, select_catalog_cloth
    from prompts import (
        IMAGE_MANAGER_INSTRUCTION,
        CATALOG_MANAGER_INSTRUCTION,
        TRYON_SPECIALIST_INSTRUCTION,
        INTERACTIVE_COORDINATOR_INSTRUCTION
    )

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
            logger.info(f"🖼️ [CALLBACK] Found reference image to process: {part.inline_data.mime_type}")
            image_part = part
            break
    
    # Process reference image if found
    if image_part:
        # Generate versioned filename for reference image
        reference_images = callback_context.state.get("reference_images", {})
        ref_count = len(reference_images) + 1
        filename = f"reference_image_v{ref_count}.png"
        logger.info(f"💾 [CALLBACK] Saving reference image as artifact: {filename} (count: {ref_count})")
        
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
            
            logger.info(f"✅ [CALLBACK] Successfully saved '{filename}' as artifact version {version}")
            logger.info(f"📊 [CALLBACK] Total reference images: {len(callback_context.state['reference_images'])}")
            
        except Exception as e:
            logger.error(f"❌ [CALLBACK] Error saving reference image artifact: {e}", exc_info=True)
    else:
        # Log when no image found (for debugging)
        has_text = any(hasattr(part, 'text') and part.text for part in latest_user_message.parts)
        if has_text:
            logger.debug(f"[CALLBACK] Text-only message, no image to process")
    
    # Don't return anything - let the original message go through
    return None

# ========================================
# SPECIALIZED AGENTS
# ========================================

# 1. Image Management Agent (Step 1: Person Image Upload)
# Handles: Image uploads, validation, listing, clearing
# Output: latest_reference_image stored in state
image_manager_agent = LlmAgent(
    name="image_manager_agent",
    model="gemini-2.5-flash",
    instruction=IMAGE_MANAGER_INSTRUCTION,
    description="Step 1: Manages person image uploads and validation",
    tools=[
        list_reference_images,
        clear_reference_images,
        load_artifacts_tool,
        generate_multiview_person
    ],
    output_key="latest_reference_image",  # Pass image filename to next agent
    before_model_callback=process_reference_images_callback
)

# 2. Catalog Management Agent (Step 2: Garment Selection)
# Handles: Catalog display, garment selection, catalog-only policy
# Input: latest_reference_image from previous agent
# Output: selected_garment stored in state
catalog_manager_agent = LlmAgent(
    name="catalog_manager_agent",
    model="gemini-2.5-flash",
    instruction=CATALOG_MANAGER_INSTRUCTION,
    description="Step 2: Displays catalog and manages garment selection",
    tools=[
        list_catalog_clothes,
        select_catalog_cloth
    ],
    output_key="selected_garment",  # Pass garment path to next agent
    before_model_callback=process_reference_images_callback
)

# 3. Virtual Try-On Specialist Agent (Step 3: Try-On Execution)
# Handles: Try-on execution, results, comparison, rate limiting, video generation
# Input: latest_reference_image and selected_garment from previous agents
# Output: tryon_result stored in state
tryon_specialist_agent = LlmAgent(
    name="tryon_specialist_agent",
    model="gemini-2.5-flash",
    instruction=TRYON_SPECIALIST_INSTRUCTION,
    description="Step 3: Executes virtual try-on, manages results, and generates videos",
    tools=[
        virtual_tryon,
        list_tryon_results,
        get_rate_limit_status,
        batch_multiview_tryon,
        generate_video_from_results
    ],
    output_key="tryon_result",  # Store final result
    before_model_callback=process_reference_images_callback
)

# ========================================
# ROOT AGENT: INTERACTIVE COORDINATOR
# ========================================

# Main Coordinator Agent with sub-agents (user-driven interactive workflow)
# Uses instruction from prompts.py for clean separation of concerns
root_agent = LlmAgent(
    name="virtual_tryon_coordinator",
    model="gemini-2.5-flash",
    instruction=INTERACTIVE_COORDINATOR_INSTRUCTION,
    description="Interactive coordinator managing user-driven virtual try-on workflow",
    sub_agents=[
        image_manager_agent,
        catalog_manager_agent,
        tryon_specialist_agent
    ],
    before_model_callback=process_reference_images_callback
)

# --- Configure and Expose the Runner ---
runner = Runner(
    agent=root_agent,
    app_name="virtual_tryon_app",
    session_service=None,  # Using default InMemorySessionService
    artifact_service=InMemoryArtifactService(),
)

logger.info("🎯 Virtual Try-On Agent System (v3.1.0) - Ready!")