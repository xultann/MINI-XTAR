"""
Download missing SDXL model components to complete the local model
"""
import os
import sys
from pathlib import Path

try:
    from huggingface_hub import hf_hub_download
    HF_HUB_AVAILABLE = True
except ImportError:
    try:
        # Try using diffusers/transformers to download
        from diffusers import StableDiffusionXLPipeline
        from transformers import CLIPTextModel, CLIPTextModelWithProjection, CLIPTokenizer
        HF_HUB_AVAILABLE = False
        USE_DIFFUSERS = True
    except ImportError:
        print("❌ Need either huggingface_hub or diffusers installed")
        print("   Install with: pip install huggingface_hub")
        sys.exit(1)

def download_sdxl_components(model_dir: Path):
    """Download missing SDXL components from HuggingFace"""
    repo_id = "stabilityai/stable-diffusion-xl-base-1.0"
    
    print(f"Downloading SDXL components to: {model_dir}")
    print(f"Repository: {repo_id}\n")
    
    if not HF_HUB_AVAILABLE:
        print("⚠️ huggingface_hub not available, using diffusers to download...")
        return download_with_diffusers(model_dir, repo_id)
    
    # Components to download
    components = {
        "text_encoder": ["model.safetensors", "config.json"],
        "text_encoder_2": ["model.safetensors", "config.json"],
        "tokenizer": ["tokenizer_config.json", "vocab.json", "merges.txt"],
        "tokenizer_2": ["tokenizer_config.json", "vocab.json", "merges.txt"]
    }
    
    # Download text_encoder
    if not (model_dir / "text_encoder" / "model.safetensors").exists():
        print("Downloading text_encoder...")
        try:
            text_encoder_path = hf_hub_download(
                repo_id=repo_id,
                filename="text_encoder/model.safetensors",
                local_dir=str(model_dir),
                local_dir_use_symlinks=False
            )
            print(f"✅ Downloaded text_encoder/model.safetensors")
        except Exception as e:
            print(f"❌ Failed to download text_encoder: {e}")
        
        try:
            config_path = hf_hub_download(
                repo_id=repo_id,
                filename="text_encoder/config.json",
                local_dir=str(model_dir),
                local_dir_use_symlinks=False
            )
            print(f"✅ Downloaded text_encoder/config.json")
        except Exception as e:
            print(f"⚠️ Failed to download text_encoder/config.json: {e}")
    else:
        print("✅ text_encoder/model.safetensors already exists")
    
    # Download text_encoder_2
    if not (model_dir / "text_encoder_2" / "model.safetensors").exists():
        print("\nDownloading text_encoder_2...")
        try:
            text_encoder_2_path = hf_hub_download(
                repo_id=repo_id,
                filename="text_encoder_2/model.safetensors",
                local_dir=str(model_dir),
                local_dir_use_symlinks=False
            )
            print(f"✅ Downloaded text_encoder_2/model.safetensors")
        except Exception as e:
            print(f"❌ Failed to download text_encoder_2: {e}")
        
        try:
            config_path = hf_hub_download(
                repo_id=repo_id,
                filename="text_encoder_2/config.json",
                local_dir=str(model_dir),
                local_dir_use_symlinks=False
            )
            print(f"✅ Downloaded text_encoder_2/config.json")
        except Exception as e:
            print(f"⚠️ Failed to download text_encoder_2/config.json: {e}")
    else:
        print("✅ text_encoder_2/model.safetensors already exists")
    
    # Download tokenizer files
    if not (model_dir / "tokenizer" / "tokenizer_config.json").exists():
        print("\nDownloading tokenizer...")
        tokenizer_files = ["tokenizer_config.json", "vocab.json", "merges.txt"]
        for filename in tokenizer_files:
            try:
                hf_hub_download(
                    repo_id=repo_id,
                    filename=f"tokenizer/{filename}",
                    local_dir=str(model_dir),
                    local_dir_use_symlinks=False
                )
                print(f"✅ Downloaded tokenizer/{filename}")
            except Exception as e:
                print(f"⚠️ Failed to download tokenizer/{filename}: {e}")
    else:
        print("✅ tokenizer files already exist")
    
    # Download tokenizer_2 files (SDXL uses two tokenizers)
    tokenizer_2_dir = model_dir / "tokenizer_2"
    if not tokenizer_2_dir.exists():
        tokenizer_2_dir.mkdir(exist_ok=True)
    
    if not (tokenizer_2_dir / "tokenizer_config.json").exists():
        print("\nDownloading tokenizer_2...")
        tokenizer_files = ["tokenizer_config.json", "vocab.json", "merges.txt"]
        for filename in tokenizer_files:
            try:
                hf_hub_download(
                    repo_id=repo_id,
                    filename=f"tokenizer_2/{filename}",
                    local_dir=str(model_dir),
                    local_dir_use_symlinks=False
                )
                print(f"✅ Downloaded tokenizer_2/{filename}")
            except Exception as e:
                print(f"⚠️ Failed to download tokenizer_2/{filename}: {e}")
    else:
        print("✅ tokenizer_2 files already exist")
    
    # Rename existing unet and vae files if needed
    unet_dir = model_dir / "unet"
    if (unet_dir / "sd_xl_base_1.0.safetensors").exists() and not (unet_dir / "diffusion_pytorch_model.safetensors").exists():
        print("\nRenaming unet file...")
        (unet_dir / "sd_xl_base_1.0.safetensors").rename(unet_dir / "diffusion_pytorch_model.safetensors")
        print("✅ Renamed unet/sd_xl_base_1.0.safetensors -> diffusion_pytorch_model.safetensors")
    
    vae_dir = model_dir / "vae"
    if (vae_dir / "sdXL_v10VAEFix.safetensors").exists() and not (vae_dir / "diffusion_pytorch_model.safetensors").exists():
        print("\nRenaming vae file...")
        (vae_dir / "sdXL_v10VAEFix.safetensors").rename(vae_dir / "diffusion_pytorch_model.safetensors")
        print("✅ Renamed vae/sdXL_v10VAEFix.safetensors -> diffusion_pytorch_model.safetensors")
    
    # Download unet config if missing
    if not (unet_dir / "config.json").exists():
        print("\nDownloading unet config...")
        try:
            hf_hub_download(
                repo_id=repo_id,
                filename="unet/config.json",
                local_dir=str(model_dir),
                local_dir_use_symlinks=False
            )
            print("✅ Downloaded unet/config.json")
        except Exception as e:
            print(f"⚠️ Failed to download unet/config.json: {e}")
    
    # Download vae config if missing
    if not (vae_dir / "config.json").exists():
        print("\nDownloading vae config...")
        try:
            hf_hub_download(
                repo_id=repo_id,
                filename="vae/config.json",
                local_dir=str(model_dir),
                local_dir_use_symlinks=False
            )
            print("✅ Downloaded vae/config.json")
        except Exception as e:
            print(f"⚠️ Failed to download vae/config.json: {e}")
    
    print("\n✅ Download complete!")


def download_with_diffusers(model_dir: Path, repo_id: str):
    """Download using diffusers pipeline (slower but works without huggingface_hub)"""
    print("Using diffusers to download model components...")
    print("This will download the full model temporarily, then extract components.\n")
    
    try:
        import torch
        from diffusers import StableDiffusionXLPipeline
        
        # Create a temp directory
        temp_dir = model_dir.parent / "temp_download"
        temp_dir.mkdir(exist_ok=True)
        
        print("Downloading full pipeline (this may take a while)...")
        pipe = StableDiffusionXLPipeline.from_pretrained(
            repo_id,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            cache_dir=str(temp_dir)
        )
        
        # Now copy components to the model directory
        import shutil
        
        components_to_copy = {
            "text_encoder": ["model.safetensors", "config.json"],
            "text_encoder_2": ["model.safetensors", "config.json"],
            "tokenizer": ["tokenizer_config.json", "vocab.json", "merges.txt"],
            "tokenizer_2": ["tokenizer_config.json", "vocab.json", "merges.txt"],
            "unet": ["diffusion_pytorch_model.safetensors", "config.json"],
            "vae": ["diffusion_pytorch_model.safetensors", "config.json"]
        }
        
        # Find the cache directory
        cache_base = Path.home() / ".cache" / "huggingface" / "hub"
        model_cache = None
        for item in cache_base.glob(f"models--{repo_id.replace('/', '--')}*"):
            if item.is_dir():
                model_cache = item
                break
        
        if not model_cache:
            print("❌ Could not find downloaded model in cache")
            return
        
        print(f"Found model cache: {model_cache}")
        
        # Copy files
        for component, files in components_to_copy.items():
            comp_dir = model_dir / component
            comp_dir.mkdir(exist_ok=True)
            
            # Find source directory
            source_patterns = [
                model_cache / "snapshots" / "*" / component,
                cache_base / "**" / component
            ]
            
            source_dir = None
            for pattern in source_patterns:
                matches = list(cache_base.glob(str(pattern).replace(str(cache_base), "").lstrip("/")))
                if matches:
                    source_dir = matches[0]
                    break
            
            if not source_dir or not source_dir.exists():
                print(f"⚠️ Could not find {component} in cache")
                continue
            
            for filename in files:
                src = source_dir / filename
                dst = comp_dir / filename
                
                if src.exists() and not dst.exists():
                    shutil.copy2(src, dst)
                    print(f"✅ Copied {component}/{filename}")
                elif dst.exists():
                    print(f"✅ {component}/{filename} already exists")
        
        # Clean up temp dir
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        print("\n✅ Download complete!")
        
    except Exception as e:
        print(f"❌ Error downloading with diffusers: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Get model directory
    script_dir = Path(__file__).parent
    model_dir = script_dir / "models" / "image" / "my_model"
    
    if len(sys.argv) > 1:
        model_dir = Path(sys.argv[1]).resolve()
    
    if not model_dir.exists():
        print(f"❌ Model directory not found: {model_dir}")
        sys.exit(1)
    
    download_sdxl_components(model_dir)

