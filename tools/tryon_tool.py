import os
import logging
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
    additional_instructions: str = Field(default="", description="Optional: Additional instructions for the try-on (e.g., 'keep original background', 'adjust lighting', 'show bare arms for short sleeves')")
    garment_type: str = Field(default="auto", description="Type of garment: 'short-sleeve', 'long-sleeve', 'sleeveless', 'dress', 'jacket', or 'auto' to detect automatically")


async def virtual_tryon(tool_context: ToolContext, inputs: VirtualTryOnInput) -> str:
    """Performs virtual try-on by combining person and garment images using Gemini's image generation."""
    if "GEMINI_API_KEY" not in os.environ:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    # Check rate limiting
    if not rate_limiter.can_make_call():
        wait_time = rate_limiter.time_until_next_call()
        logger.info(f"Rate limit: Need to wait {wait_time:.1f}s before next API call")
        return f"⏳ Rate limit active. Please wait {wait_time:.1f} seconds before making another try-on request.\n\nThis helps prevent API overuse and ensures stable service. Current cooldown: {RATE_LIMIT_COOLDOWN}s between requests."
    
    print("Starting virtual try-on...")
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        inputs = VirtualTryOnInput(**inputs)
        
        # Load both images
        logger.info(f"Loading person image: {inputs.person_image_filename}")
        person_image = await load_image(tool_context, inputs.person_image_filename)
        if not person_image:
            return f"❌ Error: Could not load person image '{inputs.person_image_filename}'.\n\nPlease make sure you've uploaded the person image first. Use list_reference_images to see all uploaded images."
        
        logger.info(f"Loading garment image: {inputs.garment_image_filename}")
        garment_image = await load_image(tool_context, inputs.garment_image_filename)
        if not garment_image:
            return f"❌ Error: Could not load garment image '{inputs.garment_image_filename}'.\n\nPlease make sure you've uploaded the garment image first. Use list_reference_images to see all uploaded images."
        
        # Create virtual try-on prompt optimized for Gemini image generation
        # Add garment-specific instructions based on type
        garment_specific = ""
        if inputs.garment_type == "short-sleeve":
            garment_specific = "\n⚠️ CRITICAL: This is a SHORT-SLEEVED garment. Show the person's BARE ARMS from the sleeve edge down. Remove any long-sleeve undershirts completely."
        elif inputs.garment_type == "long-sleeve":
            garment_specific = "\n⚠️ CRITICAL: This is a LONG-SLEEVED garment. Cover the arms completely with the garment's sleeves."
        elif inputs.garment_type == "sleeveless":
            garment_specific = "\n⚠️ CRITICAL: This is a SLEEVELESS garment. Show the person's BARE ARMS and SHOULDERS. Remove any existing sleeves completely."
        
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

IMPORTANT: If the new garment has different sleeve length than original clothing:
- Short-sleeved garment → Show natural arms below the sleeves (remove any long-sleeve undershirts)
- Long-sleeved garment → Extend sleeves to cover arms completely
- Sleeveless garment → Show natural shoulders and arms (remove all sleeves)
- Remove any visible parts of the original clothing (like undershirt sleeves showing through)

{f"ADDITIONAL INSTRUCTIONS: {inputs.additional_instructions}" if inputs.additional_instructions else ""}

Output: Generate the virtual try-on image in 9:16 portrait aspect ratio."""

        # Use Gemini's image generation capability (same as original repo)
        model = "gemini-2.5-flash-image-preview"
        
        # Build content parts with both images and prompt
        contents = [
            types.Content(
                role="user",
                parts=[
                    person_image,
                    garment_image,
                    types.Part.from_text(text=tryon_prompt)
                ],
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            response_modalities=[
                "IMAGE",
                "TEXT",
            ],
        )
        
        # Record API call for rate limiting
        rate_limiter.record_call()
        logger.info(f"API call recorded. Total calls: {rate_limiter.total_calls}")
        
        try:
            # Generate the try-on result using Gemini's generate_content_stream (like original repo)
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
            ):
                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue
                if chunk.candidates[0].content.parts[0].inline_data and chunk.candidates[0].content.parts[0].inline_data.data:
                    inline_data = chunk.candidates[0].content.parts[0].inline_data
                    
                    # Create a Part object from the inline data to save as artifact
                    image_part = types.Part(inline_data=inline_data)
                    
                    # Save as artifact with versioning
                    version = get_next_version_number(tool_context, inputs.result_name)
                    filename = create_versioned_filename(inputs.result_name, version)
                    
                    logger.info(f"Saving try-on result as: {filename}")
                    
                    try:
                        saved_version = await tool_context.save_artifact(
                            filename=filename,
                            artifact=image_part
                        )
                        
                        # Update version tracking
                        update_asset_version(tool_context, inputs.result_name, version, filename)
                        
                        # Store in session state for deep think loop
                        tool_context.state["last_tryon_result"] = filename
                        tool_context.state["last_generated_image"] = filename  # For deep think compatibility
                        tool_context.state["current_result_name"] = inputs.result_name
                        tool_context.state["current_asset_name"] = inputs.result_name  # For compatibility
                        
                        logger.info(f"✅ Virtual try-on completed successfully!")
                        
                        return f"""✅ Virtual Try-On Successful!

📁 Result saved as: {filename} (version {version})
👤 Person: {inputs.person_image_filename}
👔 Garment: {inputs.garment_image_filename}

The try-on image has been generated and saved. You can view it in the artifacts panel or request to see it."""
                        
                    except Exception as e:
                        logger.error(f"Error saving artifact: {e}")
                        return f"❌ Error saving try-on result: {e}"
                else:
                    # Text response from model
                    if hasattr(chunk, 'text'):
                        print(chunk.text)
                        
            return "❌ No image was generated. Please try again or check if the images are valid."
                
        except Exception as e:
            logger.error(f"Error during image generation: {e}")
            return f"❌ Error generating try-on image: {e}\n\nThis might happen if:\n- Images are not in 9:16 format\n- Images contain inappropriate content\n- API limitations were reached"
        
    except Exception as e:
        logger.error(f"Virtual try-on error: {e}")
        return f"❌ Virtual try-on failed: {e}"


class CompareTryOnInput(BaseModel):
    """Input model for comparing try-on results."""
    result_filenames: list[str] = Field(..., description="List of try-on result filenames to compare (e.g., ['tryon_result_v1.png', 'tryon_result_v2.png'])")
    show_details: bool = Field(default=True, description="Whether to show detailed comparison information")


def compare_tryon_results(tool_context: ToolContext, inputs: CompareTryOnInput) -> str:
    """
    Compare multiple virtual try-on results side-by-side.
    
    Shows version history, metadata, and helps user select the best result.
    """
    if len(inputs.result_filenames) < 2:
        return "❌ Please provide at least 2 result filenames to compare.\n\nExample: ['tryon_result_v1.png', 'tryon_result_v2.png']"
    
    if len(inputs.result_filenames) > 4:
        return "❌ Maximum 4 results can be compared at once. Please select up to 4 filenames."
    
    # Get all asset history
    asset_versions = tool_context.state.get("asset_versions", {})
    
    if not asset_versions:
        return "No try-on results have been created yet. Generate some results first using virtual_tryon."
    
    comparison_lines = ["📊 Virtual Try-On Results Comparison"]
    comparison_lines.append("=" * 70)
    comparison_lines.append("")
    
    # Build comparison table
    results_data = []
    
    for idx, filename in enumerate(inputs.result_filenames, 1):
        # Extract asset name and version from filename
        # Format: asset_name_vX.png
        try:
            if "_v" in filename and ".png" in filename:
                parts = filename.replace(".png", "").split("_v")
                asset_name = parts[0]
                version = int(parts[1])
            else:
                comparison_lines.append(f"⚠️  Could not parse filename: {filename}")
                continue
            
            # Get history for this asset
            history_key = f"{asset_name}_history"
            history = tool_context.state.get(history_key, [])
            
            # Find this specific version in history
            version_data = None
            for item in history:
                if item.get("version") == version:
                    version_data = item
                    break
            
            if not version_data:
                comparison_lines.append(f"⚠️  Version data not found for: {filename}")
                continue
            
            results_data.append({
                "index": idx,
                "filename": filename,
                "asset_name": asset_name,
                "version": version,
                "data": version_data
            })
            
        except Exception as e:
            logger.warning(f"Error processing filename {filename}: {e}")
            comparison_lines.append(f"⚠️  Error processing: {filename}")
    
    if not results_data:
        return "❌ No valid results found to compare. Check your filenames."
    
    # Display comparison header
    comparison_lines.append(f"Comparing {len(results_data)} results:")
    comparison_lines.append("")
    
    # Create comparison table
    header = "│ # │ Filename                    │ Version │"
    separator = "├───┼─────────────────────────────┼─────────┤"
    
    comparison_lines.append("┌───┬─────────────────────────────┬─────────┐")
    comparison_lines.append(header)
    comparison_lines.append(separator)
    
    for result in results_data:
        filename_display = result["filename"][:27] + "..." if len(result["filename"]) > 27 else result["filename"]
        row = f"│ {result['index']} │ {filename_display:27} │ v{result['version']:5} │"
        comparison_lines.append(row)
    
    comparison_lines.append("└───┴─────────────────────────────┴─────────┘")
    comparison_lines.append("")
    
    # Show detailed information if requested
    if inputs.show_details:
        comparison_lines.append("📋 Detailed Information:")
        comparison_lines.append("")
        
        for result in results_data:
            comparison_lines.append(f"🔹 Result #{result['index']}: {result['filename']}")
            comparison_lines.append(f"   • Asset name: {result['asset_name']}")
            comparison_lines.append(f"   • Version: v{result['version']}")
            
            # Get content review if available (from deep think mode)
            content_review = tool_context.state.get("content_review")
            if content_review and result['index'] == len(results_data):  # Only for latest
                comparison_lines.append(f"   • Quality Review: Available")
                if hasattr(content_review, 'garment_fit'):
                    comparison_lines.append(f"     - Garment fit: {'✅' if content_review.garment_fit else '⚠️'}")
                if hasattr(content_review, 'realistic_lighting'):
                    comparison_lines.append(f"     - Lighting: {'✅' if content_review.realistic_lighting else '⚠️'}")
                if hasattr(content_review, 'visual_appeal'):
                    comparison_lines.append(f"     - Visual appeal: {'✅' if content_review.visual_appeal else '⚠️'}")
            
            comparison_lines.append("")
    
    # Add recommendations
    comparison_lines.append("💡 Recommendations:")
    comparison_lines.append("")
    comparison_lines.append("   • View all images in the artifacts panel to compare visually")
    comparison_lines.append("   • Use load_artifacts_tool to load and view specific versions")
    comparison_lines.append(f"   • Latest version is usually: {results_data[-1]['filename']}")
    
    # Add selection helper
    comparison_lines.append("")
    comparison_lines.append("📌 To select your preferred result:")
    comparison_lines.append("   1. View the images in the artifacts panel")
    comparison_lines.append("   2. Note which version looks best")
    comparison_lines.append("   3. That image is already saved and ready to use!")
    
    return "\n".join(comparison_lines)


def get_comparison_summary(tool_context: ToolContext) -> str:
    """Get a quick summary of all try-on results for easy comparison."""
    asset_versions = tool_context.state.get("asset_versions", {})
    
    if not asset_versions:
        return "No try-on results available. Create some results first using virtual_tryon."
    
    summary_lines = ["📊 Quick Comparison Summary"]
    summary_lines.append("=" * 60)
    summary_lines.append("")
    
    total_results = 0
    for asset_name, current_version in asset_versions.items():
        history_key = f"{asset_name}_history"
        history = tool_context.state.get(history_key, [])
        total_versions = len(history)
        total_results += total_versions
        
        summary_lines.append(f"🎨 {asset_name}:")
        summary_lines.append(f"   • Total versions: {total_versions}")
        summary_lines.append(f"   • Latest: v{current_version}")
        
        # List all versions
        if total_versions > 0:
            summary_lines.append(f"   • Available versions:")
            for item in history:
                summary_lines.append(f"     - {item['filename']}")
        
        summary_lines.append("")
    
    summary_lines.append(f"Total results created: {total_results}")
    summary_lines.append("")
    summary_lines.append("💡 To compare specific versions, use compare_tryon_results with the filenames above.")
    
    return "\n".join(summary_lines)
