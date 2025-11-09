import os
import logging
from typing import Optional
from google import genai
from google.genai import types
from google.adk.tools import ToolContext
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from PIL import Image
import io
from .rate_limiter import get_rate_limiter

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Get rate limiter configuration from environment
RATE_LIMIT_COOLDOWN = float(os.getenv("RATE_LIMIT_COOLDOWN", "5.0"))
rate_limiter = get_rate_limiter(RATE_LIMIT_COOLDOWN)

def get_next_version_number(tool_context: ToolContext, asset_name: str) -> int:
    """Get the next version number for a given asset name."""
    asset_versions = tool_context.state.get("asset_versions", {})
    current_version = asset_versions.get(asset_name, 0)
    next_version = current_version + 1
    return next_version

def update_asset_version(tool_context: ToolContext, asset_name: str, version: int, filename: str) -> None:
    """Update the version tracking for an asset."""
    if "asset_versions" not in tool_context.state:
        tool_context.state["asset_versions"] = {}
    if "asset_filenames" not in tool_context.state:
        tool_context.state["asset_filenames"] = {}
    
    tool_context.state["asset_versions"][asset_name] = version
    tool_context.state["asset_filenames"][asset_name] = filename
    
    # Also maintain a list of all versions for this asset
    asset_history_key = f"{asset_name}_history"
    if asset_history_key not in tool_context.state:
        tool_context.state[asset_history_key] = []
    tool_context.state[asset_history_key].append({"version": version, "filename": filename})

def create_versioned_filename(asset_name: str, version: int, file_extension: str = "png") -> str:
    """Create a versioned filename for an asset."""
    return f"{asset_name}_v{version}.{file_extension}"

def validate_image_aspect_ratio(image_data: bytes, expected_ratio: tuple = (9, 16), tolerance: float = 0.1) -> tuple[bool, str]:
    """
    Validate if image has the expected aspect ratio (default 9:16 for portrait).
    
    Args:
        image_data: Image binary data
        expected_ratio: Tuple of (width, height) ratio
        tolerance: Acceptable deviation from exact ratio (0.1 = 10%)
    
    Returns:
        Tuple of (is_valid, message)
    """
    try:
        image = Image.open(io.BytesIO(image_data))
        width, height = image.size
        
        # Calculate actual and expected ratios
        actual_ratio = width / height
        expected = expected_ratio[0] / expected_ratio[1]
        
        # Check if within tolerance
        ratio_diff = abs(actual_ratio - expected) / expected
        
        if ratio_diff <= tolerance:
            return True, f"✅ Image aspect ratio: {width}x{height} (ratio: {actual_ratio:.2f})"
        else:
            return False, f"⚠️ Image aspect ratio {width}x{height} (ratio: {actual_ratio:.2f}) is not close to {expected_ratio[0]}:{expected_ratio[1]} (expected: {expected:.2f}). Results may not be optimal."
    except Exception as e:
        logger.warning(f"Could not validate image aspect ratio: {e}")
        return True, "⚠️ Could not validate aspect ratio, proceeding anyway"

async def load_image(tool_context: ToolContext, filename: str):
    """Load an uploaded image artifact by filename or from catalog."""
    try:
        # First, try to load from artifacts (uploaded images)
        loaded_part = await tool_context.load_artifact(filename)
        if loaded_part:
            logger.info(f"Successfully loaded image from artifacts: {filename}")
            return loaded_part
        
        # If not found in artifacts, check if it's a catalog reference
        # Handle both "catalog/1.jpg" and "1.jpg" formats
        from pathlib import Path
        
        # Check if filename starts with "catalog/"
        if filename.startswith("catalog/"):
            catalog_path = Path(__file__).parent.parent / filename
        else:
            # Try to find it in catalog directory
            catalog_path = Path(__file__).parent.parent / "catalog" / filename
        
        # If catalog file exists, read it and create Part
        if catalog_path.exists():
            logger.info(f"Loading image from catalog: {catalog_path}")
            with open(catalog_path, 'rb') as f:
                image_data = f.read()
            
            # Determine mime type
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(catalog_path))
            if not mime_type:
                mime_type = "image/jpeg"  # default
            
            from google.genai.types import Part
            part = Part.from_bytes(data=image_data, mime_type=mime_type)
            logger.info(f"Successfully loaded image from catalog: {filename}")
            return part
        
        logger.warning(f"Image not found in artifacts or catalog: {filename}")
        return None
        
    except Exception as e:
        logger.error(f"Error loading image {filename}: {e}")
        return None

def list_tryon_results(tool_context: ToolContext) -> str:
    """List all virtual try-on results created in this session."""
    asset_versions = tool_context.state.get("asset_versions", {})
    if not asset_versions:
        return "No virtual try-on results have been created yet."
    
    info_lines = ["Virtual Try-On Results:"]
    for asset_name, current_version in asset_versions.items():
        history_key = f"{asset_name}_history"
        history = tool_context.state.get(history_key, [])
        total_versions = len(history)
        latest_filename = tool_context.state.get("asset_filenames", {}).get(asset_name, "Unknown")
        info_lines.append(f"  • {asset_name}: {total_versions} result(s), latest is v{current_version} ({latest_filename})")
    
    return "\n".join(info_lines)

def list_reference_images(tool_context: ToolContext) -> str:
    """List all uploaded images in the session."""
    reference_images = tool_context.state.get("reference_images", {})
    if not reference_images:
        return "No images have been uploaded yet.\n\nPlease upload:\n1. Person image (9:16 aspect ratio)\n2. Garment/clothing image (9:16 aspect ratio)"
    
    info_lines = ["Uploaded images:"]
    
    # Sort by filename to ensure consistent ordering
    sorted_images = sorted(reference_images.items())
    
    for idx, (filename, info) in enumerate(sorted_images, 1):
        version = info.get("version", "Unknown")
        info_lines.append(f"  {idx}. {filename} (v{version})")
    
    total_count = len(reference_images)
    info_lines.append(f"\nTotal: {total_count} image(s) uploaded")
    
    if total_count == 1:
        info_lines.append("\n⚠️  You need 2 images for virtual try-on:")
        info_lines.append("   • First image should be: Person (full body or upper body)")
        info_lines.append("   • Please upload the garment/clothing image")
    elif total_count >= 2:
        info_lines.append("\n✅ You have enough images for virtual try-on!")
        info_lines.append("   • Use the filenames above when calling virtual_tryon")
        info_lines.append("   • Example: person_image_filename='reference_image_v1.png'")
        info_lines.append("   • Example: garment_image_filename='reference_image_v2.png'")
    else:
        info_lines.append("\n⚠️  Please upload 2 images:")
        info_lines.append("   1. Person image (full body or upper body, 9:16 ratio)")
        info_lines.append("   2. Garment/clothing image (9:16 ratio)")
    
    return "\n".join(info_lines)


class ClearImagesInput(BaseModel):
    """Input model for clearing reference images."""
    confirm: bool = Field(..., description="Set to True to confirm deletion of all reference images")


def clear_reference_images(tool_context: ToolContext, inputs: ClearImagesInput) -> str:
    """Clear all uploaded reference images from the session."""
    if not inputs.confirm:
        return "❌ Deletion cancelled. Set confirm=True to delete all reference images."
    
    reference_images = tool_context.state.get("reference_images", {})
    if not reference_images:
        return "No reference images to delete."
    
    count = len(reference_images)
    
    # Clear the state
    tool_context.state["reference_images"] = {}
    tool_context.state["latest_reference_image"] = None
    
    return f"✅ Successfully deleted {count} reference image(s). You can now upload new images."


def get_rate_limit_status(tool_context: ToolContext) -> str:
    """Get current rate limit status and statistics."""
    stats = rate_limiter.get_stats()
    
    status_lines = ["📊 Rate Limit Status:"]
    status_lines.append(f"   • Cooldown period: {stats['cooldown_seconds']:.1f} seconds")
    status_lines.append(f"   • Total API calls made: {stats['total_calls']}")
    
    if stats['last_call_time']:
        status_lines.append(f"   • Last API call: {stats['last_call_time']}")
    else:
        status_lines.append(f"   • Last API call: Never")
    
    time_remaining = stats['time_until_next_call']
    if time_remaining > 0:
        status_lines.append(f"   • Time until next call: {time_remaining:.1f} seconds")
        status_lines.append(f"   • Status: ⏳ Cooldown active")
    else:
        status_lines.append(f"   • Time until next call: Ready now")
        status_lines.append(f"   • Status: ✅ Ready for API call")
    
    status_lines.append(f"\n💡 Tip: Rate limiting prevents API overuse and ensures stable service.")
    status_lines.append(f"   You can adjust RATE_LIMIT_COOLDOWN in .env file (currently {RATE_LIMIT_COOLDOWN}s)")
    
    return "\n".join(status_lines)


class VirtualTryOnInput(BaseModel):
    person_image_filename: str = Field(..., description="Filename of the person image that was uploaded (e.g., 'reference_image_v1.png')")
    garment_image_filename: str = Field(..., description="Filename of the garment/clothing image that was uploaded (e.g., 'reference_image_v2.png') or from catalog (e.g., 'catalog/1.jpg')")
    result_name: str = Field(default="tryon_result", description="Name for the try-on result (will be versioned automatically)")
    additional_instructions: Optional[str] = Field(default="", description="Optional: Additional instructions for the try-on")
    garment_type: str = Field(default="auto", description="Type of garment: 'short-sleeve', 'long-sleeve', 'sleeveless', 'dress', 'jacket', or 'auto' to detect automatically")
    # NOTE: Size control removed due to Gemini model limitations
    # The model cannot reliably generate different sizes based on text prompts alone

async def virtual_tryon(
    tool_context: ToolContext,
    person_image_filename: str,
    garment_image_filename: str,
    result_name: str = "tryon_result",
    additional_instructions: Optional[str] = "",
    garment_type: str = "auto"
) -> str:
    """
    AFC-friendly Virtual Try-On tool:
    - Flat parameters for easier Automatic Function Calling.
    - Wraps into VirtualTryOnInput internally for validation.
    
    Note: Size/fit control has been removed due to limitations of the Gemini image generation model.
    The model cannot reliably produce visibly different sizes based on text prompts alone.
    """
    if "GEMINI_API_KEY" not in os.environ:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    # Rate limiting check
    if not rate_limiter.can_make_call():
        wait_time = rate_limiter.time_until_next_call()
        logger.info(f"Rate limit active. Wait {wait_time:.1f}s")
        return (
            f"⏳ Rate limit active. Please wait {wait_time:.1f} seconds before trying again."
        )

    print("Starting virtual try-on...")

    try:
        # ✅ Safely wrap args into Pydantic model
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

        # Full try-on prompt
        tryon_prompt = f"""Create a photorealistic virtual try-on image showing the person from the first image wearing the garment from the second image.
{garment_specific}

CRITICAL REQUIREMENTS:
1. Preserve the person's exact pose, body proportions, and facial features
2. COMPLETELY REPLACE any existing clothing with the new garment - remove all previous garments
3. If person is wearing long sleeves and new garment is short-sleeved: Show natural bare arms/skin
4. If person is wearing short sleeves and new garment is long-sleeved: Extend with garment sleeves
5. Apply the garment naturally onto the person's body with realistic fit
6. Maintain proper fabric physics - wrinkles, shadows, and natural draping
7. Keep realistic lighting that matches the person's original image
8. Preserve the background from the person image
9. Ensure the garment looks like it's actually being worn, not just overlaid
10. Match skin tones and lighting conditions realistically
11. The result should look like a real photograph, not a composite
12. Handle sleeve length transitions smoothly - show appropriate skin or fabric
13. Create a seamless, professional result that looks completely natural

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

        model = "gemini-2.5-flash-image-preview"
        contents = [
            types.Content(
                role="user",
                parts=[person_image, garment_image, types.Part.from_text(text=tryon_prompt)],
            )
        ]
        generate_content_config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])

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
            result_lines.append("   1. View all 3 results in the artifacts panel")
            result_lines.append("   2. Try another garment or upload new person image!")
            
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


class GenerateMultiviewInput(BaseModel):
    """Input model for generating multi-view person images."""
    person_image_filename: str = Field(..., description="Filename of the person image (front view) to generate other views from")
    save_as_prefix: str = Field(default="multiview_person", description="Prefix for saved images (will be suffixed with _front, _side, _back)")


async def generate_multiview_person(
    tool_context: ToolContext,
    person_image_filename: str,
    save_as_prefix: str = "multiview_person"
) -> str:
    """
    Generate 3 views (front, side, back) of a person from a single front-view image.
    
    This function attempts to create side and back views using AI image generation.
    Note: Results may vary in quality due to AI model limitations with 3D understanding.
    
    Args:
        person_image_filename: The front-view person image filename
        save_as_prefix: Prefix for saved multiview images (default: "multiview_person")
    
    Returns:
        Status message with generated image filenames
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
        
        side_prompt = """Generate a REALISTIC side profile view (90 degrees) of this person.

CRITICAL REQUIREMENTS:
1. Show the person from the SIDE (profile view)
2. The person should be facing LEFT or RIGHT (90-degree angle from camera)
3. Maintain the EXACT SAME person - same face, hair, body, clothing, and appearance
4. Keep the same clothing style and colors
5. Same body proportions and height
6. Natural side profile pose (standing straight)
7. Same background style
8. Same lighting conditions
9. Photorealistic quality
10. 9:16 portrait aspect ratio

IMPORTANT:
- This is a SIDE VIEW, not front view
- Show the person's profile clearly
- Maintain consistent appearance with the original image
- Natural and realistic pose"""

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
                logger.warning("Side view generation returned no image")
                
        except Exception as e:
            logger.error(f"Error generating side view: {e}")
            result_lines.append(f"❌ Side view failed: {e}")
        
        # View 3: Back View
        logger.info("🔄 View 3: Generating back view...")
        result_lines.append("")
        result_lines.append("🔄 Generating back view (this may take a moment)...")
        
        back_prompt = """Generate a REALISTIC back view (180 degrees) of this person.

CRITICAL REQUIREMENTS:
1. Show the person from the BACK (rear view)
2. The person should be facing AWAY from camera (180-degree turn)
3. Maintain the EXACT SAME person - same hair, body, clothing, and appearance
4. Keep the same clothing style and colors - show the BACK of the garment
5. Same body proportions and height
6. Natural back pose (standing straight, facing away)
7. Same background style
8. Same lighting conditions
9. Photorealistic quality
10. 9:16 portrait aspect ratio

IMPORTANT:
- This is a BACK VIEW, not front view
- Show the back of the person's head, body, and clothing
- Maintain consistent appearance with the original image
- Natural and realistic pose
- Show what the clothing looks like from behind"""

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
                logger.warning("Back view generation returned no image")
                
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
            result_lines.append("   1. Review the generated views in the artifacts panel")
            result_lines.append("   2. Use any of these views with virtual_tryon")
            result_lines.append("   3. Try-on the same garment on all 3 views for complete preview!")
            
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