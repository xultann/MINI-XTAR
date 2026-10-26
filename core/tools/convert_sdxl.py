from diffusers.pipelines.stable_diffusion.convert_from_ckpt import download_from_original_stable_diffusion_ckpt

MODEL_PATH = r"C:\Users\sulta\OneDrive\Desktop\MINI_XTAR\sd_xl_base_1.0.safetensors"
VAE_PATH = r"C:\Users\sulta\OneDrive\Desktop\MINI_XTAR\sdXL_v10VAEFix.safetensors"
OUTPUT = r"C:\Users\sulta\OneDrive\Desktop\MINI_XTAR\core\tools\models\image\my_model"

print("Converting SDXL model to Diffusers format...")
download_from_original_stable_diffusion_ckpt(
    checkpoint_path=MODEL_PATH,
    dump_path=OUTPUT,
    vae_checkpoint_path=VAE_PATH,
    from_safetensors=True
)

print("✅ DONE. Diffusers model ready.")
