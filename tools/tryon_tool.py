"""
ADK Design Agent - Virtual Try-On Tool 👗✨
===========================================

AI-powered virtual try-on tool for fashion design and visualization.

Core Capabilities:
1. 🎭 Virtual Try-On: Apply garments onto person images
2. 🔄 Multiview Generation: Create 3 views (front/side/back) from a single image
3. 📦 Batch Try-On: Process all 3 views simultaneously
4. 🎥 Video Generation: Create 360° rotation videos from try-on results

Technologies:
- 🤖 Google Gemini 3.1: For virtual try-on and multiview generation
- 🎬 Google Veo 3.1: For high-resolution video generation (1080p)
- 🖼️ PIL (Pillow): For image processing and validation
"""

import os
import logging
from typing import Optional
from google import genai
from google.genai import types
from google.genai.types import Image as GenAIImage
from google.adk.tools import ToolContext
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from PIL import Image
import io
import base64
import requests
import time
import asyncio
from .rate_limiter import get_rate_limiter

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Get rate limiter configuration from environment
# Rate limiter prevents excessive API calls
RATE_LIMIT_COOLDOWN = float(os.getenv("RATE_LIMIT_COOLDOWN", "5.0"))
rate_limiter = get_rate_limiter(RATE_LIMIT_COOLDOWN)

def get_next_version_number(tool_context: ToolContext, asset_name: str) -> int:
    """
    Get the next version number for a given asset name.
    
    Used to maintain version history of generated images.
    """
    asset_versions = tool_context.state.get("asset_versions", {})
    current_version = asset_versions.get(asset_name, 0)
    next_version = current_version + 1
    return next_version

def update_asset_version(tool_context: ToolContext, asset_name: str, version: int, filename: str) -> None:
    """
    Update version tracking information for an asset in the state.
    
    Maintains complete version history for each asset.
    """
    if "asset_versions" not in tool_context.state:
        tool_context.state["asset_versions"] = {}
    if "asset_filenames" not in tool_context.state:
        tool_context.state["asset_filenames"] = {}
    
    tool_context.state["asset_versions"][asset_name] = version
    tool_context.state["asset_filenames"][asset_name] = filename
    
    # Maintain complete history of all versions
    asset_history_key = f"{asset_name}_history"
    if asset_history_key not in tool_context.state:
        tool_context.state[asset_history_key] = []
    tool_context.state[asset_history_key].append({"version": version, "filename": filename})

def create_versioned_filename(asset_name: str, version: int, file_extension: str = "png") -> str:
    """
    Create a versioned filename for an asset.
    
    Example: tryon_result_v1.png, tryon_result_v2.png
    """
    return f"{asset_name}_v{version}.{file_extension}"

def validate_image_aspect_ratio(image_data: bytes, expected_ratio: tuple = (9, 16), tolerance: float = 0.1) -> tuple[bool, str]:
    """
    Validate if image has the expected aspect ratio.
    
    Default: 9:16 (portrait) - optimal for social media and mobile devices
    
    Args:
        image_data: Binary image data
        expected_ratio: Expected (width, height) ratio, e.g., (9, 16)
        tolerance: Acceptable deviation from exact ratio (0.1 = 10%)
    
    Returns:
        Tuple of (is_valid, status_message)
    """
    try:
        image = Image.open(io.BytesIO(image_data))
        width, height = image.size
        
        # Calculate actual vs expected ratios
        actual_ratio = width / height
        expected = expected_ratio[0] / expected_ratio[1]
        
        # Check if within tolerance range
        ratio_diff = abs(actual_ratio - expected) / expected
        
        if ratio_diff <= tolerance:
            return True, f"✅ Image aspect ratio: {width}x{height} (ratio: {actual_ratio:.2f})"
        else:
            return False, f"⚠️ Image aspect ratio {width}x{height} (ratio: {actual_ratio:.2f}) is not close to {expected_ratio[0]}:{expected_ratio[1]} (expected: {expected:.2f}). Results may not be optimal."
    except Exception as e:
        logger.warning(f"Could not validate image aspect ratio: {e}")
        return True, "⚠️ Could not validate aspect ratio, proceeding anyway"

async def load_image(tool_context: ToolContext, filename: str):
    """
    Load an image from artifacts or catalog directory.
    
    Supports:
    - Artifacts: User-uploaded images
    - Catalog: Garment images from catalog/ directory
    """
    try:
        # First, try loading from artifacts (user uploads)
        loaded_part = await tool_context.load_artifact(filename)
        if loaded_part:
            logger.info(f"✅ Successfully loaded image from artifacts: {filename}")
            return loaded_part
        
        # If not found in artifacts, check catalog directory
        from pathlib import Path
        
        # Support both "catalog/1.jpg" and "1.jpg" formats
        if filename.startswith("catalog/"):
            catalog_path = Path(__file__).parent.parent / filename
        else:
            # Try to find it in catalog directory
            catalog_path = Path(__file__).parent.parent / "catalog" / filename
        
        # If catalog file exists, read and create Part object
        if catalog_path.exists():
            logger.info(f"📂 Loading image from catalog: {catalog_path}")
            with open(catalog_path, 'rb') as f:
                image_data = f.read()
            
            # Determine MIME type
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(catalog_path))
            if not mime_type:
                mime_type = "image/jpeg"  # default
            
            from google.genai.types import Part
            part = Part.from_bytes(data=image_data, mime_type=mime_type)
            logger.info(f"✅ Successfully loaded image from catalog: {filename}")
            return part
        
        logger.warning(f"⚠️ Image not found in artifacts or catalog: {filename}")
        return None
        
    except Exception as e:
        logger.error(f"Error loading image {filename}: {e}")
        return None

def list_tryon_results(tool_context: ToolContext) -> str:
    """List all virtual try-on results created in this session."""
    asset_versions = tool_context.state.get("asset_versions", {})
    if not asset_versions:
        return "📭 No virtual try-on results have been created yet."
    
    info_lines = ["Virtual Try-On Results:"]
    for asset_name, current_version in asset_versions.items():
        history_key = f"{asset_name}_history"
        history = tool_context.state.get(history_key, [])
        total_versions = len(history)
        latest_filename = tool_context.state.get("asset_filenames", {}).get(asset_name, "Unknown")
        info_lines.append(f"  • {asset_name}: {total_versions} result(s), latest is v{current_version} ({latest_filename})")
    
    return "\n".join(info_lines)

def list_reference_images(tool_context: ToolContext) -> str:
    """
    List all uploaded images in the current session.
    
    Returns formatted information about available images.
    """
    reference_images = tool_context.state.get("reference_images", {})
    if not reference_images:
        return "📭 No images have been uploaded yet.\n\n📋 Please upload:\n1. 👤 Person image (9:16 aspect ratio)\n2. 👔 Garment/clothing image (9:16 aspect ratio)"
    
    info_lines = ["📁 Uploaded images:"]
    
    # Sort by filename for consistent ordering
    sorted_images = sorted(reference_images.items())
    
    for idx, (filename, info) in enumerate(sorted_images, 1):
        version = info.get("version", "Unknown")
        info_lines.append(f"  {idx}. 🖼️ {filename} (v{version})")
    
    total_count = len(reference_images)
    info_lines.append(f"\n📊 Total: {total_count} image(s) uploaded")
    
    if total_count == 1:
        info_lines.append("\n⚠️ You need 2 images for virtual try-on:")
        info_lines.append("   • First image should be: 👤 Person (full body or upper body)")
        info_lines.append("   • Please upload: 👔 Garment/clothing image")
    elif total_count >= 2:
        info_lines.append("\n✅ You have enough images for virtual try-on!")
        info_lines.append("   • 💡 Use the filenames above when calling virtual_tryon")
        info_lines.append("   • 📝 Example: person_image_filename='reference_image_v1.png'")
        info_lines.append("   • 📝 Example: garment_image_filename='reference_image_v2.png'")
    else:
        info_lines.append("\n⚠️ Please upload 2 images:")
        info_lines.append("   1. 👤 Person image (full body or upper body, 9:16 ratio)")
        info_lines.append("   2. 👔 Garment/clothing image (9:16 ratio)")
    
    return "\n".join(info_lines)


class ClearImagesInput(BaseModel):
    """Input model for clearing reference images."""
    confirm: bool = Field(..., description="Set to True to confirm deletion of all reference images")


def clear_reference_images(tool_context: ToolContext, inputs: ClearImagesInput) -> str:
    """
    Clear all uploaded reference images from the session.
    
    Requires confirmation to prevent accidental deletion.
    """
    if not inputs.confirm:
        return "❌ Deletion cancelled. Set confirm=True to delete all reference images."
    
    reference_images = tool_context.state.get("reference_images", {})
    if not reference_images:
        return "📭 No reference images to delete."
    
    count = len(reference_images)
    
    # Clear the state
    tool_context.state["reference_images"] = {}
    tool_context.state["latest_reference_image"] = None
    
    return f"✅ Successfully deleted {count} reference image(s). 🆕 You can now upload new images."


def get_rate_limit_status(tool_context: ToolContext) -> str:
    """
    Get current rate limit status and API usage statistics.
    
    Returns detailed information about API call patterns.
    """
    stats = rate_limiter.get_stats()
    
    status_lines = ["📊 Rate Limit Status:"]
    status_lines.append(f"   • ⏱️ Cooldown period: {stats['cooldown_seconds']:.1f} seconds")
    status_lines.append(f"   • 📞 Total API calls made: {stats['total_calls']}")
    
    if stats['last_call_time']:
        status_lines.append(f"   • 🕐 Last API call: {stats['last_call_time']}")
    else:
        status_lines.append(f"   • 🕐 Last API call: Never")
    
    time_remaining = stats['time_until_next_call']
    if time_remaining > 0:
        status_lines.append(f"   • ⏱️ Time until next call: {time_remaining:.1f} seconds")
        status_lines.append(f"   • 🚦 Status: ⏳ Cooldown active")
    else:
        status_lines.append(f"   • ⏱️ Time until next call: Ready now")
        status_lines.append(f"   • 🚦 Status: ✅ Ready for API call")
    
    status_lines.append(f"\n💡 Tip: Rate limiting prevents API overuse and ensures stable service.")
    status_lines.append(f"   🔧 You can adjust RATE_LIMIT_COOLDOWN in .env file (currently {RATE_LIMIT_COOLDOWN}s)")
    
    return "\n".join(status_lines)


# ============================================================================
# 🎭 Virtual Try-On - Main Function
# ============================================================================

class VirtualTryOnInput(BaseModel):
    """Input model for virtual try-on operation."""
    person_image_filename: str = Field(
        ..., 
        description="Filename of the person image (e.g., 'reference_image_v1.png')"
    )
    garment_image_filename: str = Field(
        ..., 
        description="Filename of the garment image (e.g., 'reference_image_v2.png' or 'catalog/1.jpg')"
    )
    result_name: str = Field(
        default="tryon_result", 
        description="Name for the try-on result (auto-versioned)"
    )
    additional_instructions: Optional[str] = Field(
        default="", 
        description="Optional: Additional instructions for the try-on"
    )
    garment_type: str = Field(
        default="auto", 
        description="Garment type: 'short-sleeve', 'long-sleeve', 'sleeveless', 'dress', 'jacket', or 'auto'"
    )
    # NOTE: Size control removed due to Gemini model limitations
    # The model cannot reliably generate different sizes based on text prompts

async def virtual_tryon(
    tool_context: ToolContext,
    person_image_filename: str,
    garment_image_filename: str,
    result_name: str = "tryon_result",
    additional_instructions: Optional[str] = "",
    garment_type: str = "auto"
) -> str:
    """
    🎭 Virtual Try-On - Apply garments onto person images using AI
    
    This function performs photorealistic virtual try-on by combining:
    - A person image (full body or upper body)
    - A garment/clothing image
    
    The AI preserves the person's pose and features while applying the garment naturally.
    
    Args:
        tool_context: ADK tool context
        person_image_filename: Person image filename
        garment_image_filename: Garment image filename (from uploads or catalog)
        result_name: Output filename prefix (will be auto-versioned)
        additional_instructions: Optional custom instructions
        garment_type: Type of garment for better fit handling
    
    Returns:
        Status message with result filename
    
    Note: Size/fit control removed due to Gemini model limitations.
    The model cannot reliably produce different sizes from text prompts alone.
    """
    if "GEMINI_API_KEY" not in os.environ:
        raise ValueError("❌ GEMINI_API_KEY environment variable not set.")

    # Rate limiting check
    if not rate_limiter.can_make_call():
        wait_time = rate_limiter.time_until_next_call()
        logger.info(f"⏳ Rate limit active. Wait {wait_time:.1f}s")
        return (
            f"⏳ Rate limit active. Please wait {wait_time:.1f} seconds before trying again."
        )

    logger.info("🎭 Starting virtual try-on...")

    try:
        # Wrap arguments into Pydantic model for validation
        inputs = VirtualTryOnInput(
            person_image_filename=person_image_filename,
            garment_image_filename=garment_image_filename,
            result_name=result_name,
            additional_instructions=additional_instructions or "",
            garment_type=garment_type
        )
        
        # Log the try-on parameters
        logger.info(f"🎯 Try-on parameters: Type={inputs.garment_type}")
        print(f"📦 Using garment type: {inputs.garment_type}")

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

        # Load person image
        logger.info(f"Loading person image: {inputs.person_image_filename}")
        person_image = await load_image(tool_context, inputs.person_image_filename)
        if not person_image:
            return f"❌ Error: Could not load person image '{inputs.person_image_filename}'."

        # Load garment image
        logger.info(f"Loading garment image: {inputs.garment_image_filename}")
        garment_image = await load_image(tool_context, inputs.garment_image_filename)
        if not garment_image:
            return f"❌ Error: Could not load garment image '{inputs.garment_image_filename}'."

        # Build garment-specific instructions
        garment_specific = ""
        if inputs.garment_type == "short-sleeve":
            garment_specific = "\n⚠️ SHORT-SLEEVE: Show bare arms below sleeve edge."
        elif inputs.garment_type == "long-sleeve":
            garment_specific = "\n⚠️ LONG-SLEEVE: Cover arms completely."
        elif inputs.garment_type == "sleeveless":
            garment_specific = "\n⚠️ SLEEVELESS: Show bare shoulders and arms."

        # Enhanced try-on prompt optimized for ultra-high quality and photorealism
        # Emphasizes maximum detail, sharpness, and professional photography quality
        tryon_prompt = f"""Create an ULTRA-HIGH QUALITY, PHOTOREALISTIC virtual try-on image showing the person from the first image wearing the garment from the second image.

{garment_specific}

🎯 CRITICAL IMAGE QUALITY REQUIREMENTS (HIGHEST PRIORITY):
✨ MAXIMUM RESOLUTION: Generate at the HIGHEST possible quality setting with ULTRA-SHARP, CRYSTAL-CLEAR details
✨ PROFESSIONAL PHOTOGRAPHY: Studio-quality lighting with professional photo aesthetic, perfect exposure
✨ RAZOR-SHARP FOCUS: Perfect clarity on fabric texture, person's features, and every garment detail
✨ ZERO ARTIFACTS: Absolutely NO distortion, blurriness, noise, or AI generation artifacts
✨ HYPER-REALISTIC TEXTURE: Clearly visible fabric weave patterns, natural skin texture with pores, precise detail rendering at pixel level
✨ HIGH-END CAMERA QUALITY: Result must match quality of images from professional DSLR cameras (Canon EOS R5, Sony A7R IV level)
✨ PERFECT COLOR ACCURACY: Accurate color reproduction with proper white balance and color saturation
✨ ULTRA-FINE DETAILS: Render every small detail - buttons, stitching, fabric patterns, skin texture - with maximum clarity

📸 TECHNICAL SPECIFICATIONS FOR MAXIMUM QUALITY:
- Output resolution: Maximum possible quality for 9:16 aspect ratio
- Detail level: Ultra-high definition with visible micro-textures
- Sharpness: Professional-grade sharpness across entire image
- Lighting: Studio-quality three-point lighting setup
- Noise level: Zero noise, completely clean image
- Dynamic range: Full tonal range from deep shadows to bright highlights

CRITICAL FIT AND ACCURACY REQUIREMENTS:
1. Preserve the person's EXACT pose, body proportions, and facial features with PERFECT accuracy
2. COMPLETELY REPLACE any existing clothing with the new garment - remove ALL previous garments
3. If person is wearing long sleeves and new garment is short-sleeved: Show natural bare arms/skin with realistic skin texture
4. If person is wearing short sleeves and new garment is long-sleeved: Extend with garment sleeves naturally
5. Apply the garment onto the person's body with PERFECT, REALISTIC fit - it must look like real clothing worn by a real person
6. Maintain PERFECT fabric physics - natural wrinkles, realistic shadows, and proper draping behavior
7. Keep REALISTIC, PROFESSIONAL lighting that matches studio-quality photography
8. Preserve the background from the person image WITHOUT any distortion
9. Ensure the garment looks EXACTLY like it's actually being worn - not overlaid, not floating, PERFECTLY fitted
10. Match skin tones and lighting conditions with PHOTOREALISTIC accuracy
11. The result MUST look like an actual professional photograph taken by a high-end camera
12. Handle sleeve length transitions SMOOTHLY - show appropriate skin or fabric with natural transitions
13. Create a SEAMLESS, PROFESSIONAL, ULTRA-REALISTIC result with ZERO visible flaws

SIZE AND FIT GUIDELINES (CRITICAL - MUST BE VISUALLY OBVIOUS):
- **SMALLER SIZES (XS, S)**: Fabric STRETCHES across body, TIGHT fit, sleeves are SHORT, minimal wrinkles, body shape CLEARLY visible
- **MEDIUM SIZE (M, true-to-size)**: Natural comfortable fit, standard proportions, moderate room
- **LARGER SIZES (L, XL, XXL)**: EXCESS FABRIC creates WRINKLES and FOLDS, sleeves are LONGER, shoulders DROP, body is HIDDEN by loose fabric
- **OVERSIZED**: DRAMATICALLY BAGGY, dropped shoulders AT BICEPS, extra length COVERING HIPS, BOXY wide shape, fabric HANGS loosely
- **SLIM FIT**: Cut HUGS body tightly, EMPHASIZES shape, CLEAN fitted lines, NO bagginess
- **RELAXED/OVERSIZED FIT**: LOOSE throughout, EXTRA ROOM, fabric has SPACE from body, casual draping

⚠️ **VISUAL DIFFERENCE REQUIREMENT**: 
- XS should look NOTICEABLY TIGHTER than M
- XXL should look NOTICEABLY BAGGIER than M  
- The difference MUST be OBVIOUS in shoulder width, sleeve length, torso looseness, and overall proportions
- If sizes look similar, you have FAILED the requirement!

IMPORTANT: If the new garment has different sleeve length than original clothing:
- Short-sleeved garment → Show natural arms below the sleeves (remove any long-sleeve undershirts)
- Long-sleeved garment → Extend sleeves to cover arms completely
- Sleeveless garment → Show natural shoulders and arms (remove all sleeves)
- Remove any visible parts of the original clothing (like undershirt sleeves showing through)

{f"ADDITIONAL INSTRUCTIONS: {inputs.additional_instructions}" if inputs.additional_instructions else ""}

Output: Generate the virtual try-on image in 9:16 portrait aspect ratio with the specified size and fit characteristics clearly visible."""

        # Use high-quality model for better image generation
        model = "gemini-2.5-flash-image-preview"
        contents = [
            types.Content(
                role="user",
                parts=[person_image, garment_image, types.Part.from_text(text=tryon_prompt)],
            )
        ]
        
        # Configure for maximum image quality and detail
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=0.4,  # Lower temperature for more consistent, high-quality results
        )

        # Record API call
        rate_limiter.record_call()
        logger.info(f"API call recorded. Total calls: {rate_limiter.total_calls}")

        # --- Streamed generation ---
        image_saved = False
        try:
            for chunk in client.models.generate_content_stream(
                model=model, contents=contents, config=generate_content_config
            ):
                if not chunk.candidates or not chunk.candidates[0].content:
                    continue

                for part in chunk.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        image_part = types.Part(inline_data=part.inline_data)
                        version = get_next_version_number(tool_context, inputs.result_name)
                        filename = create_versioned_filename(inputs.result_name, version)
                        logger.info(f"Saving try-on result as: {filename}")
                        try:
                            saved_version = await tool_context.save_artifact(
                                filename=filename, artifact=image_part
                            )
                            update_asset_version(tool_context, inputs.result_name, version, filename)
                            tool_context.state["last_tryon_result"] = filename
                            tool_context.state["last_generated_image"] = filename
                            tool_context.state["current_result_name"] = inputs.result_name
                            tool_context.state["current_asset_name"] = inputs.result_name
                            image_saved = True
                            return (
                                f"✅ Virtual Try-On Successful!\n📁 Result: {filename} (v{version})"
                            )
                        except Exception as e:
                            logger.error(f"Error saving artifact: {e}")
                            return f"❌ Error saving try-on result: {e}"

            if not image_saved:
                logger.warning("No inline image data found. Falling back to non-streaming...")

        except Exception as stream_err:
            logger.error(f"Streaming failed: {stream_err}")

        # --- Fallback non-streaming ---
        resp = client.models.generate_content(
            model=model, contents=contents, config=generate_content_config
        )
        if resp.candidates and resp.candidates[0].content:
            for part in resp.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_part = types.Part(inline_data=part.inline_data)
                    version = get_next_version_number(tool_context, inputs.result_name)
                    filename = create_versioned_filename(inputs.result_name, version)
                    try:
                        saved_version = await tool_context.save_artifact(
                            filename=filename, artifact=image_part
                        )
                        update_asset_version(tool_context, inputs.result_name, version, filename)
                        return (
                            f"✅ Virtual Try-On Successful (non-streamed)!\n📁 Result: {filename} (v{version})"
                        )
                    except Exception as e:
                        logger.error(f"Error saving artifact: {e}")
                        return f"❌ Error saving try-on result: {e}"

        return "❌ No image was generated in either mode."

    except Exception as e:
        logger.exception("Virtual try-on error")
        return f"❌ Virtual try-on failed: {e}"

    
class BatchMultiviewTryOnInput(BaseModel):
    """Input model for batch try-on on all 3 multiview images."""
    garment_image_filename: str = Field(..., description="Filename of the garment to try on all 3 views")
    result_name_prefix: str = Field(default="tryon_result", description="Prefix for result filenames")


async def batch_multiview_tryon(
    tool_context: ToolContext,
    garment_image_filename: str,
    result_name_prefix: str = "tryon_result"
) -> str:
    """
    Automatically try-on a garment on all 3 multiview images (front, side, back).
    
    This function looks for the latest multiview set generated by generate_multiview_person
    and performs try-on on all 3 views automatically.
    
    Args:
        garment_image_filename: The garment to try on (e.g., "catalog/1.jpg")
        result_name_prefix: Prefix for result filenames (default: "tryon_result")
    
    Returns:
        Status message with all 3 try-on results
    """
    if "GEMINI_API_KEY" not in os.environ:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    
    logger.info(f"🎨 Starting batch multiview try-on with garment: {garment_image_filename}")
    print(f"🎨 Batch multiview try-on starting...")
    
    try:
        inputs = BatchMultiviewTryOnInput(
            garment_image_filename=garment_image_filename,
            result_name_prefix=result_name_prefix
        )
        
        # Get the latest multiview set from state
        multiview_set = tool_context.state.get("latest_multiview_set")
        if not multiview_set:
            return "❌ No multiview images found. Please generate multiview first using generate_multiview_person."
        
        if len(multiview_set) < 3:
            return f"⚠️ Only {len(multiview_set)} views available. Expected 3 (front/side/back)."
        
        result_lines = ["🎨 Batch Multi-View Try-On Started"]
        result_lines.append("=" * 60)
        result_lines.append("")
        result_lines.append(f"📦 Garment: {inputs.garment_image_filename}")
        result_lines.append("")
        
        results = {}
        views = ['front', 'side', 'back']
        
        for idx, view_name in enumerate(views, 1):
            if view_name not in multiview_set:
                result_lines.append(f"⚠️ {view_name.capitalize()} view not found, skipping...")
                continue
            
            person_image_filename = multiview_set[view_name]
            result_lines.append(f"🔄 Try-on {idx}/3: {view_name.capitalize()} view...")
            result_lines.append(f"   Person: {person_image_filename}")
            
            logger.info(f"Processing {view_name} view: {person_image_filename}")
            
            # Call virtual_tryon for this view
            try:
                tryon_result = await virtual_tryon(
                    tool_context=tool_context,
                    person_image_filename=person_image_filename,
                    garment_image_filename=inputs.garment_image_filename,
                    result_name=inputs.result_name_prefix,
                    additional_instructions=f"This is the {view_name} view of the person.",
                    garment_type="auto"
                )
                
                # Extract result filename from the result message
                if "✅" in tryon_result and ".png" in tryon_result:
                    # Parse the result filename
                    import re
                    match = re.search(r'(tryon_result_v\d+\.png)', tryon_result)
                    if match:
                        result_filename = match.group(1)
                        results[view_name] = result_filename
                        result_lines.append(f"   ✅ Success: {result_filename}")
                    else:
                        result_lines.append(f"   ✅ Success (filename not parsed)")
                else:
                    result_lines.append(f"   ⚠️ {tryon_result}")
                
                logger.info(f"✅ Completed {view_name} view")
                
            except Exception as e:
                logger.error(f"Error in {view_name} view try-on: {e}")
                result_lines.append(f"   ❌ Failed: {e}")
            
            result_lines.append("")
        
        # Summary
        result_lines.append("=" * 60)
        result_lines.append("📊 Batch Try-On Summary:")
        result_lines.append(f"   • Total views processed: {len(results)}/3")
        
        if results:
            result_lines.append("")
            result_lines.append("📁 Generated Results:")
            if 'front' in results:
                result_lines.append(f"   🔹 Front: {results['front']}")
            if 'side' in results:
                result_lines.append(f"   🔹 Side: {results['side']}")
            if 'back' in results:
                result_lines.append(f"   🔹 Back: {results['back']}")
            
            result_lines.append("")
            result_lines.append("💡 Next Steps:")
            result_lines.append("   1. 🖼️ View all 3 results in the artifacts panel")
            result_lines.append("   2. 🔄 Try another garment or upload new person image!")
            
            # Store batch results in state
            tool_context.state["latest_batch_tryon"] = results
            tool_context.state["batch_tryon_garment"] = inputs.garment_image_filename
            
        else:
            result_lines.append("")
            result_lines.append("❌ No try-ons were successful.")
            result_lines.append("💡 Tip: Check your multiview images and garment file.")
        
        return "\n".join(result_lines)
        
    except Exception as e:
        logger.exception("Batch multiview try-on error")
        return f"❌ Batch multiview try-on failed: {e}"


# ============================================================================
# 🔄 Multiview Person Generation (Create 3 views from single image)
# ============================================================================

class GenerateMultiviewInput(BaseModel):
    """
    Input model for generating multi-view person images.
    
    Used to create side view and back view from a single front view image.
    """
    person_image_filename: str = Field(
        ..., 
        description="Person image filename (front view) to generate other views from"
    )
    save_as_prefix: str = Field(
        default="multiview_person", 
        description="Prefix for output filenames (will append _front, _side, _back)"
    )


async def generate_multiview_person(
    tool_context: ToolContext,
    person_image_filename: str,
    save_as_prefix: str = "multiview_person"
) -> str:
    """
    🔄 Generate 3 views (front, side, back) from a single front-view image.
    
    This function uses AI to create side (90°) and back (180°) views from the front view.
    Results are saved as 3 separate files.
    
    Note: Quality of generated images may vary depending on the AI model's ability
    to understand 3D dimensions and create new viewpoints.
    
    Args:
        tool_context: ADK tool context for file management
        person_image_filename: Front-view person image filename
        save_as_prefix: Prefix for output filenames (default: "multiview_person")
    
    Returns:
        Status message with all 3 generated image filenames
    """
    if "GEMINI_API_KEY" not in os.environ:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    logger.info(f"🔄 Generating multiview images from: {person_image_filename}")
    print(f"🔄 Starting multiview generation from {person_image_filename}...")

    try:
        # Wrap into Pydantic model
        inputs = GenerateMultiviewInput(
            person_image_filename=person_image_filename,
            save_as_prefix=save_as_prefix
        )
        
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        
        # Load the original person image
        logger.info(f"Loading person image: {inputs.person_image_filename}")
        person_image = await load_image(tool_context, inputs.person_image_filename)
        if not person_image:
            return f"❌ Error: Could not load person image '{inputs.person_image_filename}'."
        
        result_lines = ["🎨 Multi-View Generation Started"]
        result_lines.append("=" * 60)
        result_lines.append("")
        
        generated_files = {}
        
        # View 1: Front (keep original)
        logger.info("📸 View 1: Front (using original image)")
        front_filename = f"{inputs.save_as_prefix}_front_v1.png"
        try:
            # Save original as front view
            await tool_context.save_artifact(filename=front_filename, artifact=person_image)
            generated_files['front'] = front_filename
            result_lines.append(f"✅ Front view: {front_filename} (original)")
            logger.info(f"✅ Saved front view: {front_filename}")
        except Exception as e:
            logger.error(f"Error saving front view: {e}")
            result_lines.append(f"❌ Front view failed: {e}")
        
        # View 2: Side View
        logger.info("🔄 View 2: Generating side view...")
        result_lines.append("")
        result_lines.append("🔄 Generating side view (this may take a moment)...")
        
        side_prompt = """Generate an ULTRA-HIGH QUALITY, PHOTOREALISTIC side profile view (90 degrees) of this person.

🎯 CRITICAL IMAGE QUALITY REQUIREMENTS (HIGHEST PRIORITY):
✨ MAXIMUM RESOLUTION: Generate at the HIGHEST possible quality with ULTRA-SHARP, CRYSTAL-CLEAR details
✨ PROFESSIONAL PHOTOGRAPHY: Studio-quality lighting with professional photo aesthetic, perfect exposure
✨ RAZOR-SHARP FOCUS: Perfect clarity on all details - face profile, hair, clothing, body features
✨ ZERO ARTIFACTS: Absolutely NO distortion, blurriness, noise, or AI generation artifacts
✨ HYPER-REALISTIC TEXTURE: Natural skin texture, fabric details, hair strands all clearly visible
✨ HIGH-END CAMERA QUALITY: Match quality of professional DSLR cameras (Canon EOS R5, Sony A7R IV)

📸 VIEW REQUIREMENTS:
1. Show the person from the SIDE (90-degree profile view)
2. Person facing LEFT or RIGHT (clear side angle from camera)
3. Maintain EXACT SAME person - identical face, hair, body, clothing, appearance
4. Keep identical clothing style, colors, and all details
5. Same body proportions, height, and posture
6. Natural side profile pose (standing straight, professional)
7. Consistent background style and quality
8. Same professional lighting conditions
9. Ultra-photorealistic quality with maximum detail
10. Perfect 9:16 portrait aspect ratio

⚠️ CRITICAL ACCURACY:
- This MUST be a genuine SIDE VIEW showing the person's profile
- Show clear profile of face, body, and clothing from the side
- NOT a slight turn - full 90-degree side view
- Maintain PERFECT consistency with original image
- Natural, realistic pose with professional quality
- Every detail must be sharp and clear"""

        try:
            # Check rate limit
            if not rate_limiter.can_make_call():
                wait_time = rate_limiter.time_until_next_call()
                logger.info(f"⏳ Rate limit: waiting {wait_time:.1f}s")
                rate_limiter.wait_if_needed()
            
            rate_limiter.record_call()
            
            model = "gemini-2.5-flash-image-preview"
            contents = [
                types.Content(
                    role="user",
                    parts=[person_image, types.Part.from_text(text=side_prompt)],
                )
            ]
            config = types.GenerateContentConfig(response_modalities=["IMAGE"])
            
            # Generate side view
            response = client.models.generate_content(
                model=model, contents=contents, config=config
            )
            
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        image_part = types.Part(inline_data=part.inline_data)
                        side_filename = f"{inputs.save_as_prefix}_side_v1.png"
                        await tool_context.save_artifact(filename=side_filename, artifact=image_part)
                        generated_files['side'] = side_filename
                        result_lines.append(f"✅ Side view: {side_filename}")
                        logger.info(f"✅ Generated side view: {side_filename}")
                        break
            else:
                result_lines.append(f"⚠️ Side view: No image generated")
                logger.warning("⚠️ Side view generation returned no image")
                
        except Exception as e:
            logger.error(f"Error generating side view: {e}")
            result_lines.append(f"❌ Side view failed: {e}")
        
        # View 3: Back View
        logger.info("🔄 View 3: Generating back view...")
        result_lines.append("")
        result_lines.append("🔄 Generating back view (this may take a moment)...")
        
        back_prompt = """Generate an ULTRA-HIGH QUALITY, PHOTOREALISTIC back view (180 degrees) of this person.

🎯 CRITICAL IMAGE QUALITY REQUIREMENTS (HIGHEST PRIORITY):
✨ MAXIMUM RESOLUTION: Generate at the HIGHEST possible quality with ULTRA-SHARP, CRYSTAL-CLEAR details
✨ PROFESSIONAL PHOTOGRAPHY: Studio-quality lighting with professional photo aesthetic, perfect exposure
✨ RAZOR-SHARP FOCUS: Perfect clarity on all back details - hair, clothing back, body shape
✨ ZERO ARTIFACTS: Absolutely NO distortion, blurriness, noise, or AI generation artifacts
✨ HYPER-REALISTIC TEXTURE: Natural hair texture, fabric weave, clothing details all clearly visible
✨ HIGH-END CAMERA QUALITY: Match quality of professional DSLR cameras (Canon EOS R5, Sony A7R IV)

📸 VIEW REQUIREMENTS:
1. Show the person from the BACK (complete rear view, 180-degree turn)
2. Person facing COMPLETELY AWAY from camera - showing their back
3. Maintain EXACT SAME person - identical hair style, body, clothing, appearance
4. Keep identical clothing style and colors - show the BACK of the garment with all details
5. Same body proportions, height, and build
6. Natural back pose (standing straight, facing away, professional posture)
7. Consistent background style and quality
8. Same professional lighting conditions
9. Ultra-photorealistic quality with maximum detail
10. Perfect 9:16 portrait aspect ratio

⚠️ CRITICAL ACCURACY:
- This MUST be a genuine BACK VIEW showing rear of person
- Show back of head, hair, body, and clothing clearly
- NOT a side view - full 180-degree back view
- Maintain PERFECT consistency with original image
- Show what the clothing looks like from behind with all details
- Natural, realistic pose with professional quality
- Every detail must be sharp, clear, and photorealistic"""

        try:
            # Check rate limit
            if not rate_limiter.can_make_call():
                wait_time = rate_limiter.time_until_next_call()
                logger.info(f"⏳ Rate limit: waiting {wait_time:.1f}s")
                rate_limiter.wait_if_needed()
            
            rate_limiter.record_call()
            
            contents = [
                types.Content(
                    role="user",
                    parts=[person_image, types.Part.from_text(text=back_prompt)],
                )
            ]
            
            # Generate back view
            response = client.models.generate_content(
                model=model, contents=contents, config=config
            )
            
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        image_part = types.Part(inline_data=part.inline_data)
                        back_filename = f"{inputs.save_as_prefix}_back_v1.png"
                        await tool_context.save_artifact(filename=back_filename, artifact=image_part)
                        generated_files['back'] = back_filename
                        result_lines.append(f"✅ Back view: {back_filename}")
                        logger.info(f"✅ Generated back view: {back_filename}")
                        break
            else:
                result_lines.append(f"⚠️ Back view: No image generated")
                logger.warning("⚠️ Back view generation returned no image")
                
        except Exception as e:
            logger.error(f"Error generating back view: {e}")
            result_lines.append(f"❌ Back view failed: {e}")
        
        # Summary
        result_lines.append("")
        result_lines.append("=" * 60)
        result_lines.append("📊 Generation Summary:")
        result_lines.append(f"   • Total views generated: {len(generated_files)}/3")
        
        if generated_files:
            result_lines.append("")
            result_lines.append("📁 Generated Files:")
            if 'front' in generated_files:
                result_lines.append(f"   🔹 Front: {generated_files['front']}")
            if 'side' in generated_files:
                result_lines.append(f"   🔹 Side: {generated_files['side']}")
            if 'back' in generated_files:
                result_lines.append(f"   🔹 Back: {generated_files['back']}")
            
            result_lines.append("")
            result_lines.append("💡 Next Steps:")
            result_lines.append("   1. 🖼️ Review the generated views in the artifacts panel")
            result_lines.append("   2. 👗 Use any of these views with virtual_tryon")
            result_lines.append("   3. 🎨 Try-on the same garment on all 3 views for complete preview!")
            
            # Store multiview info in state
            tool_context.state["latest_multiview_set"] = generated_files
            tool_context.state["multiview_source"] = inputs.person_image_filename
            
        else:
            result_lines.append("")
            result_lines.append("❌ No views were generated successfully.")
            result_lines.append("💡 Tip: Try with a different source image or check your API key.")
        
        result_lines.append("")
        result_lines.append("⚠️ Note: AI-generated side/back views may not be perfect due to")
        result_lines.append("   model limitations with 3D understanding. For best results,")
        result_lines.append("   consider uploading actual photos from different angles.")
        
        return "\n".join(result_lines)
        
    except Exception as e:
        logger.exception("Multiview generation error")
        return f"❌ Multiview generation failed: {e}"


# ============================================================================
# Veo Video Generation from Try-On Results
# ============================================================================

class GenerateVideoFromResultsInputs(BaseModel):
    """Input parameters for generating video from batch try-on results."""
    video_length: int = Field(
        default=8,
        description="Video duration in seconds. Must be 4, 6, or 8 seconds.",
        ge=4,
        le=8
    )
    aspect_ratio: str = Field(
        default="9:16",
        description="Video aspect ratio. Only '9:16' or '16:9' supported. Use '16:9' for horizontal videos."
    )
    transition_style: str = Field(
        default="smooth_rotation",
        description="Video transition style: 'smooth_rotation', 'dynamic', 'elegant', or 'quick'"
    )

async def generate_video_from_results(
    tool_context: ToolContext,
    inputs: GenerateVideoFromResultsInputs
) -> str:
    """
    Generate a Veo 3.1 video showcasing virtual try-on results.
    
    This tool creates a professional fashion video using Google's Veo 3.1 
    text-to-video generation model. The video will show a smooth 360° rotation
    showcasing the garment from multiple angles.
    
    Note: Veo 3.1 uses image-to-video.
    The AI generates a fashion showcase video based on text descriptions.
    
    Requirements:
    - Must run batch_multiview_tryon first to generate 3 views
    - Requires GOOGLE_API_KEY environment variable
    - Video generation takes approximately 40-90 seconds
    
    Args:
        tool_context: ADK tool context with state and artifact access
        inputs: Configuration for video generation (length, aspect ratio, style)
        
    Returns:
        Formatted string with video generation status and download link
    """
    import time
    
    result_lines = []
    result_lines.append("=" * 60)
    result_lines.append("🎬 Veo 3.1 Video Generation from Try-On Results")
    result_lines.append("=" * 60)
    result_lines.append("")
    
    try:
        # Handle both dict and Pydantic model inputs
        if isinstance(inputs, dict):
            video_length = inputs.get("video_length", 8)
            aspect_ratio = inputs.get("aspect_ratio", "9:16")
            transition_style = inputs.get("transition_style", "smooth_rotation")
        else:
            video_length = inputs.video_length
            aspect_ratio = inputs.aspect_ratio
            transition_style = inputs.transition_style
        
        # Validate video length
        if video_length not in [4, 6, 8]:
            return "❌ Video length must be 4, 6, or 8 seconds."
        
        # Validate aspect ratio
        if aspect_ratio not in ["16:9", "9:16"]:
            return "❌ Aspect ratio must be '16:9' or '9:16'."
        
        # Get batch try-on results from state
        latest_batch = tool_context.state.get("latest_batch_tryon")
        if not latest_batch:
            return "❌ No batch try-on results found. Please run batch_multiview_tryon first."
        
        result_lines.append(f"📁 Loading try-on results...")
        result_lines.append(f"   • Front view: {latest_batch.get('front', 'N/A')}")
        result_lines.append(f"   • Side view: {latest_batch.get('side', 'N/A')}")
        result_lines.append(f"   • Back view: {latest_batch.get('back', 'N/A')}")
        result_lines.append("")
        
        # Check and retrieve API key for Veo (Google Generative AI)
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            return "❌ GOOGLE_API_KEY environment variable not set."
        
        # Veo 3.1 supports multi-image-to-video with reference images
        result_lines.append("📸 Loading try-on result images for video generation...")
        
        reference_images_list = []
        views = [
            ('front', 'Front view'),
            ('side', 'Side view (90° angle)'),
            ('back', 'Back view (180° angle)')
        ]
        
        # Load all 3 images as reference images for Veo 3.1
        for view_key, view_description in views:
            filename = latest_batch.get(view_key)
            if filename:
                result_lines.append(f"   📥 Loading {view_description}: {filename}")
                
                # Load the image
                image_part = await load_image(tool_context, filename)
                if image_part and hasattr(image_part, 'inline_data'):
                    reference_images_list.append({
                        'view': view_key,
                        'description': view_description,
                        'filename': filename,
                        'image_bytes': image_part.inline_data.data,
                        'mime_type': image_part.inline_data.mime_type
                    })
                    result_lines.append(f"      ✅ Loaded successfully")
                else:
                    result_lines.append(f"      ⚠️ Failed to load image")
            else:
                result_lines.append(f"   ⚠️ {view_description}: Not found in batch results")
        
        if not reference_images_list:
            return "❌ No try-on images could be loaded for video generation."
        
        result_lines.append("")
        result_lines.append(f"✅ Loaded {len(reference_images_list)}/3 reference images")
        result_lines.append("   ℹ️ Video will be generated using multi-image-to-video (Veo 3.1)")
        result_lines.append("")
        
        # Create video prompt for multi-image-to-video mode (Veo 3.1)
        # The prompt describes how to use the reference images and camera movement
        style_prompts = {
            "smooth_rotation": "Create a smooth 360-degree rotation video using these reference images as keyframes. Start with the front view, smoothly rotate to the side view (90°), continue to the back view (180°), and complete the rotation back to front (360°). Use ultra-smooth camera movements with seamless transitions between the reference images. Professional studio fashion showcase with premium lighting and cinematic quality.",
            
            "dynamic": "Create a dynamic fashion showcase using these reference images. Transition smoothly between front, side, and back views with energetic camera movements. Modern studio lighting with contemporary style. Quick but fluid transitions creating a vibrant fashion video.",
            
            "elegant": "Create an elegant, slow-motion fashion showcase using these reference images. Graceful transitions between front, side, and back views. Luxury fashion photography aesthetic with sophisticated lighting. Premium studio environment with refined camera movements.",
            
            "quick": "Create a fast-paced fashion showcase using these reference images. Quick smooth transitions between front, side, and back views with energetic style. Modern studio lighting and rapid camera movements."
        }
        
        prompt = style_prompts.get(transition_style, style_prompts["smooth_rotation"])
        
        # Add quality requirements
        prompt += " ULTRA-HIGH QUALITY production with 1080p resolution. Clean professional background. Studio-grade fashion video aesthetic. Photorealistic rendering with smooth motion."
        
        # Display video configuration information
        result_lines.append("🎨 Video Configuration:")
        result_lines.append(f"   • ⏱️ Duration: {video_length} seconds")
        result_lines.append(f"   • 📱 Aspect Ratio: {aspect_ratio} (Portrait - Vertical)")
        result_lines.append(f"   • 🎬 Resolution: 1080p (High Definition)")
        result_lines.append(f"   • 🎭 Style: {transition_style}")
        result_lines.append(f"   • 🤖 Model: Veo 3.1 (veo-3.1-multi-image-to-video)")
        result_lines.append("")
        result_lines.append("💡 Note: Veo 3.1 creates videos from multiple reference images.")
        result_lines.append("   The AI will generate a fashion showcase similar to your try-on results.")
        result_lines.append("")
        result_lines.append("📝 Camera Movement:")
        result_lines.append(f"   {prompt[:120]}...")
        result_lines.append("")
        
        # Start video generation with Veo 3.1
        result_lines.append("🚀 Starting Veo 3.1 text-to-video generation...")
        result_lines.append("   ⏱️ Estimated time: 40-90 seconds")
        result_lines.append("   🎬 Generating professional fashion showcase video")
        result_lines.append("")
        
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        # Prepare reference images for Veo 3.1 API
        # Using the VideoGenerationReferenceImage format from the official docs
        from google.genai.types import Image as GenAIImage, VideoGenerationReferenceImage
        
        reference_images_for_veo = []
        for ref_img in reference_images_list:
            # Create Image object from bytes
            image_obj = GenAIImage(
                image_bytes=ref_img['image_bytes'],
                mime_type=ref_img['mime_type']
            )
            
            # Create VideoGenerationReferenceImage with string "asset" for reference_type
            reference_images_for_veo.append(
                VideoGenerationReferenceImage(
                    image=image_obj,
                    reference_type="asset"  # Use string "asset" as per official docs
                )
            )
            result_lines.append(f"   ✅ Prepared {ref_img['description']} for video generation")
        
        result_lines.append("")
        result_lines.append(f"📊 Total reference images: {len(reference_images_for_veo)}")
        result_lines.append("")
        
        # Generate video with Veo 3.1 using multi-image-to-video mode
        result_lines.append("🎬 Calling Veo 3.1 API...")
        
        # Check if user has configured GCS output URI
        output_gcs_uri = os.getenv("VEO_OUTPUT_GCS_URI")
        if not output_gcs_uri:
            result_lines.append("⚠️ VEO_OUTPUT_GCS_URI not set in .env")
            result_lines.append("   Using default output location")
            result_lines.append("")
        
        # Build config with reference_images
        config_params = {
            "reference_images": reference_images_for_veo,
            "aspect_ratio": aspect_ratio,
        }
        
        if output_gcs_uri:
            config_params["output_gcs_uri"] = output_gcs_uri
        
        operation = client.models.generate_videos(
            model="veo-3.1-generate-preview",
            prompt=prompt,
            config=types.GenerateVideosConfig(**config_params),
        )
        
        result_lines.append(f"   ✅ Operation started: {operation.name}")
        result_lines.append("")
        result_lines.append("⏳ Waiting for video generation to complete...")
        
        # Wait for completion (max 5 minutes)
        max_wait_time = 300
        start_time = time.time()
        check_interval = 15  # Check every 15 seconds
        
        while not operation.done and (time.time() - start_time) < max_wait_time:
            elapsed = int(time.time() - start_time)
            result_lines.append(f"   ⏱️ {elapsed}s elapsed... (max {max_wait_time}s)")
            time.sleep(check_interval)
            operation = client.operations.get(operation)
        
        elapsed_time = int(time.time() - start_time)
        
        if operation.done:
            result_lines.append("")
            result_lines.append(f"✅ Video generation completed in {elapsed_time}s!")
            result_lines.append("")
            
            # Extract video URL
            if hasattr(operation, 'response') and operation.response:
                if hasattr(operation.response, 'generated_videos'):
                    videos = operation.response.generated_videos
                    
                    if videos and len(videos) > 0:
                        video = videos[0]
                        
                        if hasattr(video, 'video') and video.video and hasattr(video.video, 'uri'):
                            # Add API key to URL for download
                            video_uri = video.video.uri
                            if '?' in video_uri:
                                video_url = f"{video_uri}&key={GOOGLE_API_KEY}"
                            else:
                                video_url = f"{video_uri}?key={GOOGLE_API_KEY}"
                            
                            # Save video info to state
                            video_info = {
                                "video_url": video_url,
                                "operation_name": operation.name,
                                "duration": f"{video_length} seconds",
                                "aspect_ratio": aspect_ratio,
                                "style": transition_style,
                                "elapsed_time": elapsed_time,
                                "model": "veo-3.1-generate-preview"
                            }
                            tool_context.state["latest_video"] = video_info
                            
                            result_lines.append("🎬 VIDEO READY!")
                            result_lines.append("")
                            result_lines.append("📹 Video Details:")
                            result_lines.append(f"   • URL: {video_url}")
                            result_lines.append(f"   • Duration: {video_length} seconds")
                            result_lines.append(f"   • Aspect Ratio: {aspect_ratio}")
                            result_lines.append(f"   • Model: Veo 3.1")
                            result_lines.append(f"   • Generation Time: {elapsed_time}s")
                            result_lines.append("")
                            result_lines.append("💡 How to use:")
                            result_lines.append("   1. Click the URL above to view/download")
                            result_lines.append("   2. Video is in MP4 format")
                            result_lines.append("   3. Can be shared on social media")
                            result_lines.append("")
                            
                            return "\n".join(result_lines)
                        else:
                            result_lines.append("❌ No video URI found in response")
                    else:
                        result_lines.append("❌ No videos in response")
                else:
                    result_lines.append("❌ No generated_videos attribute in response")
            else:
                result_lines.append("❌ No response from operation")
            
            result_lines.append("")
            result_lines.append(f"⚠️ Video generation completed but no video URL available.")
            result_lines.append(f"   Operation: {operation.name}")
            return "\n".join(result_lines)
        else:
            result_lines.append("")
            result_lines.append(f"⏱️ Video generation timeout after {max_wait_time}s")
            result_lines.append(f"   Operation may still be processing: {operation.name}")
            result_lines.append("")
            result_lines.append("💡 Try checking status later or contact support.")
            return "\n".join(result_lines)
        
    except Exception as e:
        logger.exception("Video generation error")
        result_lines.append("")
        result_lines.append(f"❌ Video generation failed: {e}")
        result_lines.append("")
        result_lines.append("💡 Common issues:")
        result_lines.append("   • GOOGLE_API_KEY not set or invalid")
        result_lines.append("   • API quota exceeded")
        result_lines.append("   • Network connectivity issues")
        result_lines.append("   • Veo 3.1 service temporarily unavailable")
        return "\n".join(result_lines)