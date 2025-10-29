import os
import logging
from google import genai
from google.genai import types
from google.adk.tools import ToolContext
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from PIL import Image
import io

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

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
    """Load an uploaded image artifact by filename."""
    try:
        loaded_part = await tool_context.load_artifact(filename)
        if loaded_part:
            logger.info(f"Successfully loaded image: {filename}")
            return loaded_part
        else:
            logger.warning(f"Image not found: {filename}")
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


class VirtualTryOnInput(BaseModel):
    person_image_filename: str = Field(..., description="Filename of the person image that was uploaded (e.g., 'reference_image_v1.png')")
    garment_image_filename: str = Field(..., description="Filename of the garment/clothing image that was uploaded (e.g., 'reference_image_v2.png')")
    result_name: str = Field(default="tryon_result", description="Name for the try-on result (will be versioned automatically)")
    additional_instructions: str = Field(default="", description="Optional: Additional instructions for the try-on (e.g., 'keep original background', 'adjust lighting')")


async def virtual_tryon(tool_context: ToolContext, inputs: VirtualTryOnInput) -> str:
    """Performs virtual try-on by combining person and garment images using Gemini's image generation."""
    if "GEMINI_API_KEY" not in os.environ:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

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
        tryon_prompt = f"""Create a photorealistic virtual try-on image showing the person from the first image wearing the garment from the second image.

CRITICAL REQUIREMENTS:
1. Preserve the person's exact pose, body proportions, and facial features
2. Apply the garment naturally onto the person's body with realistic fit
3. Maintain proper fabric physics - wrinkles, shadows, and natural draping
4. Keep realistic lighting that matches the person's original image
5. Preserve the background from the person image
6. Ensure the garment looks like it's actually being worn, not just pasted on
7. Match skin tones and lighting conditions realistically
8. The result should look like a real photograph, not a composite
9. Create a seamless, professional result that looks completely natural

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
