from .data import prompt_messages

BASE_MODEL = "Qwen/Qwen2-VL-2B-Instruct"


def device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"


def load(model_name: str = BASE_MODEL, adapter: str | None = None):
    import torch
    from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

    dtype = torch.bfloat16 if device() == "cuda" else torch.float32
    model = Qwen2VLForConditionalGeneration.from_pretrained(model_name, torch_dtype=dtype).to(device())
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter).to(device())
    processor = AutoProcessor.from_pretrained(model_name, min_pixels=64 * 28 * 28, max_pixels=512 * 28 * 28)
    return processor, model.eval()


def transcribe(processor, model, image, max_new_tokens: int = 256) -> str:
    import torch

    text = processor.apply_chat_template(prompt_messages(), add_generation_prompt=True)
    inputs = processor(images=[image.convert("RGB")], text=[text], return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0].strip()
