"""
Image Generation using Diffusers (SD 1.5 for 4GB GPUs)
Optimized for RTX 3050 4GB Laptop GPU
"""

import time
from datetime import datetime
from pathlib import Path
import torch

try:
    from diffusers import (
        StableDiffusionPipeline,
        StableDiffusionImg2ImgPipeline,
        DPMSolverMultistepScheduler
    )
    from PIL import Image

    DIFFUSERS_AVAILABLE = True
except ImportError:
    print("⚠️ Diffusers not installed. Run: pip install diffusers transformers accelerate")
    DIFFUSERS_AVAILABLE = False


class ImageGenerator:
    """
    MINI-XTAR Image Generator using SD 1.5
    Optimized for 4GB VRAM GPUs
    """

    def __init__(self, model_path=None):
        """
        Initialize with local model path
        If model_path is None, will try to find it automatically
        """
        if model_path is None:
            # SD 1.5 default
            script_dir = Path(__file__).parent
            project_root = script_dir.parent.parent
            model_path = project_root / "models" / "sd15"

        # Use local path
        if Path(model_path).is_absolute():
            self.model_path = Path(model_path).resolve()
        else:
            self.model_path = Path(model_path).resolve()

        # Validate model path exists
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model path not found: {self.model_path}\n"
                f"Please ensure models/sd15 folder exists in your MINI_XTAR directory"
            )

        self.pipe = None

        # Output directory
        self.output_dir = Path(__file__).parent / "generated_images"
        self.output_dir.mkdir(exist_ok=True)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[IMAGE] Using device: {self.device}")

        if not DIFFUSERS_AVAILABLE:
            raise RuntimeError("❌ Diffusers not installed")

        self._model_loaded = False

    def _load_model(self):
        """Load SD 1.5 model from local folder"""
        if self._model_loaded:
            return

        print(f"[IMAGE] Loading SD 1.5 from local folder: {self.model_path}")

        try:
            # Check for checkpoint file first (simpler and more reliable)
            checkpoint_files = [
                "v1-5-pruned.safetensors",
                "v1-5-pruned-emaonly.safetensors",
                "v1-5-pruned.ckpt"
            ]
            checkpoint_path = None
            for ckpt in checkpoint_files:
                if (self.model_path / ckpt).exists():
                    checkpoint_path = self.model_path / ckpt
                    break

            if checkpoint_path:
                print(f"[IMAGE] Loading from checkpoint: {checkpoint_path.name}")

                if self.device == "cuda":
                    self.pipe = StableDiffusionPipeline.from_single_file(
                        str(checkpoint_path),
                        torch_dtype=torch.float16,
                        safety_checker=None,
                    )
                    self.pipe = self.pipe.to(self.device)
                    print("[IMAGE] ✅ SD 1.5 loaded in fp16 mode")
                else:
                    self.pipe = StableDiffusionPipeline.from_single_file(
                        str(checkpoint_path),
                        torch_dtype=torch.float32,
                        safety_checker=None,
                    )
                    print("[IMAGE] ✅ SD 1.5 loaded in fp32 mode (CPU)")
            else:
                # Fallback to diffusers format if no checkpoint found
                # Check if it's a proper diffusers format (has component folders with config)
                has_diffusers_format = (self.model_path / "unet" / "config.json").exists()

                if not has_diffusers_format:
                    raise FileNotFoundError(
                        f"No valid model found in {self.model_path}. "
                        f"Expected either a checkpoint file (v1-5-pruned.safetensors) "
                        f"or complete diffusers format with component folders."
                    )

                # Load from diffusers format
                if self.device == "cuda":
                    self.pipe = StableDiffusionPipeline.from_pretrained(
                        str(self.model_path),
                        torch_dtype=torch.float16,
                        safety_checker=None,
                        requires_safety_checker=False,
                        local_files_only=True,
                        use_safetensors=True
                    )
                    self.pipe = self.pipe.to(self.device)
                    print("[IMAGE] ✅ SD 1.5 loaded in fp16 mode")
                else:
                    self.pipe = StableDiffusionPipeline.from_pretrained(
                        str(self.model_path),
                        torch_dtype=torch.float32,
                        safety_checker=None,
                        requires_safety_checker=False,
                        local_files_only=True
                    )
                    print("[IMAGE] ✅ SD 1.5 loaded in fp32 mode (CPU)")

            # Faster scheduler
            self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                self.pipe.scheduler.config
            )

            # VRAM optimizations for 4GB GPU
            if self.device == "cuda":
                self.pipe.enable_attention_slicing()
                try:
                    self.pipe.enable_xformers_memory_efficient_attention()
                    print("[IMAGE] ✅ xFormers enabled")
                except:
                    print("[IMAGE] ⚠️ xFormers not available (that's ok)")

            self._model_loaded = True
            print("[IMAGE] ✅ Model loaded and ready!")

        except Exception as e:
            print(f"[IMAGE] ❌ Failed to load model: {e}")
            raise

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "low quality, blurry, distorted, ugly, bad anatomy",
        width: int = 512,
        height: int = 512,
        num_inference_steps: int = 25,
        guidance_scale: float = 7.5,
        seed: int = None,
    ):
        """Generate image from text prompt"""
        self._load_model()

        print(f"[IMAGE] Generating: {prompt[:60]}...")

        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)

        try:
            # Ensure dimensions are multiples of 8
            width = (width // 8) * 8
            height = (height // 8) * 8

            # Clamp to reasonable values for SD 1.5
            width = min(max(width, 256), 768)
            height = min(max(height, 256), 768)

            image = self.pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
            ).images[0]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"mini_xtar_{timestamp}.png"
            output_path = self.output_dir / file_name
            image.save(output_path)

            print(f"[IMAGE] ✅ Image saved: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"[IMAGE] ❌ Generation failed: {e}")
            raise

    def generate_from_image(
        self,
        prompt: str,
        image_path: str,
        strength: float = 0.7,
        negative_prompt: str = "low quality, blurry, distorted",
        num_inference_steps: int = 25,
        guidance_scale: float = 7.5,
        seed: int = None,
    ):
        """Generate image from existing image (img2img)"""
        self._load_model()

        print(f"[IMAGE] Img2Img from: {image_path}")

        # Load and resize input image
        init_image = Image.open(image_path).convert("RGB")
        # Resize to 512x512 for SD 1.5
        init_image = init_image.resize((600, 600), Image.Resampling.LANCZOS)

        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)

        try:
            # Create img2img pipeline from existing components
            img2img_pipe = StableDiffusionImg2ImgPipeline(
                vae=self.pipe.vae,
                text_encoder=self.pipe.text_encoder,
                tokenizer=self.pipe.tokenizer,
                unet=self.pipe.unet,
                scheduler=self.pipe.scheduler,
                safety_checker=None,
                feature_extractor=self.pipe.feature_extractor,
                requires_safety_checker=False
            )

            if self.device == "cuda":
                img2img_pipe = img2img_pipe.to(self.device)

            image = img2img_pipe(
                prompt=prompt,
                image=init_image,
                strength=strength,
                negative_prompt=negative_prompt,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator
            ).images[0]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"mini_xtar_img2img_{timestamp}.png"
            output_path = self.output_dir / file_name
            image.save(output_path)

            print(f"[IMAGE] ✅ Image saved: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"[IMAGE] ❌ Img2Img failed: {e}")
            raise


# ---------------- TEST ---------------- #

if __name__ == "__main__":
    print("\n=== MINI-XTAR IMAGE SYSTEM (SD 1.5) ===\n")

    generator = ImageGenerator()

    prompt = "a futuristic female AI assistant with soft glowing eyes, ultra-detailed, cinematic lighting, digital art"

    image_path = generator.generate(
        prompt=prompt,
        width=512,
        height=512,
        num_inference_steps=25,
        guidance_scale=8
    )

    print(f"\n✅ Done! Image saved at: {image_path}")