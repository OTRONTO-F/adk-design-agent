import os
import logging
from google import genai
from google.genai import types
from google.adk.tools import ToolContext
from pydantic import BaseModel, Field
from dotenv import load_dotenv

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

def get_asset_versions_info(tool_context: ToolContext) -> str:
    """Get information about all virtual try-on results in the session."""
    asset_versions = tool_context.state.get("asset_versions", {})
    if not asset_versions:
        return "No virtual try-on results have been created yet."
    
    info_lines = ["Virtual Try-On Results:"]
    for asset_name, current_version in asset_versions.items():
        history_key = f"{asset_name}_history"
        history = tool_context.state.get(history_key, [])
        total_versions = len(history)
        latest_filename = tool_context.state.get("asset_filenames", {}).get(asset_name, "Unknown")
        info_lines.append(f"  • {asset_name}: {total_versions} version(s), latest is v{current_version} ({latest_filename})")
    
    return "\n".join(info_lines)

def get_reference_images_info(tool_context: ToolContext) -> str:
    """Get information about all uploaded images in the session."""
    reference_images = tool_context.state.get("reference_images", {})
    if not reference_images:
        return "No images have been uploaded yet. Please upload:\n1. Person image (9:16)\n2. Garment image (9:16)"
    
    info_lines = ["Uploaded images:"]
    for filename, info in reference_images.items():
        version = info.get("version", "Unknown")
        image_type = info.get("type", "reference")
        info_lines.append(f"  • {filename} ({image_type} v{version})")
    
    return "\n".join(info_lines)

async def load_reference_image(tool_context: ToolContext, filename: str):
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

def get_latest_reference_image_filename(tool_context: ToolContext) -> str:
    """Get the filename of the most recently uploaded image."""
    return tool_context.state.get("latest_reference_image")

class VirtualTryOnInput(BaseModel):
    person_image_filename: str = Field(..., description="Filename of the person image (should be uploaded first)")
    garment_image_filename: str = Field(..., description="Filename of the garment/clothing image (should be uploaded first)")
    result_name: str = Field(default="tryon_result", description="Name for the try-on result (will be versioned automatically)")
    additional_instructions: str = Field(default="", description="Optional: Additional instructions for the try-on (e.g., 'adjust fit', 'maintain pose')")

class EditImageInput(BaseModel):
    artifact_filename: str = Field(..., description="The filename of the image artifact to edit.")
    prompt: str = Field(..., description="The prompt describing the desired changes.")
    asset_name: str = Field(default=None, description="Optional: specify asset name for the new version (defaults to incrementing current asset).")
    reference_image_filename: str = Field(default=None, description="Optional: filename of a reference image to guide the edit.")


async def virtual_tryon(tool_context: ToolContext, inputs: VirtualTryOnInput) -> str:
    """Performs virtual try-on by combining person and garment images."""
    if "GEMINI_API_KEY" not in os.environ:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    print("Starting virtual try-on...")
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        inputs = VirtualTryOnInput(**inputs)
        
        # Load both images
        logger.info(f"Loading person image: {inputs.person_image_filename}")
        person_image = await load_reference_image(tool_context, inputs.person_image_filename)
        if not person_image:
            return f"Error: Could not load person image '{inputs.person_image_filename}'. Please upload the person image first."
        
        logger.info(f"Loading garment image: {inputs.garment_image_filename}")
        garment_image = await load_reference_image(tool_context, inputs.garment_image_filename)
        if not garment_image:
            return f"Error: Could not load garment image '{inputs.garment_image_filename}'. Please upload the garment image first."
        
        # Create virtual try-on prompt
        tryon_prompt = f"""Create a realistic virtual try-on image showing the person wearing the garment.

Instructions:
- Maintain the person's pose, body shape, and facial features from the first image
- Apply the garment from the second image onto the person naturally
- Ensure the garment fits realistically on the person's body
- Maintain proper lighting, shadows, and wrinkles for realism
- Keep the 9:16 aspect ratio
- Preserve the background from the person image
{f"- {inputs.additional_instructions}" if inputs.additional_instructions else ""}

Generate a photorealistic result that looks natural and believable."""

        # Generate the try-on result
        model = "gemini-2.5-flash"
        
        content_parts = [
            types.Part.from_text(text=tryon_prompt),
            person_image,
            garment_image
        ]
        
        response = client.models.generate_images(
            model=model,
            prompt=tryon_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="9:16",
                safety_filter_level="block_some",
                person_generation="allow_adult"
            )
        )

        if response.generated_images:
            generated_image = response.generated_images[0].image
            
            # Save as artifact with versioning
            version = get_next_version_number(tool_context, inputs.result_name)
            filename = create_versioned_filename(inputs.result_name, version)

        contents = [
            types.Content(
                role="user",
                parts=content_parts,
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            response_modalities=[
                "IMAGE",
                "TEXT",
            ],
        )

        # Generate versioned filename for artifact
        version = get_next_version_number(tool_context, inputs.asset_name)
        artifact_filename = create_versioned_filename(inputs.asset_name, version)
        logger.info(f"Generating image with versioned artifact filename: {artifact_filename} (version {version})")

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
                
                try:
                    # Save the image as an artifact
                    version = await tool_context.save_artifact(
                        filename=artifact_filename, 
                        artifact=image_part
                    )
                    
                    # Update version tracking
                    update_asset_version(tool_context, inputs.asset_name, version, artifact_filename)
                    
                    # Store artifact filename in session state for future reference
                    tool_context.state["last_generated_image"] = artifact_filename
                    tool_context.state["current_asset_name"] = inputs.asset_name
                    
                    logger.info(f"Saved generated image as artifact '{artifact_filename}' (version {version})")
                    
                    return f"Image generated successfully! Saved as artifact: {artifact_filename} (version {version} of {inputs.asset_name})"
                    
                except Exception as e:
                    logger.error(f"Error saving artifact: {e}")
                    return f"Error saving generated image as artifact: {e}"
            else:
                print(chunk.text)
                
        return "No image was generated"
    except Exception as e:
        print(f"An error occurred: {e}")
        return ""

async def edit_image(tool_context: ToolContext, inputs: EditImageInput) -> str:
    """Edits an existing image based on a prompt."""
    if "GEMINI_API_KEY" not in os.environ:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    print("Starting image edit")

    try:
        # genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        inputs = EditImageInput(**inputs)
        # Load the image artifact
        logger.info(f"Loading artifact: {inputs.artifact_filename}")
        try:
            loaded_image_part = await tool_context.load_artifact(inputs.artifact_filename)
            if not loaded_image_part:
                return f"Could not find image artifact: {inputs.artifact_filename}"
        except Exception as e:
            logger.error(f"Error loading artifact: {e}")
            return f"Error loading image artifact: {e}"

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

        # Handle reference image if specified
        reference_image_part = None
        if inputs.reference_image_filename:
            if inputs.reference_image_filename == "latest":
                ref_filename = get_latest_reference_image_filename(tool_context)
            else:
                ref_filename = inputs.reference_image_filename
            
            if ref_filename:
                reference_image_part = await load_reference_image(tool_context, ref_filename)
                if reference_image_part:
                    logger.info(f"Using reference image for editing: {ref_filename}")
                else:
                    logger.warning(f"Could not load reference image: {ref_filename}")

        model = "gemini-2.5-flash"

        # Build content parts - include reference image if available
        content_parts = [loaded_image_part, types.Part.from_text(text=inputs.prompt)]
        if reference_image_part:
            content_parts.append(reference_image_part)

        contents = [
            types.Content(
                role="user",
                parts=content_parts,
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            response_modalities=[
                "IMAGE",
                "TEXT",
            ],
        )

        # Determine asset name and generate versioned filename
        if inputs.asset_name:
            asset_name = inputs.asset_name
        else:
            # Try to extract asset name from current artifact filename
            current_asset_name = tool_context.state.get("current_asset_name")
            if current_asset_name:
                asset_name = current_asset_name
            else:
                # Fallback: extract from filename if it follows our versioning pattern
                base_name = inputs.artifact_filename.split('_v')[0] if '_v' in inputs.artifact_filename else "marketing_post"
                asset_name = base_name
        
        version = get_next_version_number(tool_context, asset_name)
        edited_artifact_filename = create_versioned_filename(asset_name, version)
        logger.info(f"Editing image with versioned artifact filename: {edited_artifact_filename} (version {version})")

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
                edited_image_part = types.Part(inline_data=inline_data)
                
                try:
                    # Save the edited image as an artifact
                    version = await tool_context.save_artifact(
                        filename=edited_artifact_filename, 
                        artifact=edited_image_part
                    )
                    
                    # Update version tracking
                    update_asset_version(tool_context, asset_name, version, edited_artifact_filename)
                    
                    # Store artifact filename in session state for future reference
                    tool_context.state["last_generated_image"] = edited_artifact_filename
                    tool_context.state["current_asset_name"] = asset_name
                    
                    logger.info(f"Saved edited image as artifact '{edited_artifact_filename}' (version {version})")
                    
                    return f"Image edited successfully! Saved as artifact: {edited_artifact_filename} (version {version} of {asset_name})"
                    
                except Exception as e:
                    logger.error(f"Error saving edited artifact: {e}")
                    return f"Error saving edited image as artifact: {e}"
            else:
                print(chunk.text)
                
        return "No edited image was generated"
    except Exception as e:
        print(f"An error occurred: {e}")
        return ""

async def list_asset_versions(tool_context: ToolContext) -> str:
    """Lists all marketing asset versions created in this session."""
    return get_asset_versions_info(tool_context)

async def list_reference_images(tool_context: ToolContext) -> str:
    """Lists all reference images uploaded in this session."""
    return get_reference_images_info(tool_context)